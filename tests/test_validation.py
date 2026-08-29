from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.cli import main
from sunset.scanner import scan_repository
from sunset import validation
from sunset.validation import ValidationConfig, validate_candidate
from sunset.validation_models import CommandExecution, ValidationError

from conftest import repository_snapshot, run_git


def _validation_repository(
    tmp_path: Path,
    body: str = "assert True",
    *,
    extra_marker: bool = False,
) -> tuple[Path, str]:
    repository = tmp_path / "validation-repository"
    (repository / "tests").mkdir(parents=True)
    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "sunset@example.test")
    run_git(repository, "config", "user.name", "Sunset Tests")
    extra = "@pytest.mark.skip(reason='separate marker')\n" if extra_marker else ""
    (repository / "tests" / "test_marker.py").write_text(
        "".join(
            (
                "import pytest\n\n",
                "@pytest.mark.xfail(reason='temporary upstream issue')\n",
                extra,
                "def test_candidate():\n",
                f"    {body}\n",
            )
        ),
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "add disabled marker")
    return repository, scan_repository(repository).candidates[0].candidate_id


def _target_state(repository: Path) -> tuple[dict[str, str], str]:
    return (
        repository_snapshot(repository),
        run_git(repository, "status", "--porcelain=v1", "--untracked-files=all"),
    )


def test_denied_approval_creates_no_sandbox_runs_no_command_and_preserves_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, candidate_id = _validation_repository(tmp_path)
    before = _target_state(repository)
    calls: list[tuple[str, ...]] = []

    def fail_clone(*args, **kwargs):
        raise AssertionError("approval denial must not create a clone")

    def fail_command(command, cwd, timeout):
        calls.append(command)
        raise AssertionError("approval denial must not run a command")

    monkeypatch.setattr(validation, "_create_clone", fail_clone)
    result = validate_candidate(
        repository,
        store_path=tmp_path / "store",
        candidate_id=candidate_id,
        command_runner=fail_command,
    )

    assert result.status == "approval_required"
    assert not result.approved
    assert result.runs == ()
    assert calls == []
    assert not (tmp_path / "store").exists()
    assert _target_state(repository) == before


def test_approved_validation_removes_only_clone_marker_and_records_manifest_and_outputs(tmp_path: Path) -> None:
    repository, candidate_id = _validation_repository(tmp_path, extra_marker=True)
    before = _target_state(repository)
    store = ArtifactStore(tmp_path / "store")
    observed_sandboxes: list[Path] = []

    def passing_runner(command, cwd, timeout):
        observed_sandboxes.append(cwd)
        source = (cwd / "tests" / "test_marker.py").read_text(encoding="utf-8")
        assert "@pytest.mark.xfail" not in source
        assert "@pytest.mark.skip" in source
        assert "def test_candidate" in source
        return CommandExecution(0, b"", b"passed")

    result = validate_candidate(
        repository,
        store_path=store.root,
        candidate_id=candidate_id,
        approved=True,
        artifact_store=store,
        command_runner=passing_runner,
    )

    assert result.status == "confirmed"
    assert result.environment is not None
    manifest = json.loads(store.read(result.environment.artifact))
    assert manifest["candidate_id"] == candidate_id
    assert manifest["repository_head"] == result.repository_head
    assert manifest["config"]["repeat_count"] == 2
    assert len(result.runs) == 2
    assert all(store.read(run.output) for run in result.runs)
    assert all(path != repository for path in observed_sandboxes)
    assert _target_state(repository) == before
    assert "@pytest.mark.xfail" in (repository / "tests" / "test_marker.py").read_text(encoding="utf-8")


def test_actual_passing_and_failing_marker_experiments_are_classified(tmp_path: Path) -> None:
    passing_repository, passing_candidate = _validation_repository(tmp_path / "passing")
    failing_repository, failing_candidate = _validation_repository(tmp_path / "failing", body="assert False")

    passing = validate_candidate(
        passing_repository,
        store_path=tmp_path / "passing-store",
        candidate_id=passing_candidate,
        approved=True,
    )
    failing = validate_candidate(
        failing_repository,
        store_path=tmp_path / "failing-store",
        candidate_id=failing_candidate,
        approved=True,
    )

    assert passing.status == "confirmed"
    assert failing.status == "still_failing"
    assert all(run.return_code == 0 for run in passing.runs)
    assert all(run.return_code == 1 for run in failing.runs)


@pytest.mark.parametrize(
    ("codes", "expected"),
    [((0, 1), "flaky"), ((2,), "environment_error")],
)
def test_flaky_and_environment_error_classification_use_artifact_backed_runs(
    tmp_path: Path,
    codes: tuple[int, ...],
    expected: str,
) -> None:
    repository, candidate_id = _validation_repository(tmp_path)
    remaining = list(codes)

    def runner(command, cwd, timeout):
        return CommandExecution(remaining.pop(0), b"stderr", b"stdout")

    store = ArtifactStore(tmp_path / "store")
    result = validate_candidate(
        repository,
        store_path=store.root,
        candidate_id=candidate_id,
        approved=True,
        artifact_store=store,
        command_runner=runner,
    )

    assert result.status == expected
    assert result.runs
    assert all(store.read(run.output) for run in result.runs)


def test_broader_command_and_transform_failure_are_structured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository, candidate_id = _validation_repository(tmp_path)
    commands: list[tuple[str, ...]] = []

    def runner(command, cwd, timeout):
        commands.append(command)
        return CommandExecution(0, b"", b"ok")

    confirmed = validate_candidate(
        repository,
        store_path=tmp_path / "confirmed-store",
        candidate_id=candidate_id,
        approved=True,
        config=ValidationConfig(broader_commands=(("python", "-c", "print('broader')"),)),
        command_runner=runner,
    )
    monkeypatch.setattr(
        validation,
        "_remove_marker",
        lambda sandbox, candidate: ValidationError("marker_span_not_found", "fixture transform failure"),
    )
    inconclusive = validate_candidate(
        repository,
        store_path=tmp_path / "failed-store",
        candidate_id=candidate_id,
        approved=True,
    )

    assert confirmed.status == "confirmed"
    assert len(commands) == 3
    assert commands[-1] == ("python", "-c", "print('broader')")
    assert inconclusive.status == "inconclusive"
    assert inconclusive.environment is not None
    assert inconclusive.errors[0].kind == "marker_span_not_found"


def test_validate_cli_requires_approval_and_returns_structured_json(tmp_path: Path, capsys) -> None:
    repository, candidate_id = _validation_repository(tmp_path)

    exit_code = main(
        ["validate", str(repository), "--candidate-id", candidate_id, "--store", str(tmp_path / "store")]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "approval_required"
    assert payload["runs"] == []


def test_validate_cli_runs_only_with_explicit_approval(tmp_path: Path, capsys) -> None:
    repository, candidate_id = _validation_repository(tmp_path)

    exit_code = main(
        [
            "validate", str(repository), "--candidate-id", candidate_id,
            "--store", str(tmp_path / "store"), "--approve",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["approved"] is True
    assert payload["status"] == "confirmed"
    assert len(payload["runs"]) == 2
