from __future__ import annotations

from pathlib import Path
import socket

from sunset.git_repository import GitRepository, RepositoryError
from sunset.scanner import scan_repository

from conftest import repository_snapshot, run_git


def test_discovers_supported_markers_with_static_metadata(sample_repository: Path) -> None:
    result = scan_repository(sample_repository)

    assert result.repository_head == run_git(sample_repository, "rev-parse", "HEAD")
    assert len(result.candidates) == 5
    assert len(result.errors) == 1
    assert result.errors[0].kind == "parse_error"
    assert result.errors[0].path == "tests/broken_test.py"

    by_name = {candidate.qualified_name: candidate for candidate in result.candidates}
    assert set(by_name) == {
        "TestDisabledGroup",
        "TestGroupedBehavior.test_computed_reason",
        "test_expected_failure",
        "test_platform_condition",
        "test_unconditional_skip",
    }

    expected_failure = by_name["test_expected_failure"]
    assert expected_failure.marker_kind == "xfail"
    assert expected_failure.reason == "blocked by upstream issue #417"
    assert expected_failure.condition is None
    assert expected_failure.path == "tests/test_markers.py"
    assert expected_failure.line == 10
    assert expected_failure.column == 0

    platform_condition = by_name["test_platform_condition"]
    assert platform_condition.marker_kind == "skipif"
    assert platform_condition.reason == "unsupported on Windows"
    assert platform_condition.condition == 'sys.platform == "win32"'

    computed_reason = by_name["TestGroupedBehavior.test_computed_reason"]
    assert computed_reason.marker_kind == "xfail"
    assert computed_reason.column == 4
    assert computed_reason.reason is None
    assert computed_reason.condition == "FEATURE_OFF"

    disabled_group = by_name["TestDisabledGroup"]
    assert disabled_group.marker_kind == "skip"
    assert disabled_group.reason == "the entire group is unavailable"

    assert all(candidate.candidate_id.startswith("sunset-v1-") for candidate in result.candidates)
    assert all(len(candidate.blame_commit) == 40 for candidate in result.candidates)
    assert all(candidate.repository_head == result.repository_head for candidate in result.candidates)


def test_scan_is_byte_stable_for_same_commit(sample_repository: Path) -> None:
    first = scan_repository(sample_repository)
    second = scan_repository(sample_repository)

    assert first.to_json().encode("utf-8") == second.to_json().encode("utf-8")
    assert [item.candidate_id for item in first.candidates] == [
        item.candidate_id for item in second.candidates
    ]


def test_blame_commit_can_differ_from_repository_head(sample_repository: Path) -> None:
    result = scan_repository(sample_repository)
    introduction = run_git(sample_repository, "rev-list", "--max-parents=0", "HEAD")

    assert introduction != result.repository_head
    assert {candidate.blame_commit for candidate in result.candidates} == {introduction}


def test_target_subdirectory_limits_scan(sample_repository: Path) -> None:
    result = scan_repository(sample_repository / "tests")

    assert len(result.candidates) == 5
    assert all(candidate.path.startswith("tests/") for candidate in result.candidates)


def test_discovery_respects_test_names_and_repository_exclusions(
    sample_repository: Path,
) -> None:
    repository = GitRepository.open(sample_repository)

    assert repository.list_test_files() == (
        "src/not_a_test.py",
        "tests/broken_test.py",
        "tests/test_markers.py",
    )


def test_non_git_target_has_explicit_supported_error(tmp_path: Path) -> None:
    try:
        GitRepository.open(tmp_path)
    except RepositoryError as exc:
        assert exc.code == "not_git_repository"
        assert exc.message == "target is not inside a Git repository"
    else:
        raise AssertionError("expected RepositoryError")


def test_scan_does_not_mutate_or_use_network(
    sample_repository: Path,
    monkeypatch,
) -> None:
    untracked = sample_repository / "tests" / "test_untracked.py"
    untracked.write_text(
        "import pytest\n@pytest.mark.skip\ndef test_untracked(): pass\n",
        encoding="utf-8",
    )
    status_before = run_git(sample_repository, "status", "--porcelain=v1", "--untracked-files=all")
    contents_before = repository_snapshot(sample_repository)

    def forbid_network(*args, **kwargs):
        raise AssertionError("scanner attempted to create a network socket")

    monkeypatch.setattr(socket, "socket", forbid_network)
    result = scan_repository(sample_repository)

    assert len(result.candidates) == 5
    assert status_before == run_git(
        sample_repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    assert contents_before == repository_snapshot(sample_repository)
