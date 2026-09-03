from __future__ import annotations

from pathlib import Path

from sunset.git_repository import GitRepository

from conftest import run_git


def test_blame_file_maps_every_committed_line_once(tmp_path: Path) -> None:
    repository = tmp_path / "blame-repository"
    repository.mkdir()
    (repository / "example.py").write_text("first = 1\nsecond = 2\n", encoding="utf-8")
    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "sunset@example.test")
    run_git(repository, "config", "user.name", "Sunset Tests")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "add blame fixture")

    opened = GitRepository.open(repository)
    mapping = opened.blame_file("example.py")

    assert set(mapping) == {1, 2}
    assert all(len(commit) == 40 for commit in mapping.values())
    assert mapping[1] == mapping[2] == opened.head
