"""Deterministic local-Git provenance collection for scanner candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.git_repository import GitRepository, RepositoryError
from sunset.models import Candidate
from sunset.provenance_models import (
    CandidateProvenance,
    ProvenanceError,
    ProvenanceIssue,
    ProvenanceResult,
)
from sunset.provenance_providers import ArtifactStoreProvider, GitProvenanceProvider
from sunset.scanner import scan_repository


def collect_provenance(
    target: str | Path,
    *,
    store_path: str | Path,
    artifact_store: ArtifactStoreProvider | None = None,
) -> ProvenanceResult:
    """Collect and cache local Git provenance without modifying *target*."""

    repository = GitRepository.open(target)
    store: ArtifactStoreProvider = artifact_store or ArtifactStore(store_path)
    expected_store_root = Path(store_path).expanduser().resolve()
    if store.root != expected_store_root:
        raise ValueError("injected artifact store does not match store_path")
    _assert_store_is_external(repository, store)
    identity_kind, identity_value = repository.repository_identity()
    scan_result = scan_repository(target)

    errors = [
        ProvenanceError(
            kind=error.kind,
            message=error.message,
            path=error.path,
            line=error.line,
            column=error.column,
        )
        for error in scan_result.errors
    ]
    entries: list[CandidateProvenance] = []
    shallow = repository.is_shallow()

    for candidate in scan_result.candidates:
        try:
            entries.append(
                _collect_candidate(
                    repository,
                    store,
                    candidate,
                    identity_kind=identity_kind,
                    identity_value=identity_value,
                    shallow=shallow,
                )
            )
        except (ArtifactStoreError, RepositoryError, ValueError, KeyError, TypeError) as exc:
            errors.append(
                ProvenanceError(
                    kind=_error_code(exc),
                    message=str(exc),
                    candidate_id=candidate.candidate_id,
                    path=candidate.path,
                    line=candidate.line,
                    column=candidate.column,
                )
            )

    entries.sort(key=lambda item: (item.path, item.candidate_id))
    errors.sort(
        key=lambda item: (
            item.path or "",
            item.line if item.line is not None else -1,
            item.column if item.column is not None else -1,
            item.kind,
            item.candidate_id or "",
        )
    )
    return ProvenanceResult(
        candidates=tuple(entries),
        errors=tuple(errors),
        repository_head=repository.head,
        repository_identity_kind=identity_kind,
        repository_identity_value=identity_value,
    )


def _collect_candidate(
    repository: GitProvenanceProvider,
    store: ArtifactStoreProvider,
    candidate: Candidate,
    *,
    identity_kind: str,
    identity_value: str,
    shallow: bool,
) -> CandidateProvenance:
    view_id = _view_id(identity_kind, identity_value, candidate)
    cached = store.read_view(view_id)
    if cached is not None:
        entry = CandidateProvenance.from_dict(json.loads(cached))
        for artifact in entry.artifacts:
            store.read(artifact)
        return entry

    source = repository.read_bytes(candidate.path)
    history = repository.history_bytes(candidate.path)
    artifacts = [
        store.put(
            source,
            media_type="text/x-python",
            source_kind="marker_source",
            source_locator=f"git:{repository.head}:{candidate.path}",
        ),
        store.put(
            history,
            media_type="text/plain",
            source_kind="focused_history",
            source_locator=f"git:log:follow:{repository.head}:{candidate.path}",
        ),
    ]
    uncertainties: list[ProvenanceIssue] = []
    if shallow:
        uncertainties.append(
            ProvenanceIssue(
                kind="shallow_history",
                message="repository history is shallow; introduction evidence may be incomplete",
            )
        )
    if not history:
        uncertainties.append(
            ProvenanceIssue(
                kind="empty_history",
                message="Git returned no focused history for the candidate path",
            )
        )
    try:
        patch = repository.commit_patch_bytes(candidate.blame_commit, candidate.path)
    except RepositoryError:
        if not shallow:
            raise
        uncertainties.append(
            ProvenanceIssue(
                kind="missing_blame_commit_patch",
                message="shallow history does not contain the blame commit patch",
            )
        )
    else:
        artifacts.append(
            store.put(
                patch,
                media_type="text/x-patch",
                source_kind="blame_commit_patch",
                source_locator=f"git:show:{candidate.blame_commit}:{candidate.path}",
            )
        )

    entry = CandidateProvenance(
        artifacts=tuple(artifacts),
        blame_commit=candidate.blame_commit,
        candidate_id=candidate.candidate_id,
        introduction_commit=candidate.blame_commit,
        path=candidate.path,
        repository_head=repository.head,
        uncertainties=tuple(uncertainties),
        view_id=view_id,
    )
    store.put_view(view_id, entry.to_json().encode("utf-8"))
    return entry


def _assert_store_is_external(
    repository: GitProvenanceProvider,
    store: ArtifactStoreProvider,
) -> None:
    try:
        store.root.relative_to(repository.root)
    except ValueError:
        return
    raise RepositoryError(
        "artifact_store_inside_repository",
        "artifact store must be outside the analyzed repository",
    )


def _view_id(identity_kind: str, identity_value: str, candidate: Candidate) -> str:
    key = "\0".join(
        (
            "sunset-provenance-view-v1",
            identity_kind,
            identity_value,
            candidate.repository_head,
            candidate.candidate_id,
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _error_code(error: Exception) -> str:
    if isinstance(error, (ArtifactStoreError, RepositoryError)):
        return error.code
    if isinstance(error, json.JSONDecodeError):
        return "cached_view_decode_failed"
    return "provenance_decode_failed"
