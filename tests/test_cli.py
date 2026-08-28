from __future__ import annotations

import json
from pathlib import Path

from sunset.cli import main


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

