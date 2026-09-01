"""Framework-independent contracts for one bounded model reasoning step."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal

from sunset.agent_tool_models import ToolReceipt


MODEL_RUNTIME_SCHEMA_VERSION = "1"
REASONING_PROMPT_VERSION = "1"
REASONING_OUTPUT_SCHEMA_VERSION = "1"

ReasoningStatus = Literal["success", "inconclusive", "disabled", "error", "budget_exhausted"]
ClaimKind = Literal["supporting", "contradicting", "unknown"]
AssumptionStatus = Literal["active", "expired", "unknown"]


@dataclass(frozen=True, slots=True)
class ReasoningError:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningError:
        return cls(kind=str(value["kind"]), message=str(value["message"]))


@dataclass(frozen=True, slots=True)
class ReasoningClaim:
    kind: ClaimKind
    summary: str
    citations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in {"supporting", "contradicting", "unknown"}:
            raise ValueError(f"unsupported reasoning claim kind: {self.kind}")

    def to_dict(self) -> dict[str, Any]:
        return {"citations": list(self.citations), "kind": self.kind, "summary": self.summary}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningClaim:
        return cls(
            kind=value["kind"],
            summary=str(value["summary"]),
            citations=tuple(str(item) for item in value["citations"]),
        )


@dataclass(frozen=True, slots=True)
class ReasoningHypothesis:
    """A compact model-derived interpretation, never evidence or authority."""

    assumption_status: AssumptionStatus
    summary: str
    claims: tuple[ReasoningClaim, ...]
    open_questions: tuple[str, ...]
    proposed_tools: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.assumption_status not in {"active", "expired", "unknown"}:
            raise ValueError(f"unsupported assumption status: {self.assumption_status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption_status": self.assumption_status,
            "claims": [item.to_dict() for item in self.claims],
            "open_questions": list(self.open_questions),
            "proposed_tools": list(self.proposed_tools),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningHypothesis:
        return cls(
            assumption_status=value["assumption_status"],
            claims=tuple(ReasoningClaim.from_dict(item) for item in value["claims"]),
            open_questions=tuple(str(item) for item in value["open_questions"]),
            proposed_tools=tuple(str(item) for item in value["proposed_tools"]),
            summary=str(value["summary"]),
        )


@dataclass(frozen=True, slots=True)
class ReasoningUsage:
    input_tokens: int
    output_tokens: int
    estimated: bool
    cost_usd: float | None

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token usage must be non-negative")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise ValueError("model cost must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningUsage:
        cost = value.get("cost_usd")
        return cls(
            input_tokens=int(value["input_tokens"]),
            output_tokens=int(value["output_tokens"]),
            estimated=bool(value["estimated"]),
            cost_usd=float(cost) if cost is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ReasoningBudget:
    input_tokens_debit: int
    input_tokens_remaining: int
    output_tokens_debit: int
    output_tokens_remaining: int

    def __post_init__(self) -> None:
        if min(
            self.input_tokens_debit,
            self.input_tokens_remaining,
            self.output_tokens_debit,
            self.output_tokens_remaining,
        ) < 0:
            raise ValueError("reasoning budget values must be non-negative")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningBudget:
        return cls(
            input_tokens_debit=int(value["input_tokens_debit"]),
            input_tokens_remaining=int(value["input_tokens_remaining"]),
            output_tokens_debit=int(value["output_tokens_debit"]),
            output_tokens_remaining=int(value["output_tokens_remaining"]),
        )


@dataclass(frozen=True, slots=True)
class TransientEvidence:
    """Immediate-only evidence supplied outside checkpoint state."""

    artifact_id: str
    content: str


@dataclass(frozen=True, slots=True)
class ReasoningRequest:
    """Checkpoint-safe request inputs; transient content is passed separately."""

    receipts: tuple[ToolReceipt, ...]
    task: str = "Interpret the supplied evidence conservatively."

    def to_dict(self) -> dict[str, Any]:
        return {"receipts": [item.to_dict() for item in self.receipts], "task": self.task}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningRequest:
        return cls(
            receipts=tuple(ToolReceipt.from_dict(item) for item in value["receipts"]),
            task=str(value["task"]),
        )


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    """Persistable result from one model invocation with no raw prompt/response."""

    invocation_id: str
    provider_identity: str
    status: ReasoningStatus
    input_receipt_ids: tuple[str, ...]
    hypothesis: ReasoningHypothesis | None
    errors: tuple[ReasoningError, ...]
    usage: ReasoningUsage
    budget: ReasoningBudget
    prompt_version: str = REASONING_PROMPT_VERSION
    runtime_schema_version: str = MODEL_RUNTIME_SCHEMA_VERSION
    output_schema_version: str = REASONING_OUTPUT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"success", "inconclusive", "disabled", "error", "budget_exhausted"}:
            raise ValueError(f"unsupported reasoning status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget": self.budget.to_dict(),
            "errors": [item.to_dict() for item in self.errors],
            "hypothesis": self.hypothesis.to_dict() if self.hypothesis is not None else None,
            "input_receipt_ids": list(self.input_receipt_ids),
            "invocation_id": self.invocation_id,
            "output_schema_version": self.output_schema_version,
            "prompt_version": self.prompt_version,
            "provider_identity": self.provider_identity,
            "runtime_schema_version": self.runtime_schema_version,
            "status": self.status,
            "usage": self.usage.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReasoningResult:
        hypothesis = value.get("hypothesis")
        return cls(
            budget=ReasoningBudget.from_dict(value["budget"]),
            errors=tuple(ReasoningError.from_dict(item) for item in value["errors"]),
            hypothesis=ReasoningHypothesis.from_dict(hypothesis) if hypothesis is not None else None,
            input_receipt_ids=tuple(str(item) for item in value["input_receipt_ids"]),
            invocation_id=str(value["invocation_id"]),
            output_schema_version=str(value.get("output_schema_version", REASONING_OUTPUT_SCHEMA_VERSION)),
            prompt_version=str(value.get("prompt_version", REASONING_PROMPT_VERSION)),
            provider_identity=str(value["provider_identity"]),
            runtime_schema_version=str(value.get("runtime_schema_version", MODEL_RUNTIME_SCHEMA_VERSION)),
            status=value["status"],
            usage=ReasoningUsage.from_dict(value["usage"]),
        )


@dataclass(frozen=True, slots=True)
class ModelInvocationTelemetry:
    invocation_id: str
    provider_identity: str
    latency_ms: int
    framework_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReasoningGraphTelemetry:
    invocation_id: str
    cache_reused: bool
    latency_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
