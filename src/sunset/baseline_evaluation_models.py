"""Versioned contracts for the offline G24 baseline evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

BASELINE_EVALUATION_SCHEMA_VERSION = "1"
EvaluationMode = Literal["heuristic", "agentic_recorded"]
RunStatus = Literal["completed", "inconclusive", "budget_exhausted", "malformed_trace", "excluded"]


@dataclass(frozen=True, slots=True)
class RecordedTrace:
    case_id: str
    mode: EvaluationMode
    split: str
    condition_status: str
    observed_status: str
    proof_obligations: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    citation_accuracy: float
    unsupported_claims: int
    tool_calls: int
    input_tokens: int
    latency_ms: int
    trace_id: str
    run_status: RunStatus
    error_kind: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RecordedTrace":
        required = {"case_id", "mode", "split", "condition_status", "observed_status", "proof_obligations", "evidence_ids", "citation_accuracy", "unsupported_claims", "tool_calls", "input_tokens", "latency_ms", "trace_id", "run_status"}
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"missing trace field: {missing[0]}")
        unknown = set(value) - required - {"error_kind"}
        if unknown:
            raise ValueError(f"unknown trace field: {sorted(unknown)[0]}")
        return cls(
            case_id=str(value["case_id"]), mode=value["mode"], split=str(value["split"]),
            condition_status=str(value["condition_status"]), observed_status=str(value["observed_status"]),
            proof_obligations=tuple(str(item) for item in value["proof_obligations"]),
            evidence_ids=tuple(str(item) for item in value["evidence_ids"]),
            citation_accuracy=float(value["citation_accuracy"]), unsupported_claims=int(value["unsupported_claims"]),
            tool_calls=int(value["tool_calls"]), input_tokens=int(value["input_tokens"]), latency_ms=int(value["latency_ms"]),
            trace_id=str(value["trace_id"]), run_status=value["run_status"],
            error_kind=str(value["error_kind"]) if value.get("error_kind") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "case_id": self.case_id, "mode": self.mode, "split": self.split,
            "condition_status": self.condition_status, "observed_status": self.observed_status,
            "proof_obligations": list(self.proof_obligations), "evidence_ids": list(self.evidence_ids),
            "citation_accuracy": self.citation_accuracy, "unsupported_claims": self.unsupported_claims,
            "tool_calls": self.tool_calls, "input_tokens": self.input_tokens, "latency_ms": self.latency_ms,
            "trace_id": self.trace_id, "run_status": self.run_status,
        }
        if self.error_kind is not None:
            result["error_kind"] = self.error_kind
        return result


@dataclass(frozen=True, slots=True)
class BaselineReport:
    evaluation_id: str
    corpus_digest: str
    manifest_digest: str
    trace_fixture_digest: str
    split_identities: dict[str, tuple[str, ...]]
    limitations: tuple[str, ...]
    metrics: dict[str, Any]
    traces: tuple[dict[str, Any], ...]
    references: tuple[dict[str, Any], ...]
    schema_version: str = BASELINE_EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id, "corpus_digest": self.corpus_digest,
            "manifest_digest": self.manifest_digest, "trace_fixture_digest": self.trace_fixture_digest,
            "split_identities": {key: list(value) for key, value in sorted(self.split_identities.items())},
            "limitations": list(self.limitations), "metrics": self.metrics,
            "traces": [dict(item) for item in self.traces], "references": [dict(item) for item in self.references],
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = ["BASELINE_EVALUATION_SCHEMA_VERSION", "BaselineReport", "EvaluationMode", "RecordedTrace", "RunStatus"]
