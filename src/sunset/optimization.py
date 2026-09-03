"""Deterministic, offline split-safe experiment selection and holdout sealing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sunset.optimization_models import Experiment, OptimizationReport


class OptimizationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_COMPONENTS = {"prompt", "retrieval", "tool_policy", "threshold"}
_STATUSES = {"preregistered", "evaluated_development", "selected", "rejected", "holdout_sealed", "inconclusive"}


def _read(path: str | Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OptimizationError("fixture_invalid", str(exc)) from exc
    if not isinstance(value, dict):
        raise OptimizationError("fixture_invalid", "fixture must be an object")
    return value, raw


def load_experiments(path: str | Path) -> tuple[Experiment, ...]:
    value, _ = _read(path)
    if value.get("schema_version") != "1" or not isinstance(value.get("experiments"), list):
        raise OptimizationError("experiment_fixture_invalid", "schema version 1 and experiments list are required")
    try:
        experiments = tuple(Experiment.from_dict(item) for item in value["experiments"])
    except (TypeError, ValueError, KeyError) as exc:
        raise OptimizationError("experiment_fixture_invalid", str(exc)) from exc
    seen: set[str] = set()
    for experiment in experiments:
        if experiment.experiment_id in seen or not experiment.experiment_id:
            raise OptimizationError("duplicate_experiment", experiment.experiment_id)
        if experiment.component not in _COMPONENTS or experiment.status not in _STATUSES:
            raise OptimizationError("experiment_enum_invalid", experiment.experiment_id)
        if experiment.budget <= 0 or not _SHA64.fullmatch(experiment.corpus_digest) or not _SHA64.fullmatch(experiment.holdout_digest):
            raise OptimizationError("experiment_identity_invalid", experiment.experiment_id)
        if not experiment.change_id or not experiment.development_case_ids:
            raise OptimizationError("experiment_registration_invalid", experiment.experiment_id)
        seen.add(experiment.experiment_id)
    return experiments


def run_optimization(g24_report_path: str | Path, experiments_path: str | Path) -> OptimizationReport:
    report, _ = _read(g24_report_path)
    if report.get("schema_version") != "1":
        raise OptimizationError("baseline_invalid", "G24 report schema must be 1")
    corpus_digest = str(report.get("corpus_digest", ""))
    split = report.get("split_identities")
    if not _SHA64.fullmatch(corpus_digest) or not isinstance(split, dict):
        raise OptimizationError("baseline_invalid", "G24 corpus identity is required")
    holdout_ids = tuple(sorted(str(item) for item in split.get("holdout", [])))
    if not holdout_ids:
        raise OptimizationError("holdout_missing", "sealed holdout identity is required")
    holdout_digest = hashlib.sha256(_canonical({"corpus_digest": corpus_digest, "holdout": holdout_ids})).hexdigest()
    experiments = load_experiments(experiments_path)
    for experiment in experiments:
        if experiment.corpus_digest != corpus_digest or experiment.holdout_digest != holdout_digest:
            raise OptimizationError("experiment_binding_invalid", experiment.experiment_id)
        if experiment.status in {"selected", "holdout_sealed"} and experiment.holdout is None:
            raise OptimizationError("holdout_missing", experiment.experiment_id)
        # Recorded holdout payloads may be present in a preregistration fixture,
        # but are ignored until development selection has completed.
    selected: Experiment | None = None
    normalized: list[dict[str, Any]] = []
    for experiment in experiments:
        item = experiment.to_dict()
        if experiment.status == "preregistered":
            item["status"] = "evaluated_development"
        if experiment.status in {"preregistered", "evaluated_development"}:
            decision, reason = _development_decision(experiment.development, experiment.budget)
            item["status"] = "evaluated_development" if decision else "rejected"
            if reason:
                item["rejection_reason"] = reason
            if decision and selected is None:
                selected = experiment
        elif experiment.status == "selected":
            if selected is not None:
                raise OptimizationError("duplicate_selection", experiment.experiment_id)
            selected = experiment
        normalized.append(item)
    if selected is None:
        holdout = None
    else:
        selected_item = next(item for item in normalized if item["experiment_id"] == selected.experiment_id)
        selected_item["status"] = "selected"
        if selected.holdout is None:
            raise OptimizationError("holdout_missing", selected.experiment_id)
        holdout = {"experiment_id": selected.experiment_id, "status": "holdout_sealed", "metrics": dict(selected.holdout), "case_ids": list(holdout_ids)}
    unsigned = {"corpus_digest": corpus_digest, "holdout_digest": holdout_digest, "experiments": normalized, "holdout": holdout}
    optimization_id = hashlib.sha256(_canonical(unsigned) + b"\noptimization-policy-v1").hexdigest()
    limitations = ("Development selection is descriptive and bounded by recorded G24 traces.", "Holdout is sealed once and cannot select, reject, or retune a change.", "No experiment establishes production removability or authorizes cleanup.")
    return OptimizationReport(optimization_id, corpus_digest, holdout_digest, selected.experiment_id if selected else None, tuple(normalized), holdout, limitations)


def _development_decision(metrics: dict[str, Any], budget: int) -> tuple[bool, str | None]:
    if metrics.get("run_status") in {"malformed_trace", "budget_exhausted", "inconclusive"}:
        return False, str(metrics.get("run_status"))
    if int(metrics.get("input_tokens", 0)) > 1000 or int(metrics.get("safety_signals", 0)) > 0:
        return False, "safety_or_budget_regression"
    if float(metrics.get("condition_accuracy", 0.0)) < 0.6667:
        return False, "below_baseline_accuracy"
    if float(metrics.get("unsupported_claim_rate", 1.0)) > 0.3333:
        return False, "unsupported_claim_regression"
    return True, None


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


__all__ = ["OptimizationError", "load_experiments", "run_optimization"]
