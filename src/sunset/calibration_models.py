"""Versioned contracts for calibration and the final release gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal


CALIBRATION_SCHEMA_VERSION = "1"
Modes = Literal["heuristic", "agentic"]


@dataclass(frozen=True, slots=True)
class ExpectedConditionLabel:
    condition_state: str
    historical_outcome: str
    contradictions: tuple[str, ...] = ()
    proof_obligations: tuple[str, ...] = ()
    evidence_scope: tuple[str, ...] = ()
    valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"condition_state": self.condition_state, "historical_outcome": self.historical_outcome, "contradictions": list(self.contradictions), "proof_obligations": list(self.proof_obligations), "evidence_scope": list(self.evidence_scope), "valid": self.valid}


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    candidate_family: str
    protected_condition: str
    label: ExpectedConditionLabel
    historical_outcome: str
    schema_version: str = CALIBRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.case_id or not self.candidate_family or not self.protected_condition:
            raise ValueError("benchmark case identity and protected condition are required")

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "candidate_family": self.candidate_family, "protected_condition": self.protected_condition, "label": self.label.to_dict(), "historical_outcome": self.historical_outcome, "schema_version": self.schema_version}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BenchmarkCase:
        label = value["label"]
        return cls(str(value["case_id"]), str(value["candidate_family"]), str(value["protected_condition"]), ExpectedConditionLabel(str(label["condition_state"]), str(label["historical_outcome"]), tuple(label.get("contradictions", ())), tuple(label.get("proof_obligations", ())), tuple(label.get("evidence_scope", ())), bool(label.get("valid", True))), str(value["historical_outcome"]), str(value.get("schema_version", CALIBRATION_SCHEMA_VERSION)))


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    case_id: str
    mode: Modes
    observed_condition_state: str
    observed_recommendation: str
    contradiction_detected: bool
    proof_obligations: tuple[str, ...]
    citation_accuracy: float
    unsupported_claims: int
    cost_usd: float | None
    latency_ms: int
    trace_id: str
    excluded_reason: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"heuristic", "agentic"} or not self.case_id or not self.trace_id or self.latency_ms < 0 or self.unsupported_claims < 0:
            raise ValueError("evaluation run is invalid")
        if not 0 <= self.citation_accuracy <= 1:
            raise ValueError("citation accuracy must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MetricRecord:
    name: str
    mode: Modes | Literal["combined"]
    value: float | int | None
    denominator: int
    exclusions: tuple[str, ...]
    uncertainty: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReleaseThreshold:
    threshold_id: str
    minimum_coverage: float = 1.0
    minimum_condition_accuracy: float = 0.8
    maximum_false_removal_risk: float = 0.0
    maximum_unsupported_claim_rate: float = 0.0

    def __post_init__(self) -> None:
        if not self.threshold_id or not 0 <= self.minimum_coverage <= 1 or not 0 <= self.minimum_condition_accuracy <= 1 or not 0 <= self.maximum_false_removal_risk <= 1 or not 0 <= self.maximum_unsupported_claim_rate <= 1:
            raise ValueError("release threshold is invalid")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReleaseGateResult:
    evaluation_id: str
    threshold: ReleaseThreshold
    metrics: tuple[MetricRecord, ...]
    passed: bool
    inconclusive: bool
    reasons: tuple[str, ...]
    non_authority: bool = True
    schema_version: str = CALIBRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.evaluation_id or not self.non_authority:
            raise ValueError("release results require an ID and non-authority marker")

    def to_dict(self) -> dict[str, Any]:
        return {"evaluation_id": self.evaluation_id, "threshold": self.threshold.to_dict(), "metrics": [metric.to_dict() for metric in self.metrics], "passed": self.passed, "inconclusive": self.inconclusive, "reasons": list(self.reasons), "non_authority": self.non_authority, "schema_version": self.schema_version}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = [f"# Sunset release gate: {self.evaluation_id}", "", f"- Verdict: **{'PASS' if self.passed else 'INCONCLUSIVE' if self.inconclusive else 'FAIL'}**", f"- Threshold: `{self.threshold.threshold_id}`", "- Authority: `non-authoritative`", "", "| Metric | Mode | Value | Denominator |", "| --- | --- | ---: | ---: |"]
        lines.extend(f"| {metric.name} | {metric.mode} | {metric.value} | {metric.denominator} |" for metric in self.metrics)
        lines.extend(("", "## Reasons", ""))
        lines.extend(f"- {reason}" for reason in self.reasons)
        lines.append("\nBenchmark results describe historical labeled cases; they do not prove production removability.")
        return "\n".join(lines) + "\n"


__all__ = ["BenchmarkCase", "EvaluationRun", "ExpectedConditionLabel", "MetricRecord", "ReleaseGateResult", "ReleaseThreshold"]
