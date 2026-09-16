"""G30 — escalation loop and empirical adjudication (recorded-first, offline)."""

from __future__ import annotations

import pytest

from sunset.escalation_loop import (
    approval_set,
    decide_escalation,
    recorded_reasoner,
    run_escalation_case,
    run_escalation_evaluation,
)


def _never_call_validator(_case_id: str):
    raise AssertionError("validator must not run without approval")


# --- escalation decision -----------------------------------------------------

def test_agreement_does_not_escalate() -> None:
    escalate, reason = decide_escalation("likely_active", "likely_active")
    assert escalate is False
    assert reason == "agreement"


def test_agent_uncertainty_escalates() -> None:
    for status in ("unknown", "contradictory"):
        escalate, reason = decide_escalation("likely_active", status)  # type: ignore[arg-type]
        assert escalate is True
        assert reason == "agent_uncertain"


def test_definite_disagreement_escalates() -> None:
    escalate, reason = decide_escalation("likely_active", "likely_expired")
    assert escalate is True
    assert reason == "disagreement"


# --- approval gating (fail-closed) ------------------------------------------

def test_no_validator_call_without_approval() -> None:
    # default gate denies; validator must never run
    result = run_escalation_case("c1", "likely_active", "likely_expired", validator=_never_call_validator)
    assert result.escalation == "escalation_requested"
    assert result.approved is False
    assert result.validation_outcome is None
    assert result.empirical_status == "not_adjudicated"
    assert result.agent_correct is None and result.heuristic_correct is None


def test_no_escalation_means_no_validation() -> None:
    result = run_escalation_case("c1", "likely_active", "likely_active", validator=_never_call_validator)
    assert result.escalation == "no_escalation"
    assert result.approved is False
    assert result.empirical_status == "not_adjudicated"


# --- empirical adjudication (the "was the agent right?" core) -----------------

def test_empirical_result_adjudicates_agent_correct() -> None:
    # heuristic says active, agent says expired; run the code -> confirmed (passes
    # without marker) -> empirically expired -> the AGENT was right.
    result = run_escalation_case(
        "c1", "likely_active", "likely_expired",
        validator=lambda _c: "confirmed",
        approve=approval_set({"c1"}),
    )
    assert result.approved is True
    assert result.validation_outcome == "confirmed"
    assert result.empirical_status == "likely_expired"
    assert result.escalation_resolved is True
    assert result.agent_correct is True
    assert result.heuristic_correct is False


def test_empirical_result_adjudicates_heuristic_correct() -> None:
    # same disagreement, but still_failing -> empirically active -> HEURISTIC right.
    result = run_escalation_case(
        "c1", "likely_active", "likely_expired",
        validator=lambda _c: "still_failing",
        approve=approval_set({"c1"}),
    )
    assert result.empirical_status == "likely_active"
    assert result.agent_correct is False
    assert result.heuristic_correct is True


def test_uncertain_agent_escalation_resolves_unknown() -> None:
    # agent unknown -> escalate -> validated -> unknown becomes an empirical fact.
    result = run_escalation_case(
        "c1", "likely_active", "unknown",
        validator=lambda _c: "confirmed",
        approve=approval_set({"c1"}),
    )
    assert result.escalation_reason == "agent_uncertain"
    assert result.escalation_resolved is True
    assert result.empirical_status == "likely_expired"
    # agent made no definite claim, so no correctness is asserted for it
    assert result.agent_correct is None
    # heuristic made a definite (wrong) claim
    assert result.heuristic_correct is False


def test_inconclusive_validation_is_not_adjudicated() -> None:
    for outcome in ("flaky", "environment_error", "inconclusive"):
        result = run_escalation_case(
            "c1", "likely_active", "likely_expired",
            validator=lambda _c, o=outcome: o,
            approve=approval_set({"c1"}),
        )
        assert result.approved is True
        assert result.empirical_status == "not_adjudicated"
        assert result.escalation_resolved is False
        assert result.agent_correct is None and result.heuristic_correct is None


# --- evaluation report --------------------------------------------------------

def test_evaluation_report_aggregates_empirically() -> None:
    cases = ("agree", "disagree_agent_right", "disagree_heur_right", "uncertain")
    heuristic = recorded_reasoner({
        "agree": "likely_active",
        "disagree_agent_right": "likely_active",
        "disagree_heur_right": "likely_active",
        "uncertain": "likely_expired",
    })
    agent = recorded_reasoner({
        "agree": "likely_active",
        "disagree_agent_right": "likely_expired",
        "disagree_heur_right": "likely_expired",
        "uncertain": "unknown",
    })
    outcomes = {
        "disagree_agent_right": "confirmed",     # empirically expired -> agent right
        "disagree_heur_right": "still_failing",  # empirically active  -> heuristic right
        "uncertain": "confirmed",
    }
    report = run_escalation_evaluation(
        cases, heuristic, agent,
        validator=lambda c: outcomes[c],
        approve=approval_set(set(outcomes)),
    )
    agg = report.to_dict()["aggregates"]
    assert agg["case_count"] == 4
    assert agg["disagreements"] == 2          # two definite conflicts (abstention is not a disagreement)
    assert agg["escalations"] == 3            # both disagreements + the uncertain case
    assert agg["escalations_resolved"] == 3
    assert agg["adjudicated_disagreements"] == 2
    assert agg["agent_correct_on_adjudicated_disagreements"] == 1     # only disagree_agent_right
    assert agg["heuristic_correct_on_adjudicated_disagreements"] == 1  # only disagree_heur_right
    assert report.to_dict()["ground_truth"] == "empirical_validation"


def test_recorded_reasoner_is_deterministic_and_offline() -> None:
    reasoner = recorded_reasoner({"c1": "likely_expired"})
    assert reasoner("c1") == "likely_expired"
    assert reasoner("missing") == "unknown"  # unknown -> would escalate, never guesses
