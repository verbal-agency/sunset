"""Deterministic, receipt-only dispatch for the G10 local tool registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ValidationError

from sunset.agent_tool_models import ToolReceipt
from sunset.agent_tools import LOCAL_READ_ONLY_EFFECT, BoundToolRegistry


DISPATCH_SCHEMA_VERSION = "1"
DispatchStatus = Literal["completed", "reused", "rejected"]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """A complete request assembled by policy, never a framework tool call."""

    tool_name: str
    tool_input: dict[str, Any]
    origin: Literal["initial", "reasoning"]
    antecedent_reasoning_id: str | None = None

    @property
    def key(self) -> str:
        return _canonical({"input": self.tool_input, "tool_name": self.tool_name})

    def to_dict(self) -> dict[str, Any]:
        return {
            "antecedent_reasoning_id": self.antecedent_reasoning_id,
            "origin": self.origin,
            "tool_input": self.tool_input,
            "tool_name": self.tool_name,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ToolRequest:
        return cls(
            tool_name=str(value["tool_name"]),
            tool_input=dict(value["tool_input"]),
            origin=value["origin"],
            antecedent_reasoning_id=(
                str(value["antecedent_reasoning_id"])
                if value.get("antecedent_reasoning_id") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class DispatchError:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DispatchObservation:
    """Safe dispatch result. Raw excerpt content is intentionally not retained."""

    request: ToolRequest
    status: DispatchStatus
    receipt: ToolReceipt | None = None
    error: DispatchError | None = None
    transient_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "error": self.error.to_dict() if self.error is not None else None,
            "receipt": self.receipt.to_dict() if self.receipt is not None else None,
            "request": self.request.to_dict(),
            "schema_version": DISPATCH_SCHEMA_VERSION,
            "status": self.status,
        }
        # This method is only for immediate inspection. Agent-loop checkpoints
        # use checkpoint_dict(), which cannot include transient content.
        if self.transient_content is not None:
            value["transient_content"] = self.transient_content
        return value

    def checkpoint_dict(self) -> dict[str, Any]:
        return {
            "error": self.error.to_dict() if self.error is not None else None,
            "receipt": self.receipt.to_dict() if self.receipt is not None else None,
            "request": self.request.to_dict(),
            "schema_version": DISPATCH_SCHEMA_VERSION,
            "status": self.status,
        }


class DeterministicToolDispatcher:
    """The only G12 path that invokes a context-bound G10 BaseTool."""

    def __init__(self, registry: BoundToolRegistry, *, allowed_effects: tuple[dict[str, Any], ...] | None = None) -> None:
        self._tools = {tool.name: tool for tool in registry.tools}
        self._allowed_effects = allowed_effects or (LOCAL_READ_ONLY_EFFECT.to_dict(),)

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def dispatch(
        self,
        request: ToolRequest,
        *,
        completed: Mapping[str, ToolReceipt] | None = None,
    ) -> DispatchObservation:
        completed = completed or {}
        if request.origin == "reasoning" and not request.antecedent_reasoning_id:
            return self._rejected(request, "reasoning_antecedent_missing", "non-initial calls require a reasoning result")
        if request.origin == "initial" and request.antecedent_reasoning_id is not None:
            return self._rejected(request, "initial_antecedent_forbidden", "initial calls cannot carry a reasoning antecedent")
        existing = completed.get(request.key)
        if existing is not None:
            return DispatchObservation(request=request, status="reused", receipt=existing)
        tool = self._tools.get(request.tool_name)
        if tool is None:
            return self._rejected(request, "tool_not_allowlisted", "request is outside the bound G10 registry")
        try:
            effect = tool.metadata.get("sunset_effect") if tool.metadata else None
            if effect not in self._allowed_effects:
                return self._rejected(request, "tool_effect_rejected", "tool does not declare an allowed effect")
            schema = tool.args_schema
            if not isinstance(schema, type) or not issubclass(schema, BaseModel):
                return self._rejected(request, "tool_schema_invalid", "tool does not expose a typed input schema")
            normalized = schema.model_validate(request.tool_input).model_dump()
        except (TypeError, ValidationError, ValueError) as exc:
            return self._rejected(request, "tool_input_invalid", str(exc))
        try:
            output = tool.invoke(normalized)
            receipt = ToolReceipt.from_dict(output["receipt"])
        except (KeyError, TypeError, ValueError) as exc:
            return self._rejected(request, "tool_output_invalid", str(exc))
        transient = output.get("transient_content") if isinstance(output, dict) else None
        return DispatchObservation(
            request=request,
            status="completed",
            receipt=receipt,
            transient_content=str(transient) if transient is not None else None,
        )

    @staticmethod
    def _rejected(request: ToolRequest, kind: str, message: str) -> DispatchObservation:
        return DispatchObservation(
            request=request,
            status="rejected",
            error=DispatchError(kind=kind, message=message),
        )
