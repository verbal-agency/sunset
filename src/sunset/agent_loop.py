"""A bounded LangGraph local-evidence loop with explicit policy transitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import time
from typing import Any, Callable, Literal, TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from sunset.agent_dispatch import DeterministicToolDispatcher, ToolRequest
from sunset.agent_loop_models import AgentCallRecord, AgentLoopError, AgentRunResult, AgentTraceEvent
from sunset.agent_tools import DISCOVER_TOOL, EXCERPT_TOOL, LOCAL_READ_ONLY_EFFECT, PROVENANCE_TOOL, ToolExecutionContext, create_tool_registry
from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.external_agent_tools import EXTERNAL_TOOL_NAMES, ExternalEvidenceContext, create_external_tool_registry
from sunset.model_runtime import ModelRuntime
from sunset.model_runtime_models import ReasoningRequest, ReasoningResult, TransientEvidence
from sunset.reasoning_graph import ReasoningGraph


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


@dataclass(frozen=True, slots=True)
class AgentLoopConfig:
    mode: Literal["heuristic", "recorded", "live"] = "heuristic"
    max_iterations: int = 12
    max_tool_calls: int = 12
    max_evidence_bytes: int = 65_536
    max_wall_time_seconds: float = 30.0
    task: str = "Identify the next useful local evidence request conservatively."
    # Explicit test/host interruption boundary; it has no automatic retry semantics.
    interrupt_after_steps: int | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"heuristic", "recorded", "live"}:
            raise ValueError(f"unsupported agent loop mode: {self.mode}")
        if self.max_iterations < 1 or self.max_tool_calls < 1 or self.max_evidence_bytes < 0:
            raise ValueError("agent loop budgets must be non-negative and iterations/calls positive")
        if self.max_wall_time_seconds <= 0:
            raise ValueError("agent wall-time budget must be positive")

    def fingerprint(self, runtime: ModelRuntime | None) -> str:
        return hashlib.sha256(_canonical({
            "mode": self.mode,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "max_evidence_bytes": self.max_evidence_bytes,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "task": self.task,
            "runtime": runtime.config.fingerprint() if runtime is not None else None,
            "schema_version": "1",
        })).hexdigest()


class _GraphState(TypedDict):
    result: dict[str, Any]


class LocalEvidenceAgentLoop:
    """One-action-at-a-time graph. Policy, not the model, owns control flow."""

    def __init__(
        self,
        context: ToolExecutionContext,
        *,
        config: AgentLoopConfig = AgentLoopConfig(),
        runtime: ModelRuntime | None = None,
        external_context: ExternalEvidenceContext | None = None,
        seed_receipts: tuple[Any, ...] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if config.mode == "heuristic" and runtime is not None:
            raise ValueError("heuristic mode must not construct a model runtime")
        if config.mode != "heuristic" and runtime is None:
            raise ValueError("recorded and live modes require an injected model runtime")
        if runtime is not None and runtime.config.mode != config.mode:
            raise ValueError("agent loop mode must match the injected model runtime mode")
        self.context = context
        self.config = config
        self.runtime = runtime
        self.external_context = external_context
        self.seed_receipts = tuple(seed_receipts)
        if external_context is not None and external_context.local is not context:
            raise ValueError("external evidence must use the same trusted local context")
        if external_context is not None and runtime is not None:
            missing = set(EXTERNAL_TOOL_NAMES).difference(runtime.config.allowed_tool_names)
            if missing:
                raise ValueError("model runtime must explicitly allow configured external tools")
        self.clock = clock
        self.dispatcher = DeterministicToolDispatcher(create_tool_registry(context))
        self.external_dispatcher = (
            DeterministicToolDispatcher(
                create_external_tool_registry(external_context),
                allowed_effects=(external_context.effect.to_dict(),),
            ) if external_context is not None else None
        )
        self.reasoning_graph = ReasoningGraph(runtime, context.store) if runtime is not None else None
        graph = StateGraph(_GraphState)
        graph.add_node("advance", RunnableLambda(self._advance))
        graph.add_edge(START, "advance")
        graph.add_edge("advance", END)
        self._graph = graph.compile()

    def run(self, *, run_id: str | None = None) -> AgentRunResult:
        run_id = run_id or self._new_run_id()
        result = self._load_latest(run_id)
        if result is None:
            result = self._new_result(run_id)
        else:
            self._assert_compatible(result)
            if result.terminal_reason == "interrupted":
                result = replace(result, terminal_reason=None)
        started = self.clock()
        while result.terminal_reason is None:
            if result.iterations >= self.config.max_iterations:
                result = self._terminal(result, "iteration_budget_exhausted", "iteration budget is exhausted")
            elif self.clock() - started >= self.config.max_wall_time_seconds:
                result = self._terminal(result, "wall_time_exhausted", "wall-time budget is exhausted")
            else:
                result = AgentRunResult.from_dict(self._graph.invoke({"result": result.to_dict()})["result"])
                if self.config.interrupt_after_steps is not None and result.iterations >= self.config.interrupt_after_steps and result.terminal_reason is None:
                    result = self._terminal(result, "interrupted", "host interrupted the bounded run")
            result = self._checkpoint(result)
        return result

    def _advance(self, state: _GraphState) -> dict[str, Any]:
        result = AgentRunResult.from_dict(state["result"])
        if result.pending_request is not None:
            return {"result": self._dispatch_pending(result).to_dict()}
        if not result.receipts:
            initial = ToolRequest(DISCOVER_TOOL, {}, "initial")
            return {"result": self._dispatch(result, initial).to_dict()}
        if self.config.mode == "heuristic":
            next_request = self._heuristic_request(result)
            if next_request is None:
                return {"result": self._terminal(result, "completed", "heuristic local path is complete").to_dict()}
            return {"result": self._dispatch(result, next_request).to_dict()}
        return {"result": self._reason(result).to_dict()}

    def _reason(self, result: AgentRunResult) -> AgentRunResult:
        assert self.reasoning_graph is not None
        reasoning = self.reasoning_graph.run(ReasoningRequest(receipts=result.receipts, task=self.config.task))
        updated = replace(
            result,
            reasoning=(*result.reasoning, reasoning),
            iterations=result.iterations + 1,
            trace=(*result.trace, AgentTraceEvent("reasoning", reasoning.invocation_id, reasoning.status)),
        )
        if reasoning.status in {"error", "disabled", "budget_exhausted"}:
            return self._terminal(updated, "model_error", f"model reasoning ended with {reasoning.status}")
        if reasoning.status != "success" or reasoning.hypothesis is None:
            return self._terminal(updated, "insufficient_evidence", "model produced no usable hypothesis")
        request = self._request_from_hypothesis(updated, reasoning)
        if request is None:
            reason = "completed" if not reasoning.hypothesis.open_questions else "insufficient_evidence"
            return self._terminal(updated, reason, "no proposed local request can be safely resolved")
        return replace(updated, pending_request=request)

    def _dispatch_pending(self, result: AgentRunResult) -> AgentRunResult:
        assert result.pending_request is not None
        return self._dispatch(replace(result, pending_request=None), result.pending_request)

    def _dispatch(self, result: AgentRunResult, request: ToolRequest) -> AgentRunResult:
        completed = {
            record.request.key: receipt
            for record in result.call_ledger
            if record.status == "completed" and record.receipt_id is not None
            for receipt in result.receipts
            if receipt.invocation_id == record.receipt_id
        }
        tool_calls = sum(1 for record in result.call_ledger if record.status == "completed")
        evidence_bytes = sum(receipt.budget.evidence_bytes_debit for receipt in result.receipts)
        is_external = request.tool_name in EXTERNAL_TOOL_NAMES
        if tool_calls >= self.config.max_tool_calls:
            return self._terminal(result, "tool_budget_exhausted", "aggregate tool-call budget is exhausted")
        if evidence_bytes >= self.config.max_evidence_bytes:
            return self._terminal(result, "tool_budget_exhausted", "aggregate evidence-byte budget is exhausted")
        if is_external:
            if self.external_context is None or self.external_dispatcher is None:
                return self._terminal(result, "tool_error", "external tool is not configured")
            if self.external_context.requests_remaining == 0 or self.external_context.response_bytes_remaining == 0:
                return self._terminal(result, "tool_budget_exhausted", "external provider budget is exhausted")
            observation = self.external_dispatcher.dispatch(request, completed=completed)
        else:
            if self.context.tool_calls_remaining == 0 or self.context.evidence_bytes_remaining == 0:
                return self._terminal(result, "tool_budget_exhausted", "G10 local tool budget is exhausted")
            observation = self.dispatcher.dispatch(request, completed=completed)
        record = AgentCallRecord(request, observation.status, observation.receipt.invocation_id if observation.receipt else None, observation.error)
        updated = replace(
            result,
            call_ledger=(*result.call_ledger, record),
            iterations=result.iterations + 1,
            trace=(*result.trace, AgentTraceEvent("tool", observation.receipt.invocation_id if observation.receipt else None, observation.status)),
        )
        if observation.status == "rejected":
            return self._terminal(updated, "tool_error", observation.error.message if observation.error else "tool request rejected")
        if observation.status == "reused":
            return updated
        assert observation.receipt is not None
        updated = replace(updated, receipts=(*updated.receipts, observation.receipt))
        if observation.receipt.status == "budget_exhausted":
            return self._terminal(updated, "tool_budget_exhausted", "G10 tool budget is exhausted")
        if observation.receipt.status == "error":
            return self._terminal(updated, "tool_error", "bounded tool returned a structured error")
        return updated

    def _heuristic_request(self, result: AgentRunResult) -> ToolRequest | None:
        if not any(receipt.tool_name == PROVENANCE_TOOL for receipt in result.receipts):
            candidate_id = self._first_candidate_id(result)
            if candidate_id is not None:
                return ToolRequest(PROVENANCE_TOOL, {"candidate_id": candidate_id}, "reasoning", "heuristic-policy-v1")
        return None

    def _request_from_hypothesis(self, result: AgentRunResult, reasoning: ReasoningResult) -> ToolRequest | None:
        assert reasoning.hypothesis is not None
        for tool_name in reasoning.hypothesis.proposed_tools:
            if tool_name == DISCOVER_TOOL and not result.receipts:
                return ToolRequest(tool_name, {}, "reasoning", reasoning.invocation_id)
            if tool_name == PROVENANCE_TOOL:
                candidate_id = self._first_candidate_id(result)
                if candidate_id is not None and not self._already_completed(result, tool_name, {"candidate_id": candidate_id}):
                    return ToolRequest(tool_name, {"candidate_id": candidate_id}, "reasoning", reasoning.invocation_id)
            if tool_name == EXCERPT_TOOL:
                artifact_id = self._first_unread_grant(result)
                if artifact_id is not None:
                    request = {"artifact_id": artifact_id, "offset": 0, "length": min(512, self.context.max_excerpt_bytes)}
                    if not self._already_completed(result, tool_name, request):
                        return ToolRequest(tool_name, request, "reasoning", reasoning.invocation_id)
            if tool_name in EXTERNAL_TOOL_NAMES and self.external_context is not None:
                reference_id = self._first_unresolved_external_reference(result)
                if reference_id is not None:
                    return ToolRequest(tool_name, {"reference_id": reference_id}, "reasoning", reasoning.invocation_id)
        return None

    @staticmethod
    def _first_candidate_id(result: AgentRunResult) -> str | None:
        for receipt in result.receipts:
            if receipt.tool_name != DISCOVER_TOOL:
                continue
            candidates = receipt.result.get("candidates", [])
            identifiers = sorted(str(item["candidate_id"]) for item in candidates if isinstance(item, dict) and "candidate_id" in item)
            if identifiers:
                return identifiers[0]
        return None

    def _first_unread_grant(self, result: AgentRunResult) -> str | None:
        read = {
            str(receipt.result.get("artifact_id"))
            for receipt in result.receipts if receipt.tool_name == EXCERPT_TOOL
        }
        return next((artifact_id for artifact_id in sorted(self.context.granted_artifacts) if artifact_id not in read), None)

    def _first_unresolved_external_reference(self, result: AgentRunResult) -> str | None:
        assert self.external_context is not None
        completed = {
            str(receipt.result.get("reference", {}).get("reference_id"))
            for receipt in result.receipts if receipt.tool_name in EXTERNAL_TOOL_NAMES
        }
        return next((reference_id for reference_id in sorted(self.external_context.references) if reference_id not in completed), None)

    @staticmethod
    def _already_completed(result: AgentRunResult, tool_name: str, tool_input: dict[str, Any]) -> bool:
        request = ToolRequest(tool_name, tool_input, "reasoning", "identity")
        return any(record.status == "completed" and record.request.key == request.key for record in result.call_ledger)

    def _terminal(self, result: AgentRunResult, reason: str, detail: str) -> AgentRunResult:
        errors = result.errors
        if reason not in {"completed", "insufficient_evidence"}:
            errors = (*errors, AgentLoopError(reason, detail))
        return replace(
            result,
            terminal_reason=reason,
            errors=errors,
            trace=(*result.trace, AgentTraceEvent("terminal", None, detail)),
        )

    def _new_run_id(self) -> str:
        identity_kind, identity_value = self.context.repository_identity
        value = {
            "config": self.config.fingerprint(self.runtime),
            "context_policy": self._context_policy_fingerprint(),
            "ledger": {"evidence_bytes_used": self.context.evidence_bytes_used, "tool_calls_used": self.context.tool_calls_used},
            "repository": {"head": self.context.repository.head, "identity": [identity_kind, identity_value]},
            "schema_version": "1",
        }
        return hashlib.sha256(_canonical(value)).hexdigest()

    def _new_result(self, run_id: str) -> AgentRunResult:
        kind, value = self.context.repository_identity
        return AgentRunResult(
            run_id=run_id,
            repository_identity={"kind": kind, "value": value},
            repository_head=self.context.repository.head,
            context_policy_fingerprint=self._context_policy_fingerprint(),
            config_fingerprint=self.config.fingerprint(self.runtime),
            initial_grant_scope=tuple(sorted(self.context.granted_artifacts)),
            initial_tool_calls_used=self.context.tool_calls_used,
            initial_evidence_bytes_used=self.context.evidence_bytes_used,
            receipts=self.seed_receipts, reasoning=(), call_ledger=(), trace=(), errors=(), iterations=0,
            checkpoint_sequence=0, terminal_reason=None,
        )

    def _assert_compatible(self, result: AgentRunResult) -> None:
        kind, value = self.context.repository_identity
        if result.repository_identity != {"kind": kind, "value": value} or result.repository_head != self.context.repository.head:
            raise ValueError("checkpoint is incompatible with the bound repository identity or HEAD")
        if result.context_policy_fingerprint != self._context_policy_fingerprint():
            raise ValueError("checkpoint is incompatible with the bound context policy")
        if result.config_fingerprint != self.config.fingerprint(self.runtime):
            raise ValueError("checkpoint is incompatible with the model or loop configuration")
        expected_calls = result.initial_tool_calls_used + sum(1 for record in result.call_ledger if record.status == "completed")
        expected_bytes = result.initial_evidence_bytes_used + sum(receipt.budget.evidence_bytes_debit for receipt in result.receipts)
        if self.context.tool_calls_used not in {result.initial_tool_calls_used, expected_calls} or self.context.evidence_bytes_used not in {result.initial_evidence_bytes_used, expected_bytes}:
            raise ValueError("checkpoint is incompatible with the current G10 budget ledger")
        expected_grants = set(result.initial_grant_scope).union(
            reference.artifact_id for receipt in result.receipts
            if receipt.effect == LOCAL_READ_ONLY_EFFECT
            for reference in receipt.evidence
        )
        actual_grants = set(self.context.granted_artifacts)
        if actual_grants != set(result.initial_grant_scope) and actual_grants != expected_grants:
            raise ValueError("checkpoint is incompatible with the current evidence grant scope")
        for receipt in result.receipts:
            if receipt.effect != LOCAL_READ_ONLY_EFFECT:
                continue
            for reference in receipt.evidence:
                self.context.granted_artifacts.setdefault(reference.artifact_id, reference)

    def _context_policy_fingerprint(self) -> str:
        value = {"local": self.context.policy_fingerprint(), "external": self.external_context.policy_fingerprint() if self.external_context else None}
        return hashlib.sha256(_canonical(value)).hexdigest()

    def _checkpoint(self, result: AgentRunResult) -> AgentRunResult:
        result = replace(result, checkpoint_sequence=result.checkpoint_sequence + 1)
        view_id = f"sunset-agent-loop-v1-{result.run_id}-{result.checkpoint_sequence:04d}"
        try:
            self.context.store.put_view(view_id, result.to_json().encode("utf-8"))
        except ArtifactStoreError as exc:
            raise RuntimeError(f"unable to persist agent checkpoint: {exc.code}") from exc
        return result

    def _load_latest(self, run_id: str) -> AgentRunResult | None:
        prefix = f"sunset-agent-loop-v1-{run_id}-"
        views = self.context.store.list_views(prefix)
        if not views:
            return None
        data = self.context.store.read_view(views[-1])
        if data is None:
            return None
        return AgentRunResult.from_dict(json.loads(data))
