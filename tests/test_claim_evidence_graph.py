from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

from sunset.claim_evidence_graph import GraphValidationError, build_graph, graph_from_epistemic_result
from sunset.claim_evidence_models import Claim, Contradiction, EvidenceEdge, GraphProofObligation, GraphResult
from sunset.temporal_epistemics_models import ConditionHypothesis, EvidenceStatement, TemporalDebtCandidate, TemporalEpistemicResult, TemporalConclusion


def _claim(claim_id: str = "c1", *, scope: str = "production") -> Claim:
    return Claim(claim_id, "candidate-1", "production no longer supports the legacy runtime", scope)


def _edge(edge_id: str, claim_id: str = "c1", role: str = "support", *, scope: str = "production", freshness: str = "2026-09") -> EvidenceEdge:
    return EvidenceEdge(edge_id, claim_id, f"evidence-{edge_id}", role, "operational", scope, freshness, provenance=(edge_id,))  # type: ignore[arg-type]


def test_g16_ac01_graph_integrity() -> None:
    result = build_graph((_claim(),), (_edge("e1", role="establish"),), proof_obligations=(GraphProofObligation("p1", "c1", "Confirm customer inventory", "Local deployment is not established by upstream status.", "customers"),))
    restored = GraphResult.from_dict(json.loads(result.to_json()))
    assert restored.claims[0].status == "established"
    assert restored.proof_obligations[0].claim_id == "c1"
    with pytest.raises(GraphValidationError, match="unknown claim"):
        build_graph((_claim(),), (_edge("e2", claim_id="missing"),))


def test_g16_ac02_scope_aware_establishment() -> None:
    claim = _claim(scope="production")
    established = build_graph((claim,), (_edge("e1", role="establish", scope="production", freshness="current"),))
    stale = build_graph((claim,), (_edge("e2", role="establish", scope="production", freshness="stale:2024"),))
    limited = build_graph((claim,), (_edge("e3", role="support", scope="upstream", freshness="current"),))
    assert established.claims[0].status == "established"
    assert stale.claims[0].status == "unknown"
    assert limited.claims[0].status == "unknown"


def test_g16_ac03_preserves_contradictions() -> None:
    contradiction = Contradiction("x1", "c1", "e1", "e2", "inventory conflicts with support policy")
    result = build_graph((_claim(),), (_edge("e1", role="establish"), _edge("e2", role="contradict")), (contradiction,))
    assert result.claims[0].status == "contradictory_evidence"
    assert {edge.edge_id for edge in result.evidence_edges} == {"e1", "e2"}
    assert result.contradictions[0].left_edge_id == "e1"


def test_g16_ac04_conservative_inference() -> None:
    supported = build_graph((_claim(),), (_edge("e1", role="support"),))
    no_edges = build_graph((_claim(),), ())
    assert supported.claims[0].status == "supported"
    assert no_edges.claims[0].status == "insufficient_evidence"
    assert any(item.reason.startswith("Supporting evidence") for item in supported.proof_obligations)
    assert any(item.reason.startswith("No evidence") for item in no_edges.proof_obligations)
    assert supported.non_authority is True


def test_g16_ac05_receipt_and_authority_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("graph must be offline")))
    candidate = TemporalDebtCandidate("candidate-2", "version_guard", None, "runtime_version_guard")
    hypothesis = ConditionHypothesis("h1", candidate.candidate_id, "legacy runtime remains supported")
    evidence = EvidenceStatement("ev1", candidate.candidate_id, "external", "establish", "upstream status", "the bound investigation", "recorded-v1", provenance=("receipt-1",))
    epistemic = TemporalEpistemicResult(candidate, (hypothesis,), (evidence,), (), TemporalConclusion(candidate.candidate_id, "condition_hypothesized", ("h1",), ("ev1",), (), ()))
    graph = graph_from_epistemic_result(epistemic)
    assert graph.evidence_edges[0].provenance == ("receipt-1",)
    assert "upstream status" not in graph.to_json()


def test_g16_ac06_documented_verification() -> None:
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G16-claim-evidence-graph.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert "### Deterministic behavior matrix" in text
    assert all(f"G16-AC0{i}" in text for i in range(1, 7))
    fixture = Path(__file__).parent / "fixtures" / "claim_evidence" / "g16-cases.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert {item["case_id"] for item in payload["cases"]} == {
        "upstream-eol-local-support", "active-condition", "contradictory-sources", "missing-evidence", "stale-validation"
    }
