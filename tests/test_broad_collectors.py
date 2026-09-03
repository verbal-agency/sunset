from __future__ import annotations

from pathlib import Path

import sunset.broad_collectors as broad_collectors
from sunset.broad_collectors import discover_broad_repository, enrich_broad_provenance, scan_broad_repository
from sunset.git_repository import GitRepository

from conftest import repository_snapshot, run_git


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "broad-repository"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "src" / "legacy.py").write_text(
        "import os\n\nif os.getenv('SUNSET_FLAG'):\n    use_legacy()\n\nimport warnings\nwarnings.warn('old API', DeprecationWarning)\n\nif os.getenv(dynamic_name):\n    use_dynamic()\n",
        encoding="utf-8",
    )
    (repo / "tests" / "legacy.test.ts").write_text(
        "if (process.env.SUNSET_FLAG) { useLegacy(); }\nif (button.isEnabled()) { useLegacy(); }\n/** @deprecated use modern */\nexport function oldApi() {}\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text("requires-python = \">=3.11\"\n", encoding="utf-8")
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "sunset@example.test")
    run_git(repo, "config", "user.name", "Sunset Tests")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-qm", "add broad signal fixtures")
    return repo


def test_discovers_repository_and_javascript_temporal_signals(tmp_path: Path) -> None:
    result = scan_broad_repository(_repository(tmp_path))
    assert result.errors == ()
    signals = {candidate.signal for candidate in result.candidates}
    assert {"environment_gate", "deprecation_annotation", "support_constraint"} <= signals
    assert {candidate.language for candidate in result.candidates} >= {"python", "typescript"}
    assert all(candidate.candidate_id.startswith("sunset-broad-v2-") for candidate in result.candidates)
    assert all(len(candidate.blame_commit) == 40 for candidate in result.candidates)
    assert not any(candidate.signal == "feature_flag_lifecycle" and "isEnabled" in (candidate.condition or "") for candidate in result.candidates)


def test_discovery_defers_history_and_enrichment_batches_by_file(tmp_path: Path, monkeypatch) -> None:
    repo = _repository(tmp_path)
    broad_collectors._BLAME_CACHE.clear()
    calls: list[str] = []
    original = GitRepository.blame_file

    def counted(self: GitRepository, path: str):
        calls.append(path)
        return original(self, path)

    monkeypatch.setattr(GitRepository, "blame_file", counted)
    discovered = discover_broad_repository(repo)
    assert discovered.provenance_mode == "deferred"
    assert discovered.candidates and all(item.provenance_status == "deferred" for item in discovered.candidates)
    assert all(item.blame_commit == "" for item in discovered.candidates)
    assert calls == []

    enriched = enrich_broad_provenance(repo, discovered)
    assert enriched.provenance_mode == "complete"
    assert all(item.provenance_status == "complete" for item in enriched.candidates)
    assert len(calls) == len({item.path for item in discovered.candidates})

    calls.clear()
    replay = enrich_broad_provenance(repo, discovered)
    assert replay.to_json() == enriched.to_json()
    assert calls == []


def test_dynamic_forms_are_explicit_and_committed_snapshot_only(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    before = repository_snapshot(repo)
    first = scan_broad_repository(repo)
    (repo / "src" / "untracked.py").write_text("@deprecated\n", encoding="utf-8")
    second = scan_broad_repository(repo)
    dynamic = [item for item in first.candidates if item.condition and "dynamic_name" in item.condition]
    assert dynamic and dynamic[0].unsupported_dynamic is True
    assert first.to_json() == second.to_json()
    after = repository_snapshot(repo)
    assert before == {key: value for key, value in after.items() if key != "src/untracked.py"}
