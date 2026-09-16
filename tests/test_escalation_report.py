"""G30 AC03/AC05 — the escalation evaluation report (offline, deterministic).

Reproduces the report metrics from recorded inputs (the live run's agent statuses
and clone outcomes), so CI verifies the report without live calls or real clones.
"""

from __future__ import annotations

import json
from pathlib import Path

from sunset.escalation_loop import approval_set, conservative_heuristic_reasoner, recorded_reasoner
from sunset.escalation_report import escalation_metrics, evaluate, recorded_validator
from sunset.escalation_loop import run_escalation_evaluation

CASES = Path("tests/fixtures/benchmarks/g30-escalation-cases-v1.json")


def _inputs() -> tuple[tuple[str, ...], dict, dict]:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    ids = tuple(c["case_id"] for c in data["cases"])
    agent = {c["case_id"]: c["agent_status"] for c in data["cases"]}
    outcomes = {c["case_id"]: c["validation_outcome"] for c in data["cases"] if c["validation_outcome"] is not None}
    return ids, agent, outcomes


def test_report_reproduces_live_run_metrics() -> None:
    ids, agent, outcomes = _inputs()
    report = evaluate(
        ids,
        conservative_heuristic_reasoner(),
        recorded_reasoner(agent),
        validator=recorded_validator(outcomes),
        approve=approval_set(set(ids)),
        run_id="g30-escalation-report-v1",
        mode="recorded",
        model="claude-sonnet-4-5",
        execution="executed",
        generated_on="2026-09-16",
    )
    m = report.metrics()
    assert m["case_count"] == 3
    assert m["escalations"] == 2               # upstream-fixed, misleading-temp
    assert m["escalations_resolved"] == 2
    assert m["adjudicated_disagreements"] == 2
    assert m["agent_wins_on_disagreements"] == 1       # upstream-fixed
    assert m["heuristic_wins_on_disagreements"] == 1   # misleading-temp
    assert m["error_catches"] == 1                     # misleading-temp: agent wrong, clone caught it
    assert m["resolved_unknowns"] == 0                 # no abstentions in this run

    d = report.to_dict()
    assert d["ground_truth"] == "empirical_validation"
    assert d["execution"] == "executed"
    assert len(d["cases"]) == 3
    md = report.to_markdown()
    assert "Escalation evaluation report" in md
    assert "agent wrong (clone caught)" in md  # the safety-net row renders


def test_recorded_validator_only_called_on_escalation() -> None:
    ids, agent, outcomes = _inputs()
    # platform-active has no recorded outcome; if the loop called the validator for
    # it (a non-escalated case), recorded_validator would raise KeyError.
    report = run_escalation_evaluation(
        ids,
        conservative_heuristic_reasoner(),
        recorded_reasoner(agent),
        validator=recorded_validator(outcomes),
        approve=approval_set(set(ids)),
    )
    by_id = {c.case_id: c for c in report.cases}
    assert by_id["platform-active"].escalation == "no_escalation"
    assert by_id["platform-active"].validation_outcome is None


def test_metrics_count_error_catches_and_resolved_unknowns() -> None:
    # synthetic: one abstention resolved, one definite-wrong caught
    report = run_escalation_evaluation(
        ("uncertain", "wrong"),
        conservative_heuristic_reasoner(),                       # both likely_active
        recorded_reasoner({"uncertain": "unknown", "wrong": "likely_expired"}),
        validator=recorded_validator({"uncertain": "confirmed", "wrong": "still_failing"}),
        approve=approval_set({"uncertain", "wrong"}),
    )
    m = escalation_metrics(report)
    assert m["resolved_unknowns"] == 1   # 'uncertain' abstention -> empirical fact
    assert m["error_catches"] == 1       # 'wrong' definite-wrong -> clone caught it
