"""Sunset's deterministic discovery API."""

from sunset.models import Candidate, ScanError, ScanResult
from sunset.scanner import scan_repository
from sunset.claim_evidence_graph import GraphValidationError, build_graph, graph_from_epistemic_result
from sunset.claim_evidence_models import Claim, Contradiction, EvidenceEdge, GraphProofObligation, GraphResult
from sunset.context_expansion import ContextExpansionContext, ContextExpansionError
from sunset.context_expansion_models import ContextExpansionObservation, ContextExpansionReceipt, ContextExpansionRequest
from sunset.operational_evidence import ExplicitLiveOperationalProvider, OperationalEvidenceContext, RecordedOperationalProvider, receipt_to_evidence_edge
from sunset.operational_evidence_models import FreshnessMetadata, OperationalEvidenceReceipt, OperationalQuery, PrivacyPolicy
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
    "ContextExpansionContext",
    "ContextExpansionError",
    "ContextExpansionObservation",
    "ContextExpansionReceipt",
    "ContextExpansionRequest",
    "ExplicitLiveOperationalProvider",
    "FreshnessMetadata",
    "Contradiction",
    "EvidenceEdge",
    "EvidenceStatement",
    "GraphValidationError",
    "ProofObligation",
    "ProtectedCondition",
    "GraphProofObligation",
    "GraphResult",
    "OperationalEvidenceContext",
    "OperationalEvidenceReceipt",
    "OperationalQuery",
    "PrivacyPolicy",
    "RecordedOperationalProvider",
    "ScanError",
    "ScanResult",
    "TemporalConclusion",
    "TemporalDebtCandidate",
    "TemporalEpistemicResult",
    "build_graph",
    "graph_from_epistemic_result",
    "receipt_to_evidence_edge",
    "scan_repository",
]
__version__ = "0.1.0"
