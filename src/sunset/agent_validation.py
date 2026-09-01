"""Human-gated bridge from bounded agent evidence to the G06 validator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import time
from typing import Any, Callable, Literal, NotRequired, TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from sunset.agent_tool_models import ToolReceipt
from sunset.agent_tools import ToolExecutionContext
from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.git_repository import GitRepository, RepositoryError
from sunset.validation import ValidationConfig, validate_candidate
from sunset.validation_models import ValidationResult


AGENT_VALIDATION_SCHEMA_VERSION = "1"
Decision = Literal["approve", "deny"]
ValidationGateStatus = Literal["awaiting_approval", "denied", "approval_expired", "approval_incompatible", "validated"]
Validator = Callable[..., ValidationResult]


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    """A reviewable, host-derived request; it is not permission to execute."""

    plan_id: str
    candidate_id: str
    collector: str
    repository_head: str
    evidence_receipt_ids: tuple[str, ...]
    validation_config: dict[str, object]
    policy_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "collector": self.collector,
            "evidence_receipt_ids": list(self.evidence_receipt_ids),
            "plan_id": self.plan_id,
            "policy_version": self.policy_version,
            "repository_head": self.repository_head,
            "validation_config": self.validation_config,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ValidationPlan:
        return cls(
            plan_id=str(value["plan_id"]), candidate_id=str(value["candidate_id"]), collector=str(value["collector"]),
            repository_head=str(value["repository_head"]), evidence_receipt_ids=tuple(str(item) for item in value["evidence_receipt_ids"]),
            validation_config=dict(value["validation_config"]), policy_version=str(value.get("policy_version", "1")),
        )


@dataclass(frozen=True, slots=True)
class ValidationApproval:
    """An explicit human decision scoped to one plan and expiry instant."""

    approval_id: str
    plan_id: str
    decision: Decision
    expires_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ValidationApproval:
        return cls(str(value["approval_id"]), str(value["plan_id"]), value["decision"], float(value["expires_at"]))


@dataclass(frozen=True, slots=True)
class AgentValidationError:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AgentValidationResult:
    plan: ValidationPlan
    status: ValidationGateStatus
    approval: ValidationApproval | None
    validation: ValidationResult | None
    errors: tuple[AgentValidationError, ...]
    checkpoint_sequence: int = 0
    schema_version: str = AGENT_VALIDATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval": self.approval.to_dict() if self.approval else None,
            "checkpoint_sequence": self.checkpoint_sequence,
            "errors": [item.to_dict() for item in self.errors],
            "plan": self.plan.to_dict(),
            "schema_version": self.schema_version,
            "status": self.status,
            "validation": self.validation.to_dict() if self.validation else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AgentValidationResult:
        approval = value.get("approval")
        validation = value.get("validation")
        return cls(
            plan=ValidationPlan.from_dict(value["plan"]), status=value["status"],
            approval=ValidationApproval.from_dict(approval) if approval else None,
            validation=ValidationResult.from_dict(validation) if validation else None,
            errors=tuple(AgentValidationError(**item) for item in value["errors"]),
            checkpoint_sequence=int(value.get("checkpoint_sequence", 0)),
            schema_version=str(value.get("schema_version", AGENT_VALIDATION_SCHEMA_VERSION)),
        )


def build_validation_plan(
    context: ToolExecutionContext,
    receipts: tuple[ToolReceipt, ...],
    *,
    validation_config: ValidationConfig = ValidationConfig(),
) -> ValidationPlan:
    """Derive the one G06-compatible candidate/configuration plan from receipts."""

    candidates: set[str] = set()
    for receipt in receipts:
        if receipt.repository_head != context.repository.head:
            continue
        candidate = receipt.result.get("candidate")
        if isinstance(candidate, dict) and isinstance(candidate.get("candidate_id"), str):
            candidates.add(candidate["candidate_id"])
    if len(candidates) != 1:
        raise ValueError("validation plan requires exactly one current candidate provenance receipt")
    candidate_id = next(iter(candidates))
    receipt_ids = tuple(sorted({item.invocation_id for item in receipts}))
    payload = {
        "candidate_id": candidate_id, "collector": context.collector, "evidence_receipt_ids": receipt_ids,
        "repository_head": context.repository.head, "validation_config": validation_config.to_dict(), "policy_version": "1",
    }
    plan_id = f"validation-plan-v1-{hashlib.sha256(_canonical(payload)).hexdigest()[:24]}"
    return ValidationPlan(plan_id=plan_id, **payload)


class _GateState(TypedDict):
    result: dict[str, Any]
    approval: NotRequired[dict[str, Any] | None]


class AgentValidationGate:
    """A LangGraph pause/resume boundary; only a supplied approval can cross it."""

    def __init__(
        self,
        context: ToolExecutionContext,
        receipts: tuple[ToolReceipt, ...],
        *,
        validation_config: ValidationConfig = ValidationConfig(),
        validator: Validator = validate_candidate,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.context = context
        self.plan = build_validation_plan(context, receipts, validation_config=validation_config)
        self.validation_config = validation_config
        self.validator = validator
        self.clock = clock
        graph = StateGraph(_GateState)
        graph.add_node("decide", RunnableLambda(self._decide))
        graph.add_edge(START, "decide")
        graph.add_edge("decide", END)
        self._graph = graph.compile()

    def run(self, approval: ValidationApproval | None = None) -> AgentValidationResult:
        prior = self._load_latest()
        if prior is not None:
            if prior.validation is not None:
                return prior
            if prior.status in {"denied", "approval_expired", "approval_incompatible"}:
                return prior
        initial = prior or AgentValidationResult(self.plan, "awaiting_approval", None, None, ())
        state = self._graph.invoke({"result": initial.to_dict(), "approval": approval.to_dict() if approval else None})
        result = AgentValidationResult.from_dict(state["result"])
        return self._checkpoint(result)

    def _decide(self, state: _GateState) -> dict[str, Any]:
        result = AgentValidationResult.from_dict(state["result"])
        value = state.get("approval")
        if value is None:
            return {"result": result.to_dict()}
        try:
            approval = ValidationApproval.from_dict(value)
        except (KeyError, TypeError, ValueError) as exc:
            return {"result": self._failure("approval_incompatible", "approval_malformed", str(exc)).to_dict()}
        if approval.plan_id != self.plan.plan_id:
            return {"result": self._failure("approval_incompatible", "approval_plan_mismatch", "approval does not match this validation plan", approval).to_dict()}
        if approval.expires_at <= self.clock():
            return {"result": self._failure("approval_expired", "approval_expired", "approval has expired", approval).to_dict()}
        if approval.decision == "deny":
            return {"result": AgentValidationResult(self.plan, "denied", approval, None, ()).to_dict()}
        if approval.decision != "approve":
            return {"result": self._failure("approval_incompatible", "approval_decision_invalid", "approval decision is invalid", approval).to_dict()}
        try:
            current = GitRepository.open(self.context.target)
        except RepositoryError as exc:
            return {"result": self._failure("approval_incompatible", exc.code, exc.message, approval).to_dict()}
        if current.root != self.context.repository.root or current.head != self.plan.repository_head:
            return {"result": self._failure("approval_incompatible", "approval_repository_changed", "repository HEAD changed after plan review", approval).to_dict()}
        validation = self.validator(
            self.context.target, store_path=self.context.store.root, candidate_id=self.plan.candidate_id,
            approved=True, collector=self.plan.collector, config=self.validation_config, artifact_store=self.context.store,
        )
        return {"result": AgentValidationResult(self.plan, "validated", approval, validation, ()).to_dict()}

    def _failure(self, status: ValidationGateStatus, kind: str, message: str, approval: ValidationApproval | None = None) -> AgentValidationResult:
        return AgentValidationResult(self.plan, status, approval, None, (AgentValidationError(kind, message),))

    def _checkpoint(self, result: AgentValidationResult) -> AgentValidationResult:
        result = AgentValidationResult(result.plan, result.status, result.approval, result.validation, result.errors, result.checkpoint_sequence + 1)
        try:
            self.context.store.put_view(f"sunset-agent-validation-v1-{self.plan.plan_id}-{result.checkpoint_sequence:04d}", result.to_json().encode("utf-8"))
        except ArtifactStoreError as exc:
            raise RuntimeError(f"unable to persist validation-gate checkpoint: {exc.code}") from exc
        return result

    def _load_latest(self) -> AgentValidationResult | None:
        prefix = f"sunset-agent-validation-v1-{self.plan.plan_id}-"
        views = self.context.store.list_views(prefix)
        if not views:
            return None
        data = self.context.store.read_view(views[-1])
        return AgentValidationResult.from_dict(json.loads(data)) if data is not None else None
