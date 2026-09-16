"""Contracts for the live-agent escalation loop and empirical adjudication.

The loop compares two condition hypotheses per case — one from a deterministic
heuristic, one from an agent reasoner — and escalates to empirical validation when
the agent is uncertain or the two disagree. The **disposable-clone validation
result is the adjudicating ground truth**; asserted (reviewer) labels are not used
here. See docs/goals/G30-live-agentic-escalation-evaluation.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ESCALATION_SCHEMA_VERSION = "1"

# Empirically meaningful condition statuses a reasoner can assert.
ConditionStatus = Literal["likely_active", "likely_expired", "unknown", "contradictory"]
# Definite claims (the two an empirical result can confirm or refute).
DEFINITE_STATUSES: frozenset[str] = frozenset({"likely_active", "likely_expired"})

# G06 disposable-clone outcome classes.
ValidationOutcome = Literal["confirmed", "still_failing", "flaky", "environment_error", "inconclusive"]

EscalationDecision = Literal["no_escalation", "escalation_requested"]
EscalationReason = Literal["agreement", "agent_uncertain", "disagreement"]
# The empirical ground truth derived from running the code (or none).
EmpiricalStatus = Literal["likely_active", "likely_expired", "not_adjudicated"]

# Map a disposable-clone outcome to the empirical condition it establishes in scope.
# confirmed  = test passes without the marker -> the disabling condition is gone.
# still_failing = test still fails without the marker -> the condition still holds.
# everything else yields no empirical conclusion.
_OUTCOME_TO_EMPIRICAL: dict[str, EmpiricalStatus] = {
    "confirmed": "likely_expired",
    "still_failing": "likely_active",
    "flaky": "not_adjudicated",
    "environment_error": "not_adjudicated",
    "inconclusive": "not_adjudicated",
}


def empirical_status_for(outcome: ValidationOutcome | None) -> EmpiricalStatus:
    if outcome is None:
        return "not_adjudicated"
    return _OUTCOME_TO_EMPIRICAL.get(outcome, "not_adjudicated")


@dataclass(frozen=True, slots=True)
class EscalationCaseResult:
    case_id: str
    heuristic_status: ConditionStatus
    agent_status: ConditionStatus
    disagreement: bool
    escalation: EscalationDecision
    escalation_reason: EscalationReason
    approved: bool
    validation_outcome: ValidationOutcome | None
    empirical_status: EmpiricalStatus
    escalation_resolved: bool
    agent_correct: bool | None
    heuristic_correct: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "heuristic_status": self.heuristic_status,
            "agent_status": self.agent_status,
            "disagreement": self.disagreement,
            "escalation": self.escalation,
            "escalation_reason": self.escalation_reason,
            "approved": self.approved,
            "validation_outcome": self.validation_outcome,
            "empirical_status": self.empirical_status,
            "escalation_resolved": self.escalation_resolved,
            "agent_correct": self.agent_correct,
            "heuristic_correct": self.heuristic_correct,
        }


@dataclass(frozen=True, slots=True)
class EscalationReport:
    cases: tuple[EscalationCaseResult, ...]
    schema_version: str = ESCALATION_SCHEMA_VERSION

    # --- aggregate accessors (empirical, not label-based) ---
    @property
    def disagreements(self) -> int:
        return sum(1 for c in self.cases if c.disagreement)

    @property
    def escalations(self) -> int:
        return sum(1 for c in self.cases if c.escalation == "escalation_requested")

    @property
    def escalations_resolved(self) -> int:
        return sum(1 for c in self.cases if c.escalation_resolved)

    @property
    def adjudicated_disagreements(self) -> int:
        return sum(1 for c in self.cases if c.disagreement and c.empirical_status != "not_adjudicated")

    @property
    def agent_correct_on_adjudicated_disagreements(self) -> int:
        return sum(1 for c in self.cases if c.disagreement and c.empirical_status != "not_adjudicated" and c.agent_correct)

    @property
    def heuristic_correct_on_adjudicated_disagreements(self) -> int:
        return sum(1 for c in self.cases if c.disagreement and c.empirical_status != "not_adjudicated" and c.heuristic_correct)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cases": [c.to_dict() for c in self.cases],
            "aggregates": {
                "case_count": len(self.cases),
                "disagreements": self.disagreements,
                "escalations": self.escalations,
                "escalations_resolved": self.escalations_resolved,
                "adjudicated_disagreements": self.adjudicated_disagreements,
                "agent_correct_on_adjudicated_disagreements": self.agent_correct_on_adjudicated_disagreements,
                "heuristic_correct_on_adjudicated_disagreements": self.heuristic_correct_on_adjudicated_disagreements,
            },
            "ground_truth": "empirical_validation",
            "non_authority": True,
        }


__all__ = [
    "ConditionStatus",
    "DEFINITE_STATUSES",
    "ESCALATION_SCHEMA_VERSION",
    "EmpiricalStatus",
    "EscalationCaseResult",
    "EscalationDecision",
    "EscalationReason",
    "EscalationReport",
    "ValidationOutcome",
    "empirical_status_for",
]
