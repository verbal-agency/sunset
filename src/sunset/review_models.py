"""Versioned contracts for bounded skeptical review and case files."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal

from sunset.claim_evidence_models import GraphResult


REVIEW_SCHEMA_VERSION = "1"
FindingKind = Literal["support", "contradiction", "scope_limit", "missing", "inconclusive"]
ReviewStatus = Literal["complete", "inconclusive", "budget_exhausted", "rejected"]


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    graph: GraphResult
    reviewer_version: str = "deterministic-skeptic-v1"
    budget: int = 64
    mode: Literal["recorded", "deterministic"] = "deterministic"
    schema_version: str = REVIEW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.budget < 1 or not self.reviewer_version:
            raise ValueError("review budget and reviewer version are required")
        if self.mode not in {"recorded", "deterministic"}:
            raise ValueError("unsupported review mode")


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    claim_id: str
    kind: FindingKind
    statement: str
    evidence_ids: tuple[str, ...] = ()
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "kind": self.kind, "statement": self.statement, "evidence_ids": list(self.evidence_ids), "blocking": self.blocking}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReviewFinding:
        return cls(str(value["claim_id"]), value["kind"], str(value["statement"]), tuple(value.get("evidence_ids", ())), bool(value.get("blocking", True)))


@dataclass(frozen=True, slots=True)
class ClaimVerification:
    claim_id: str
    status: str
    citation_status: Literal["establishes", "supports", "contradicts", "unknown"]
    edge_ids: tuple[str, ...]
    scope: str
    freshness: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "status": self.status, "citation_status": self.citation_status, "edge_ids": list(self.edge_ids), "scope": self.scope, "freshness": list(self.freshness)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ClaimVerification:
        return cls(str(value["claim_id"]), str(value["status"]), value["citation_status"], tuple(value.get("edge_ids", ())), str(value["scope"]), tuple(value.get("freshness", ())))


@dataclass(frozen=True, slots=True)
class CaseFile:
    candidate_id: str
    repository_head: str
    claims: tuple[ClaimVerification, ...]
    evidence_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    proof_obligations: tuple[str, ...]
    review_findings: tuple[ReviewFinding, ...]
    terminal_state: str
    non_authority: bool = True
    schema_version: str = REVIEW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.repository_head or not self.non_authority:
            raise ValueError("case files require a candidate, repository HEAD, and non-authority marker")

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "claims": [item.to_dict() for item in self.claims], "contradiction_ids": list(self.contradiction_ids), "evidence_ids": list(self.evidence_ids), "non_authority": self.non_authority, "proof_obligations": list(self.proof_obligations), "repository_head": self.repository_head, "review_findings": [item.to_dict() for item in self.review_findings], "schema_version": self.schema_version, "terminal_state": self.terminal_state}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = [f"# Sunset skeptical case file: {self.candidate_id}", "", f"- Repository HEAD: `{self.repository_head}`", f"- Terminal state: `{self.terminal_state}`", "- Authority: `non-authoritative`", "", "## Claim verification", ""]
        for claim in self.claims:
            lines.append(f"- `{claim.claim_id}`: `{claim.status}` / `{claim.citation_status}`; edges: {', '.join(f'`{item}`' for item in claim.edge_ids) or 'none'}; scope: `{claim.scope}`")
        lines.extend(("", "## Review findings", ""))
        for finding in self.review_findings:
            lines.append(f"- {'blocking' if finding.blocking else 'non-blocking'} `{finding.kind}` ({finding.claim_id}): {finding.statement} — {', '.join(f'`{item}`' for item in finding.evidence_ids) or 'no evidence'}")
        lines.extend(("", "## Open proof obligations", ""))
        lines.extend(f"- {item}" for item in self.proof_obligations)
        return "\n".join(lines) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CaseFile:
        return cls(str(value["candidate_id"]), str(value["repository_head"]), tuple(ClaimVerification.from_dict(item) for item in value.get("claims", [])), tuple(value.get("evidence_ids", ())), tuple(value.get("contradiction_ids", ())), tuple(value.get("proof_obligations", ())), tuple(ReviewFinding.from_dict(item) for item in value.get("review_findings", [])), str(value["terminal_state"]), bool(value.get("non_authority", True)), str(value.get("schema_version", REVIEW_SCHEMA_VERSION)))


class CaseFileError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "message": self.message}


@dataclass(frozen=True, slots=True)
class ReviewResult:
    status: ReviewStatus
    findings: tuple[ReviewFinding, ...]
    errors: tuple[CaseFileError, ...] = ()
    non_authority: bool = True

    def __post_init__(self) -> None:
        if not self.non_authority:
            raise ValueError("review results remain non-authoritative")


__all__ = ["CaseFile", "CaseFileError", "ClaimVerification", "ReviewFinding", "ReviewRequest", "ReviewResult"]
