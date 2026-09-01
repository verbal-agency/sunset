"""Deterministic skeptical review and artifact-verified case-file finalization."""

from __future__ import annotations

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.claim_evidence_models import GraphResult
from sunset.review_models import CaseFile, CaseFileError, ClaimVerification, ReviewFinding, ReviewRequest, ReviewResult


def review_graph(request: ReviewRequest) -> ReviewResult:
    """Challenge graph claims without mutating the graph or granting authority."""

    if request.budget < len(request.graph.claims):
        return ReviewResult("budget_exhausted", (), (CaseFileError("review_budget_exhausted", "review budget cannot inspect every claim"),))
    findings: list[ReviewFinding] = []
    for claim in request.graph.claims:
        edges = tuple(edge for edge in request.graph.evidence_edges if edge.claim_id == claim.claim_id)
        edge_ids = tuple(edge.edge_id for edge in edges)
        if claim.status == "contradictory_evidence":
            findings.append(ReviewFinding(claim.claim_id, "contradiction", "Contradictory evidence remains unresolved.", edge_ids, True))
        elif claim.status in {"unknown", "insufficient_evidence"}:
            findings.append(ReviewFinding(claim.claim_id, "missing", "The claim lacks decisive evidence in its required scope.", edge_ids, True))
        elif claim.status == "supported":
            findings.append(ReviewFinding(claim.claim_id, "scope_limit", "Supporting evidence does not establish the required scope.", edge_ids, True))
        else:
            findings.append(ReviewFinding(claim.claim_id, "support", "The claim has fresh evidence within its declared scope.", edge_ids, False))
    for obligation in request.graph.proof_obligations:
        findings.append(ReviewFinding(obligation.claim_id, "missing", obligation.description, (), True))
    return ReviewResult("complete", tuple(findings))


def finalize_case_file(
    graph: GraphResult,
    *,
    store_path: str,
    review: ReviewResult | None = None,
    artifact_store: ArtifactStore | None = None,
) -> CaseFile:
    """Verify every graph artifact reference before rendering a passive case file."""

    store = artifact_store or ArtifactStore(store_path)
    errors: list[CaseFileError] = []
    for edge in graph.evidence_edges:
        for artifact_id in edge.artifact_ids:
            try:
                store.read_artifact_id(artifact_id)
            except ArtifactStoreError as exc:
                errors.append(CaseFileError("artifact_unresolved", f"{edge.edge_id}: {artifact_id} ({exc.code})"))
    if errors:
        raise errors[0]
    result = review or review_graph(ReviewRequest(graph))
    claims: list[ClaimVerification] = []
    for claim in graph.claims:
        edges = tuple(edge for edge in graph.evidence_edges if edge.claim_id == claim.claim_id)
        statuses = {edge.role for edge in edges}
        citation_status = "contradicts" if claim.status == "contradictory_evidence" else "establishes" if claim.status == "established" else "supports" if "support" in statuses else "unknown"
        claims.append(ClaimVerification(claim.claim_id, claim.status, citation_status, tuple(edge.edge_id for edge in edges), claim.required_scope, tuple(edge.freshness for edge in edges)))
    candidate_id = graph.claims[0].candidate_id if graph.claims else "unknown-candidate"
    state = "inconclusive" if result.status != "complete" or any(item.blocking for item in result.findings) else "reviewed"
    return CaseFile(candidate_id, _head(graph), tuple(claims), tuple(edge.evidence_id for edge in graph.evidence_edges), tuple(item.contradiction_id for item in graph.contradictions), tuple(item.description for item in graph.proof_obligations), result.findings, state)


def _head(graph: GraphResult) -> str:
    for edge in graph.evidence_edges:
        for provenance in edge.provenance:
            if provenance.startswith("head:"):
                return provenance.removeprefix("head:")
    return "unbound"


__all__ = ["finalize_case_file", "review_graph"]
