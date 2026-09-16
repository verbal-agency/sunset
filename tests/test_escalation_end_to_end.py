"""G30-AC06 — end-to-end escalation: reason -> escalate -> approve -> real clone
run -> empirical adjudication. This actually creates disposable clones and runs
pytest; asserted labels play no part.
"""

from __future__ import annotations

from pathlib import Path

from sunset.escalation_loop import (
    approval_set,
    build_g06_validator,
    conservative_heuristic_reasoner,
    recorded_reasoner,
    run_escalation_evaluation,
)
from sunset.scanner import scan_repository

from conftest import repository_snapshot, run_git


def _marker_repo(tmp_path: Path, name: str, body: str) -> tuple[Path, str]:
    """A repo with one xfail marker whose test body decides the empirical outcome."""

    repo = tmp_path / name
    (repo / "tests").mkdir(parents=True)
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "sunset@example.test")
    run_git(repo, "config", "user.name", "Sunset Tests")
    (repo / "tests" / "test_marker.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.xfail(reason='temporary upstream issue')\n"
        "def test_candidate():\n"
        f"    {body}\n",
        encoding="utf-8",
    )
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-qm", "add disabled marker")
    return repo, scan_repository(repo).candidates[0].candidate_id


def test_end_to_end_empirical_adjudication(tmp_path: Path) -> None:
    # "expired": the test actually passes now, so removing the marker -> confirmed.
    expired_repo, expired_id = _marker_repo(tmp_path, "expired", "assert True")
    # "active": the test still fails, so removing the marker -> still_failing.
    active_repo, active_id = _marker_repo(tmp_path, "active", "assert False")

    targets = {
        "case_expired": (expired_repo, expired_id),
        "case_active": (active_repo, active_id),
    }
    validator = build_g06_validator(targets.__getitem__, tmp_path / "store")

    # The agent claims both are expired; the heuristic conservatively says both are
    # active. They disagree on both -> escalate both -> run the code to adjudicate.
    agent = recorded_reasoner({"case_expired": "likely_expired", "case_active": "likely_expired"})
    heuristic = conservative_heuristic_reasoner()

    before_expired = repository_snapshot(expired_repo)
    before_active = repository_snapshot(active_repo)

    report = run_escalation_evaluation(
        ("case_expired", "case_active"),
        heuristic,
        agent,
        validator=validator,
        approve=approval_set({"case_expired", "case_active"}),
    )

    cases = {c.case_id: c for c in report.cases}

    # Expired case: empirical result confirms the agent, refutes the heuristic.
    exp = cases["case_expired"]
    assert exp.disagreement is True and exp.escalation == "escalation_requested"
    assert exp.validation_outcome == "confirmed"
    assert exp.empirical_status == "likely_expired"
    assert exp.agent_correct is True and exp.heuristic_correct is False

    # Active case: empirical result confirms the heuristic, refutes the agent.
    act = cases["case_active"]
    assert act.validation_outcome == "still_failing"
    assert act.empirical_status == "likely_active"
    assert act.agent_correct is False and act.heuristic_correct is True

    # Aggregates: one win each, decided empirically.
    agg = report.to_dict()["aggregates"]
    assert agg["adjudicated_disagreements"] == 2
    assert agg["agent_correct_on_adjudicated_disagreements"] == 1
    assert agg["heuristic_correct_on_adjudicated_disagreements"] == 1

    # AC06 side-effect boundary: the target repos are untouched.
    assert repository_snapshot(expired_repo) == before_expired
    assert repository_snapshot(active_repo) == before_active


def test_denied_approval_runs_no_clone(tmp_path: Path) -> None:
    repo, cid = _marker_repo(tmp_path, "denied", "assert True")
    calls: list[str] = []

    def resolve(case_id: str):
        calls.append(case_id)
        return (repo, cid)

    validator = build_g06_validator(resolve, tmp_path / "store")
    # approve nothing -> the loop must never invoke the validator (no clone, no run)
    report = run_escalation_evaluation(
        ("case",),
        conservative_heuristic_reasoner(),
        recorded_reasoner({"case": "likely_expired"}),
        validator=validator,
        approve=approval_set(set()),
    )
    only = report.cases[0]
    assert only.escalation == "escalation_requested"
    assert only.approved is False
    assert only.empirical_status == "not_adjudicated"
    assert calls == []  # resolve/validator never reached
