"""Framework-independent, checkpoint-safe G12 run contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal, Mapping

from sunset.agent_dispatch import DispatchError, ToolRequest
from sunset.agent_tool_models import ToolReceipt
from sunset.model_runtime_models import ReasoningResult


AGENT_LOOP_SCHEMA_VERSION = "1"
TerminalReason = Literal[
    "completed", "insufficient_evidence", "tool_error", "model_error",
    "tool_budget_exhausted", "iteration_budget_exhausted", "wall_time_exhausted", "interrupted",
]


@dataclass(frozen=True, slots=True)
class AgentLoopError:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AgentLoopError:
        return cls(kind=str(value["kind"]), message=str(value["message"]))


@dataclass(frozen=True, slots=True)
class AgentCallRecord:
    request: ToolRequest
    status: Literal["completed", "reused", "rejected"]
    receipt_id: str | None
    error: DispatchError | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error.to_dict() if self.error is not None else None,
            "receipt_id": self.receipt_id,
            "request": self.request.to_dict(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AgentCallRecord:
        error = value.get("error")
        return cls(
            request=ToolRequest.from_dict(value["request"]),
            status=value["status"],
            receipt_id=str(value["receipt_id"]) if value.get("receipt_id") is not None else None,
            error=DispatchError(**error) if error is not None else None,
        )


@dataclass(frozen=True, slots=True)
class AgentTraceEvent:
    kind: Literal["tool", "reasoning", "terminal"]
    reference_id: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AgentTraceEvent:
        return cls(kind=value["kind"], reference_id=value.get("reference_id"), detail=str(value["detail"]))


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    run_id: str
    repository_identity: dict[str, str]
    repository_head: str
    context_policy_fingerprint: str
    config_fingerprint: str
    initial_grant_scope: tuple[str, ...]
    initial_tool_calls_used: int
    initial_evidence_bytes_used: int
    receipts: tuple[ToolReceipt, ...]
    reasoning: tuple[ReasoningResult, ...]
    call_ledger: tuple[AgentCallRecord, ...]
    trace: tuple[AgentTraceEvent, ...]
    errors: tuple[AgentLoopError, ...]
    iterations: int
    checkpoint_sequence: int
    terminal_reason: TerminalReason | None
    pending_request: ToolRequest | None = None
    schema_version: str = AGENT_LOOP_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_ledger": [item.to_dict() for item in self.call_ledger],
            "config_fingerprint": self.config_fingerprint,
            "context_policy_fingerprint": self.context_policy_fingerprint,
            "errors": [item.to_dict() for item in self.errors],
            "iterations": self.iterations,
            "initial_evidence_bytes_used": self.initial_evidence_bytes_used,
            "initial_grant_scope": list(self.initial_grant_scope),
            "initial_tool_calls_used": self.initial_tool_calls_used,
            "checkpoint_sequence": self.checkpoint_sequence,
            "pending_request": self.pending_request.to_dict() if self.pending_request is not None else None,
            "reasoning": [item.to_dict() for item in self.reasoning],
            "receipts": [item.to_dict() for item in self.receipts],
            "repository_head": self.repository_head,
            "repository_identity": self.repository_identity,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "terminal_reason": self.terminal_reason,
            "trace": [item.to_dict() for item in self.trace],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AgentRunResult:
        pending = value.get("pending_request")
        return cls(
            run_id=str(value["run_id"]),
            repository_identity=dict(value["repository_identity"]),
            repository_head=str(value["repository_head"]),
            context_policy_fingerprint=str(value["context_policy_fingerprint"]),
            config_fingerprint=str(value["config_fingerprint"]),
            initial_grant_scope=tuple(str(item) for item in value.get("initial_grant_scope", [])),
            initial_tool_calls_used=int(value.get("initial_tool_calls_used", 0)),
            initial_evidence_bytes_used=int(value.get("initial_evidence_bytes_used", 0)),
            receipts=tuple(ToolReceipt.from_dict(item) for item in value["receipts"]),
            reasoning=tuple(ReasoningResult.from_dict(item) for item in value["reasoning"]),
            call_ledger=tuple(AgentCallRecord.from_dict(item) for item in value["call_ledger"]),
            trace=tuple(AgentTraceEvent.from_dict(item) for item in value["trace"]),
            errors=tuple(AgentLoopError.from_dict(item) for item in value["errors"]),
            iterations=int(value["iterations"]),
            checkpoint_sequence=int(value.get("checkpoint_sequence", 0)),
            terminal_reason=value.get("terminal_reason"),
            pending_request=ToolRequest.from_dict(pending) if pending is not None else None,
            schema_version=str(value.get("schema_version", AGENT_LOOP_SCHEMA_VERSION)),
        )
