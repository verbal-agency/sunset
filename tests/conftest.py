from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pytest_repo"


def run_git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def sample_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "sample-repository"
    shutil.copytree(FIXTURE_ROOT, repository)

    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "sunset@example.test")
    run_git(repository, "config", "user.name", "Sunset Tests")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "add pytest marker fixtures")

    (repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
    run_git(repository, "add", "README.md")
    run_git(repository, "commit", "-qm", "add unrelated documentation")

    (repository / "tests" / "ignored_test.py").write_text(
        "import pytest\n@pytest.mark.xfail\ndef test_ignored(): pass\n",
        encoding="utf-8",
    )
    return repository


def repository_snapshot(repository: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(repository.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(repository).as_posix()
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot

