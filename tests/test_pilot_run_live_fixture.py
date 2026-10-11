from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from sunset.artifact_store import ArtifactStore
from sunset.pilot_models import PilotRequest
from sunset.pilot_runtime import LivePilotBackend, RuntimePolicy
from sunset.pilot_service import PilotService
from sunset.validation_models import CommandExecution


def _recipe(tmp_path: Path, url: str, ref: str) -> Path:
    value = {
        "schema_version": "2",
        "environments": [{
            "environment_id": "fixture-py-v1",
            "repository_url": url,
            "pinned_ref": ref,
            "python": "CPython fixture",
            "install_commands": [["python", "-m", "pip", "install", "-e", "."]],
            "test_command": ["python", "-m", "pytest", "{candidate_path}::{test}"],
            "dependency_digest": hashlib.sha256(b"fixture-dependencies").hexdigest(),
            "packages": {"pytest": "fixture"},
            "budgets": {"max_network_bytes": 1, "max_packages": 4, "timeout_seconds": 30},
        }],
    }
    path = tmp_path / "environment.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _runner(command: tuple[str, ...], cwd: Path, timeout: int) -> CommandExecution:
    if "-m" in command and "pip" in command and "install" in command:
        return CommandExecution(0, b"", b"fixture install recorded")
    result = subprocess.run(command, cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return CommandExecution(result.returncode, result.stderr, result.stdout)


def test_single_request_drives_real_pipeline(sample_repository: Path, tmp_path: Path) -> None:
    head = subprocess.check_output(("git", "-C", str(sample_repository), "rev-parse", "HEAD"), text=True).strip()
    request = PilotRequest(
        "https://github.com/example/fixture",
        head,
        "tests",
        "test_markers.py",
        "test_expected_failure",
        mode="live",
        validation_requested=True,
    )
    store = ArtifactStore(tmp_path / "store")
    backend = LivePilotBackend(
        environment_path=_recipe(tmp_path, request.repository_url, head),
        store=store,
        policy=RuntimePolicy(source_checkout=sample_repository, python_executable=str(Path(".venv/bin/python").resolve()), network_enabled=True),
        command_runner=_runner,
    )
    before = {path.relative_to(sample_repository).as_posix(): path.read_bytes() for path in sample_repository.rglob("*") if path.is_file() and ".git" not in path.parts}
    service = PilotService(backend, store=store)
    pending = service.run(request)
    assert pending.status == "approval_required"
    assert pending.setup_receipt is not None
    assert pending.evidence_ids
    assert pending.approval is not None
    terminal = service.approve(pending.run_id, pending.approval.token, decision="approve")
    assert terminal.status in {"completed", "inconclusive", "environment_error", "unvalidatable"}
    after = {path.relative_to(sample_repository).as_posix(): path.read_bytes() for path in sample_repository.rglob("*") if path.is_file() and ".git" not in path.parts}
    assert after == before
    assert terminal.case_file is not None
    assert terminal.case_file.non_authority is True
