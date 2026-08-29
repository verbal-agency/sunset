from __future__ import annotations

import json
from pathlib import Path

from sunset.cli import main
from sunset.scanner import scan_repository


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
