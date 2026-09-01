"""Sunset's deterministic discovery API."""

from sunset.models import Candidate, ScanError, ScanResult
from sunset.scanner import scan_repository
from sunset.claim_evidence_graph import GraphValidationError, build_graph, graph_from_epistemic_result
from sunset.claim_evidence_models import Claim, Contradiction, EvidenceEdge, GraphProofObligation, GraphResult
from sunset.temporal_epistemics_models import (
    ConditionHypothesis,
    EvidenceStatement,
    ProofObligation,
    ProtectedCondition,
    TemporalConclusion,
    TemporalDebtCandidate,
    TemporalEpistemicResult,
)

__all__ = [
    "Candidate",
    "Claim",
    "ConditionHypothesis",
    "Contradiction",
    "EvidenceEdge",
    "EvidenceStatement",
    "GraphValidationError",
    "ProofObligation",
    "ProtectedCondition",
    "GraphProofObligation",
    "GraphResult",
    "ScanError",
    "ScanResult",
    "TemporalConclusion",
    "TemporalDebtCandidate",
    "TemporalEpistemicResult",
    "build_graph",
    "graph_from_epistemic_result",
    "scan_repository",
]
__version__ = "0.1.0"
