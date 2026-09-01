"""Framework-independent contracts for Sunset's temporal-debt epistemology.

These models deliberately describe evidence and uncertainty rather than making
cleanup decisions.  Raw artifact bodies stay in the artifact store; only
content-addressed identifiers and bounded metadata cross this boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal


TEMPORAL_EPISTEMICS_SCHEMA_VERSION = "1"

CandidateFamily = Literal[
    "disabled_test",
    "compatibility_shim",
    "version_guard",
    "feature_flag_like",
    "unknown",
]
EvidenceRole = Literal["support", "contradict", "establish", "scope_limit", "missing"]
EvidenceSource = Literal[
    "static",
    "historical",
    "operational",
    "external",
    "validation",
    "unknown",
]
ConditionState = Literal[
    "discovered",
    "condition_hypothesized",
    "condition_identified",
    "condition_likely_expired",
    "condition_likely_active",
    "removal_testable",
    "validated_in_scope",
    "human_approved",
    "contradictory_evidence",
    "insufficient_evidence",
    "unvalidatable",
]

CANDIDATE_FAMILIES = frozenset(
    {"disabled_test", "compatibility_shim", "version_guard", "feature_flag_like", "unknown"}
)
EVIDENCE_ROLES = frozenset({"support", "contradict", "establish", "scope_limit", "missing"})
EVIDENCE_SOURCES = frozenset({"static", "historical", "operational", "external", "validation", "unknown"})
CONDITION_STATES = frozenset(
    {
        "discovered",
        "condition_hypothesized",
        "condition_identified",
        "condition_likely_expired",
        "condition_likely_active",
        "removal_testable",
        "validated_in_scope",
        "human_approved",
        "contradictory_evidence",
        "insufficient_evidence",
        "unvalidatable",
    }
)
TERMINAL_STATES = frozenset(
    {"validated_in_scope", "human_approved", "contradictory_evidence", "insufficient_evidence", "unvalidatable"}
)


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True, slots=True)
class ProtectedCondition:
    """A normalized shape for the condition a candidate may protect."""

    kind: str
    statement: str
    expression: str | None = None
    subject: str | None = None
    operator: str | None = None
    threshold: str | None = None
    protected_symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.kind or not self.statement:
            raise ValueError("protected condition kind and statement are required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"protected_symbols": list(self.protected_symbols)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProtectedCondition:
        return cls(
            kind=str(value["kind"]),
            statement=str(value["statement"]),
            expression=str(value["expression"]) if value.get("expression") is not None else None,
            subject=str(value["subject"]) if value.get("subject") is not None else None,
            operator=str(value["operator"]) if value.get("operator") is not None else None,
            threshold=str(value["threshold"]) if value.get("threshold") is not None else None,
            protected_symbols=_tuple(value.get("protected_symbols")),
        )


@dataclass(frozen=True, slots=True)
class TemporalDebtCandidate:
    """A deterministic candidate normalized into a bounded family."""

    candidate_id: str
    family: CandidateFamily
    protected_condition: ProtectedCondition | None
    source_kind: str
    path: str | None = None
    line: int | None = None
    source_receipt_ids: tuple[str, ...] = ()
    schema_version: str = TEMPORAL_EPISTEMICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.family not in CANDIDATE_FAMILIES:
            raise ValueError(f"unsupported temporal-debt family: {self.family}")
        if not self.candidate_id or not self.source_kind:
            raise ValueError("candidate_id and source_kind are required")
        if self.line is not None and self.line < 1:
            raise ValueError("candidate line must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "family": self.family,
            "line": self.line,
            "path": self.path,
            "protected_condition": self.protected_condition.to_dict() if self.protected_condition else None,
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "source_receipt_ids": list(self.source_receipt_ids),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TemporalDebtCandidate:
        condition = value.get("protected_condition")
        return cls(
            candidate_id=str(value["candidate_id"]),
            family=value["family"],
            protected_condition=ProtectedCondition.from_dict(condition) if condition else None,
            source_kind=str(value["source_kind"]),
            path=str(value["path"]) if value.get("path") is not None else None,
            line=int(value["line"]) if value.get("line") is not None else None,
            source_receipt_ids=_tuple(value.get("source_receipt_ids")),
            schema_version=str(value.get("schema_version", TEMPORAL_EPISTEMICS_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class ConditionHypothesis:
    """One competing explanation for a candidate's protected condition."""

    hypothesis_id: str
    candidate_id: str
    statement: str
    state: ConditionState = "condition_hypothesized"
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    scope_limiting_evidence_ids: tuple[str, ...] = ()
    proof_obligation_ids: tuple[str, ...] = ()
    schema_version: str = TEMPORAL_EPISTEMICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.state not in CONDITION_STATES:
            raise ValueError(f"unsupported condition state: {self.state}")
        if not self.hypothesis_id or not self.candidate_id or not self.statement:
            raise ValueError("hypothesis ID, candidate ID, and statement are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "hypothesis_id": self.hypothesis_id,
            "proof_obligation_ids": list(self.proof_obligation_ids),
            "schema_version": self.schema_version,
            "scope_limiting_evidence_ids": list(self.scope_limiting_evidence_ids),
            "state": self.state,
            "statement": self.statement,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ConditionHypothesis:
        return cls(
            hypothesis_id=str(value["hypothesis_id"]),
            candidate_id=str(value["candidate_id"]),
            statement=str(value["statement"]),
            state=value.get("state", "condition_hypothesized"),
            supporting_evidence_ids=_tuple(value.get("supporting_evidence_ids")),
            contradicting_evidence_ids=_tuple(value.get("contradicting_evidence_ids")),
            scope_limiting_evidence_ids=_tuple(value.get("scope_limiting_evidence_ids")),
            proof_obligation_ids=_tuple(value.get("proof_obligation_ids")),
            schema_version=str(value.get("schema_version", TEMPORAL_EPISTEMICS_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class EvidenceStatement:
    """A claim about a condition with explicit role, scope, and provenance."""

    evidence_id: str
    candidate_id: str
    source_class: EvidenceSource
    role: EvidenceRole
    statement: str
    scope: str
    freshness: str
    provenance: tuple[str, ...] = ()
    hypothesis_id: str | None = None
    artifact_ids: tuple[str, ...] = ()
    schema_version: str = TEMPORAL_EPISTEMICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.source_class not in EVIDENCE_SOURCES:
            raise ValueError(f"unsupported evidence source: {self.source_class}")
        if self.role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.role}")
        if not self.evidence_id or not self.candidate_id or not self.statement or not self.scope or not self.freshness:
            raise ValueError("evidence ID, candidate ID, statement, scope, and freshness are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ids": list(self.artifact_ids),
            "candidate_id": self.candidate_id,
            "evidence_id": self.evidence_id,
            "freshness": self.freshness,
            "hypothesis_id": self.hypothesis_id,
            "provenance": list(self.provenance),
            "role": self.role,
            "schema_version": self.schema_version,
            "scope": self.scope,
            "source_class": self.source_class,
            "statement": self.statement,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EvidenceStatement:
        return cls(
            evidence_id=str(value["evidence_id"]),
            candidate_id=str(value["candidate_id"]),
            source_class=value.get("source_class", "unknown"),
            role=value["role"],
            statement=str(value["statement"]),
            scope=str(value["scope"]),
            freshness=str(value["freshness"]),
            provenance=_tuple(value.get("provenance")),
            hypothesis_id=str(value["hypothesis_id"]) if value.get("hypothesis_id") is not None else None,
            artifact_ids=_tuple(value.get("artifact_ids")),
            schema_version=str(value.get("schema_version", TEMPORAL_EPISTEMICS_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class ProofObligation:
    """Evidence still needed before a human can assess a counterfactual."""

    obligation_id: str
    candidate_id: str
    description: str
    why_it_matters: str
    scope: str
    owner: str | None = None
    validation_can_address: bool = False
    schema_version: str = TEMPORAL_EPISTEMICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.obligation_id or not self.candidate_id or not self.description or not self.why_it_matters or not self.scope:
            raise ValueError("proof obligation fields are required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProofObligation:
        return cls(
            obligation_id=str(value["obligation_id"]),
            candidate_id=str(value["candidate_id"]),
            description=str(value["description"]),
            why_it_matters=str(value["why_it_matters"]),
            scope=str(value["scope"]),
            owner=str(value["owner"]) if value.get("owner") is not None else None,
            validation_can_address=bool(value.get("validation_can_address", False)),
            schema_version=str(value.get("schema_version", TEMPORAL_EPISTEMICS_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class TemporalConclusion:
    """A non-authoritative condition status and its proof obligations."""

    candidate_id: str
    state: ConditionState
    hypothesis_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    proof_obligation_ids: tuple[str, ...]
    non_authority: bool = True
    schema_version: str = TEMPORAL_EPISTEMICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.state not in CONDITION_STATES:
            raise ValueError(f"unsupported conclusion state: {self.state}")
        if not self.candidate_id or not self.non_authority:
            raise ValueError("conclusions must identify a candidate and remain non-authoritative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "contradiction_ids": list(self.contradiction_ids),
            "evidence_ids": list(self.evidence_ids),
            "hypothesis_ids": list(self.hypothesis_ids),
            "non_authority": self.non_authority,
            "proof_obligation_ids": list(self.proof_obligation_ids),
            "schema_version": self.schema_version,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TemporalConclusion:
        return cls(
            candidate_id=str(value["candidate_id"]),
            state=value["state"],
            hypothesis_ids=_tuple(value.get("hypothesis_ids")),
            evidence_ids=_tuple(value.get("evidence_ids")),
            contradiction_ids=_tuple(value.get("contradiction_ids")),
            proof_obligation_ids=_tuple(value.get("proof_obligation_ids")),
            non_authority=bool(value.get("non_authority", True)),
            schema_version=str(value.get("schema_version", TEMPORAL_EPISTEMICS_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class TemporalEpistemicResult:
    candidate: TemporalDebtCandidate
    hypotheses: tuple[ConditionHypothesis, ...]
    evidence: tuple[EvidenceStatement, ...]
    proof_obligations: tuple[ProofObligation, ...]
    conclusion: TemporalConclusion
    errors: tuple[str, ...] = ()
    source_receipt_ids: tuple[str, ...] = ()
    schema_version: str = TEMPORAL_EPISTEMICS_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "conclusion": self.conclusion.to_dict(),
            "errors": list(self.errors),
            "evidence": [item.to_dict() for item in self.evidence],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "proof_obligations": [item.to_dict() for item in self.proof_obligations],
            "schema_version": self.schema_version,
            "source_receipt_ids": list(self.source_receipt_ids),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TemporalEpistemicResult:
        return cls(
            candidate=TemporalDebtCandidate.from_dict(value["candidate"]),
            hypotheses=tuple(ConditionHypothesis.from_dict(item) for item in value.get("hypotheses", [])),
            evidence=tuple(EvidenceStatement.from_dict(item) for item in value.get("evidence", [])),
            proof_obligations=tuple(ProofObligation.from_dict(item) for item in value.get("proof_obligations", [])),
            conclusion=TemporalConclusion.from_dict(value["conclusion"]),
            errors=_tuple(value.get("errors")),
            source_receipt_ids=_tuple(value.get("source_receipt_ids")),
            schema_version=str(value.get("schema_version", TEMPORAL_EPISTEMICS_SCHEMA_VERSION)),
        )
