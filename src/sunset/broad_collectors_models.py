"""Language-neutral contracts for bounded repository-level candidate discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

BROAD_COLLECTOR_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class BroadCandidate:
    candidate_id: str
    candidate_family: str
    language: str
    path: str
    line: int
    column: int
    signal: str
    subject: str | None
    condition: str | None
    evidence_role: str
    repository_head: str
    blame_commit: str
    unsupported_dynamic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BroadScanResult:
    repository_head: str | None
    candidates: tuple[BroadCandidate, ...] = ()
    errors: tuple[dict[str, Any], ...] = ()
    schema_version: str = BROAD_COLLECTOR_SCHEMA_VERSION
    collector: str = "broad"

    def to_dict(self) -> dict[str, Any]:
        return {"candidates": [item.to_dict() for item in self.candidates], "collector": self.collector, "errors": [dict(item) for item in self.errors], "repository_head": self.repository_head, "schema_version": self.schema_version}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = ["BROAD_COLLECTOR_SCHEMA_VERSION", "BroadCandidate", "BroadScanResult"]
