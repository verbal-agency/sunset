"""Deterministic, offline exploration of empirically-adjudicated feedback."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from sunset.feedback_models import (
    FeedbackAudit,
    FeedbackCase,
    FeedbackCaseResult,
    FeedbackComparisonReport,
    FeedbackMechanismReport,
    FeedbackPacket,
    FeedbackStatus,
)


_ELIGIBLE_OUTCOMES = {"confirmed", "still_failing"}
_OUTCOME_TO_STATUS = {"confirmed": "likely_expired", "still_failing": "likely_active"}
_DEFINITE = {"likely_active", "likely_expired"}
_MECHANISMS = {"baseline", "exemplar_memory", "calibration_guard"}


class FeedbackError(ValueError):
    """A malformed or unsafe feedback packet."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_feedback_packet(path: str | Path) -> FeedbackPacket:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedbackError("packet_invalid", str(exc)) from exc
    if not isinstance(value, dict):
        raise FeedbackError("packet_invalid", "feedback packet must be an object")
    try:
        return FeedbackPacket.from_dict(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise FeedbackError("packet_invalid", str(exc)) from exc


def audit_feedback_packet(
    packet: FeedbackPacket,
    *,
    holdout_case_ids: Iterable[str] = (),
    holdout_artifact_digests: Iterable[str] = (),
    expected_source_report_digest: str | None = None,
) -> FeedbackAudit:
    """Validate eligibility and reject holdout leakage before any mechanism runs."""

    packet_digest = packet.digest()
    errors: list[str] = []
    exclusions: dict[str, str] = {}
    case_ids = [case.case_id for case in packet.cases]
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicates:
        errors.append(f"duplicate_case_id:{duplicates[0]}")

    sealed_cases = set(holdout_case_ids) | set(packet.holdout_case_ids)
    sealed_digests = set(holdout_artifact_digests)
    if packet.holdout_case_ids:
        errors.append("holdout_case_ids_present")
    if expected_source_report_digest is not None and packet.source_report_digest != expected_source_report_digest:
        errors.append("source_report_digest_mismatch")
    _find_leakage(packet.mechanism_inputs, sealed_cases, sealed_digests, errors)

    expected_development = {case.case_id for case in packet.cases if case.split == "development"}
    if set(packet.development_case_ids) != expected_development:
        errors.append("development_case_ids_mismatch")

    for case in packet.cases:
        if case.case_id in sealed_cases or case.split == "holdout":
            errors.append(f"holdout_case_present:{case.case_id}")
            continue
        if case.split != "development":
            exclusions[case.case_id] = "unsupported_split"
            continue
        if case.source_report_digest != packet.source_report_digest:
            errors.append(f"source_report_digest_mismatch:{case.case_id}")
            continue
        expected = _OUTCOME_TO_STATUS.get(case.validation_outcome)
        if case.validation_outcome not in _ELIGIBLE_OUTCOMES or case.empirical_status != expected:
            exclusions[case.case_id] = "non_conclusive_or_mismatched_empirical_outcome"

    declared_excluded = set(packet.excluded_case_ids)
    if declared_excluded != set(exclusions):
        errors.append("excluded_case_ids_mismatch")
    eligible = tuple(sorted(case.case_id for case in packet.cases if case.case_id not in exclusions and case.split == "development"))
    if not eligible:
        errors.append("no_eligible_cases")

    return FeedbackAudit(
        status="passed" if not errors else "rejected",
        packet_digest=packet_digest,
        eligible_case_ids=eligible,
        excluded_case_ids=tuple(sorted(exclusions)),
        errors=tuple(sorted(set(errors))),
        exclusions=exclusions,
    )


def run_feedback_comparison(
    packet: FeedbackPacket,
    *,
    holdout_case_ids: Iterable[str] = (),
    holdout_artifact_digests: Iterable[str] = (),
    expected_source_report_digest: str | None = None,
    mechanisms: tuple[str, ...] = ("baseline", "exemplar_memory", "calibration_guard"),
) -> FeedbackComparisonReport:
    """Run bounded comparison mechanisms after a passing leakage audit."""

    audit = audit_feedback_packet(
        packet,
        holdout_case_ids=holdout_case_ids,
        holdout_artifact_digests=holdout_artifact_digests,
        expected_source_report_digest=expected_source_report_digest,
    )
    unknown_mechanisms = sorted(set(mechanisms) - _MECHANISMS)
    if unknown_mechanisms:
        audit = FeedbackAudit(
            status="rejected",
            packet_digest=audit.packet_digest,
            eligible_case_ids=audit.eligible_case_ids,
            excluded_case_ids=audit.excluded_case_ids,
            errors=tuple(sorted(set((*audit.errors, f"unknown_mechanism:{unknown_mechanisms[0]}")))),
            exclusions=audit.exclusions,
        )
    if audit.status == "rejected":
        return FeedbackComparisonReport(
            packet_digest=audit.packet_digest,
            audit=audit,
            mechanisms=(),
            recommendation="reject",
            limitations=("No mechanism ran because the packet failed the eligibility or leakage audit.",),
        )

    eligible = tuple(case for case in packet.cases if case.case_id in set(audit.eligible_case_ids))
    reports = tuple(_run_mechanism(name, eligible) for name in mechanisms)
    recommendation = _recommend(reports, len(eligible))
    limitations = (
        "The empirical signal is a selected, small, clone-runnable subset.",
        "Development-only leave-one-out comparison; no holdout score was read.",
        "Mechanisms change hypotheses/escalation requests only and cannot authorize cleanup.",
    )
    return FeedbackComparisonReport(audit.packet_digest, audit, reports, recommendation, limitations)


def _run_mechanism(mechanism_id: str, cases: tuple[FeedbackCase, ...]) -> FeedbackMechanismReport:
    results: list[FeedbackCaseResult] = []
    for case in cases:
        status = _status_for(mechanism_id, case, cases)
        correct = status == case.empirical_status if status in _DEFINITE else None
        results.append(
            FeedbackCaseResult(
                case_id=case.case_id,
                baseline_status=case.baseline_status,
                proposed_status=status,
                empirical_status=case.empirical_status,
                escalation=_needs_escalation(case.heuristic_status, status),
                correct=correct,
                input_tokens=case.input_tokens,
                output_tokens=case.output_tokens,
                cost_usd=case.cost_usd,
                latency_ms=case.latency_ms,
            )
        )
    return FeedbackMechanismReport(mechanism_id, tuple(results), _metrics(results))


def _status_for(mechanism_id: str, case: FeedbackCase, cases: tuple[FeedbackCase, ...]) -> FeedbackStatus:
    if mechanism_id == "baseline":
        return case.baseline_status
    if mechanism_id == "calibration_guard":
        if case.baseline_status == "likely_expired" and case.heuristic_status == "likely_active":
            return "unknown"
        return case.baseline_status
    peers = {
        peer.empirical_status
        for peer in cases
        if peer.case_id != case.case_id and peer.candidate_family == case.candidate_family
    }
    if len(peers) == 1:
        return next(iter(peers))  # type: ignore[return-value]
    return case.baseline_status


def _needs_escalation(heuristic_status: FeedbackStatus, proposed_status: FeedbackStatus) -> bool:
    return proposed_status not in _DEFINITE or heuristic_status != proposed_status


def _metrics(results: list[FeedbackCaseResult]) -> dict[str, Any]:
    definite = [item for item in results if item.correct is not None]
    costs = [item.cost_usd for item in results]
    latencies = [item.latency_ms for item in results]
    return {
        "case_count": len(results),
        "definite_count": len(definite),
        "accuracy": round(sum(bool(item.correct) for item in definite) / len(definite), 4) if definite else None,
        "escalations": sum(item.escalation for item in results),
        "escalation_rate": round(sum(item.escalation for item in results) / len(results), 4) if results else None,
        "input_tokens": sum(item.input_tokens for item in results),
        "output_tokens": sum(item.output_tokens for item in results),
        "cost_usd": round(sum(cost for cost in costs if cost is not None), 8) if all(cost is not None for cost in costs) else None,
        "latency_ms": round(sum(latency for latency in latencies if latency is not None) / len(latencies), 2) if latencies and all(latency is not None for latency in latencies) else None,
        "token_cost_latency_delta": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0, "latency_ms": 0},
    }


def _recommend(reports: tuple[FeedbackMechanismReport, ...], eligible_count: int) -> str:
    if eligible_count < 10:
        return "defer"
    baseline = next(report for report in reports if report.mechanism_id == "baseline")
    baseline_accuracy = baseline.metrics["accuracy"] or 0
    for report in reports:
        if report.mechanism_id == "baseline":
            continue
        if (report.metrics["accuracy"] or 0) > baseline_accuracy and report.metrics["escalation_rate"] <= baseline.metrics["escalation_rate"]:
            return "build"
    return "reject"


def _find_leakage(value: Any, case_ids: set[str], digests: set[str], errors: list[str], path: str = "mechanism_inputs") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if "holdout" in lowered:
                errors.append(f"holdout_field:{path}.{key}")
            _find_leakage(item, case_ids, digests, errors, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _find_leakage(item, case_ids, digests, errors, f"{path}[{index}]")
    elif isinstance(value, str):
        if value in case_ids:
            errors.append(f"holdout_case_reference:{path}")
        if value in digests:
            errors.append(f"holdout_artifact_reference:{path}")


__all__ = [
    "FeedbackError",
    "audit_feedback_packet",
    "load_feedback_packet",
    "run_feedback_comparison",
]
