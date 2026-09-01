"""Versioned domain contracts for Sunset's bounded LangChain tool boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal

from sunset.provenance_models import ArtifactRef


TOOL_CONTRACT_SCHEMA_VERSION = "1"
ToolStatus = Literal["success", "partial", "error", "budget_exhausted"]


@dataclass(frozen=True, slots=True)
class ToolEffect:
    effect_class: str = "local_read_only"
    network_access: bool = False
    target_writes: bool = False
    target_code_execution: bool = False
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolEffect:
        return cls(
            effect_class=str(value["effect_class"]),
            network_access=bool(value["network_access"]),
            target_writes=bool(value["target_writes"]),
            target_code_execution=bool(value["target_code_execution"]),
            approval_required=bool(value["approval_required"]),
        )


@dataclass(frozen=True, slots=True)
class ToolFailure:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolFailure:
        return cls(kind=str(value["kind"]), message=str(value["message"]))


@dataclass(frozen=True, slots=True)
class ToolBudget:
    evidence_bytes_debit: int
    evidence_bytes_remaining: int
    tool_calls_remaining: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolBudget:
        return cls(
            evidence_bytes_debit=int(value["evidence_bytes_debit"]),
            evidence_bytes_remaining=int(value["evidence_bytes_remaining"]),
            tool_calls_remaining=int(value["tool_calls_remaining"]),
        )


@dataclass(frozen=True, slots=True)
class ToolReceipt:
    """Checkpoint-safe tool result; raw observation content is excluded."""

    tool_name: str
    invocation_id: str
    repository_identity_kind: str
    repository_identity_value: str
    repository_head: str
    status: ToolStatus
    result: dict[str, Any]
    evidence: tuple[ArtifactRef, ...]
    errors: tuple[ToolFailure, ...]
    uncertainties: tuple[ToolFailure, ...]
    effect: ToolEffect
    budget: ToolBudget
    schema_version: str = TOOL_CONTRACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget": self.budget.to_dict(),
            "effect": self.effect.to_dict(),
            "errors": [item.to_dict() for item in self.errors],
            "evidence": [item.to_dict() for item in self.evidence],
            "invocation_id": self.invocation_id,
            "repository_head": self.repository_head,
            "repository_identity": {
                "kind": self.repository_identity_kind,
                "value": self.repository_identity_value,
            },
            "result": self.result,
            "schema_version": self.schema_version,
            "status": self.status,
            "tool_name": self.tool_name,
            "uncertainties": [item.to_dict() for item in self.uncertainties],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolReceipt:
        identity = value["repository_identity"]
        return cls(
            budget=ToolBudget.from_dict(value["budget"]),
            effect=ToolEffect.from_dict(value["effect"]),
            errors=tuple(ToolFailure.from_dict(item) for item in value["errors"]),
            evidence=tuple(ArtifactRef.from_dict(item) for item in value["evidence"]),
            invocation_id=str(value["invocation_id"]),
            repository_head=str(value["repository_head"]),
            repository_identity_kind=str(identity["kind"]),
            repository_identity_value=str(identity["value"]),
            result=dict(value["result"]),
            schema_version=str(value.get("schema_version", TOOL_CONTRACT_SCHEMA_VERSION)),
            status=value["status"],
            tool_name=str(value["tool_name"]),
            uncertainties=tuple(ToolFailure.from_dict(item) for item in value["uncertainties"]),
        )


@dataclass(frozen=True, slots=True)
class ToolObservation:
    """Immediate invocation result with optional transient raw excerpt content."""

    receipt: ToolReceipt
    transient_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"receipt": self.receipt.to_dict()}
        if self.transient_content is not None:
            value["transient_content"] = self.transient_content
        return value


@dataclass(frozen=True, slots=True)
class InvocationTelemetry:
    """Non-authoritative runtime measurements excluded from receipt identity."""

    tool_name: str
    invocation_id: str
    cache_reused: bool
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
