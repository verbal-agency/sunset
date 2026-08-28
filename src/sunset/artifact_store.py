"""A small, local content-addressed store for raw provenance evidence."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile

from sunset.provenance_models import ArtifactRef


class ArtifactStoreError(RuntimeError):
    """A stable error for store integrity and persistence failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ArtifactStore:
    """Stores immutable artifact bytes by SHA-256 and cached JSON views by key."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.artifact_write_count = 0
        self.view_write_count = 0

    def put(
        self,
        data: bytes,
        *,
        media_type: str,
        source_kind: str,
        source_locator: str,
    ) -> ArtifactRef:
        digest = hashlib.sha256(data).hexdigest()
        path = self._artifact_path_for_digest(digest)
        if path.exists():
            self._verify_bytes(path, digest)
        else:
            self._atomic_write(path, data)
            self.artifact_write_count += 1
        return ArtifactRef(
            artifact_id=f"sha256:{digest}",
            byte_length=len(data),
            digest=digest,
            media_type=media_type,
            source_kind=source_kind,
            source_locator=source_locator,
        )

    def read(self, reference: ArtifactRef) -> bytes:
        path = self._artifact_path_for_digest(reference.digest)
        if not path.exists():
            raise ArtifactStoreError(
                "artifact_missing",
                f"artifact {reference.artifact_id} is not present in the store",
            )
        return self._verify_bytes(path, reference.digest)

    def put_view(self, view_id: str, data: bytes) -> None:
        path = self.root / "views" / f"{view_id}.json"
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                raise ArtifactStoreError(
                    "view_conflict",
                    f"cached view {view_id} does not match deterministic output",
                )
            return
        self._atomic_write(path, data)
        self.view_write_count += 1

    def read_view(self, view_id: str) -> bytes | None:
        path = self.root / "views" / f"{view_id}.json"
        return path.read_bytes() if path.exists() else None

    def artifact_path(self, reference: ArtifactRef) -> Path:
        """Expose an artifact location for integrity-focused tests and tools."""

        return self._artifact_path_for_digest(reference.digest)

    def _artifact_path_for_digest(self, digest: str) -> Path:
        return self.root / "artifacts" / "sha256" / digest

    def _verify_bytes(self, path: Path, expected_digest: str) -> bytes:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ArtifactStoreError(
                "artifact_read_failed",
                f"unable to read artifact {expected_digest}: {exc.strerror or exc}",
            ) from exc
        actual_digest = hashlib.sha256(data).hexdigest()
        if actual_digest != expected_digest:
            raise ArtifactStoreError(
                "artifact_integrity_error",
                f"artifact sha256:{expected_digest} failed digest verification",
            )
        return data

    def _atomic_write(self, path: Path, data: bytes) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".sunset-",
                dir=path.parent,
            )
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_path, path)
            finally:
                if temporary_path.exists():
                    temporary_path.unlink()
        except OSError as exc:
            raise ArtifactStoreError(
                "artifact_write_failed",
                f"unable to write Sunset store: {exc.strerror or exc}",
            ) from exc
