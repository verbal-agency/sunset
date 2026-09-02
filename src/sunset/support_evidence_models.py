"""Versioned contracts for declared-support evidence supplements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sunset.provenance_models import ArtifactRef


SUPPORT_EVIDENCE_SCHEMA_VERSION = "1"
SupportSourceKind = Literal["public_git", "public_registry"]
SupportEvidenceClass = Literal[
    "packaging_metadata",
    "published_artifact",
    "ci_support",
    "support_documentation",
    "dependency_marker",
]
SupportEntryStatus = Literal["capture", "not_applicable"]
SupportOutcome = Literal[
    "available", "missing", "failed", "budget_exhausted", "unsupported", "not_applicable"
]
SupportCaptureStatus = Literal["verified", "partial", "blocked"]


@dataclass(frozen=True, slots=True)
class SupportEvidenceEntry:
    case_id: str
    evidence_id: str
    status: SupportEntryStatus
    evidence_class: SupportEvidenceClass
    description: str
    source_kind: SupportSourceKind | None = None
    locator: str | None = None
    commit_sha: str | None = None
    path: str | None = None
    release_identity: str | None = None
    freshness_scope: str | None = None
    reason: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SupportEvidenceEntry":
        allowed = {
            "case_id", "evidence_id", "status", "evidence_class", "description",
            "source_kind", "locator", "commit_sha", "path", "release_identity",
            "freshness_scope", "reason",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown support evidence field: {sorted(unknown)[0]}")
        return cls(
            case_id=str(value["case_id"]),
            evidence_id=str(value["evidence_id"]),
            status=value["status"],
            evidence_class=value["evidence_class"],
            description=str(value["description"]),
            source_kind=value.get("source_kind"),
            locator=str(value["locator"]) if value.get("locator") is not None else None,
            commit_sha=str(value["commit_sha"]) if value.get("commit_sha") is not None else None,
            path=str(value["path"]) if value.get("path") is not None else None,
            release_identity=str(value["release_identity"]) if value.get("release_identity") is not None else None,
            freshness_scope=str(value["freshness_scope"]) if value.get("freshness_scope") is not None else None,
            reason=str(value["reason"]) if value.get("reason") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "case_id": self.case_id,
            "evidence_id": self.evidence_id,
            "status": self.status,
            "evidence_class": self.evidence_class,
            "description": self.description,
        }
        for key in ("source_kind", "locator", "commit_sha", "path", "release_identity", "freshness_scope", "reason"):
            item = getattr(self, key)
            if item is not None:
                value[key] = item
        return value


@dataclass(frozen=True, slots=True)
class SupportEvidenceCase:
    case_id: str
    candidate_path: str
    entries: tuple[SupportEvidenceEntry, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SupportEvidenceCase":
        return cls(
            case_id=str(value["case_id"]),
            candidate_path=str(value["candidate_path"]),
            entries=tuple(SupportEvidenceEntry.from_dict(item) for item in value["entries"]),
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "case_id": self.case_id,
            "candidate_path": self.candidate_path,
            "entries": [item.to_dict() for item in self.entries],
        }


@dataclass(frozen=True, slots=True)
class SupportEvidenceSelection:
    supplement_id: str
    schema_version: str
    selection_status: str
    owner_approval_required: bool
    g21_manifest_id: str
    g21_manifest_digest: str
    repository: str
    repository_url: str
    pinned_head: str
    published_release: dict[str, str]
    cases: tuple[SupportEvidenceCase, ...]
    selection_basis: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SupportEvidenceSelection":
        return cls(
            supplement_id=str(value["supplement_id"]),
            schema_version=str(value.get("schema_version", SUPPORT_EVIDENCE_SCHEMA_VERSION)),
            selection_status=str(value.get("selection_status", "proposed")),
            owner_approval_required=bool(value.get("owner_approval_required", True)),
            g21_manifest_id=str(value["g21_manifest_id"]),
            g21_manifest_digest=str(value["g21_manifest_digest"]),
            repository=str(value["repository"]),
            repository_url=str(value["repository_url"]),
            pinned_head=str(value["pinned_head"]),
            published_release={str(k): str(v) for k, v in dict(value.get("published_release", {})).items()},
            cases=tuple(SupportEvidenceCase.from_dict(item) for item in value["cases"]),
            selection_basis=str(value["selection_basis"]) if value.get("selection_basis") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "supplement_id": self.supplement_id,
            "schema_version": self.schema_version,
            "selection_status": self.selection_status,
            "owner_approval_required": self.owner_approval_required,
            "g21_manifest_id": self.g21_manifest_id,
            "g21_manifest_digest": self.g21_manifest_digest,
            "repository": self.repository,
            "repository_url": self.repository_url,
            "pinned_head": self.pinned_head,
            "published_release": dict(self.published_release),
            "cases": [item.to_dict() for item in self.cases],
        }
        if self.selection_basis is not None:
            value["selection_basis"] = self.selection_basis
        return value


@dataclass(frozen=True, slots=True)
class SupportEvidenceReceipt:
    entry: SupportEvidenceEntry
    outcome: SupportOutcome
    summary: str
    source_locator: str | None
    artifact: ArtifactRef | None = None
    digest: str | None = None
    byte_length: int = 0
    provider: str = "recorded-support"
    freshness_key: str = "recorded-v1"
    error_kind: str | None = None
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
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


@dataclass(frozen=True, slots=True)
class SupportCaptureDiagnostic:
    phase: str
    error_kind: str
    message: str
    host: str | None = None
    status_code: int | None = None
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "error_kind": self.error_kind,
            "message": self.message,
            "host": self.host,
            "status_code": self.status_code,
            "non_authority": self.non_authority,
        }


@dataclass(frozen=True, slots=True)
class SupportEvidenceSupplement:
    supplement_id: str
    g21_manifest_digest: str
    selection_digest: str
    receipts: tuple[SupportEvidenceReceipt, ...]
    diagnostics: tuple[SupportCaptureDiagnostic, ...]
    status: SupportCaptureStatus
    fixture_digest: str | None = None
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SUPPORT_EVIDENCE_SCHEMA_VERSION,
            "supplement_id": self.supplement_id,
            "g21_manifest_digest": self.g21_manifest_digest,
            "selection_digest": self.selection_digest,
            "receipts": [item.to_dict() for item in self.receipts],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "status": self.status,
            "fixture_digest": self.fixture_digest,
            "non_authority": self.non_authority,
        }


__all__ = [
    "SUPPORT_EVIDENCE_SCHEMA_VERSION",
    "SupportCaptureDiagnostic",
    "SupportCaptureStatus",
    "SupportEvidenceCase",
    "SupportEvidenceEntry",
    "SupportEvidenceReceipt",
    "SupportEvidenceSelection",
    "SupportEvidenceSupplement",
]
