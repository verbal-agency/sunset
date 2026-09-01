"""A single checkpoint-safe LangGraph node over the G11 model runtime."""

from __future__ import annotations

import json
import time
from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.runnables import RunnableLambda

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.model_runtime import ModelRuntime
from sunset.model_runtime_models import (
    ReasoningError,
    ReasoningGraphTelemetry,
    ReasoningRequest,
    ReasoningResult,
    TransientEvidence,
)


class _ReasoningState(TypedDict):
    invocation_id: str
    request: dict[str, Any]
    result: NotRequired[dict[str, Any]]


class ReasoningGraph:
    """Persist only a safe request/result pair; keep transient evidence ephemeral."""

    def __init__(self, runtime: ModelRuntime, store: ArtifactStore) -> None:
        self.runtime = runtime
        self.store = store
        self._transient_by_invocation: dict[str, tuple[TransientEvidence, ...]] = {}
        self.telemetry: list[ReasoningGraphTelemetry] = []
        graph = StateGraph(_ReasoningState)
        graph.add_node("reason", RunnableLambda(self._reason, afunc=self._areason))
        graph.add_edge(START, "reason")
        graph.add_edge("reason", END)
        self._graph = graph.compile()

    def run(
        self,
        request: ReasoningRequest,
        *,
        transient_evidence: tuple[TransientEvidence, ...] = (),
    ) -> ReasoningResult:
        started = time.monotonic_ns()
        invocation_id = self.runtime.invocation_id(request, transient_evidence)
        cached = self._load(invocation_id)
        if cached is not None:
            self._record(invocation_id, started, cache_reused=True)
            return cached
        self._transient_by_invocation[invocation_id] = transient_evidence
        try:
            final_state = self._graph.invoke(
                {"invocation_id": invocation_id, "request": request.to_dict()}
            )
        finally:
            self._transient_by_invocation.pop(invocation_id, None)
        result = ReasoningResult.from_dict(final_state["result"])
        try:
            self.store.put_view(self._view_id(invocation_id), result.to_json().encode("utf-8"))
        except ArtifactStoreError as exc:
            result = _cache_failure(result, exc)
        self._record(invocation_id, started, cache_reused=False)
        return result

    async def arun(
        self,
        request: ReasoningRequest,
        *,
        transient_evidence: tuple[TransientEvidence, ...] = (),
    ) -> ReasoningResult:
        started = time.monotonic_ns()
        invocation_id = self.runtime.invocation_id(request, transient_evidence)
        cached = self._load(invocation_id)
        if cached is not None:
            self._record(invocation_id, started, cache_reused=True)
            return cached
        self._transient_by_invocation[invocation_id] = transient_evidence
        try:
            final_state = await self._graph.ainvoke(
                {"invocation_id": invocation_id, "request": request.to_dict()}
            )
        finally:
            self._transient_by_invocation.pop(invocation_id, None)
        result = ReasoningResult.from_dict(final_state["result"])
        try:
            self.store.put_view(self._view_id(invocation_id), result.to_json().encode("utf-8"))
        except ArtifactStoreError as exc:
            result = _cache_failure(result, exc)
        self._record(invocation_id, started, cache_reused=False)
        return result

    def _reason(self, state: _ReasoningState) -> dict[str, Any]:
        request = ReasoningRequest.from_dict(state["request"])
        transient = self._transient_by_invocation.get(state["invocation_id"], ())
        return {"result": self.runtime.run(request, transient_evidence=transient).to_dict()}

    async def _areason(self, state: _ReasoningState) -> dict[str, Any]:
        request = ReasoningRequest.from_dict(state["request"])
        transient = self._transient_by_invocation.get(state["invocation_id"], ())
        return {"result": (await self.runtime.arun(request, transient_evidence=transient)).to_dict()}

    def _view_id(self, invocation_id: str) -> str:
        return f"sunset-reasoning-v1-{invocation_id}"

    def _load(self, invocation_id: str) -> ReasoningResult | None:
        try:
            data = self.store.read_view(self._view_id(invocation_id))
        except OSError:
            return None
        if data is None:
            return None
        try:
            return ReasoningResult.from_dict(json.loads(data))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def _record(self, invocation_id: str, started: int, *, cache_reused: bool) -> None:
        self.telemetry.append(
            ReasoningGraphTelemetry(
                invocation_id=invocation_id,
                cache_reused=cache_reused,
                latency_ms=max(0, (time.monotonic_ns() - started) // 1_000_000),
            )
        )


def _cache_failure(result: ReasoningResult, error: ArtifactStoreError) -> ReasoningResult:
    return ReasoningResult(
        invocation_id=result.invocation_id,
        provider_identity=result.provider_identity,
        status="error",
        input_receipt_ids=result.input_receipt_ids,
        hypothesis=result.hypothesis,
        errors=(*result.errors, ReasoningError(error.code, error.message)),
        usage=result.usage,
        budget=result.budget,
        prompt_version=result.prompt_version,
        runtime_schema_version=result.runtime_schema_version,
        output_schema_version=result.output_schema_version,
    )
