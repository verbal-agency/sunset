"""Contracts and report assembly for G37's maintainer-independent benchmark.

G37 deliberately combines two evidence lanes without conflating them: the G32
natural corpus exercises the pinned-clone/orchestration path, while G34 supplies
historical outcomes from three additional public repositories. Neither lane is
a human-confirmed protected-condition label.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


G37_SCHEMA_VERSION = "1"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_LABEL_PROVENANCE = {"historical_proxy", "unadjudicated", "synthetic_negative"}
_MODES = {"heuristic", "agentic_recorded"}
_OUTCOMES = {"confirmed", "still_failing", "flaky", "environment_error", "unvalidatable", "inconclusive", None}
_STAGE_TRACE = ("setup", "resolve", "evidence", "investigation", "casefile")
_NEGATIVE_CASE_COVERAGE = {
    "contradictory": "contradictory_evidence",
    "malformed": "inconclusive",
    "moving_ref": "reject_before_execution",
    "unavailable_runtime": "environment_error",
    "holdout": "reported_without_tuning",
}


class IndependentValidationError(ValueError):
    """Malformed or unsafe G37 benchmark data."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentValidationError("json_invalid", str(exc)) from exc
    if not isinstance(value, dict):
        raise IndependentValidationError("document_invalid", "G37 documents must be objects")
    return value


