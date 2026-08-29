"""Additive, versioned models for deterministic compatibility candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from sunset.models import ScanError


COMPATIBILITY_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """An inclusive, repository-relative Python source span."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True, slots=True)
class CompatibilityCandidate:
    """A syntactic compatibility lead, never a removal recommendation."""

    candidate_id: str
    candidate_kind: str
    path: str
    line: int
    column: int
    condition: str | None
    comparator: str | None
    subject: str | None
    threshold: str | None
    guard_span: SourceSpan
    protected_span: SourceSpan
    fallback_span: SourceSpan | None
    protected_imports: tuple[str, ...]
    fallback_imports: tuple[str, ...]
    repository_head: str
    blame_commit: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CompatibilityScanResult:
    """Normalized result from the compatibility collector family."""

    repository_head: str | None
    candidates: tuple[CompatibilityCandidate, ...] = ()
    errors: tuple[ScanError, ...] = ()
    schema_version: str = COMPATIBILITY_SCHEMA_VERSION
    collector: str = "compatibility"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "collector": self.collector,
            "errors": [error.to_dict() for error in self.errors],
            "repository_head": self.repository_head,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
