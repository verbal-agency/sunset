from __future__ import annotations

import json
from pathlib import Path

import pytest

import sunset.agent_tools as agent_tools
from sunset.cli import main
from sunset.agent_tools import TOOL_NAMES
from sunset.scanner import scan_repository


def test_cli_reports_package_version(capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--version"])

    assert stopped.value.code == 0
    assert capsys.readouterr().out == "sunset 0.1.0\n"


def test_tools_cli_is_deterministic_and_context_free(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_tools.GitRepository,
        "open",
        lambda *args, **kwargs: pytest.fail("tool catalog opened a repository"),
    )
    monkeypatch.setattr(
        agent_tools.ArtifactStore,
        "read_view",
        lambda *args, **kwargs: pytest.fail("tool catalog accessed an artifact store"),
    )
    first_exit = main(["tools", "--format", "json"])
    first = capsys.readouterr().out
    second_exit = main(["tools", "--format", "json"])
    second = capsys.readouterr().out
    payload = json.loads(first)

    assert first_exit == second_exit == 0
    assert first == second
    assert payload["schema_version"] == "1"
    assert [item["name"] for item in payload["tools"]] == list(TOOL_NAMES)
    assert all(item["effect"]["network_access"] is False for item in payload["tools"])


def test_cli_emits_normalized_json_and_partial_failure_status(
    sample_repository: Path,
    capsys,
) -> None:
    exit_code = main(["scan", str(sample_repository), "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["schema_version"] == "1"
    assert len(payload["candidates"]) == 5
    assert payload["errors"] == [
        {
            "column": 16,
            "kind": "parse_error",
            "line": 1,
            "message": "'(' was never closed",
            "path": "tests/broken_test.py",
        }
    ]


def test_cli_reports_non_git_target_as_json(tmp_path: Path, capsys) -> None:
    exit_code = main(["scan", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["repository_head"] is None
    assert payload["candidates"] == []
    assert payload["errors"][0]["kind"] == "not_git_repository"


def test_provenance_cli_emits_cached_artifact_references(
    renamed_repository: Path,
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(
        [
            "provenance",
            str(renamed_repository),
            "--store",
            str(tmp_path / "store"),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "1"
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["artifacts"]
    assert payload["repository_identity"]["kind"] == "local_path_sha256"


def test_provenance_cli_rejects_store_inside_target(
    renamed_repository: Path,
    capsys,
) -> None:
    exit_code = main(
        [
            "provenance",
            str(renamed_repository),
            "--store",
            str(renamed_repository / ".sunset-artifacts"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["errors"][0]["kind"] == "artifact_store_inside_repository"


def test_compatibility_cli_and_provenance_selection(
    compatibility_repository: Path,
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(["collect", str(compatibility_repository), "--collector", "compatibility"])
    collection = json.loads(capsys.readouterr().out)
    provenance_exit = main(
        [
            "provenance", str(compatibility_repository), "--collector", "compatibility",
            "--store", str(tmp_path / "store"),
        ]
    )
    provenance = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert collection["collector"] == "compatibility"
    assert len(collection["candidates"]) == 6
    assert provenance_exit == 0
    assert len(provenance["candidates"]) == 6


def test_investigate_cli_emits_inconclusive_checkpointed_result(
    renamed_repository: Path,
    tmp_path: Path,
    capsys,
) -> None:
    candidate_id = scan_repository(renamed_repository).candidates[0].candidate_id
    exit_code = main(
        [
            "investigate", str(renamed_repository), "--candidate-id", candidate_id,
            "--store", str(tmp_path / "store"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "inconclusive"
    assert payload["checkpoint_id"]
    assert payload["token_usage"]


def test_investigate_cli_exposes_explicit_recorded_evidence_mode(
    renamed_repository: Path,
    tmp_path: Path,
    capsys,
) -> None:
    candidate_id = scan_repository(renamed_repository).candidates[0].candidate_id
    fixture = Path(__file__).parent / "fixtures" / "evidence" / "recorded_responses.json"
    exit_code = main(
        [
            "investigate", str(renamed_repository), "--candidate-id", candidate_id,
            "--store", str(tmp_path / "store"),
            "--evidence-mode", "recorded", "--recorded-evidence", str(fixture),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["assumption_status"] == "unknown"
    assert payload["status"] == "inconclusive"


def test_blame_evidence_fetch_cli_replays_recorded_line(capsys) -> None:
    fixture = Path("tests/fixtures/blame_evidence/openclaw-g27-blame-v1.json")
    exit_code = main([
        "blame-evidence", "fetch",
        "--fixture", str(fixture),
        "--repository", "https://github.com/openclaw/openclaw",
        "--commit", "0965053fe6b9341776df147a6934b7485c60b5ca",
        "--path", "ui/src/e2e/activity-run-inspector.e2e.test.ts",
        "--line", "22",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["outcome"] == "complete"
    assert payload["provenance_status"] == "complete"
    assert payload["introducing_commit"] == "7ab5d99a6c3c2bd72a23b08cb0a7a6ad7b68899d"


def test_blame_evidence_capture_cli_fails_closed_without_credential(tmp_path: Path, capsys) -> None:
    requests = tmp_path / "req.json"
    requests.write_text(json.dumps([
        {
            "subject_id": "s",
            "repository_url": "https://github.com/openclaw/openclaw",
            "commit_sha": "0965053fe6b9341776df147a6934b7485c60b5ca",
            "path": "ui/src/e2e/tool-titles.e2e.test.ts",
            "line": 199,
        }
    ]), encoding="utf-8")
    out = tmp_path / "out.json"
    exit_code = main([
        "blame-evidence", "capture",
        "--requests", str(requests),
        "--output-fixture", str(out),
        "--live",
        "--token-env", "SUNSET_DEFINITELY_UNSET_TOKEN",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert payload["receipts"][0]["error_kind"] == "credential_absent"
    assert not out.exists()
