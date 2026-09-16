"""Versioned contracts for authenticated exact-SHA line-blame evidence.

Blame evidence answers one narrow question: which commit introduced a specific
line at a specific committed head. It is deliberately separate from the G22
source/patch evidence provider. A result is either ``complete`` (an
authenticated exact-SHA blame resolved the line to a commit) or it carries an
``incomplete`` provenance status; the pipeline must never treat a non-``complete``
outcome as a historical fact, and must never emit a guessed commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

BLAME_EVIDENCE_SCHEMA_VERSION = "1"
BLAME_CAPTURE_SCHEMA_VERSION = "1"

BlameOutcome = Literal["complete", "missing", "incomplete", "unsupported", "failed"]
BlameProvenanceStatus = Literal["complete", "incomplete"]
BlameCaptureStatus = Literal["verified", "partial", "blocked"]


def provenance_status_for(outcome: BlameOutcome) -> BlameProvenanceStatus:
    """Only a ``complete`` outcome establishes provenance; all else is incomplete."""

    return "complete" if outcome == "complete" else "incomplete"


@dataclass(frozen=True, slots=True)
class BlameRequest:
    subject_id: str
    repository_url: str
    commit_sha: str
    path: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "repository_url": self.repository_url,
            "commit_sha": self.commit_sha,
            "path": self.path,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class BlameResponse:
    outcome: BlameOutcome
    summary: str
    source_locator: str
    introducing_commit: str | None = None
    committed_date: str | None = None
    message_headline: str | None = None
    error_kind: str | None = None

    @property
    def provenance_status(self) -> BlameProvenanceStatus:
        return provenance_status_for(self.outcome)


@dataclass(frozen=True, slots=True)
class BlameReceipt:
    request: BlameRequest
    outcome: BlameOutcome
    provenance_status: BlameProvenanceStatus
    summary: str
    source_locator: str
    introducing_commit: str | None = None
    committed_date: str | None = None
    message_headline: str | None = None
    provider: str = "recorded-blame"
    freshness_key: str = "recorded-v1"
    error_kind: str | None = None
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "outcome": self.outcome,
            "provenance_status": self.provenance_status,
            "summary": self.summary,
            "source_locator": self.source_locator,
            "introducing_commit": self.introducing_commit,
            "committed_date": self.committed_date,
            "message_headline": self.message_headline,
            "provider": self.provider,
            "freshness_key": self.freshness_key,
            "error_kind": self.error_kind,
            "non_authority": self.non_authority,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BlameReceipt":
        return cls(
            request=BlameRequest(**value["request"]),
            outcome=value["outcome"],
            provenance_status=value.get("provenance_status", provenance_status_for(value["outcome"])),
            summary=str(value["summary"]),
            source_locator=str(value["source_locator"]),
            introducing_commit=value.get("introducing_commit"),
            committed_date=value.get("committed_date"),
            message_headline=value.get("message_headline"),
            provider=str(value.get("provider", "recorded-blame")),
            freshness_key=str(value.get("freshness_key", "recorded-v1")),
            error_kind=value.get("error_kind"),
            non_authority=bool(value.get("non_authority", True)),
        )


@dataclass(frozen=True, slots=True)
class BlameCaptureReport:
    provider: str
    receipts: tuple[BlameReceipt, ...]
    fixture_digest: str | None
    request_count: int
    complete_count: int
    status: BlameCaptureStatus
    schema_version: str = BLAME_CAPTURE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "receipts": [item.to_dict() for item in self.receipts],
            "fixture_digest": self.fixture_digest,
            "request_count": self.request_count,
            "complete_count": self.complete_count,
            "status": self.status,
            "non_authority": True,
        }


__all__ = [
    "BLAME_CAPTURE_SCHEMA_VERSION",
    "BLAME_EVIDENCE_SCHEMA_VERSION",
    "BlameCaptureReport",
    "BlameCaptureStatus",
    "BlameOutcome",
    "BlameProvenanceStatus",
    "BlameReceipt",
    "BlameRequest",
    "BlameResponse",
    "provenance_status_for",
]
