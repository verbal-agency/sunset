"""Explicit, replaceable runtime for one structured Sunset reasoning call."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Annotated, Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sunset.agent_tools import TOOL_NAMES
from sunset.model_runtime_models import (
    MODEL_RUNTIME_SCHEMA_VERSION,
    REASONING_OUTPUT_SCHEMA_VERSION,
    REASONING_PROMPT_VERSION,
    ModelInvocationTelemetry,
    ReasoningBudget,
    ReasoningClaim,
    ReasoningError,
    ReasoningHypothesis,
    ReasoningRequest,
    ReasoningResult,
    ReasoningUsage,
    TransientEvidence,
)


RuntimeMode = Literal["disabled", "recorded", "live"]
_MAX_TASK_CHARS = 1_000
_MAX_TRANSIENT_BYTES = 8_192
_MAX_SUMMARY_CHARS = 1_200
_MAX_CLAIMS = 12
_MAX_QUESTIONS = 12
_MAX_PROPOSED_TOOLS = 8
_FORBIDDEN_RESULT_KEYS = frozenset(
    {"body", "content", "credential", "diff", "history", "patch", "raw", "response", "source", "store", "text", "transcript"}
)


class _RecordedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["supporting", "contradicting", "unknown"]
    summary: str = Field(min_length=1, max_length=_MAX_SUMMARY_CHARS)
    citations: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=8)


class _RecordedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_status: Literal["active", "expired", "unknown"]
    summary: str = Field(min_length=1, max_length=_MAX_SUMMARY_CHARS)
    claims: list[_RecordedClaim] = Field(default_factory=list, max_length=_MAX_CLAIMS)
    open_questions: list[Annotated[str, Field(min_length=1, max_length=_MAX_SUMMARY_CHARS)]] = Field(default_factory=list, max_length=_MAX_QUESTIONS)
    proposed_tools: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=_MAX_PROPOSED_TOOLS)


@dataclass(frozen=True, slots=True)
class ModelRuntimeConfig:
    mode: RuntimeMode = "disabled"
    model_identity: str = "disabled"
    recorded_fixture_path: str | None = None
    max_input_tokens: int = 4_000
    max_output_tokens: int = 1_000
    max_cost_usd: float | None = None
    timeout_seconds: float | None = None
    prompt_version: str = REASONING_PROMPT_VERSION
    output_schema_version: str = REASONING_OUTPUT_SCHEMA_VERSION
    allowed_tool_names: tuple[str, ...] = TOOL_NAMES

    def __post_init__(self) -> None:
        if self.mode not in {"disabled", "recorded", "live"}:
            raise ValueError(f"unsupported model runtime mode: {self.mode}")
        if self.max_input_tokens < 1 or self.max_output_tokens < 1:
            raise ValueError("model token budgets must be positive")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("model cost budget must be non-negative")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("model timeout must be positive")
        if self.mode == "recorded" and self.recorded_fixture_path is None:
            raise ValueError("recorded mode requires a recorded fixture path")
        if self.mode == "live" and self.model_identity in {"", "disabled"}:
            raise ValueError("live mode requires an explicit model identity")
        if not self.allowed_tool_names or len(set(self.allowed_tool_names)) != len(self.allowed_tool_names):
            raise ValueError("allowed tool names must be a non-empty unique tuple")

    def fingerprint(self) -> str:
        value = {
            "fixture_digest": _fixture_digest(self.recorded_fixture_path),
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_cost_usd": self.max_cost_usd,
            "allowed_tool_names": self.allowed_tool_names,
            "mode": self.mode,
            "model_identity": self.model_identity,
            "output_schema_version": self.output_schema_version,
            "prompt_version": self.prompt_version,
            "runtime_schema_version": MODEL_RUNTIME_SCHEMA_VERSION,
            "timeout_seconds": self.timeout_seconds,
        }
        return hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclass(slots=True)
class ModelRuntime:
    """A runtime with an explicit mode and no hidden model/provider selection."""

    config: ModelRuntimeConfig
    model: BaseChatModel | None = None
    telemetry: list[ModelInvocationTelemetry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.config.mode == "live" and self.model is None:
            raise ValueError("live mode requires an injected BaseChatModel")
        if self.config.mode != "live" and self.model is not None:
            raise ValueError("only live mode accepts an injected BaseChatModel")

    @property
    def provider_identity(self) -> str:
        if self.config.mode == "recorded":
            return f"recorded:{_fixture_digest(self.config.recorded_fixture_path)}"
        return self.config.model_identity

    def invocation_id(
        self,
        request: ReasoningRequest,
        transient_evidence: tuple[TransientEvidence, ...] = (),
    ) -> str:
        if not isinstance(request.task, str):
            raise ValueError("reasoning task must be text")
        if any(not isinstance(item.content, str) for item in transient_evidence):
            raise ValueError("transient evidence content must be text")
        value = {
            "config_fingerprint": self.config.fingerprint(),
            "output_schema_version": self.config.output_schema_version,
            "prompt_version": self.config.prompt_version,
            "receipt_ids": [item.invocation_id for item in request.receipts],
            "runtime_schema_version": MODEL_RUNTIME_SCHEMA_VERSION,
            "task": request.task,
            "transient_digests": [
                {"artifact_id": item.artifact_id, "digest": hashlib.sha256(item.content.encode("utf-8")).hexdigest()}
                for item in transient_evidence
            ],
        }
        return hashlib.sha256(_canonical_json(value)).hexdigest()

    def run(
        self,
        request: ReasoningRequest,
        *,
        transient_evidence: tuple[TransientEvidence, ...] = (),
    ) -> ReasoningResult:
        started = time.monotonic_ns()
        try:
            invocation_id = self.invocation_id(request, transient_evidence)
            prompt = assemble_prompt(request, transient_evidence=transient_evidence, allowed_tool_names=self.config.allowed_tool_names)
        except (AttributeError, TypeError, ValueError) as exc:
            result = self._result(
                request,
                _invalid_invocation_id(request),
                "error",
                errors=(ReasoningError("prompt_input_invalid", str(exc)),),
            )
            self._record(result, started)
            return result
        estimated_input = _estimate_tokens(prompt.encode("utf-8"))
        if estimated_input > self.config.max_input_tokens:
            result = self._result(
                request,
                invocation_id,
                "budget_exhausted",
                errors=(ReasoningError("input_token_budget_exhausted", "bounded prompt exceeds input token budget"),),
                input_tokens=estimated_input,
            )
            self._record(result, started)
            return result
        if self.config.mode == "disabled":
            result = self._result(
                request,
                invocation_id,
                "disabled",
                errors=(ReasoningError("model_disabled", "model runtime is explicitly disabled"),),
                input_tokens=estimated_input,
            )
            self._record(result, started)
            return result
        try:
            content, usage = self._recorded_response() if self.config.mode == "recorded" else self._live_response(prompt)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, TimeoutError) as exc:
            result = self._result(
                request,
                invocation_id,
                "error",
                errors=(ReasoningError(_error_kind(exc), str(exc)),),
                input_tokens=estimated_input,
            )
            self._record(result, started)
            return result
        except Exception as exc:  # Provider implementations are untrusted adapters.
            result = self._result(
                request,
                invocation_id,
                "error",
                errors=(ReasoningError("model_provider_failed", str(exc)),),
                input_tokens=estimated_input,
            )
            self._record(result, started)
            return result

        result = self._validate_response(request, invocation_id, content, usage, estimated_input)
        self._record(result, started)
        return result

    async def arun(
        self,
        request: ReasoningRequest,
        *,
        transient_evidence: tuple[TransientEvidence, ...] = (),
    ) -> ReasoningResult:
        if self.config.mode != "live":
            return self.run(request, transient_evidence=transient_evidence)
        started = time.monotonic_ns()
        try:
            invocation_id = self.invocation_id(request, transient_evidence)
            prompt = assemble_prompt(request, transient_evidence=transient_evidence, allowed_tool_names=self.config.allowed_tool_names)
        except (AttributeError, TypeError, ValueError) as exc:
            result = self._result(request, _invalid_invocation_id(request), "error", errors=(ReasoningError("prompt_input_invalid", str(exc)),))
            self._record(result, started)
            return result
        estimated_input = _estimate_tokens(prompt.encode("utf-8"))
        if estimated_input > self.config.max_input_tokens:
            result = self._result(
                request, invocation_id, "budget_exhausted",
                errors=(ReasoningError("input_token_budget_exhausted", "bounded prompt exceeds input token budget"),),
                input_tokens=estimated_input,
            )
            self._record(result, started)
            return result
        try:
            assert self.model is not None
            invocation = self.model.ainvoke(_messages(prompt))
            response = (
                await asyncio.wait_for(invocation, timeout=self.config.timeout_seconds)
                if self.config.timeout_seconds is not None
                else await invocation
            )
            content = _message_content(response)
            usage = _usage_from_message(response)
        except asyncio.CancelledError:
            result = self._result(
                request, invocation_id, "error", errors=(ReasoningError("model_cancelled", "model invocation was cancelled"),), input_tokens=estimated_input,
            )
            self._record(result, started)
            return result
        except (TypeError, ValueError, TimeoutError) as exc:
            result = self._result(request, invocation_id, "error", errors=(ReasoningError(_error_kind(exc), str(exc)),), input_tokens=estimated_input)
            self._record(result, started)
            return result
        except Exception as exc:
            result = self._result(request, invocation_id, "error", errors=(ReasoningError("model_provider_failed", str(exc)),), input_tokens=estimated_input)
            self._record(result, started)
            return result
        result = self._validate_response(request, invocation_id, content, usage, estimated_input)
        self._record(result, started)
        return result

    def _recorded_response(self) -> tuple[str, dict[str, Any] | None]:
        assert self.config.recorded_fixture_path is not None
        fixture = json.loads(Path(self.config.recorded_fixture_path).read_text(encoding="utf-8"))
        if fixture.get("schema_version") != "1":
            raise ValueError("recorded model fixture schema_version must be 1")
        response = fixture["response"]
        return json.dumps(response, ensure_ascii=False, sort_keys=True), fixture.get("usage")

    def _live_response(self, prompt: str) -> tuple[str, dict[str, Any] | None]:
        assert self.model is not None
        started = time.monotonic()
        response = self.model.invoke(_messages(prompt))
        if self.config.timeout_seconds is not None and time.monotonic() - started > self.config.timeout_seconds:
            raise TimeoutError("model invocation exceeded the configured timeout")
        return _message_content(response), _usage_from_message(response)

    def _validate_response(
        self,
        request: ReasoningRequest,
        invocation_id: str,
        content: str,
        usage: dict[str, Any] | None,
        estimated_input: int,
    ) -> ReasoningResult:
        try:
            input_tokens, output_tokens, cost, usage_estimated = _normalized_usage(
                usage,
                estimated_input,
                _estimate_tokens(content.encode("utf-8")),
            )
        except (TypeError, ValueError) as exc:
            return self._result(
                request,
                invocation_id,
                "inconclusive",
                errors=(ReasoningError("provider_usage_invalid", str(exc)),),
                input_tokens=estimated_input,
                output_tokens=_estimate_tokens(content.encode("utf-8")),
            )
        try:
            payload = json.loads(content)
            parsed = _RecordedResponse.model_validate(payload)
            allowed_evidence = {
                reference.artifact_id for receipt in request.receipts for reference in receipt.evidence
            }
            for claim in parsed.claims:
                unknown = set(claim.citations).difference(allowed_evidence)
                if unknown:
                    raise ValueError(f"response cites ungranted evidence: {sorted(unknown)}")
            unknown_tools = set(parsed.proposed_tools).difference(self.config.allowed_tool_names)
            if unknown_tools:
                raise ValueError(f"response proposes unregistered tools: {sorted(unknown_tools)}")
            hypothesis = ReasoningHypothesis(
                assumption_status=parsed.assumption_status,
                summary=parsed.summary,
                claims=tuple(
                    ReasoningClaim(item.kind, item.summary, tuple(item.citations)) for item in parsed.claims
                ),
                open_questions=tuple(parsed.open_questions),
                proposed_tools=tuple(parsed.proposed_tools),
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            return self._result(
                request,
                invocation_id,
                "inconclusive",
                errors=(ReasoningError("model_output_invalid", str(exc)),),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                usage_estimated=usage_estimated,
                cost_usd=cost,
            )
        if input_tokens > self.config.max_input_tokens or output_tokens > self.config.max_output_tokens:
            return self._result(
                request,
                invocation_id,
                "budget_exhausted",
                errors=(ReasoningError("model_token_budget_exhausted", "model usage exceeds the configured token budget"),),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                usage_estimated=usage_estimated,
                cost_usd=cost,
            )
        if self.config.max_cost_usd is not None and cost is not None and cost > self.config.max_cost_usd:
            return self._result(
                request,
                invocation_id,
                "budget_exhausted",
                errors=(ReasoningError("model_cost_budget_exhausted", "model cost exceeds the configured budget"),),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                usage_estimated=usage_estimated,
                cost_usd=cost,
            )
        return self._result(
            request,
            invocation_id,
            "success",
            hypothesis=hypothesis,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usage_estimated=usage_estimated,
            cost_usd=cost,
        )

    def _result(
        self,
        request: ReasoningRequest,
        invocation_id: str,
        status: Literal["success", "inconclusive", "disabled", "error", "budget_exhausted"],
        *,
        hypothesis: ReasoningHypothesis | None = None,
        errors: tuple[ReasoningError, ...] = (),
        input_tokens: int = 0,
        output_tokens: int = 0,
        usage_estimated: bool = True,
        cost_usd: float | None = None,
    ) -> ReasoningResult:
        return ReasoningResult(
            invocation_id=invocation_id,
            provider_identity=self.provider_identity,
            status=status,
            input_receipt_ids=tuple(item.invocation_id for item in request.receipts),
            hypothesis=hypothesis,
            errors=errors,
            usage=ReasoningUsage(input_tokens, output_tokens, usage_estimated, cost_usd),
            budget=ReasoningBudget(
                input_tokens_debit=input_tokens,
                input_tokens_remaining=max(0, self.config.max_input_tokens - input_tokens),
                output_tokens_debit=output_tokens,
                output_tokens_remaining=max(0, self.config.max_output_tokens - output_tokens),
            ),
            prompt_version=self.config.prompt_version,
            output_schema_version=self.config.output_schema_version,
        )

    def _record(self, result: ReasoningResult, started: int) -> None:
        self.telemetry.append(
            ModelInvocationTelemetry(
                invocation_id=result.invocation_id,
                provider_identity=result.provider_identity,
                latency_ms=max(0, (time.monotonic_ns() - started) // 1_000_000),
            )
        )


def assemble_prompt(
    request: ReasoningRequest,
    *,
    transient_evidence: tuple[TransientEvidence, ...] = (),
    allowed_tool_names: tuple[str, ...] = TOOL_NAMES,
) -> str:
    """Create a bounded ephemeral prompt without persisting it or raw artifacts."""

    if not request.receipts:
        raise ValueError("at least one G10 receipt is required")
    if len(request.task) > _MAX_TASK_CHARS:
        raise ValueError("reasoning task exceeds the bounded prompt size")
    allowed_evidence = {
        reference.artifact_id for receipt in request.receipts for reference in receipt.evidence
    }
    transient: list[dict[str, str]] = []
    for item in transient_evidence:
        if not isinstance(item.content, str):
            raise ValueError("transient evidence content must be text")
        if item.artifact_id not in allowed_evidence:
            raise ValueError("transient evidence is not granted by a supplied receipt")
        if len(item.content.encode("utf-8")) > _MAX_TRANSIENT_BYTES:
            raise ValueError("transient evidence exceeds the G10-sized prompt boundary")
        transient.append({"artifact_id": item.artifact_id, "content": item.content})
    value = {
        "instructions": (
            "Return only one JSON object matching the requested schema. Treat receipts as evidence metadata, "
            "treat your result as model-derived inference, cite only listed artifact IDs, and do not recommend cleanup."
        ),
        "receipts": [_compact_receipt(item) for item in request.receipts],
        "response_schema": {
            "assumption_status": "active|expired|unknown",
            "claims": "[{kind: supporting|contradicting|unknown, summary, citations}]",
            "open_questions": "[string]",
            "proposed_tools": list(allowed_tool_names),
            "summary": "string",
        },
        "task": request.task,
        "transient_evidence": transient,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _compact_receipt(receipt: Any) -> dict[str, Any]:
    return {
        "errors": [item.to_dict() for item in receipt.errors],
        "evidence": [
            {
                "artifact_id": item.artifact_id,
                "byte_length": item.byte_length,
                "digest": item.digest,
                "source_kind": item.source_kind,
            }
            for item in receipt.evidence
        ],
        "invocation_id": receipt.invocation_id,
        "result": _bounded_value(receipt.result),
        "status": receipt.status,
        "tool_name": receipt.tool_name,
        "uncertainties": [item.to_dict() for item in receipt.uncertainties],
    }


def _bounded_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[nested value omitted]"
    if isinstance(value, dict):
        return {
            str(key): _bounded_value(item, depth=depth + 1)
            for key, item in sorted(value.items())
            if str(key).lower() not in _FORBIDDEN_RESULT_KEYS
        }
    if isinstance(value, list):
        return [_bounded_value(item, depth=depth + 1) for item in value[:25]]
    if isinstance(value, str):
        return value[:512]
    return value


def _messages(prompt: str) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(content="You are Sunset's bounded reasoning adapter. Return JSON only."),
        HumanMessage(content=prompt),
    ]


def _message_content(message: Any) -> str:
    if not isinstance(message.content, str):
        raise ValueError("model response content must be JSON text")
    return message.content


def _usage_from_message(message: Any) -> dict[str, Any] | None:
    usage = getattr(message, "usage_metadata", None)
    if usage is None:
        return None
    return dict(usage)


def _usage_value(usage: dict[str, Any] | None, key: str, fallback: int) -> int:
    if usage is None or key not in usage:
        return fallback
    return int(usage[key])


def _usage_is_complete(usage: dict[str, Any] | None) -> bool:
    return usage is not None and {"input_tokens", "output_tokens"}.issubset(usage)


def _normalized_usage(
    usage: dict[str, Any] | None,
    fallback_input: int,
    fallback_output: int,
) -> tuple[int, int, float | None, bool]:
    input_tokens = _usage_value(usage, "input_tokens", fallback_input)
    output_tokens = _usage_value(usage, "output_tokens", fallback_output)
    cost = _cost_value(usage)
    if input_tokens < 0 or output_tokens < 0 or (cost is not None and cost < 0):
        raise ValueError("provider usage values must be non-negative")
    return input_tokens, output_tokens, cost, not _usage_is_complete(usage)


def _cost_value(usage: dict[str, Any] | None) -> float | None:
    if usage is None or usage.get("cost_usd") is None:
        return None
    return float(usage["cost_usd"])


def _estimate_tokens(data: bytes) -> int:
    return math.ceil(len(data) / 4)


def _fixture_digest(path: str | None) -> str:
    if path is None:
        return "none"
    try:
        return hashlib.sha256(Path(path).expanduser().read_bytes()).hexdigest()
    except OSError:
        return f"unavailable:{Path(path).expanduser()}"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _invalid_invocation_id(request: ReasoningRequest) -> str:
    value = {"receipt_count": len(request.receipts), "task_type": type(request.task).__name__}
    return f"invalid-{hashlib.sha256(_canonical_json(value)).hexdigest()}"


def _error_kind(error: Exception) -> str:
    if isinstance(error, json.JSONDecodeError):
        return "recorded_response_invalid"
    if isinstance(error, TimeoutError):
        return "model_timeout"
    if isinstance(error, OSError):
        return "recorded_fixture_unavailable"
    return "model_provider_invalid"
