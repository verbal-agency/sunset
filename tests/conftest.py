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


@pytest.fixture
def renamed_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "renamed-repository"
    (repository / "tests").mkdir(parents=True)
    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "sunset@example.test")
    run_git(repository, "config", "user.name", "Sunset Tests")

    legacy_path = repository / "tests" / "test_legacy.py"
    legacy_path.write_text(
        "import pytest\n\n\n@pytest.mark.xfail(reason=\"upstream issue #417\")\ndef test_compatibility():\n    pass\n",
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "introduce compatibility marker")

    run_git(repository, "mv", "tests/test_legacy.py", "tests/test_markers.py")
    run_git(repository, "commit", "-qm", "rename compatibility test")

    (repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
    run_git(repository, "add", "README.md")
    run_git(repository, "commit", "-qm", "add unrelated documentation")
    return repository


@pytest.fixture
def shallow_repository(renamed_repository: Path, tmp_path: Path) -> Path:
    repository = tmp_path / "shallow-repository"
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--depth",
            "1",
            renamed_repository.as_uri(),
            str(repository),
        ],
        check=True,
    )
    return repository
