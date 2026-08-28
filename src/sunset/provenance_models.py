"""Versioned, deterministic models for stored Git provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any


PROVENANCE_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    byte_length: int
    digest: str
    media_type: str
    source_kind: str
    source_locator: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ArtifactRef:
        return cls(
            artifact_id=str(value["artifact_id"]),
            byte_length=int(value["byte_length"]),
            digest=str(value["digest"]),
            media_type=str(value["media_type"]),
            source_kind=str(value["source_kind"]),
            source_locator=str(value["source_locator"]),
        )


@dataclass(frozen=True, slots=True)
class ProvenanceIssue:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProvenanceIssue:
        return cls(kind=str(value["kind"]), message=str(value["message"]))


@dataclass(frozen=True, slots=True)
class ProvenanceError:
    kind: str
    message: str
    candidate_id: str | None = None
    path: str | None = None
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CandidateProvenance:
    artifacts: tuple[ArtifactRef, ...]
    blame_commit: str
    candidate_id: str
    introduction_commit: str
    path: str
    repository_head: str
    uncertainties: tuple[ProvenanceIssue, ...]
    view_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "blame_commit": self.blame_commit,
            "candidate_id": self.candidate_id,
            "introduction_commit": self.introduction_commit,
            "path": self.path,
            "repository_head": self.repository_head,
            "uncertainties": [issue.to_dict() for issue in self.uncertainties],
            "view_id": self.view_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CandidateProvenance:
        return cls(
            artifacts=tuple(ArtifactRef.from_dict(item) for item in value["artifacts"]),
            blame_commit=str(value["blame_commit"]),
            candidate_id=str(value["candidate_id"]),
            introduction_commit=str(value["introduction_commit"]),
            path=str(value["path"]),
            repository_head=str(value["repository_head"]),
            uncertainties=tuple(
                ProvenanceIssue.from_dict(item) for item in value["uncertainties"]
            ),
            view_id=str(value["view_id"]),
        )

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"


@dataclass(frozen=True, slots=True)
class ProvenanceResult:
    candidates: tuple[CandidateProvenance, ...]
    errors: tuple[ProvenanceError, ...]
    repository_head: str | None
    repository_identity_kind: str | None
    repository_identity_value: str | None
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        repository_identity = None
        if self.repository_identity_kind is not None:
            repository_identity = {
                "kind": self.repository_identity_kind,
                "value": self.repository_identity_value,
            }
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "errors": [error.to_dict() for error in self.errors],
            "repository_head": self.repository_head,
            "repository_identity": repository_identity,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
