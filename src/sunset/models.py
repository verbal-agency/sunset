"""Versioned domain objects for deterministic candidate discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any


SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class Candidate:
    """One pytest marker that may eventually warrant an investigation."""

    candidate_id: str
    marker_kind: str
    path: str
    line: int
    column: int
    qualified_name: str
    reason: str | None
    condition: str | None
    repository_head: str
    blame_commit: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScanError:
    """A structured failure that does not fabricate missing scan data."""

    kind: str
    path: str
    message: str
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Normalized output from one repository scan."""

    repository_head: str | None
    candidates: tuple[Candidate, ...] = ()
    errors: tuple[ScanError, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "errors": [error.to_dict() for error in self.errors],
            "repository_head": self.repository_head,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        """Return byte-stable, human-readable JSON terminated by one newline."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"