def validate_manifest(document: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if document.get("schema_version") != G37_SCHEMA_VERSION:
        raise IndependentValidationError("manifest_schema_unsupported", str(document.get("schema_version")))
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise IndependentValidationError("manifest_cases_missing", "at least one case is required")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise IndependentValidationError("case_invalid", "case must be an object")
        case_id = str(case.get("case_id", ""))
        if not case_id or case_id in seen:
            raise IndependentValidationError("case_id_duplicate", case_id)
        seen.add(case_id)
        if not _SHA_RE.fullmatch(str(case.get("pinned_ref", ""))):
            raise IndependentValidationError("pinned_ref_invalid", case_id)
        selector = case.get("candidate_selector")
        if not isinstance(selector, dict) or not selector.get("path") or not selector.get("test"):
            raise IndependentValidationError("candidate_selector_invalid", case_id)
        if case.get("label_provenance") not in _LABEL_PROVENANCE:
            raise IndependentValidationError("label_provenance_invalid", case_id)
        if case.get("split") not in {"development", "holdout"}:
            raise IndependentValidationError("split_invalid", case_id)
    return tuple(cases)


def validate_runs(document: dict[str, Any], case_ids: Iterable[str]) -> tuple[dict[str, Any], ...]:
    if document.get("schema_version") != G37_SCHEMA_VERSION:
        raise IndependentValidationError("runs_schema_unsupported", str(document.get("schema_version")))
    runs = document.get("runs")
    if not isinstance(runs, list) or not runs:
        raise IndependentValidationError("runs_missing", "at least one run is required")
    allowed = set(case_ids)
    seen: set[tuple[str, str]] = set()
    for run in runs:
        if not isinstance(run, dict):
            raise IndependentValidationError("run_invalid", "run must be an object")
        key = (str(run.get("case_id", "")), str(run.get("mode", "")))
        if key[0] not in allowed:
            raise IndependentValidationError("run_case_unknown", key[0])
        if key in seen:
            raise IndependentValidationError("run_duplicate", f"{key[0]}:{key[1]}")
        seen.add(key)
        if key[1] not in _MODES:
            raise IndependentValidationError("run_mode_invalid", key[1])
        if tuple(run.get("stage_trace", ())) != _STAGE_TRACE:
            raise IndependentValidationError("stage_trace_incomplete", key[0])
        if run.get("validation_outcome") not in _OUTCOMES:
            raise IndependentValidationError("validation_outcome_invalid", key[0])
        if run.get("target_unchanged") is not True:
            raise IndependentValidationError("target_mutated", key[0])
        if not isinstance(run.get("unresolved_obligations"), list):
            raise IndependentValidationError("obligations_missing", key[0])
    return tuple(runs)


def validate_negative_cases(document: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Validate the deterministic fail-closed matrix used by G37 replay tests."""

    if document.get("schema_version") != G37_SCHEMA_VERSION:
        raise IndependentValidationError("negative_schema_unsupported", str(document.get("schema_version")))
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise IndependentValidationError("negative_cases_missing", "negative cases must be a list")
    by_kind = {str(case.get("kind")): case for case in cases if isinstance(case, dict)}
    if set(by_kind) != set(_NEGATIVE_CASE_COVERAGE):
        raise IndependentValidationError("negative_case_matrix_incomplete", ",".join(sorted(by_kind)))
    for kind, expected in _NEGATIVE_CASE_COVERAGE.items():
        if by_kind[kind].get("expected") != expected:
            raise IndependentValidationError("negative_case_expectation_mismatch", kind)
    if set(by_kind["contradictory"].get("evidence_roles", ())) != {"support", "contradict"}:
        raise IndependentValidationError("contradictory_fixture_incomplete", "support and contradict are required")
    if by_kind["moving_ref"].get("ref") != "main":
        raise IndependentValidationError("moving_ref_fixture_invalid", "moving ref must be explicit")
    if by_kind["holdout"].get("tuning") is not False:
        raise IndependentValidationError("holdout_tuning_fixture_invalid", "holdout tuning must be disabled")
    return tuple(cases)


def build_report(
    manifest: dict[str, Any],
    runs: dict[str, Any],
    *,
    g32_report: dict[str, Any],
    g34_cases: dict[str, Any],
    g34_runs: dict[str, Any],
    replay_byte_identical: bool,
) -> dict[str, Any]:
    cases = validate_manifest(manifest)
    run_rows = validate_runs(runs, (str(case["case_id"]) for case in cases))
    mode_counts = Counter(str(run["mode"]) for run in run_rows)
    outcome_counts = Counter(str(run["validation_outcome"]) for run in run_rows if run["validation_outcome"] is not None)
    complete_receipts = sum(1 for run in run_rows if tuple(run["stage_trace"]) == _STAGE_TRACE)
    unchanged = sum(1 for run in run_rows if run["target_unchanged"] is True)

    historical_cases = {str(item["case_id"]): item for item in g34_cases.get("cases", ())}
    historical_runs = {str(item["case_id"]): item for item in g34_runs.get("runs", ())}
    proxy_total = proxy_agree = 0
    for case_id, case in historical_cases.items():
        run = historical_runs.get(case_id)
        if run is None or case.get("event_class") == "retained":
            continue
        proxy_total += 1
        expected = "likely_expired" if case.get("event_class") == "marker_only_removal" else "likely_active"
        if run.get("heuristic_status") == expected:
            proxy_agree += 1

    natural_cases = list(g32_report.get("cases", ()))
    natural_outcomes = Counter(str(item.get("validation_outcome")) for item in natural_cases if item.get("validation_outcome") is not None)
    report = {
        "schema_version": G37_SCHEMA_VERSION,
        "benchmark_id": str(manifest.get("benchmark_id", "g37-maintainer-independent-v1")),
        "manifest_digest": digest(manifest),
        "run_digest": digest(runs),
        "execution": {"status": "recorded_replay", "network": "none", "model_calls": 0},
        "mechanical_correctness": {
            "case_count": len(cases),
            "run_count": len(run_rows),
            "mode_counts": dict(sorted(mode_counts.items())),
            "complete_receipts": complete_receipts,
            "target_unchanged_receipts": unchanged,
            "replay_byte_identical": replay_byte_identical,
        },
        "evidence_quality": {
            "exact_sha_cases": len(cases),
            "recorded_agent_cases": len(natural_cases),
            "unsupported_condition_labels": len(cases),
            "contradictions_established": 0,
            "note": "G37 records evidence availability and provenance; it does not adjudicate protected conditions.",
        },
        "negative_case_coverage": dict(_NEGATIVE_CASE_COVERAGE),
        "validation": {
            "outcomes": dict(sorted(outcome_counts.items())),
            "g32_natural_outcomes": dict(sorted(natural_outcomes.items())),
            "scope": "declared disposable-clone tests only",
        },
        "historical_agreement": {
            "source": "G34 historical removal backtest",
            "proxy_cases": proxy_total,
            "heuristic_agreements": proxy_agree,
            "agreement_rate": round(proxy_agree / proxy_total, 4) if proxy_total else None,
            "label_provenance": "historical_proxy",
        },
        "limitations": [
            "No protected-condition label is human adjudicated in this benchmark.",
            "Historical removal or retention is a proxy outcome, not proof that a condition expired or that deletion is safe.",
            "The full orchestration replay is recorded/offline and does not measure live-model quality.",
            "The LangChain natural corpus is one repository and a selected clone-runnable subset; it does not estimate repository-wide recall.",
            "A passing disposable validation proves only the declared test scope and deployment assumptions remain unproven.",
        ],
        "non_authority": True,
    }
    return report


def report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = [
    "G37_SCHEMA_VERSION",
    "IndependentValidationError",
    "build_report",
    "canonical_json",
    "digest",
    "read_json",
    "report_json",
    "validate_manifest",
    "validate_negative_cases",
    "validate_runs",
]
