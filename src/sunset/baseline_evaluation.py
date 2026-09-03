"""Offline, replayable evaluation of heuristic and recorded-agentic traces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from statistics import median
from typing import Any

from sunset.adjudication import source_corpus_digest
from sunset.baseline_evaluation_models import BaselineReport, RecordedTrace
from sunset.validation_corpus import load_validation_corpus


class BaselineEvaluationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MODES = {"heuristic", "agentic_recorded"}
_STATUSES = {"identified", "active", "likely_expired", "unknown", "contradictory"}
_RUN_STATUSES = {"completed", "inconclusive", "budget_exhausted", "malformed_trace", "excluded"}


def _read(path: str | Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineEvaluationError("fixture_invalid", str(exc)) from exc
    if not isinstance(value, dict):
        raise BaselineEvaluationError("fixture_invalid", "fixture must be an object")
    return value, raw


def load_recorded_traces(path: str | Path) -> tuple[RecordedTrace, ...]:
    value, _ = _read(path)
    if value.get("schema_version") != "1" or not isinstance(value.get("traces"), list):
        raise BaselineEvaluationError("trace_fixture_invalid", "schema version 1 and traces list are required")
    try:
        traces = tuple(RecordedTrace.from_dict(item) for item in value["traces"])
    except (TypeError, ValueError, KeyError) as exc:
        raise BaselineEvaluationError("trace_fixture_invalid", str(exc)) from exc
    if not traces:
        raise BaselineEvaluationError("trace_fixture_empty", "at least one trace is required")
    for trace in traces:
        if trace.mode not in _MODES or trace.run_status not in _RUN_STATUSES:
            raise BaselineEvaluationError("trace_enum_invalid", trace.trace_id)
        if trace.condition_status not in _STATUSES or trace.observed_status not in _STATUSES:
            raise BaselineEvaluationError("trace_status_invalid", trace.trace_id)
        if not trace.trace_id or trace.citation_accuracy < 0 or trace.citation_accuracy > 1:
            raise BaselineEvaluationError("trace_value_invalid", trace.trace_id)
        if min(trace.unsupported_claims, trace.tool_calls, trace.input_tokens, trace.latency_ms) < 0:
            raise BaselineEvaluationError("trace_value_invalid", trace.trace_id)
    return traces


def load_reference_cases(path: str | Path) -> tuple[dict[str, Any], ...]:
    value, _ = _read(path)
    if value.get("schema_version") != "1" or value.get("authority") != "reference_only":
        raise BaselineEvaluationError("reference_authority_invalid", "reference fixture must be reference_only schema 1")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BaselineEvaluationError("reference_fixture_empty", "reference cases are required")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise BaselineEvaluationError("reference_case_invalid", "case must be an object")
        required = {"reference_id", "repository", "commit_sha", "path", "source_url", "reference_class", "criteria"}
        if set(case) != required:
            raise BaselineEvaluationError("reference_case_invalid", "reference fields must be explicit")
        identifier = str(case["reference_id"])
        sha = str(case["commit_sha"])
        path_value = str(case["path"])
        if not identifier or identifier in seen or not _SHA_RE.fullmatch(sha) or not path_value or path_value.startswith("/") or ".." in Path(path_value).parts:
            raise BaselineEvaluationError("reference_case_invalid", identifier)
        url = str(case["source_url"])
        if sha not in url or path_value.replace(" ", "%20") not in url:
            raise BaselineEvaluationError("reference_not_pinned", identifier)
        if not isinstance(case["criteria"], list) or not case["criteria"] or any(not str(item) for item in case["criteria"]):
            raise BaselineEvaluationError("reference_criteria_invalid", identifier)
        seen.add(identifier)
        result.append({"reference_id": identifier, "repository": str(case["repository"]), "commit_sha": sha, "path": path_value, "source_url": url, "reference_class": str(case["reference_class"]), "criteria": [str(item) for item in case["criteria"]]})
    return tuple(sorted(result, key=lambda item: item["reference_id"]))


def evaluate_baseline(
    manifest_path: str | Path,
    traces_path: str | Path,
    references_path: str | Path | None = None,
) -> BaselineReport:
    manifest_value, _ = _read(manifest_path)
    if manifest_value.get("schema_version") != "1" or not manifest_value.get("manifest_digest"):
        raise BaselineEvaluationError("manifest_invalid", "frozen manifest identity is required")
    # The frozen manifest carries the corpus digest; bind it without consulting the target repository.
    source_digest = str(manifest_value.get("source_corpus_digest", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", source_digest):
        raise BaselineEvaluationError("manifest_invalid", "source corpus digest is invalid")
    source_path = Path(manifest_path).parent.parent / "validation_corpus" / "langchain-validation-v1.json"
    family_by_case: dict[str, str] = {}
    if source_path.exists():
        source_corpus = load_validation_corpus(source_path)
        actual_source_digest = source_corpus_digest(source_corpus)
        if actual_source_digest != source_digest:
            raise BaselineEvaluationError("manifest_binding_invalid", "source corpus digest does not match the frozen corpus")
        family_by_case = {case.case_id: case.candidate_family for case in source_corpus.cases}
    unsigned = {key: value for key, value in manifest_value.items() if key != "manifest_digest"}
    expected_manifest_digest = hashlib.sha256(_canonical(unsigned) + b"\nadjudication-freeze-policy-v1").hexdigest()
    if expected_manifest_digest != str(manifest_value["manifest_digest"]):
        raise BaselineEvaluationError("manifest_digest_invalid", "frozen manifest digest does not verify")
    included = {str(item["case_id"]): item for item in manifest_value.get("decisions", []) if isinstance(item, dict)}
    excluded = {str(item["case_id"]): str(item.get("reason", "")) for item in manifest_value.get("excluded_cases", []) if isinstance(item, dict)}
    case_ids = set(included) | set(excluded)
    if not case_ids or set(manifest_value.get("split_identities", {}).get("development", [])) | set(manifest_value.get("split_identities", {}).get("holdout", [])) != case_ids - set(manifest_value.get("split_identities", {}).get("excluded", [])):
        raise BaselineEvaluationError("manifest_binding_invalid", "split identities do not cover the frozen cases")
    traces_value, trace_raw = _read(traces_path)
    traces = load_recorded_traces(traces_path)
    by_pair: dict[tuple[str, str], RecordedTrace] = {}
    allowed_evidence: dict[str, set[str]] = {}
    for case_id, decision in included.items():
        allowed_evidence[case_id] = set(str(item) for item in decision.get("evidence_ids", []))
    for trace in traces:
        key = (trace.case_id, trace.mode)
        if key in by_pair:
            raise BaselineEvaluationError("duplicate_trace", trace.trace_id)
        if trace.case_id not in case_ids:
            raise BaselineEvaluationError("trace_case_unknown", trace.case_id)
        if trace.split not in {"development", "holdout", "excluded"}:
            raise BaselineEvaluationError("trace_split_invalid", trace.trace_id)
        if trace.case_id in excluded and trace.run_status != "excluded":
            raise BaselineEvaluationError("exclusion_mismatch", trace.case_id)
        if trace.case_id in included:
            unknown = set(trace.evidence_ids) - allowed_evidence.get(trace.case_id, set())
            if unknown:
                code = "evidence_case_mismatch" if any(not item.startswith(f"{trace.case_id}:") for item in unknown) else "evidence_not_found"
                raise BaselineEvaluationError(code, sorted(unknown)[0])
        by_pair[key] = trace
    missing = [(case_id, mode) for case_id in sorted(included) for mode in sorted(_MODES) if (case_id, mode) not in by_pair]
    if missing:
        raise BaselineEvaluationError("trace_pair_missing", f"{missing[0][0]}:{missing[0][1]}")
    references = load_reference_cases(references_path) if references_path else ()
    # Materialize unrepresented exclusions from the frozen manifest. They are
    # visible in the report but never enter any scored denominator.
    for case_id in sorted(excluded):
        for mode in sorted(_MODES):
            key = (case_id, mode)
            if key not in by_pair:
                by_pair[key] = RecordedTrace(case_id, mode, "excluded", "unknown", "unknown", (), (), 0.0, 0, 0, 0, 0, f"excluded-{case_id}-{mode}", "excluded", "not_adjudicated_in_this_pass")
    ordered = tuple(by_pair[key] for key in sorted(by_pair))
    report_metrics: dict[str, Any] = {"case_count": len(case_ids), "included_case_count": len(included), "excluded_case_count": len(excluded), "reference_case_count": len(references), "cost_availability": "unavailable", "safety_signal_count": sum(item.run_status != "completed" or item.unsupported_claims > 0 or item.observed_status == "contradictory" for item in ordered), "modes": {}}
    for mode in sorted(_MODES):
        report_metrics["modes"][mode] = _metrics_for_mode(mode, ordered, included)
    report_metrics["case_families"] = _family_metrics(ordered, included, family_by_case)
    trace_digest = hashlib.sha256(trace_raw).hexdigest()
    unsigned = {"manifest_digest": manifest_value["manifest_digest"], "source_corpus_digest": source_digest, "trace_fixture_digest": trace_digest, "traces": [item.to_dict() for item in ordered], "references": list(references)}
    evaluation_id = hashlib.sha256(_canonical(unsigned) + b"\nbaseline-evaluation-policy-v1").hexdigest()
    limitations = ("G23 labels are single-reviewer provisional decisions, not independent ground truth.", "Fifteen cases are explicitly excluded and contribute no accuracy denominator.", "Pinned public references exercise criteria only; they are reference_only and cannot establish removability or alter labels.", "Passing validation evidence is not proof of production removability.")
    return BaselineReport(evaluation_id, source_digest, str(manifest_value["manifest_digest"]), trace_digest, {key: tuple(str(item) for item in value) for key, value in manifest_value["split_identities"].items()}, limitations, report_metrics, tuple(item.to_dict() for item in ordered), references)


def _metrics_for_mode(mode: str, traces: tuple[RecordedTrace, ...], included: dict[str, Any]) -> dict[str, Any]:
    values = [item for item in traces if item.mode == mode]
    completed = [item for item in values if item.run_status == "completed" and item.case_id in included]
    denominator = len(completed)
    accuracy = sum(item.observed_status == str(included[item.case_id].get("condition_status")) for item in completed) / denominator if denominator else None
    proof = sum(set(str(item) for item in included[item.case_id].get("proof_obligations", [])) <= set(item.proof_obligations) for item in completed) / denominator if denominator else None
    unsupported = sum(item.unsupported_claims > 0 for item in completed) / denominator if denominator else None
    return {"completed_included_denominator": denominator, "coverage": round(denominator / len(included), 4) if included else 0.0, "condition_accuracy": round(accuracy, 4) if accuracy is not None else None, "proof_obligation_recall": round(proof, 4) if proof is not None else None, "citation_accuracy": round(sum(item.citation_accuracy for item in completed) / denominator, 4) if denominator else None, "unsupported_claim_rate": round(unsupported, 4) if unsupported is not None else None, "median_input_tokens": int(median(item.input_tokens for item in completed)) if completed else None, "median_latency_ms": int(median(item.latency_ms for item in completed)) if completed else None, "run_status_counts": {status: sum(item.run_status == status for item in values) for status in sorted(_RUN_STATUSES)}}


def _family_metrics(traces: tuple[RecordedTrace, ...], included: dict[str, Any], family_by_case: dict[str, str]) -> dict[str, Any]:
    families = sorted({family_by_case.get(case_id, "unknown") for case_id in included})
    result: dict[str, Any] = {}
    for family in families:
        case_ids = {case_id for case_id in included if family_by_case.get(case_id, "unknown") == family}
        result[family] = {mode: {"included_cases": len(case_ids), "completed": sum(item.case_id in case_ids and item.mode == mode and item.run_status == "completed" for item in traces)} for mode in sorted(_MODES)}
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


__all__ = ["BaselineEvaluationError", "evaluate_baseline", "load_recorded_traces", "load_reference_cases"]
