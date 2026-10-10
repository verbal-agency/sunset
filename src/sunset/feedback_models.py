"""Versioned contracts for the offline empirical-feedback exploration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Literal


FEEDBACK_SCHEMA_VERSION = "1"
FeedbackAuditStatus = Literal["passed", "rejected"]
FeedbackRecommendation = Literal["build", "defer", "reject"]
FeedbackStatus = Literal["likely_active", "likely_expired", "unknown", "contradictory"]
EmpiricalStatus = Literal["likely_active", "likely_expired", "not_adjudicated"]
ValidationOutcome = Literal["confirmed", "still_failing", "flaky", "environment_error", "inconclusive"]


@dataclass(frozen=True, slots=True)
class FeedbackCase:
    case_id: str
    split: str
    candidate_family: str
    baseline_status: FeedbackStatus
    heuristic_status: FeedbackStatus
    validation_outcome: ValidationOutcome
    empirical_status: EmpiricalStatus
    source_report_digest: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.case_id or not self.split or not self.candidate_family:
            raise ValueError("feedback case identity fields are required")
        if self.baseline_status not in {"likely_active", "likely_expired", "unknown", "contradictory"}:
            raise ValueError(f"unsupported baseline status: {self.baseline_status}")
        if self.heuristic_status not in {"likely_active", "likely_expired", "unknown", "contradictory"}:
            raise ValueError(f"unsupported heuristic status: {self.heuristic_status}")
        if self.validation_outcome not in {"confirmed", "still_failing", "flaky", "environment_error", "inconclusive"}:
            raise ValueError(f"unsupported validation outcome: {self.validation_outcome}")
        if self.empirical_status not in {"likely_active", "likely_expired", "not_adjudicated"}:
            raise ValueError(f"unsupported empirical status: {self.empirical_status}")
        if self.input_tokens < 0 or self.output_tokens < 0 or self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("feedback measurements must be non-negative")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise ValueError("feedback cost must be non-negative")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FeedbackCase":
        required = {
            "case_id", "split", "candidate_family", "baseline_status", "heuristic_status",
            "validation_outcome", "empirical_status", "source_report_digest",
        }
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"missing feedback case field: {missing[0]}")
        return cls(
            case_id=str(value["case_id"]),
            split=str(value["split"]),
            candidate_family=str(value["candidate_family"]),
            baseline_status=value["baseline_status"],
            heuristic_status=value["heuristic_status"],
            validation_outcome=value["validation_outcome"],
            empirical_status=value["empirical_status"],
            source_report_digest=str(value["source_report_digest"]),
            input_tokens=int(value.get("input_tokens", 0)),
            output_tokens=int(value.get("output_tokens", 0)),
            cost_usd=float(value["cost_usd"]) if value.get("cost_usd") is not None else None,
            latency_ms=int(value["latency_ms"]) if value.get("latency_ms") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FeedbackPacket:
    source_report_digest: str
    development_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    cases: tuple[FeedbackCase, ...]
    mechanism_inputs: dict[str, Any]
    holdout_case_ids: tuple[str, ...] = ()
    schema_version: str = FEEDBACK_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FeedbackPacket":
        if value.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
            raise ValueError("feedback packet schema_version must be 1")
        required = {"source_report_digest", "development_case_ids", "excluded_case_ids", "cases", "mechanism_inputs"}
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"missing feedback packet field: {missing[0]}")
        raw_cases = value["cases"]
        if not isinstance(raw_cases, list):
            raise ValueError("feedback packet cases must be a list")
        return cls(
            source_report_digest=str(value["source_report_digest"]),
            development_case_ids=tuple(str(item) for item in value["development_case_ids"]),
            excluded_case_ids=tuple(str(item) for item in value["excluded_case_ids"]),
            cases=tuple(FeedbackCase.from_dict(item) for item in raw_cases),
            mechanism_inputs=dict(value["mechanism_inputs"]),
            holdout_case_ids=tuple(str(item) for item in value.get("holdout_case_ids", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_report_digest": self.source_report_digest,
            "development_case_ids": list(self.development_case_ids),
            "excluded_case_ids": list(self.excluded_case_ids),
            "cases": [item.to_dict() for item in self.cases],
            "mechanism_inputs": self.mechanism_inputs,
            "holdout_case_ids": list(self.holdout_case_ids),
        }

    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict())).hexdigest()


@dataclass(frozen=True, slots=True)
class FeedbackAudit:
    status: FeedbackAuditStatus
    packet_digest: str
    eligible_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    errors: tuple[str, ...]
    exclusions: dict[str, str]
    schema_version: str = FEEDBACK_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "packet_digest": self.packet_digest,
            "eligible_case_ids": list(self.eligible_case_ids),
            "excluded_case_ids": list(self.excluded_case_ids),
            "errors": list(self.errors),
            "exclusions": dict(self.exclusions),
        }


@dataclass(frozen=True, slots=True)
class FeedbackCaseResult:
    case_id: str
    baseline_status: FeedbackStatus
    proposed_status: FeedbackStatus
    empirical_status: EmpiricalStatus
    escalation: bool
    correct: bool | None
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_ms: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FeedbackMechanismReport:
    mechanism_id: str
    cases: tuple[FeedbackCaseResult, ...]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mechanism_id": self.mechanism_id,
            "cases": [item.to_dict() for item in self.cases],
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class FeedbackComparisonReport:
    packet_digest: str
    audit: FeedbackAudit
    mechanisms: tuple[FeedbackMechanismReport, ...]
    recommendation: FeedbackRecommendation
    limitations: tuple[str, ...]
    schema_version: str = FEEDBACK_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "packet_digest": self.packet_digest,
            "audit": self.audit.to_dict(),
            "mechanisms": [item.to_dict() for item in self.mechanisms],
            "recommendation": self.recommendation,
            "limitations": list(self.limitations),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


__all__ = [
    "EmpiricalStatus",
    "FEEDBACK_SCHEMA_VERSION",
    "FeedbackAudit",
    "FeedbackAuditStatus",
    "FeedbackCase",
    "FeedbackCaseResult",
    "FeedbackComparisonReport",
    "FeedbackMechanismReport",
    "FeedbackPacket",
    "FeedbackRecommendation",
    "FeedbackStatus",
    "ValidationOutcome",
]
