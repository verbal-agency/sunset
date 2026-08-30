"""Finalize saved Sunset evidence into a conservative, citation-backed case file."""

from __future__ import annotations

from pathlib import Path

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.casefile_models import CaseClaim, CaseFile, CaseFileError, Citation, Recommendation, ReviewFinding
from sunset.investigation_models import InvestigationResult, LedgerEntry
from sunset.validation_models import ValidationResult


MATERIAL_CLAIM_KINDS = frozenset({"fact", "inference", "contradiction", "rejected_hypothesis"})
CONFIDENCE_BOUNDARY = (
    "Citations establish only that this report reloaded the referenced raw artifacts. "
    "A confirmed test run is empirical evidence, not proof that deletion is safe; "
    "a human must decide whether any cleanup should occur."
)


def build_case_file(
    investigation: InvestigationResult,
    *,
    store_path: str | Path,
    validation: ValidationResult | None = None,
    artifact_store: ArtifactStore | None = None,
) -> CaseFile:
    """Reload every cited artifact before rendering a derived, read-only report."""

    store = artifact_store or ArtifactStore(store_path)
    if validation is not None:
        _validate_result_pair(investigation, validation)

    claims = tuple(_finalize_ledger_claim(store, entry) for entry in investigation.ledger if entry.kind in MATERIAL_CLAIM_KINDS)
    if not claims:
        raise CaseFileError("case_has_no_cited_claims", "case file requires at least one citation-backed investigation claim")

    validation_claim = _finalize_validation_claim(store, validation)
    if validation_claim is not None:
        claims = (*claims, validation_claim)
    all_citations = tuple(sorted({citation for claim in claims for citation in claim.citations}, key=lambda item: item.artifact_id))
    findings = _skeptical_review(investigation, validation, all_citations)
    recommendation = _recommendation(investigation, validation, findings)
    risks = _residual_risks(investigation, validation, findings)
    return CaseFile(
        assumption_status=investigation.assumption_status,
        candidate_id=investigation.candidate_id,
        claims=claims,
        confidence_boundary=CONFIDENCE_BOUNDARY,
        recommendation=recommendation,
        repository_head=investigation.repository_head,
        residual_risks=risks,
        review_findings=findings,
        validation_status=validation.status if validation else None,
    )


def _finalize_ledger_claim(store: ArtifactStore, entry: LedgerEntry) -> CaseClaim:
    citations = _verify_citations(store, entry.evidence_ids, claim_id=entry.claim_id)
    return CaseClaim(entry.claim_id, entry.kind, entry.statement, citations)


def _finalize_validation_claim(store: ArtifactStore, validation: ValidationResult | None) -> CaseClaim | None:
    if validation is None:
        return None
    citation_ids: list[str] = []
    if validation.environment is not None:
        citation_ids.append(validation.environment.artifact.artifact_id)
    citation_ids.extend(run.output.artifact_id for run in validation.runs)
    citations = _verify_citations(store, tuple(citation_ids), claim_id="validation-result")
    return CaseClaim(
        "validation-result",
        "fact",
        f"Approved disposable-clone validation reported status {validation.status}.",
        citations,
    )


def _verify_citations(
    store: ArtifactStore,
    artifact_ids: tuple[str, ...],
    *,
    claim_id: str,
) -> tuple[Citation, ...]:
    if not artifact_ids:
        raise CaseFileError("claim_uncited", f"material claim {claim_id} has no cited artifact IDs")
    unique = tuple(sorted(set(artifact_ids)))
    for artifact_id in unique:
        try:
            store.read_artifact_id(artifact_id)
        except ArtifactStoreError as exc:
            raise CaseFileError(
                "citation_unresolved",
                f"material claim {claim_id} cannot resolve {artifact_id}: {exc.code}",
            ) from exc
    return tuple(Citation(artifact_id=artifact_id, digest=artifact_id.removeprefix("sha256:")) for artifact_id in unique)


def _validate_result_pair(investigation: InvestigationResult, validation: ValidationResult) -> None:
    if validation.candidate_id != investigation.candidate_id:
        raise CaseFileError("candidate_mismatch", "investigation and validation refer to different candidates")
    if validation.repository_head != investigation.repository_head:
        raise CaseFileError("repository_head_mismatch", "investigation and validation refer to different repository HEADs")


def _skeptical_review(
    investigation: InvestigationResult,
    validation: ValidationResult | None,
    citations: tuple[Citation, ...],
) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    citations_by_id = {citation.artifact_id: citation for citation in citations}
    for entry in investigation.ledger:
        if entry.kind == "contradiction":
            entry_citations = tuple(citations_by_id[artifact_id] for artifact_id in sorted(set(entry.evidence_ids)))
            findings.append(ReviewFinding(True, entry_citations, "evidence_conflict", entry.statement))
    if investigation.assumption_status in {"active", "unknown"}:
        findings.append(ReviewFinding(
            True, citations, "assumption_unresolved",
            f"External assumption status remains {investigation.assumption_status}.",
        ))
    if validation is None:
        findings.append(ReviewFinding(True, citations, "validation_missing", "No approved validation result was supplied."))
    elif validation.status != "confirmed":
        findings.append(ReviewFinding(
            True, citations, "validation_not_confirmed",
            f"Disposable-clone validation reported {validation.status}, not confirmed.",
        ))
    for error in investigation.errors:
        findings.append(ReviewFinding(True, citations, "investigation_error", error.message))
    if validation is not None:
        for error in validation.errors:
            findings.append(ReviewFinding(True, citations, "validation_error", error.message))
    return tuple(findings)


def _recommendation(
    investigation: InvestigationResult,
    validation: ValidationResult | None,
    findings: tuple[ReviewFinding, ...],
) -> Recommendation:
    if not any(finding.blocking for finding in findings):
        return "eligible_for_human_cleanup"
    if investigation.assumption_status == "active":
        return "retain"
    if validation is not None and validation.status == "still_failing":
        return "retain"
    return "inconclusive"


def _residual_risks(
    investigation: InvestigationResult,
    validation: ValidationResult | None,
    findings: tuple[ReviewFinding, ...],
) -> tuple[str, ...]:
    risks = list(investigation.open_questions)
    if validation is None:
        risks.append("No approved disposable-clone validation was supplied.")
    risks.extend(finding.statement for finding in findings)
    risks.append("No target repository was changed; any cleanup remains a human decision.")
    return tuple(dict.fromkeys(risks))
