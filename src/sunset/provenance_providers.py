"""Structural boundaries for replaceable provenance and storage adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sunset.provenance_models import ArtifactRef


class GitProvenanceProvider(Protocol):
    """Read-only committed-Git evidence needed by provenance collection."""

    root: Path
    head: str

    def read_bytes(self, path: str) -> bytes: ...

    def history_bytes(self, path: str, *, max_count: int = 25) -> bytes: ...

    def commit_patch_bytes(self, commit: str, path: str) -> bytes: ...

    def repository_identity(self) -> tuple[str, str]: ...

    def is_shallow(self) -> bool: ...


class ArtifactStoreProvider(Protocol):
    """Persistence boundary for immutable evidence and derived views."""

    root: Path

    def put(
        self,
        data: bytes,
        *,
        media_type: str,
        source_kind: str,
        source_locator: str,
    ) -> ArtifactRef: ...

    def read(self, reference: ArtifactRef) -> bytes: ...

    def put_view(self, view_id: str, data: bytes) -> None: ...

    def read_view(self, view_id: str) -> bytes | None: ...
