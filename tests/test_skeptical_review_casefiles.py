from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.claim_evidence_graph import build_graph
from sunset.claim_evidence_models import Claim, Contradiction, EvidenceEdge
from sunset.casefile_finalizer import finalize_case_file, review_graph
from sunset.review_models import CaseFile, CaseFileError, ReviewRequest


def _graph(tmp_path: Path, *, contradictory: bool = False):
    store = ArtifactStore(tmp_path / "store")
    artifact = store.put(b'{"source":"fixture"}\n', media_type="application/json", source_kind="fixture", source_locator="fixture://e1")
    claim = Claim("claim-1", "candidate-1", "legacy condition is no longer active", "production")
    edges = [EvidenceEdge("edge-1", "claim-1", "evidence-1", "establish", "operational", "production", "current", (artifact.artifact_id,), ("head:abc",))]
    contradictions = ()
    if contradictory:
        edges.append(EvidenceEdge("edge-2", "claim-1", "evidence-2", "contradict", "operational", "production", "current", (artifact.artifact_id,), ("head:abc",)))
        contradictions = (Contradiction("contra-1", "claim-1", "edge-1", "edge-2", "fixture conflict"),)
    return build_graph((claim,), tuple(edges), contradictions), store


def test_g19_ac01_independent_challenge(tmp_path: Path) -> None:
    graph, _ = _graph(tmp_path)
    result = review_graph(ReviewRequest(graph))
    assert result.non_authority is True
    assert any(item.kind == "support" for item in result.findings)
    assert graph.claims[0].status == "established"


def test_g19_ac02_claim_verification(tmp_path: Path) -> None:
    graph, store = _graph(tmp_path)
    case = finalize_case_file(graph, store_path=str(store.root))
    assert case.claims[0].citation_status == "establishes"
    assert case.claims[0].edge_ids == ("edge-1",)


def test_g19_ac03_contradiction_visibility(tmp_path: Path) -> None:
    graph, store = _graph(tmp_path, contradictory=True)
    case = finalize_case_file(graph, store_path=str(store.root))
    assert case.claims[0].status == "contradictory_evidence"
    assert case.contradiction_ids == ("contra-1",)
    assert any(item.kind == "contradiction" and item.blocking for item in case.review_findings)


def test_g19_ac04_casefile_integrity(tmp_path: Path) -> None:
    graph, store = _graph(tmp_path)
    case = finalize_case_file(graph, store_path=str(store.root))
    restored = CaseFile.from_dict(json.loads(case.to_json()))
    assert restored.non_authority is True
    assert "source" not in case.to_markdown()
    assert "evidence-1" in case.to_json()


def test_g19_ac05_failure_containment(tmp_path: Path) -> None:
    graph, store = _graph(tmp_path)
    artifact = next(iter(graph.evidence_edges[0].artifact_ids))
    (store.root / "artifacts" / "sha256" / artifact.removeprefix("sha256:")).write_bytes(b"tampered")
    with pytest.raises(CaseFileError, match="artifact_unresolved"):
        finalize_case_file(graph, store_path=str(store.root))
    assert review_graph(ReviewRequest(graph, budget=1)).status == "complete"


def test_g19_ac06_verification() -> None:
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G19-skeptical-review-case-files.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert all(f"G19-AC0{i}" in text for i in range(1, 7))
    fixture = Path(__file__).parent / "fixtures" / "casefiles" / "g19-cases.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert len(payload["cases"]) == 4
