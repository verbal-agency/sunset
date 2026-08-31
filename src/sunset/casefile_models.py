"""Versioned, citation-backed models for Sunset case files."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
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

    def to_html(self) -> str:
        """Render a self-contained, passive view of an already verified case file."""

        def code(value: str) -> str:
            return f"<code>{escape(value)}</code>"

        def citations(values: tuple[Citation, ...]) -> str:
            return ", ".join(code(item.artifact_id) for item in values)

        claims = "\n".join(
            "<li>"
            f"{code(claim.claim_id)} <span class=\"tag\">{escape(claim.kind)}</span> "
            f"{escape(claim.statement)}<div class=\"citations\">Evidence: {citations(claim.citations)}</div>"
            "</li>"
            for claim in self.claims
        )
        findings = "\n".join(
            "<li>"
            f"<strong>{'Blocking' if finding.blocking else 'Non-blocking'}:</strong> "
            f"{code(finding.kind)} {escape(finding.statement)}"
            f"<div class=\"citations\">Evidence: {citations(finding.citations)}</div>"
            "</li>"
            for finding in self.review_findings
        ) or "<li>No skeptical-review findings.</li>"
        risks = "\n".join(f"<li>{escape(risk)}</li>" for risk in self.residual_risks)
        status = escape(self.validation_status or "not supplied")
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
  <title>Sunset case file · {escape(self.candidate_id)}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0 auto; max-width: 74rem; padding: 2rem; line-height: 1.55; }}
    header, section {{ border: 1px solid #8886; border-radius: .75rem; margin: 1rem 0; padding: 1rem 1.25rem; }}
    h1, h2 {{ line-height: 1.2; }} h1 {{ margin-top: 0; }}
    dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .35rem 1rem; }}
    dt {{ font-weight: 700; }} dd {{ margin: 0; overflow-wrap: anywhere; }}
    li {{ margin: .65rem 0; }} code {{ overflow-wrap: anywhere; }}
    .boundary {{ border-left: .3rem solid #c47b00; padding-left: 1rem; }}
    .citations {{ color: #777; font-size: .9rem; margin-top: .25rem; }}
    .tag {{ border: 1px solid #8888; border-radius: 999px; font-size: .8rem; padding: .1rem .45rem; }}
  </style>
</head>
<body>
  <header>
    <p>Sunset · citation-verified human review artifact</p>
    <h1>Case file</h1>
    <dl>
      <dt>Candidate</dt><dd>{code(self.candidate_id)}</dd>
      <dt>Repository HEAD</dt><dd>{code(self.repository_head)}</dd>
      <dt>Assumption</dt><dd>{code(self.assumption_status)}</dd>
      <dt>Validation</dt><dd>{code(status)}</dd>
      <dt>Recommendation</dt><dd>{code(self.recommendation)}</dd>
    </dl>
  </header>
  <section><h2>Confidence boundary</h2><p class="boundary">{escape(self.confidence_boundary)}</p></section>
  <section><h2>Citation-backed rationale</h2><ul>{claims}</ul></section>
  <section><h2>Skeptical review</h2><ul>{findings}</ul></section>
  <section><h2>Residual risks</h2><ul>{risks}</ul></section>
</body>
</html>
"""
