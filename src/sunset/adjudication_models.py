"""Versioned contracts for owner-supplied temporal-condition adjudication."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal


ADJUDICATION_SCHEMA_VERSION = "1"
ReviewMode = Literal["single_reviewer"]
SecondReviewStatus = Literal["not_available", "appended"]
ConditionStatus = Literal[
    "identified", "active", "likely_expired", "unknown", "contradictory"
]
EvidenceSufficiency = Literal["sufficient", "insufficient", "contradictory", "abstained"]


@dataclass(frozen=True, slots=True)
class ReviewerAuthority:
    protocol_version: str
    reviewer_id: str
    authority_basis: str
    review_mode: ReviewMode = "single_reviewer"
    second_review_status: SecondReviewStatus = "not_available"
    schema_version: str = ADJUDICATION_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReviewerAuthority":
        allowed = {"protocol_version", "reviewer_id", "authority_basis", "review_mode", "second_review_status", "schema_version"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown authority field: {sorted(unknown)[0]}")
        return cls(
            protocol_version=str(value["protocol_version"]),
            reviewer_id=str(value["reviewer_id"]),
            authority_basis=str(value["authority_basis"]),
            review_mode=value.get("review_mode", "single_reviewer"),
            second_review_status=value.get("second_review_status", "not_available"),
            schema_version=str(value.get("schema_version", ADJUDICATION_SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "reviewer_id": self.reviewer_id,
            "authority_basis": self.authority_basis,
            "review_mode": self.review_mode,
            "second_review_status": self.second_review_status,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class AdjudicationDecision:
    case_id: str
    protocol_version: str
    reviewer_id: str
    evidence_ids: tuple[str, ...]
    protected_condition_hypothesis: str
    condition_status: ConditionStatus
    evidence_sufficiency: EvidenceSufficiency
    proof_obligations: tuple[str, ...]
    validation_scope: tuple[str, ...]
    abstention_reason: str | None = None
    exclusion_reason: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AdjudicationDecision":
        allowed = {
            "case_id", "protocol_version", "reviewer_id", "evidence_ids",
            "protected_condition_hypothesis", "condition_status", "evidence_sufficiency",
            "proof_obligations", "validation_scope", "abstention_reason", "exclusion_reason",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown decision field: {sorted(unknown)[0]}")
        return cls(
            case_id=str(value["case_id"]),
            protocol_version=str(value["protocol_version"]),
            reviewer_id=str(value["reviewer_id"]),
            evidence_ids=tuple(str(item) for item in value.get("evidence_ids", ())),
            protected_condition_hypothesis=str(value["protected_condition_hypothesis"]),
            condition_status=value["condition_status"],
            evidence_sufficiency=value["evidence_sufficiency"],
            proof_obligations=tuple(str(item) for item in value.get("proof_obligations", ())),
            validation_scope=tuple(str(item) for item in value.get("validation_scope", ())),
            abstention_reason=str(value["abstention_reason"]) if value.get("abstention_reason") is not None else None,
            exclusion_reason=str(value["exclusion_reason"]) if value.get("exclusion_reason") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "case_id": self.case_id,
            "protocol_version": self.protocol_version,
            "reviewer_id": self.reviewer_id,
            "evidence_ids": list(self.evidence_ids),
            "protected_condition_hypothesis": self.protected_condition_hypothesis,
            "condition_status": self.condition_status,
            "evidence_sufficiency": self.evidence_sufficiency,
            "proof_obligations": list(self.proof_obligations),
            "validation_scope": list(self.validation_scope),
        }
        if self.abstention_reason is not None:
            value["abstention_reason"] = self.abstention_reason
        if self.exclusion_reason is not None:
            value["exclusion_reason"] = self.exclusion_reason
        return value


@dataclass(frozen=True, slots=True)
class AdjudicationManifest:
    manifest_id: str
    source_corpus_id: str
    source_corpus_digest: str
    protocol_version: str
    reviewer_id: str
    review_mode: ReviewMode
    second_review_status: SecondReviewStatus
    decisions: tuple[AdjudicationDecision, ...]
    excluded_cases: tuple[dict[str, str], ...]
    split_identities: dict[str, tuple[str, ...]]
    coverage_limit: str
    manifest_digest: str | None = None
    schema_version: str = ADJUDICATION_SCHEMA_VERSION

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "source_corpus_id": self.source_corpus_id,
            "source_corpus_digest": self.source_corpus_digest,
            "protocol_version": self.protocol_version,
            "reviewer_id": self.reviewer_id,
            "review_mode": self.review_mode,
            "second_review_status": self.second_review_status,
            "decisions": [item.to_dict() for item in self.decisions],
            "excluded_cases": [dict(item) for item in self.excluded_cases],
            "split_identities": {key: list(value) for key, value in sorted(self.split_identities.items())},
            "coverage_limit": self.coverage_limit,
        }

    def to_dict(self) -> dict[str, Any]:
        value = self.unsigned_dict()
        value["manifest_digest"] = self.manifest_digest
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = [
    "ADJUDICATION_SCHEMA_VERSION", "AdjudicationDecision", "AdjudicationManifest",
    "ConditionStatus", "EvidenceSufficiency", "ReviewerAuthority",
]
