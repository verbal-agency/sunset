"""Versioned contracts for the provenance-bound validation corpus."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal


VALIDATION_CORPUS_SCHEMA_VERSION = "1"
SourceKind = Literal["public_git", "recorded_artifact"]
EvidenceRole = Literal[
    "historical_outcome",
    "introduction_context",
    "condition_evidence",
    "counter_evidence",
    "validation_scope",
]
RequirementKind = Literal[
    "introduction_context", "condition_status", "counter_evidence", "validation_scope"
]
HistoricalOutcome = Literal["removed", "retained", "unknown"]
Split = Literal["development", "holdout", "excluded"]
PacketState = Literal["unprepared", "ready_for_adjudication", "excluded"]


@dataclass(frozen=True, slots=True)
class EvidencePointer:
    evidence_id: str
    source_kind: SourceKind
    role: EvidenceRole
    locator: str
    commit_sha: str | None = None
    artifact_id: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidencePointer":
        unknown = set(value) - {"evidence_id", "source_kind", "role", "locator", "commit_sha", "artifact_id"}
        if unknown:
            raise ValueError(f"unknown evidence field: {sorted(unknown)[0]}")
        return cls(
            evidence_id=str(value["evidence_id"]),
            source_kind=value["source_kind"],
            role=value["role"],
            locator=str(value["locator"]),
            commit_sha=str(value["commit_sha"]) if value.get("commit_sha") is not None else None,
            artifact_id=str(value["artifact_id"]) if value.get("artifact_id") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "source_kind": self.source_kind,
            "role": self.role,
            "locator": self.locator,
        }
        if self.commit_sha is not None:
            value["commit_sha"] = self.commit_sha
        if self.artifact_id is not None:
            value["artifact_id"] = self.artifact_id
        return value


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    requirement_id: str
    kind: RequirementKind
    proof_obligation: str
    evidence_ids: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceRequirement":
        unknown = set(value) - {"requirement_id", "kind", "proof_obligation", "evidence_ids"}
        if unknown:
            raise ValueError(f"unknown requirement field: {sorted(unknown)[0]}")
        return cls(
            requirement_id=str(value["requirement_id"]),
            kind=value["kind"],
            proof_obligation=str(value["proof_obligation"]),
            evidence_ids=tuple(str(item) for item in value.get("evidence_ids", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "kind": self.kind,
            "proof_obligation": self.proof_obligation,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class ValidationCase:
    case_id: str
    source_case_id: str
    candidate_family: str
    repository: str
    repository_url: str
    pinned_head: str
    candidate_path: str
    historical_outcome: HistoricalOutcome
    split: Split
    packet_state: PacketState
    evidence: tuple[EvidencePointer, ...]
    requirements: tuple[EvidenceRequirement, ...]
    exclusion_reason: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ValidationCase":
        unknown = set(value) - {
            "case_id", "source_case_id", "candidate_family", "repository", "repository_url",
            "pinned_head", "candidate_path", "historical_outcome", "split", "packet_state",
            "evidence", "requirements", "exclusion_reason",
        }
        if unknown:
            raise ValueError(f"unknown case field: {sorted(unknown)[0]}")
        evidence = tuple(EvidencePointer.from_dict(item) for item in value.get("evidence", ()))
        requirements = tuple(EvidenceRequirement.from_dict(item) for item in value.get("requirements", ()))
        return cls(
            case_id=str(value["case_id"]),
            source_case_id=str(value["source_case_id"]),
            candidate_family=str(value["candidate_family"]),
            repository=str(value["repository"]),
            repository_url=str(value["repository_url"]),
            pinned_head=str(value["pinned_head"]),
            candidate_path=str(value["candidate_path"]),
            historical_outcome=value["historical_outcome"],
            split=value["split"],
            packet_state=value["packet_state"],
            evidence=evidence,
            requirements=requirements,
            exclusion_reason=str(value["exclusion_reason"]) if value.get("exclusion_reason") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "case_id": self.case_id,
            "source_case_id": self.source_case_id,
            "candidate_family": self.candidate_family,
            "repository": self.repository,
            "repository_url": self.repository_url,
            "pinned_head": self.pinned_head,
            "candidate_path": self.candidate_path,
            "historical_outcome": self.historical_outcome,
            "split": self.split,
            "packet_state": self.packet_state,
            "evidence": [item.to_dict() for item in self.evidence],
            "requirements": [item.to_dict() for item in self.requirements],
        }
        if self.exclusion_reason is not None:
            value["exclusion_reason"] = self.exclusion_reason
        return value


@dataclass(frozen=True, slots=True)
class ValidationCorpus:
    corpus_id: str
    source_manifest_id: str
    cases: tuple[ValidationCase, ...]
    schema_version: str = VALIDATION_CORPUS_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ValidationCorpus":
        return cls(
            corpus_id=str(value["corpus_id"]),
            source_manifest_id=str(value["source_manifest_id"]),
            cases=tuple(ValidationCase.from_dict(item) for item in value["cases"]),
            schema_version=str(value.get("schema_version", VALIDATION_CORPUS_SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "schema_version": self.schema_version,
            "source_manifest_id": self.source_manifest_id,
            "cases": [case.to_dict() for case in self.cases],
        }


@dataclass(frozen=True, slots=True)
class CorpusAudit:
    corpus_digest: str
    corpus_id: str
    schema_version: str
    counts: dict[str, dict[str, int]]
    missing_requirements: tuple[dict[str, str], ...]
    excluded_cases: tuple[dict[str, str], ...]
    processed_case_ids: tuple[str, ...]
    unprocessed_case_ids: tuple[str, ...]
    complete: bool
    gate_ready: bool = False
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_digest": self.corpus_digest,
            "corpus_id": self.corpus_id,
            "schema_version": self.schema_version,
            "counts": self.counts,
            "missing_requirements": [dict(item) for item in self.missing_requirements],
            "excluded_cases": [dict(item) for item in self.excluded_cases],
            "processed_case_ids": list(self.processed_case_ids),
            "unprocessed_case_ids": list(self.unprocessed_case_ids),
            "complete": self.complete,
            "gate_ready": self.gate_ready,
            "non_authority": self.non_authority,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = [
    "CorpusAudit",
    "EvidencePointer",
    "EvidenceRequirement",
    "ValidationCase",
    "ValidationCorpus",
    "VALIDATION_CORPUS_SCHEMA_VERSION",
]
