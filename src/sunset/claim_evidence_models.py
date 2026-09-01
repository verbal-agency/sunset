"""Versioned contracts for Sunset's claim–evidence graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal

from sunset.temporal_epistemics_models import EVIDENCE_ROLES, EVIDENCE_SOURCES, EvidenceRole, EvidenceSource


CLAIM_EVIDENCE_SCHEMA_VERSION = "1"
ClaimStatus = Literal["supported", "established", "unknown", "contradictory_evidence", "insufficient_evidence"]
CLAIM_STATUSES = frozenset({"supported", "established", "unknown", "contradictory_evidence", "insufficient_evidence"})


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    candidate_id: str
    statement: str
    required_scope: str
    hypothesis_id: str | None = None
    required_sources: tuple[EvidenceSource, ...] = ()
    required_freshness: str | None = None
    status: ClaimStatus = "unknown"
    schema_version: str = CLAIM_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.claim_id or not self.candidate_id or not self.statement or not self.required_scope:
            raise ValueError("claim ID, candidate ID, statement, and required scope are required")
        if self.status not in CLAIM_STATUSES:
            raise ValueError(f"unsupported claim status: {self.status}")
        if any(source not in EVIDENCE_SOURCES for source in self.required_sources):
            raise ValueError("unsupported required evidence source")

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "candidate_id": self.candidate_id,
            "hypothesis_id": self.hypothesis_id,
            "required_freshness": self.required_freshness,
            "required_scope": self.required_scope,
            "required_sources": list(self.required_sources),
            "schema_version": self.schema_version,
            "statement": self.statement,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Claim:
        return cls(
            claim_id=str(value["claim_id"]),
            candidate_id=str(value["candidate_id"]),
            statement=str(value["statement"]),
            required_scope=str(value["required_scope"]),
            hypothesis_id=str(value["hypothesis_id"]) if value.get("hypothesis_id") is not None else None,
            required_sources=_tuple(value.get("required_sources")),  # type: ignore[arg-type]
            required_freshness=str(value["required_freshness"]) if value.get("required_freshness") is not None else None,
            status=value.get("status", "unknown"),
            schema_version=str(value.get("schema_version", CLAIM_EVIDENCE_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    edge_id: str
    claim_id: str
    evidence_id: str
    role: EvidenceRole
    source_class: EvidenceSource
    scope: str
    freshness: str
    artifact_ids: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    schema_version: str = CLAIM_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.edge_id or not self.claim_id or not self.evidence_id or not self.scope or not self.freshness:
            raise ValueError("edge IDs, scope, and freshness are required")
        if self.role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.role}")
        if self.source_class not in EVIDENCE_SOURCES:
            raise ValueError(f"unsupported evidence source: {self.source_class}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ids": list(self.artifact_ids),
            "claim_id": self.claim_id,
            "edge_id": self.edge_id,
            "evidence_id": self.evidence_id,
            "freshness": self.freshness,
            "provenance": list(self.provenance),
            "role": self.role,
            "schema_version": self.schema_version,
            "scope": self.scope,
            "source_class": self.source_class,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EvidenceEdge:
        return cls(
            edge_id=str(value["edge_id"]), claim_id=str(value["claim_id"]), evidence_id=str(value["evidence_id"]),
            role=value["role"], source_class=value.get("source_class", "unknown"), scope=str(value["scope"]),
            freshness=str(value["freshness"]), artifact_ids=_tuple(value.get("artifact_ids")),
            provenance=_tuple(value.get("provenance")), schema_version=str(value.get("schema_version", CLAIM_EVIDENCE_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class Contradiction:
    contradiction_id: str
    claim_id: str
    left_edge_id: str
    right_edge_id: str
    reason: str
    schema_version: str = CLAIM_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.contradiction_id or not self.claim_id or not self.left_edge_id or not self.right_edge_id or not self.reason:
            raise ValueError("contradiction fields are required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Contradiction:
        return cls(
            contradiction_id=str(value["contradiction_id"]), claim_id=str(value["claim_id"]),
            left_edge_id=str(value["left_edge_id"]), right_edge_id=str(value["right_edge_id"]),
            reason=str(value["reason"]), schema_version=str(value.get("schema_version", CLAIM_EVIDENCE_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class GraphProofObligation:
    obligation_id: str
    claim_id: str
    description: str
    reason: str
    scope: str
    schema_version: str = CLAIM_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.obligation_id or not self.claim_id or not self.description or not self.reason or not self.scope:
            raise ValueError("graph proof obligation fields are required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GraphProofObligation:
        return cls(
            obligation_id=str(value["obligation_id"]), claim_id=str(value["claim_id"]),
            description=str(value["description"]), reason=str(value["reason"]), scope=str(value["scope"]),
            schema_version=str(value.get("schema_version", CLAIM_EVIDENCE_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class GraphResult:
    claims: tuple[Claim, ...]
    evidence_edges: tuple[EvidenceEdge, ...]
    contradictions: tuple[Contradiction, ...]
    proof_obligations: tuple[GraphProofObligation, ...]
    errors: tuple[str, ...] = ()
    non_authority: bool = True
    schema_version: str = CLAIM_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.non_authority:
            raise ValueError("graph results must remain non-authoritative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims": [item.to_dict() for item in self.claims],
            "contradictions": [item.to_dict() for item in self.contradictions],
            "errors": list(self.errors),
            "evidence_edges": [item.to_dict() for item in self.evidence_edges],
            "non_authority": self.non_authority,
            "proof_obligations": [item.to_dict() for item in self.proof_obligations],
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GraphResult:
        return cls(
            claims=tuple(Claim.from_dict(item) for item in value.get("claims", [])),
            evidence_edges=tuple(EvidenceEdge.from_dict(item) for item in value.get("evidence_edges", [])),
            contradictions=tuple(Contradiction.from_dict(item) for item in value.get("contradictions", [])),
            proof_obligations=tuple(GraphProofObligation.from_dict(item) for item in value.get("proof_obligations", [])),
            errors=_tuple(value.get("errors")), non_authority=bool(value.get("non_authority", True)),
            schema_version=str(value.get("schema_version", CLAIM_EVIDENCE_SCHEMA_VERSION)),
        )
