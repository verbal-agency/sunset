"""Versioned contracts for pinned Git source and patch evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sunset.provenance_models import ArtifactRef


GIT_EVIDENCE_SCHEMA_VERSION = "1"
EvidenceKind = Literal["blob", "patch"]
EvidenceOutcome = Literal["available", "missing", "failed", "budget_exhausted", "unsupported"]


@dataclass(frozen=True, slots=True)
class GitEvidenceRequest:
    evidence_id: str
    repository_url: str
    commit_sha: str
    path: str | None
    kind: EvidenceKind
    max_bytes: int = 65_536

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "repository_url": self.repository_url,
            "commit_sha": self.commit_sha,
            "path": self.path,
            "kind": self.kind,
            "max_bytes": self.max_bytes,
        }


@dataclass(frozen=True, slots=True)
class GitEvidenceResponse:
    outcome: EvidenceOutcome
    summary: str
    source_locator: str
    byte_length: int = 0
    raw: bytes | None = None
    error_kind: str | None = None


@dataclass(frozen=True, slots=True)
class GitEvidenceReceipt:
    request: GitEvidenceRequest
    outcome: EvidenceOutcome
    summary: str
    source_locator: str
    artifact: ArtifactRef | None = None
    digest: str | None = None
    byte_length: int = 0
    provider: str = "recorded"
    freshness_key: str = "recorded-v1"
    error_kind: str | None = None
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "outcome": self.outcome,
            "summary": self.summary,
            "source_locator": self.source_locator,
            "artifact": self.artifact.to_dict() if self.artifact else None,
            "digest": self.digest,
            "byte_length": self.byte_length,
            "provider": self.provider,
            "freshness_key": self.freshness_key,
            "error_kind": self.error_kind,
            "non_authority": self.non_authority,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GitEvidenceReceipt":
        artifact = value.get("artifact")
        return cls(
            request=GitEvidenceRequest(**value["request"]),
            outcome=value["outcome"],
            summary=str(value["summary"]),
            source_locator=str(value["source_locator"]),
            artifact=ArtifactRef.from_dict(artifact) if artifact else None,
            digest=value.get("digest"),
            byte_length=int(value.get("byte_length", 0)),
            provider=str(value.get("provider", "recorded")),
            freshness_key=str(value.get("freshness_key", "recorded-v1")),
            error_kind=value.get("error_kind"),
            non_authority=bool(value.get("non_authority", True)),
        )


__all__ = [
    "EvidenceKind",
    "EvidenceOutcome",
    "GitEvidenceReceipt",
    "GitEvidenceRequest",
    "GitEvidenceResponse",
    "GIT_EVIDENCE_SCHEMA_VERSION",
]
