from __future__ import annotations

from pathlib import Path
import socket

import pytest

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.git_repository import RepositoryError
from sunset.provenance import collect_provenance

from conftest import repository_snapshot, run_git


def test_collects_rename_aware_provenance(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    result = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )

    assert result.errors == ()
    assert result.repository_head == run_git(renamed_repository, "rev-parse", "HEAD")
    assert result.repository_identity_kind == "local_path_sha256"
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.path == "tests/test_markers.py"
    assert candidate.introduction_commit == run_git(
        renamed_repository,
        "rev-list",
        "--max-parents=0",
        "HEAD",
    )
    assert candidate.blame_commit == candidate.introduction_commit
    assert candidate.uncertainties == ()

    artifacts = {artifact.source_kind: artifact for artifact in candidate.artifacts}
    assert set(artifacts) == {
        "marker_source",
        "focused_history",
        "blame_commit_patch",
    }
    assert b"test_legacy.py" in store.read(artifacts["focused_history"])
    assert b"test_compatibility" in store.read(artifacts["marker_source"])
    assert all(artifact.artifact_id == f"sha256:{artifact.digest}" for artifact in artifacts.values())
    assert all(len(artifact.digest) == 64 for artifact in artifacts.values())


def test_repeated_collection_reuses_artifacts_and_view(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    first = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )
    first_artifact_writes = store.artifact_write_count
    first_view_writes = store.view_write_count

    second = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )

    assert first.to_json().encode("utf-8") == second.to_json().encode("utf-8")
    assert first_artifact_writes > 0
    assert store.artifact_write_count == first_artifact_writes
    assert store.view_write_count == first_view_writes


def test_configured_origin_is_used_without_contacting_it(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    run_git(
        renamed_repository,
        "remote",
        "add",
        "origin",
        "git@github.com:example/sunset-fixture.git",
    )

    result = collect_provenance(renamed_repository, store_path=tmp_path / "store")

    assert result.repository_identity_kind == "origin_remote"
    assert result.repository_identity_value == "git@github.com:example/sunset-fixture"


def test_changed_head_recomputes_view_and_reuses_immutable_artifacts(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    first = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )
    artifact_writes = store.artifact_write_count
    view_writes = store.view_write_count

    (renamed_repository / "README.md").write_text("# Changed\n", encoding="utf-8")
    run_git(renamed_repository, "add", "README.md")
    run_git(renamed_repository, "commit", "-qm", "change unrelated documentation")

    second = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )

    assert first.repository_head != second.repository_head
    assert first.candidates[0].view_id != second.candidates[0].view_id
    assert store.artifact_write_count == artifact_writes
    assert store.view_write_count == view_writes + 1


def test_artifact_integrity_failure_is_detected(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    result = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )
    source = next(
        artifact
        for artifact in result.candidates[0].artifacts
        if artifact.source_kind == "marker_source"
    )
    store.artifact_path(source).write_bytes(b"corrupted artifact")

    with pytest.raises(ArtifactStoreError, match="failed digest verification"):
        store.read(source)

    recollected = collect_provenance(
        renamed_repository,
        store_path=store.root,
        artifact_store=store,
    )
    assert recollected.candidates == ()
    assert recollected.errors[0].kind == "artifact_integrity_error"


def test_shallow_history_retains_source_evidence_with_uncertainty(
    shallow_repository: Path,
    tmp_path: Path,
) -> None:
    result = collect_provenance(shallow_repository, store_path=tmp_path / "store")

    assert result.errors == ()
    assert len(result.candidates) == 1
    uncertainty_kinds = {issue.kind for issue in result.candidates[0].uncertainties}
    assert "shallow_history" in uncertainty_kinds
    assert any(
        artifact.source_kind == "marker_source"
        for artifact in result.candidates[0].artifacts
    )


def test_provenance_does_not_mutate_target_or_use_network(
    sample_repository: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    status_before = run_git(sample_repository, "status", "--porcelain=v1", "--untracked-files=all")
    contents_before = repository_snapshot(sample_repository)

    def forbid_network(*args, **kwargs):
        raise AssertionError("provenance collection attempted to create a network socket")

    monkeypatch.setattr(socket, "socket", forbid_network)
    result = collect_provenance(sample_repository, store_path=tmp_path / "store")

    assert len(result.candidates) == 5
    assert result.errors[0].kind == "parse_error"
    assert status_before == run_git(
        sample_repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    assert contents_before == repository_snapshot(sample_repository)


def test_store_inside_target_repository_is_rejected(
    renamed_repository: Path,
) -> None:
    with pytest.raises(RepositoryError) as error:
        collect_provenance(
            renamed_repository,
            store_path=renamed_repository / ".sunset-artifacts",
        )

    assert error.value.code == "artifact_store_inside_repository"
