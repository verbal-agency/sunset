"""The G30 evaluation report: escalation-loop results with empirical metrics.

Turns an escalation run into a durable, auditable artifact (JSON + Markdown). All
metrics are grounded in the disposable-clone outcome, never in asserted labels.

Escalation *recall* is deliberately not computed: by design the loop does not
validate cases where the agent and heuristic agree (that is the efficiency
property), so there is no honest denominator for "escalations we missed". The
report says so rather than inventing a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sunset.escalation_loop import ApprovalGate, EscalationValidator, Reasoner, run_escalation_evaluation
from sunset.escalation_loop_models import EscalationReport

ESCALATION_REPORT_SCHEMA_VERSION = "1"


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def escalation_metrics(report: EscalationReport) -> dict[str, Any]:
    cases = report.cases
    escalated = [c for c in cases if c.escalation == "escalation_requested"]
    adjudicated = [c for c in escalated if c.empirical_status != "not_adjudicated"]
    adjudicated_disagreements = [c for c in adjudicated if c.disagreement]
    return {
        "case_count": len(cases),
        "escalations": len(escalated),
        "escalation_rate": _rate(len(escalated), len(cases)),
        "escalations_resolved": sum(1 for c in escalated if c.escalation_resolved),
        "escalation_resolution_rate": _rate(sum(1 for c in escalated if c.escalation_resolved), len(escalated)),
        "adjudicated_disagreements": len(adjudicated_disagreements),
        "agent_wins_on_disagreements": sum(1 for c in adjudicated_disagreements if c.agent_correct),
        "heuristic_wins_on_disagreements": sum(1 for c in adjudicated_disagreements if c.heuristic_correct),
        # A definite agent claim the clone refuted (the safety net firing).
        "error_catches": sum(1 for c in adjudicated if c.agent_correct is False),
        # An agent abstention that escalation turned into an empirical fact.
        "resolved_unknowns": sum(
            1 for c in escalated if c.escalation_reason == "agent_uncertain" and c.empirical_status != "not_adjudicated"
        ),
        "recall_note": "agreements are not validated by design; escalation recall is not computed",
    }


@dataclass(frozen=True, slots=True)
class EscalationEvaluationReport:
    run_id: str
    mode: str  # "live" | "recorded"
    model: str | None
    execution: str  # "executed" | "not_executed"
    generated_on: str
    report: EscalationReport
    case_names: dict[str, str] | None = None
    schema_version: str = ESCALATION_REPORT_SCHEMA_VERSION

    def metrics(self) -> dict[str, Any]:
        return escalation_metrics(self.report)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "mode": self.mode,
            "model": self.model,
            "execution": self.execution,
            "generated_on": self.generated_on,
            "ground_truth": "empirical_validation",
            "metrics": self.metrics(),
            "case_names": self.case_names or {},
            "cases": [c.to_dict() for c in self.report.cases],
            "non_authority": True,
        }

    def to_markdown(self) -> str:
        m = self.metrics()
        name = self.case_names or {}
        lines = [
            f"# Escalation evaluation report — {self.run_id}",
            "",
            f"- Mode: **{self.mode}** ({self.execution}); model: **{self.model or 'n/a'}**; generated {self.generated_on}",
            "- Ground truth: **empirical validation** (disposable-clone outcome), not asserted labels.",
            "",
            "| Case | Heuristic | Agent | Escalation | Clone outcome | Empirical | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for c in self.report.cases:
            verdict = (
                "agent right" if c.agent_correct is True
                else "agent wrong (clone caught)" if c.agent_correct is False
                else "not adjudicated"
            )
            lines.append(
                f"| {name.get(c.case_id, c.case_id)} | {c.heuristic_status} | {c.agent_status} | "
                f"{c.escalation_reason} | {c.validation_outcome or '—'} | {c.empirical_status} | {verdict} |"
            )
        lines += [
            "",
            "## Metrics (empirical)",
            "",
            f"- cases: {m['case_count']}; escalations: {m['escalations']} (rate {m['escalation_rate']})",
            f"- escalations resolved: {m['escalations_resolved']} (rate {m['escalation_resolution_rate']})",
            f"- adjudicated disagreements: {m['adjudicated_disagreements']} — "
            f"agent wins {m['agent_wins_on_disagreements']}, heuristic wins {m['heuristic_wins_on_disagreements']}",
            f"- error catches (agent wrong, clone caught): {m['error_catches']}",
            f"- resolved unknowns: {m['resolved_unknowns']}",
            f"- recall: {m['recall_note']}",
        ]
        return "\n".join(lines) + "\n"


def evaluate(
    case_ids: tuple[str, ...],
    heuristic_reasoner: Reasoner,
    agent_reasoner: Reasoner,
    *,
    validator: EscalationValidator,
    approve: ApprovalGate,
    run_id: str,
    mode: str,
    model: str | None,
    execution: str,
    generated_on: str,
    case_names: dict[str, str] | None = None,
) -> EscalationEvaluationReport:
    report = run_escalation_evaluation(case_ids, heuristic_reasoner, agent_reasoner, validator=validator, approve=approve)
    return EscalationEvaluationReport(
        run_id=run_id,
        mode=mode,
        model=model,
        execution=execution,
        generated_on=generated_on,
        report=report,
        case_names=case_names,
    )


def recorded_validator(outcomes: dict[str, str]) -> EscalationValidator:
    """A validator that replays recorded clone outcomes (offline, deterministic)."""

    def validate(case_id: str):
        if case_id not in outcomes:
            raise KeyError(f"no recorded validation outcome for {case_id}")
        return outcomes[case_id]  # type: ignore[return-value]

    return validate


__all__ = [
    "ESCALATION_REPORT_SCHEMA_VERSION",
    "EscalationEvaluationReport",
    "escalation_metrics",
    "evaluate",
    "recorded_validator",
]
