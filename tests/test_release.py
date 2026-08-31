from __future__ import annotations

import json
from pathlib import Path
import shutil
import socket

import pytest

from sunset.cli import main
from sunset.release import ReleaseEvidenceError, validate_public_run


ROOT = Path(__file__).parents[1]
PUBLIC_RUN = ROOT / "docs" / "releases" / "G09-public-run.json"
DEMO = ROOT / "tests" / "fixtures" / "release_demo"


def test_public_run_manifest_verifies_pinned_saved_outputs() -> None:
    manifest = validate_public_run(PUBLIC_RUN)
    scan = json.loads((PUBLIC_RUN.parent / "G09-langgraph-scan.json").read_text())
    investigation = json.loads(
        (PUBLIC_RUN.parent / "G09-langgraph-investigation.json").read_text()
    )

    assert manifest["repository"] == {
        "name": "langgraph",
        "pinned_head": "11ee185999b86bfea2d8c0e69cef9a5e37acf686",
        "target": "libs/langgraph/tests",
        "url": "https://github.com/langchain-ai/langgraph.git",
    }
    assert len(scan["candidates"]) == 11
    assert scan["errors"] == []
    assert investigation["status"] == "inconclusive"
    assert investigation["assumption_status"] == "unknown"
    assert manifest["safety"]["tree_before"] == manifest["safety"]["tree_after"]
    assert manifest["safety"]["target_code_installed"] is False
    assert manifest["safety"]["target_code_executed"] is False


def test_public_run_validator_rejects_changed_output(tmp_path: Path) -> None:
    release = tmp_path / "release"
    shutil.copytree(PUBLIC_RUN.parent, release)
    scan_path = release / "G09-langgraph-scan.json"
    scan_path.write_text(scan_path.read_text() + " ", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError) as failure:
        validate_public_run(release / PUBLIC_RUN.name)

    assert failure.value.code == "public_run_output_digest_mismatch"


def test_release_check_cli_is_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def no_network(*args, **kwargs):
        raise AssertionError("release evidence validation must remain offline")

    monkeypatch.setattr(socket, "socket", no_network)
    exit_code = main(["release-check", "--manifest", str(PUBLIC_RUN)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["result_statuses"] == {
        "investigation": "inconclusive",
        "scan": "success",
    }


def test_committed_demo_produces_eligible_and_inconclusive_without_network(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    def no_network(*args, **kwargs):
        raise AssertionError("recorded demo must remain offline")

    monkeypatch.setattr(socket, "socket", no_network)
    eligible_exit = main(
        [
            "casefile",
            "--investigation-result", str(DEMO / "expired-investigation.json"),
            "--validation-result", str(DEMO / "confirmed-validation.json"),
            "--store", str(DEMO / "store"),
        ]
    )
    eligible = json.loads(capsys.readouterr().out)
    inconclusive_exit = main(
        [
            "casefile",
            "--investigation-result", str(DEMO / "unknown-investigation.json"),
            "--store", str(DEMO / "store"),
        ]
    )
    inconclusive = json.loads(capsys.readouterr().out)

    assert eligible_exit == 0
    assert eligible["recommendation"] == "eligible_for_human_cleanup"
    assert "human must decide" in eligible["confidence_boundary"]
    assert inconclusive_exit == 0
    assert inconclusive["recommendation"] == "inconclusive"


def test_release_documentation_covers_required_boundaries() -> None:
    release = (ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    safety = (ROOT / "docs" / "SAFETY.md").read_text(encoding="utf-8")
    demo = (ROOT / "docs" / "DEMO.md").read_text(encoding="utf-8")
    public = (ROOT / "docs" / "PUBLIC-RUN.md").read_text(encoding="utf-8")
    combined = "\n".join((release, safety, demo, public)).lower()

    for required in (
        "artifacts/sha256/",
        "checkpoint",
        "--evidence-mode live",
        "--approve",
        "host permissions",
        "human",
        "no telemetry",
        "manually adjudicated",
        "historical removals",
        "target code was not",
        "inconclusive",
    ):
        assert required in combined
