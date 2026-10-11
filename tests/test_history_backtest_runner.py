from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from sunset.history_backtest import build_case, mine_repository
from sunset.history_backtest_models import BacktestError
from sunset.history_backtest_runner import (
    CloneChecker,
    CostGuard,
    Execution,
    LiveAuthorization,
    RepoRecipe,
    RunnerPolicy,
    build_runs,
    classify_runs,
    guarded_reasoner,
    remove_markers,
    run_clone_checks,
    scrubbed_env,
    subprocess_runner,
)
from test_history_backtest import repo  # noqa: F401  (synthetic repository fixture)


def test_remove_markers_removes_only_the_selected_tests_markers():
    source = (
        "import pytest\n\n@pytest.mark.xfail(reason='a')\ndef test_a():\n    pass\n\n"
        "class TestK:\n    @pytest.mark.skipif(True,\n        reason='b')\n    @pytest.mark.parametrize('x',[1])\n    def test_b(self, x):\n        pass\n\n"
        "@pytest.mark.xfail(reason='c')\ndef test_c():\n    pass\n"
    )
    out, removed = remove_markers(source, "TestK::test_b")
    assert removed == 1 and "skipif" not in out and "parametrize" in out
    assert out.count("xfail") == 2  # other tests untouched
    with pytest.raises(BacktestError):
        remove_markers(source, "test_missing")


def test_classify_runs_matches_g06_outcome_classes():
    assert classify_runs(["pass", "pass"]) == "confirmed"
    assert classify_runs(["fail", "fail"]) == "still_failing"
    assert classify_runs(["pass", "fail"]) == "flaky"
    assert classify_runs(["pass", "error"]) == "environment_error"


def test_single_run_accepts_parameterized_pytest_counts():
    from sunset.history_backtest_runner import _single_run

    assert _single_run(Execution(0, "3 passed in 0.02s", "")) == "pass"
    assert _single_run(Execution(1, "2 failed, 1 passed in 0.02s", "")) == "fail"
    assert _single_run(Execution(1, "AttributeError: platform detail\n3 failed in 0.02s", "")) == "fail"
    assert _single_run(Execution(4, "no tests ran", "ERROR: not found")) == "error"


def test_scrubbed_env_never_carries_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    env = scrubbed_env(tmp_path)
    assert "ANTHROPIC_API_KEY" not in env and "GITHUB_TOKEN" not in env
    assert env["HOME"] == str(tmp_path)


def _policy(tmp_path: Path, root: Path, *, network: bool) -> RunnerPolicy:
    return RunnerPolicy(
        work_root=tmp_path / "work",
        source_repos={"synthetic/repo": root},
        recipes={"synthetic/repo": RepoRecipe(install_args=("pytest",))},
        pythons={"3.10": "/usr/bin/python3", "3.12": "/usr/bin/python3"},
        network_enabled=network,
        workers=1,
    )


def _snapshot(root: Path) -> str:
    return subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout + (
        subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout
    )


def _case(repo):
    root = Path(repo["root"])
    event = next(e for e in mine_repository(root, "synthetic/repo", horizon_days=365).events if e.test_qualname == "test_stale")
    return root, event, build_case(root, event, "development")


def test_backtest_authority_and_cost_guards(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    root, event, case = _case(repo)
    before = _snapshot(root)
    seen_envs: list[dict] = []
    commands: list[tuple[str, ...]] = []

    def fake(command, cwd, timeout, env):
        seen_envs.append(dict(env))
        commands.append(command)
        if command[0] == "git":
            return subprocess_runner(command, cwd, timeout, env)
        if command[1:3] == ("-m", "pytest"):
            return Execution(0, "1 passed in 0.01s", "")
        return Execution(0, "", "")

    # network not authorized: fails closed as an environment error, nothing installed
    closed = CloneChecker(_policy(tmp_path / "a", root, network=False), fake)
    outcome, note, _ = closed.check(case, event.as_of_date)
    assert outcome == "environment_error" and "network_not_authorized" in (note or "")
    assert not any(c[0] == "uv" for c in commands)

    open_checker = CloneChecker(_policy(tmp_path / "b", root, network=True), fake)
    outcome, note, receipt = open_checker.check(case, event.as_of_date)
    assert outcome == "confirmed" and receipt["as_of_commit"] == case.as_of_sha
    assert all("ANTHROPIC_API_KEY" not in env for env in seen_envs)
    assert all(isinstance(c, tuple) and "|" not in c and "sh" != c[0] for c in commands)  # argv lists, no shell
    assert _snapshot(root) == before  # mined repository untouched
    checkout = open_checker._envs[(case.repository, case.as_of_sha)].checkout
    assert "xfail" in (checkout / case.test_path).read_text()  # clone restored after the check

    # live run without authorization / past the cap fails closed
    with pytest.raises(BacktestError) as err:
        CostGuard(None)
    assert err.value.code == "live_not_authorized"
    guard = CostGuard(LiveAuthorization(model="m", max_calls=1, granted_by="test"))
    reason = guarded_reasoner(lambda _cid: "unknown", guard)
    reason("a")
    with pytest.raises(BacktestError) as cap:
        reason("b")
    assert cap.value.code == "cost_cap_reached"


def test_run_clone_checks_and_build_runs(repo, tmp_path):
    root, event, case = _case(repo)

    def fake(command, cwd, timeout, env):
        if command[0] == "git":
            return subprocess_runner(command, cwd, timeout, env)
        if command[1:3] == ("-m", "pytest"):
            return Execution(1, "1 failed in 0.02s", "")
        return Execution(0, "", "")

    checker = CloneChecker(_policy(tmp_path, root, network=True), fake)
    checks = run_clone_checks([case], {case.case_id: event.as_of_date}, checker)
    assert checks[case.case_id][0] == "still_failing"
    runs = build_runs([case], checks, heuristic=lambda _c: "likely_active", agent=None)
    assert runs[0].agent_status is None and runs[0].clone_outcome == "still_failing"
