from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from sunset.history_backtest import (
    HoldoutLedger,
    assert_no_leakage,
    assign_splits,
    build_case,
    build_report,
    mine_repository,
    parse_tests,
    require_manifest_before_run,
    split_manifest,
)
from sunset.history_backtest_models import BacktestError, CaseRun, EvidenceItem, digest


def _git(repo: Path, *args: str, date: str | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def _commit(repo: Path, files: dict[str, str | None], message: str, date: str) -> str:
    for rel, content in files.items():
        target = repo / rel
        if content is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message, date=date)
    return _git(repo, "rev-parse", "HEAD")


STALE = '''import pytest

@pytest.mark.xfail(reason="old bug")
def test_stale():
    assert 1 + 1 == 2

@pytest.mark.xfail(reason="needs fix")
def test_fixed_with_code():
    assert helper() == 2

@pytest.mark.skip(reason="gone soon")
def test_deleted():
    assert True

@pytest.mark.xfail(reason="edit me")
def test_edited():
    assert True

@pytest.mark.xfail(reason="retained forever")
def test_retained():
    assert False

@pytest.mark.xfail(reason="body changes")
def test_body():
    assert 1 == 1
'''


@pytest.fixture()
def repo(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    shas = {}
    shas["c1"] = _commit(root, {"pkg/mod.py": "def helper():\n    return 1\n", "tests/test_a.py": STALE}, "init", "2020-01-01T00:00:00Z")
    # marker-only removal: only the test file changes; body untouched
    shas["c2"] = _commit(
        root,
        {"tests/test_a.py": STALE.replace('@pytest.mark.xfail(reason="old bug")\n', "")},
        "drop stale marker",
        "2021-01-01T00:00:00Z",
    )
    after2 = (root / "tests/test_a.py").read_text()
    # fix + removal: source and test change together
    shas["c3"] = _commit(
        root,
        {
            "pkg/mod.py": "def helper():\n    return 2\n",
            "tests/test_a.py": after2.replace('@pytest.mark.xfail(reason="needs fix")\n', ""),
        },
        "fix and remove",
        "2021-06-01T00:00:00Z",
    )
    after3 = (root / "tests/test_a.py").read_text()
    # deleted test, edited marker, body changed
    changed = after3.replace('@pytest.mark.skip(reason="gone soon")\ndef test_deleted():\n    assert True\n\n', "")
    changed = changed.replace('reason="edit me"', 'reason="edited reason"')
    changed = changed.replace('@pytest.mark.xfail(reason="body changes")\ndef test_body():\n    assert 1 == 1', "def test_body():\n    assert 2 == 2")
    shas["c4"] = _commit(root, {"tests/test_a.py": changed}, "misc edits", "2021-09-01T00:00:00Z")
    shas["c5"] = _commit(root, {"README.md": "x\n"}, "head", "2023-06-01T00:00:00Z")
    return {"root": str(root), **shas}


def _mine(repo: dict[str, str]):
    return mine_repository(Path(repo["root"]), "synthetic/repo", horizon_days=365, retained_limit=10)


def test_parse_tests_extracts_function_level_markers():
    tests = parse_tests(STALE)
    assert tests["test_stale"].markers[0].kind == "xfail"
    assert tests["test_stale"].markers[0].reason == "old bug"
    assert tests["test_deleted"].markers[0].kind == "skip"
    assert parse_tests("class TestX:\n    @pytest.mark.skipif(True, reason='r')\n    def test_m(self): pass\n")["TestX::test_m"].markers[0].kind == "skipif"


def test_mining_is_deterministic_and_reconciles(repo):
    first = _mine(repo)
    second = _mine(repo)
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(), sort_keys=True)
    counts = first.to_dict()["counts"]
    assert counts["included"] + counts["excluded"] == counts["mined_total"] == len(first.events) + len(first.exclusions)


