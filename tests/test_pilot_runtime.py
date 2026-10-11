from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.natural_corpus import load_environment_recipes
from sunset.pilot_models import PilotRequest
from sunset.pilot_runtime import LivePilotBackend, PilotRuntimeError, RuntimePolicy
from sunset.validation_models import CommandExecution


FIXTURES = Path(__file__).parent / "fixtures"
PILOT = FIXTURES / "pilot"


def _recipe_file(tmp_path: Path, repository_url: str, ref: str) -> Path:
    value = {
        "schema_version": "2",
        "environments": [
            {
                "environment_id": "fixture-py-v1",
                "repository_url": repository_url,
                "pinned_ref": ref,
                "python": "CPython fixture",
                "install_commands": [["python", "-m", "pip", "install", "-e", "."]],
                "test_command": ["python", "-m", "pytest", "{candidate_path}::{test}"],
                "dependency_digest": hashlib.sha256(b"fixture-dependencies").hexdigest(),
                "packages": {"pytest": "fixture"},
                "budgets": {"max_network_bytes": 1, "max_packages": 4, "timeout_seconds": 30},
            }
        ],
    }
    path = tmp_path / "environment.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _request(repository_url: str, ref: str, *, validation: bool = False) -> PilotRequest:
    return PilotRequest(
        repository_url,
        ref,
        "tests",
        "test_markers.py",
        "test_expected_failure",
        mode="live",
        validation_requested=validation,
    )


def _runner(command: tuple[str, ...], cwd: Path, timeout: int) -> CommandExecution:
    # Clone, checkout, and Git evidence are real; dependency installation is
    # recorded but not performed in this fixture because the source has no
    # package metadata and the project venv already supplies pytest.
    if "-m" in command and "pip" in command and "install" in command:
        return CommandExecution(0, b"", b"fixture install recorded")
    result = subprocess.run(command, cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return CommandExecution(result.returncode, result.stderr, result.stdout)


def test_exact_sha_checkout_and_fail_closed_refs(sample_repository: Path, tmp_path: Path) -> None:
    head = subprocess.check_output(("git", "-C", str(sample_repository), "rev-parse", "HEAD"), text=True).strip()
    request = _request("https://github.com/example/fixture", head)
    backend = LivePilotBackend(
        environment_path=_recipe_file(tmp_path, request.repository_url, head),
        store=ArtifactStore(tmp_path / "store"),
        policy=RuntimePolicy(source_checkout=sample_repository, python_executable=sys.executable, network_enabled=True),
        command_runner=_runner,
    )
    preparation = backend.prepare(request)
    assert preparation.repository_head == head
    assert preparation.setup_receipt.checkout["observed_head"] == head
    assert preparation.setup_receipt.checkout["snapshot_digest"]
    with pytest.raises(ValueError, match="full 40-character"):
        replace(request, repository_ref="main")


def test_recipe_selection_and_isolated_install_receipt(sample_repository: Path, tmp_path: Path) -> None:
    head = subprocess.check_output(("git", "-C", str(sample_repository), "rev-parse", "HEAD"), text=True).strip()
    request = _request("https://github.com/example/fixture", head)
    store = ArtifactStore(tmp_path / "store")
    backend = LivePilotBackend(
        environment_path=_recipe_file(tmp_path, request.repository_url, head),
        store=store,
        policy=RuntimePolicy(source_checkout=sample_repository, python_executable=sys.executable, network_enabled=True),
        command_runner=_runner,
    )
    preparation = backend.prepare(request)
    assert preparation.setup_receipt.environment["environment_id"] == "fixture-py-v1"
    assert preparation.setup_receipt.environment["dependency_digest"]
    assert len(preparation.artifact_ids) == 2
    assert store.read_artifact_id(preparation.artifact_ids[0])
    assert load_environment_recipes(_recipe_file(tmp_path, request.repository_url, head))["fixture-py-v1"]


def test_network_and_recipe_authority_fail_closed(tmp_path: Path) -> None:
    ref = "0" * 40
    request = _request("https://github.com/example/fixture", ref)
    backend = LivePilotBackend(
        environment_path=_recipe_file(tmp_path, request.repository_url, ref),
        store=ArtifactStore(tmp_path / "store"),
        policy=RuntimePolicy(network_enabled=False),
    )
    with pytest.raises(PilotRuntimeError, match="network"):
        backend.prepare(request)
    denied = _request("https://evil.example/fixture", ref)
    denied_backend = LivePilotBackend(
        environment_path=_recipe_file(tmp_path, denied.repository_url, ref),
        store=ArtifactStore(tmp_path / "denied"),
        policy=RuntimePolicy(network_enabled=True),
    )
    with pytest.raises(PilotRuntimeError, match="allowlist"):
        denied_backend.prepare(denied)
