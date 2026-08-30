"""Versioned, citation-backed models for Sunset case files."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal


CASE_FILE_SCHEMA_VERSION = "1"
Recommendation = Literal["eligible_for_human_cleanup", "retain", "inconclusive"]


class CaseFileError(RuntimeError):
    """A structured failure that prevents a report from being rendered."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class Citation:
    """A verified reference to one immutable raw artifact."""

    artifact_id: str
    digest: str

    def to_dict(self) -> dict[str, str]:
        return {"artifact_id": self.artifact_id, "digest": self.digest}


@dataclass(frozen=True, slots=True)
class CaseClaim:
    claim_id: str
    kind: str
    statement: str
    citations: tuple[Citation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "citations": [citation.to_dict() for citation in self.citations],
            "claim_id": self.claim_id,
            "kind": self.kind,
            "statement": self.statement,
        }


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    blocking: bool
    citations: tuple[Citation, ...]
    kind: str
    statement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocking": self.blocking,
            "citations": [citation.to_dict() for citation in self.citations],
            "kind": self.kind,
            "statement": self.statement,
        }


@dataclass(frozen=True, slots=True)
class CaseFile:
    assumption_status: str
    candidate_id: str
    claims: tuple[CaseClaim, ...]
    confidence_boundary: str
    recommendation: Recommendation
    repository_head: str
    residual_risks: tuple[str, ...]
    review_findings: tuple[ReviewFinding, ...]
    validation_status: str | None
    schema_version: str = CASE_FILE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption_status": self.assumption_status,
            "candidate_id": self.candidate_id,
            "claims": [claim.to_dict() for claim in self.claims],
            "confidence_boundary": self.confidence_boundary,
            "recommendation": self.recommendation,
            "repository_head": self.repository_head,
            "residual_risks": list(self.residual_risks),
            "review_findings": [finding.to_dict() for finding in self.review_findings],
            "schema_version": self.schema_version,
            "validation_status": self.validation_status,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = [
            f"# Sunset case file: {self.candidate_id}",
            "",
            f"- Repository HEAD: `{self.repository_head}`",
            f"- Assumption status: `{self.assumption_status}`",
            f"- Validation status: `{self.validation_status or 'not supplied'}`",
            f"- Recommendation: `{self.recommendation}`",
            "",
            "## Confidence boundary",
            "",
            self.confidence_boundary,
            "",
            "## Citation-backed rationale",
            "",
        ]
        for claim in self.claims:
            citations = ", ".join(f"`{citation.artifact_id}`" for citation in claim.citations)
            lines.append(f"- `{claim.claim_id}` ({claim.kind}): {claim.statement} — {citations}")
        lines.extend(("", "## Skeptical review", ""))
        for finding in self.review_findings:
            citations = ", ".join(f"`{citation.artifact_id}`" for citation in finding.citations)
            state = "blocking" if finding.blocking else "non-blocking"
            lines.append(f"- {state} `{finding.kind}`: {finding.statement} — {citations}")
        lines.extend(("", "## Residual risks", ""))
        for risk in self.residual_risks:
            lines.append(f"- {risk}")
        return "\n".join(lines) + "\n"
