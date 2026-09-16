"""The live-agent escalation loop: reason, escalate on doubt, run the code, adjudicate.

For each case the loop obtains a heuristic condition status and an agent condition
status. It escalates (requests validation) when the agent is uncertain or the two
disagree. Escalation only runs the disposable-clone validator through an explicit
approval gate — no approval, no run. The validator's outcome is the empirical
ground truth used to adjudicate which reasoner was right; asserted labels are never
used here.

Reasoners, the approval gate, and the validator are all injected. Recorded mode is
simply a reasoner that replays a stored mapping, so the loop runs fully offline and
deterministically with no model or network call. Live mode injects a model-backed
reasoner (G11) and the real G14/G06 validator; the loop code is identical.
"""

from __future__ import annotations

from typing import Callable

from sunset.escalation_loop_models import (
    DEFINITE_STATUSES,
    ConditionStatus,
    EscalationCaseResult,
    EscalationReason,
    EscalationReport,
    ValidationOutcome,
    empirical_status_for,
)

# A reasoner maps a case id to a condition status (recorded replay or live model).
Reasoner = Callable[[str], ConditionStatus]
# The approval gate: given a case id, may a validation experiment run? (fail-closed)
ApprovalGate = Callable[[str], bool]
# The validator: run the disposable-clone experiment, return its outcome class.
EscalationValidator = Callable[[str], ValidationOutcome]


def _deny(_case_id: str) -> bool:
    """Default approval gate denies everything (human approval is required)."""

    return False


def decide_escalation(heuristic_status: ConditionStatus, agent_status: ConditionStatus) -> tuple[bool, EscalationReason]:
    """Escalate when the agent is uncertain or the two definite statuses disagree."""

    if agent_status not in DEFINITE_STATUSES:
        return True, "agent_uncertain"
    if heuristic_status != agent_status:
        return True, "disagreement"
    return False, "agreement"


def run_escalation_case(
    case_id: str,
    heuristic_status: ConditionStatus,
    agent_status: ConditionStatus,
    *,
    validator: EscalationValidator,
    approve: ApprovalGate = _deny,
) -> EscalationCaseResult:
    escalate, reason = decide_escalation(heuristic_status, agent_status)
    # A "disagreement" is two definite claims that conflict, not an agent abstention.
    disagreement = reason == "disagreement"

    approved = False
    outcome: ValidationOutcome | None = None
    if escalate and approve(case_id):
        approved = True
        outcome = validator(case_id)  # only reached after explicit approval

    empirical = empirical_status_for(outcome)
    adjudicated = empirical != "not_adjudicated"
    escalation_resolved = escalate and adjudicated

    # Correctness is only defined for a definite claim against an empirical result.
    agent_correct: bool | None = None
    heuristic_correct: bool | None = None
    if adjudicated:
        if agent_status in DEFINITE_STATUSES:
            agent_correct = agent_status == empirical
        if heuristic_status in DEFINITE_STATUSES:
            heuristic_correct = heuristic_status == empirical

    return EscalationCaseResult(
        case_id=case_id,
        heuristic_status=heuristic_status,
        agent_status=agent_status,
        disagreement=disagreement,
        escalation="escalation_requested" if escalate else "no_escalation",
        escalation_reason=reason,
        approved=approved,
        validation_outcome=outcome,
        empirical_status=empirical,
        escalation_resolved=escalation_resolved,
        agent_correct=agent_correct,
        heuristic_correct=heuristic_correct,
    )


def run_escalation_evaluation(
    case_ids: tuple[str, ...],
    heuristic_reasoner: Reasoner,
    agent_reasoner: Reasoner,
    *,
    validator: EscalationValidator,
    approve: ApprovalGate = _deny,
) -> EscalationReport:
    """Run the loop over a set of cases and produce an empirically-grounded report."""

    results = tuple(
        run_escalation_case(
            case_id,
            heuristic_reasoner(case_id),
            agent_reasoner(case_id),
            validator=validator,
            approve=approve,
        )
        for case_id in case_ids
    )
    return EscalationReport(results)


def recorded_reasoner(mapping: dict[str, ConditionStatus]) -> Reasoner:
    """A deterministic, offline reasoner that replays a stored status mapping."""

    def reason(case_id: str) -> ConditionStatus:
        return mapping.get(case_id, "unknown")

    return reason


def conservative_heuristic_reasoner() -> Reasoner:
    """A deterministic baseline: absent evidence, assume the condition still holds.

    This is the precision-over-recall default (do not treat code as removable
    without evidence). A richer static heuristic is out of scope for the loop; the
    point of the loop is that empirical validation, not this baseline, decides.
    """

    def reason(_case_id: str) -> ConditionStatus:
        return "likely_active"

    return reason


def build_g06_validator(
    resolve: Callable[[str], tuple[object, str]],
    store_path: object,
    *,
    collector: str = "pytest",
    config: object | None = None,
    command_runner: object | None = None,
) -> EscalationValidator:
    """Adapt the G06 disposable-clone validator to the loop's validator interface.

    ``resolve`` maps a case id to ``(target_repo, candidate_id)``. The loop only
    calls this after its approval gate returns True, so the adapter invokes G06
    with ``approved=True``; G06 still creates the disposable clone, removes only the
    one marker, runs the tests, and never mutates the target. Any status outside the
    five outcome classes (e.g. an unexpected ``approval_required``) maps to
    ``inconclusive`` rather than a guessed conclusion.
    """

    from sunset.validation import validate_candidate  # local import: heavy, live-only path

    valid = {"confirmed", "still_failing", "flaky", "environment_error", "inconclusive"}

    def validate(case_id: str) -> ValidationOutcome:
        target, candidate_id = resolve(case_id)
        result = validate_candidate(
            target,  # type: ignore[arg-type]
            store_path=store_path,  # type: ignore[arg-type]
            candidate_id=candidate_id,
            approved=True,
            collector=collector,  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            command_runner=command_runner,  # type: ignore[arg-type]
        )
        return result.status if result.status in valid else "inconclusive"  # type: ignore[return-value]

    return validate


def approval_set(approved_case_ids: frozenset[str] | set[str]) -> ApprovalGate:
    """An approval gate that approves exactly the listed cases (stand-in for G14)."""

    allowed = frozenset(approved_case_ids)

    def approve(case_id: str) -> bool:
        return case_id in allowed

    return approve


__all__ = [
    "ApprovalGate",
    "EscalationValidator",
    "Reasoner",
    "approval_set",
    "build_g06_validator",
    "conservative_heuristic_reasoner",
    "decide_escalation",
    "recorded_reasoner",
    "run_escalation_case",
    "run_escalation_evaluation",
]
