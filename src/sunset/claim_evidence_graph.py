"""Deterministic claim–evidence graph construction for G16."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from sunset.claim_evidence_models import (
    CLAIM_EVIDENCE_SCHEMA_VERSION,
    CLAIM_STATUSES,
    Claim,
    Contradiction,
    EvidenceEdge,
    GraphProofObligation,
    GraphResult,
)
from sunset.temporal_epistemics_models import ConditionHypothesis, EvidenceStatement, TemporalEpistemicResult


class GraphValidationError(ValueError):
    """Raised when graph references or contracts are invalid."""


def _scope_matches(required: str, actual: str) -> bool:
    if required == actual:
        return True
    separators = ("/", ":", "|", ">", " ")
    return any(actual.startswith(required + separator) or required.startswith(actual + separator) for separator in separators)


def _fresh_enough(required: str | None, actual: str) -> bool:
    if actual.lower().startswith("stale") or actual.lower().endswith(":stale"):
        return False
    return required is None or required == actual or required in actual


def _edge_is_positive(edge: EvidenceEdge) -> bool:
    return edge.role in {"support", "establish"}


def build_graph(
    claims: Iterable[Claim],
    evidence_edges: Iterable[EvidenceEdge],
    contradictions: Iterable[Contradiction] = (),
    proof_obligations: Iterable[GraphProofObligation] = (),
) -> GraphResult:
    """Validate references and derive conservative per-claim statuses."""

    claims = tuple(claims)
    edges = tuple(evidence_edges)
    conflicts = tuple(contradictions)
    obligations = tuple(proof_obligations)
    claim_ids = {item.claim_id for item in claims}
    if len(claim_ids) != len(claims):
        raise GraphValidationError("duplicate claim ID")
    edge_ids = {item.edge_id for item in edges}
    if len(edge_ids) != len(edges):
        raise GraphValidationError("duplicate evidence edge ID")
    if any(item.claim_id not in claim_ids for item in edges):
        raise GraphValidationError("evidence edge references an unknown claim")
    if any(
        item.claim_id not in claim_ids
        or item.left_edge_id not in edge_ids
        or item.right_edge_id not in edge_ids
        or next(edge for edge in edges if edge.edge_id == item.left_edge_id).claim_id != item.claim_id
        or next(edge for edge in edges if edge.edge_id == item.right_edge_id).claim_id != item.claim_id
        for item in conflicts
    ):
        raise GraphValidationError("contradiction references an unknown claim or edge")
    if any(item.claim_id not in claim_ids for item in obligations):
        raise GraphValidationError("proof obligation references an unknown claim")
    updated: list[Claim] = []
    obligation_ids = {item.obligation_id for item in obligations}
    generated_obligations = list(obligations)

    def add_obligation(claim: Claim, suffix: str, description: str, reason: str) -> None:
        obligation_id = f"proof:{claim.claim_id}:{suffix}"
        if obligation_id not in obligation_ids:
            generated_obligations.append(GraphProofObligation(obligation_id, claim.claim_id, description, reason, claim.required_scope))
            obligation_ids.add(obligation_id)

    for claim in claims:
        related = tuple(item for item in edges if item.claim_id == claim.claim_id)
        claim_conflicts = tuple(item for item in conflicts if item.claim_id == claim.claim_id)
        positive = tuple(item for item in related if _edge_is_positive(item) and _scope_matches(claim.required_scope, item.scope) and _fresh_enough(claim.required_freshness, item.freshness))
        explicit_contradiction = any(item.role == "contradict" for item in related) or bool(claim_conflicts)
        if explicit_contradiction and positive:
            status = "contradictory_evidence"
        elif positive and any(item.role == "establish" for item in positive):
            status = "established"
        elif positive:
            status = "supported"
        elif related:
            status = "unknown"
        else:
            status = "insufficient_evidence"
        if status == "insufficient_evidence":
            add_obligation(claim, "evidence", "Provide evidence for this protected-condition claim.", "No evidence edge is attached to the claim.")
        elif status == "unknown":
            add_obligation(claim, "scope", "Provide fresh evidence within the claim's required scope.", "Attached evidence is stale, scope-limited, or non-decisive.")
        elif status == "supported":
            add_obligation(claim, "establishment", "Establish the claim within its required scope.", "Supporting evidence does not establish the required scope.")
        elif status == "contradictory_evidence":
            add_obligation(claim, "contradiction", "Resolve the contradictory evidence before proceeding.", "Positive and contradicting evidence remain simultaneously applicable.")
        updated.append(replace(claim, status=status))
    return GraphResult(
        claims=tuple(updated), evidence_edges=edges, contradictions=conflicts,
        proof_obligations=tuple(generated_obligations), schema_version=CLAIM_EVIDENCE_SCHEMA_VERSION,
    )


def graph_from_epistemic_result(result: TemporalEpistemicResult) -> GraphResult:
    """Adapt G15 normalized records into a graph without reading raw artifacts."""

    claims: list[Claim] = []
    claim_by_hypothesis: dict[str, str] = {}
    for hypothesis in result.hypotheses:
        claim_id = f"claim:{hypothesis.hypothesis_id}"
        claim_by_hypothesis[hypothesis.hypothesis_id] = claim_id
        claims.append(
            Claim(
                claim_id=claim_id, candidate_id=result.candidate.candidate_id,
                statement=hypothesis.statement, required_scope="the bound investigation",
                hypothesis_id=hypothesis.hypothesis_id,
            )
        )
    if not claims:
        claims.append(
            Claim(
                claim_id=f"claim:{result.candidate.candidate_id}", candidate_id=result.candidate.candidate_id,
                statement=(result.candidate.protected_condition.statement if result.candidate.protected_condition else "The candidate protects an unknown condition."),
                required_scope="the bound investigation",
            )
        )
    default_claim = claims[0].claim_id
    edges: list[EvidenceEdge] = []
    for item in result.evidence:
        claim_id = claim_by_hypothesis.get(item.hypothesis_id or "", default_claim)
        edges.append(
            EvidenceEdge(
                edge_id=f"edge:{item.evidence_id}", claim_id=claim_id, evidence_id=item.evidence_id,
                role=item.role, source_class=item.source_class, scope=item.scope, freshness=item.freshness,
                artifact_ids=item.artifact_ids, provenance=item.provenance,
            )
        )
    obligations = tuple(
        GraphProofObligation(item.obligation_id, default_claim, item.description, item.why_it_matters, item.scope)
        for item in result.proof_obligations
    )
    graph = build_graph(claims, edges, proof_obligations=obligations)
    return GraphResult(
        claims=graph.claims,
        evidence_edges=graph.evidence_edges,
        contradictions=graph.contradictions,
        proof_obligations=graph.proof_obligations,
        errors=result.errors,
        schema_version=graph.schema_version,
    )


__all__ = ["GraphValidationError", "build_graph", "graph_from_epistemic_result"]
