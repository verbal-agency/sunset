from __future__ import annotations

from pathlib import Path
import socket

from sunset.artifact_store import ArtifactStore
from sunset.investigation import InvestigationConfig, investigate_candidate
from sunset.scanner import scan_repository

from conftest import repository_snapshot, run_git


class CountingArtifactStore(ArtifactStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.read_count = 0

    def read(self, reference):
        self.read_count += 1
        return super().read(reference)


def _candidate_id(repository: Path) -> str:
    return scan_repository(repository).candidates[0].candidate_id


def test_interrupted_investigation_resumes_without_refetching_core_evidence(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store = CountingArtifactStore(tmp_path / "store")
    candidate_id = _candidate_id(renamed_repository)
    interrupted = investigate_candidate(
        renamed_repository,
        store_path=store.root,
        candidate_id=candidate_id,
        config=InvestigationConfig(interrupt_after="retrieve_core"),
        artifact_store=store,
    )
    reads_before_resume = store.read_count
    resumed = investigate_candidate(
        renamed_repository,
        store_path=store.root,
        candidate_id=candidate_id,
        artifact_store=store,
    )

    assert interrupted.status == "interrupted"
    assert resumed.status == "inconclusive"
    assert store.read_count == reads_before_resume
    assert resumed.run_id == interrupted.run_id
    assert {entry.kind for entry in resumed.ledger} >= {"fact", "inference", "unknown", "rejected_hypothesis"}
    assert all(usage.estimated for usage in resumed.token_usage)
    assert resumed.open_questions
    assert {item.source_kind for item in resumed.selected_evidence} == {"marker_source", "blame_commit_patch"}


def test_adaptive_history_is_selected_without_storing_raw_history(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "history-repository"
    (repository / "tests").mkdir(parents=True)
    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "sunset@example.test")
    run_git(repository, "config", "user.name", "Sunset Tests")
    (repository / "tests" / "test_history.py").write_text(
        "import pytest\n\n@pytest.mark.xfail\ndef test_history():\n    pass\n",
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "add marker without rationale cue")
    candidate_id = _candidate_id(repository)
    store = ArtifactStore(tmp_path / "store")
    result = investigate_candidate(
        repository,
        store_path=store.root,
        candidate_id=candidate_id,
        artifact_store=store,
    )

    assert result.status == "inconclusive"
    assert {item.source_kind for item in result.selected_evidence} == {
        "marker_source", "focused_history", "blame_commit_patch",
    }
    assert "add marker without rationale cue" not in result.to_json()
    checkpoint = store.read_view(result.checkpoint_id)
    assert checkpoint is not None
    assert b"add marker without rationale cue" not in checkpoint
    assert result.token_baseline.full_context_tokens > 0
    assert result.token_baseline.working_memory_tokens > 0


def test_budget_failure_is_structured_before_any_model_call(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    result = investigate_candidate(
        renamed_repository,
        store_path=tmp_path / "store",
        candidate_id=_candidate_id(renamed_repository),
        config=InvestigationConfig(max_input_tokens=1),
    )

    assert result.status == "error"
    assert result.errors[0].kind == "input_token_budget_exceeded"
    assert result.ledger
    assert result.token_usage


def test_changed_head_creates_new_investigation_run(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    first = investigate_candidate(
        renamed_repository, store_path=store.root, candidate_id=_candidate_id(renamed_repository), artifact_store=store
    )
    (renamed_repository / "README.md").write_text("# Changed\n", encoding="utf-8")
    run_git(renamed_repository, "add", "README.md")
    run_git(renamed_repository, "commit", "-qm", "change unrelated documentation")
    second = investigate_candidate(
        renamed_repository, store_path=store.root, candidate_id=_candidate_id(renamed_repository), artifact_store=store
    )

    assert first.repository_head != second.repository_head
    assert first.run_id != second.run_id
    assert second.status == "inconclusive"


def test_investigation_is_read_only_and_network_free(
    renamed_repository: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    status_before = run_git(renamed_repository, "status", "--porcelain=v1", "--untracked-files=all")
    contents_before = repository_snapshot(renamed_repository)

    def forbid_network(*args, **kwargs):
        raise AssertionError("investigation attempted to create a network socket")

    monkeypatch.setattr(socket, "socket", forbid_network)
    result = investigate_candidate(
        renamed_repository, store_path=tmp_path / "store", candidate_id=_candidate_id(renamed_repository)
    )

    assert result.status == "inconclusive"
    assert status_before == run_git(renamed_repository, "status", "--porcelain=v1", "--untracked-files=all")
    assert contents_before == repository_snapshot(renamed_repository)


def test_shallow_history_is_carried_into_the_investigation_ledger(
    shallow_repository: Path,
    tmp_path: Path,
) -> None:
    result = investigate_candidate(
        shallow_repository,
        store_path=tmp_path / "store",
        candidate_id=_candidate_id(shallow_repository),
    )

    assert result.status == "inconclusive"
    assert any(
        entry.kind == "unknown" and "shallow" in entry.statement
        for entry in result.ledger
    )