def test_event_classification_and_exclusions(repo):
    result = _mine(repo)
    by_name = {e.test_qualname: e for e in result.events if e.event_class != "retained"}
    assert by_name["test_stale"].event_class == "marker_only_removal"
    assert by_name["test_stale"].as_of_sha == repo["c1"] and by_name["test_stale"].outcome_sha == repo["c2"]
    assert by_name["test_fixed_with_code"].event_class == "fix_with_removal"
    reasons = {(x.test_qualname, x.reason) for x in result.exclusions}
    assert ("test_deleted", "test_missing_at_child") in reasons
    assert ("test_edited", "marker_edited") in reasons
    assert ("test_body", "test_modified") in reasons
    retained = {e.test_qualname for e in result.events if e.event_class == "retained"}
    assert "test_retained" in retained
    # a removed marker is never also reported as retained
    assert "test_stale" not in retained


def test_case_evidence_is_parent_bound(repo):
    root = Path(repo["root"])
    result = _mine(repo)
    event = next(e for e in result.events if e.test_qualname == "test_stale")
    case = build_case(root, event, "development")
    assert case.as_of_sha == repo["c1"]
    assert all(item.derived_from_sha == repo["c1"] or item.derived_from_sha == repo["c1"] for item in case.evidence)
    assert "drop stale marker" not in case.evidence_text  # the outcome commit never reaches evidence
    assert "old bug" in case.evidence_text


def test_leaky_case_is_rejected(repo):
    root = Path(repo["root"])
    event = next(e for e in _mine(repo).events if e.test_qualname == "test_stale")
    case = build_case(root, event, "development")
    leaky_items = (*case.evidence, EvidenceItem("blame", repo["c2"], "removed later"))
    leaky = type(case)(**{**{f: getattr(case, f) for f in case.__dataclass_fields__}, "evidence": leaky_items, "evidence_digest": digest([i.to_dict() for i in leaky_items])})
    with pytest.raises(BacktestError) as err:
        assert_no_leakage(leaky, root)
    assert err.value.code == "leakage_detected"
    tampered = type(case)(**{**{f: getattr(case, f) for f in case.__dataclass_fields__}, "evidence_digest": "0" * 64})
    with pytest.raises(BacktestError):
        assert_no_leakage(tampered, root)


def test_splits_fixed_before_run_and_holdout_single_read(repo, tmp_path):
    root = Path(repo["root"])
    events = list(_mine(repo).events)
    assignment = assign_splits(events)
    assert set(assignment.values()) <= {"development", "holdout"}
    cases = [build_case(root, e, assignment[e.event_id]) for e in events]
    manifest = split_manifest(cases, declared_on="2026-10-10")
    require_manifest_before_run(manifest, cases)
    altered = [type(cases[0])(**{**{f: getattr(cases[0], f) for f in cases[0].__dataclass_fields__}, "split": "holdout" if cases[0].split == "development" else "development"}), *cases[1:]]
    with pytest.raises(BacktestError) as err:
        require_manifest_before_run(manifest, altered)
    assert err.value.code == "manifest_mismatch"
    ledger = HoldoutLedger(tmp_path / "ledger.json")
    ledger.read_once(manifest["manifest_digest"], reader="first")
    with pytest.raises(BacktestError) as second:
        ledger.read_once(manifest["manifest_digest"], reader="second")
    assert second.value.code == "holdout_already_read"


def test_report_is_stratified_with_n_and_unknowns(repo):
    root = Path(repo["root"])
    events = list(_mine(repo).events)
    assignment = assign_splits(events)
    cases = [build_case(root, e, assignment[e.event_id]) for e in events]
    runs = [
        CaseRun(c.case_id, "likely_active", "unknown" if i % 2 else "likely_expired", "confirmed" if c.event_class == "marker_only_removal" else "still_failing")
        for i, c in enumerate(cases)
    ]
    manifest = split_manifest(cases, declared_on="2026-10-10")
    report = build_report(cases, runs, run_id="t", mode="recorded", model=None, generated_on="2026-10-10", manifest_digest=manifest["manifest_digest"])
    assert report["strata"], "expected at least one stratum"
    for stratum in report["strata"].values():
        assert stratum["n"] >= 1
        assert "clone_not_adjudicated" in stratum and "agent_abstention_rate" in stratum
    assert any("lead time is unknown" in text for text in report["limitations"])


def test_report_states_bias_and_label_limits(repo):
    report = build_report([], [], run_id="t", mode="recorded", model=None, generated_on="2026-10-10", manifest_digest="x")
    text = " ".join(report["limitations"])
    assert "retained means not_removed" in text and "not representative" in text and "fix_with_removal" in text
    assert report["non_authority"] is True
