"""Sunset's deterministic discovery API."""

from sunset.models import Candidate, ScanError, ScanResult
from sunset.scanner import scan_repository
from sunset.claim_evidence_graph import GraphValidationError, build_graph, graph_from_epistemic_result
from sunset.claim_evidence_models import Claim, Contradiction, EvidenceEdge, GraphProofObligation, GraphResult
from sunset.context_expansion import ContextExpansionContext, ContextExpansionError
from sunset.context_expansion_models import ContextExpansionObservation, ContextExpansionReceipt, ContextExpansionRequest
from sunset.operational_evidence import ExplicitLiveOperationalProvider, OperationalEvidenceContext, RecordedOperationalProvider, receipt_to_evidence_edge
from sunset.operational_evidence_models import FreshnessMetadata, OperationalEvidenceReceipt, OperationalQuery, PrivacyPolicy
from sunset.casefile_finalizer import finalize_case_file, review_graph
from sunset.review_models import CaseFile, CaseFileError, ClaimVerification, ReviewFinding, ReviewRequest, ReviewResult
from sunset.calibration import CalibrationError, evaluate_release
from sunset.adjudication import AdjudicationError, freeze_adjudication
from sunset.adjudication_models import AdjudicationDecision, AdjudicationManifest, ReviewerAuthority
from sunset.baseline_evaluation import BaselineEvaluationError, evaluate_baseline, load_recorded_traces, load_reference_cases
from sunset.optimization import OptimizationError, load_experiments, run_optimization
from sunset.calibration_models import BenchmarkCase as CalibrationCase, EvaluationRun, ExpectedConditionLabel, MetricRecord, ReleaseGateResult, ReleaseThreshold
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
    "CaseFile",
    "CaseFileError",
    "CalibrationCase",
    "CalibrationError",
    "AdjudicationError",
    "AdjudicationDecision",
    "AdjudicationManifest",
    "BaselineEvaluationError",
    "OptimizationError",
    "ReviewerAuthority",
    "Claim",
    "ConditionHypothesis",
    "ContextExpansionContext",
    "ContextExpansionError",
    "ContextExpansionObservation",
    "ContextExpansionReceipt",
    "ContextExpansionRequest",
    "ClaimVerification",
    "ExplicitLiveOperationalProvider",
    "FreshnessMetadata",
    "ReviewFinding",
    "ReviewRequest",
    "ReviewResult",
    "EvaluationRun",
    "ExpectedConditionLabel",
    "MetricRecord",
    "ReleaseGateResult",
    "ReleaseThreshold",
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
    "finalize_case_file",
    "review_graph",
    "evaluate_release",
    "freeze_adjudication",
    "evaluate_baseline",
    "load_recorded_traces",
    "load_reference_cases",
    "load_experiments",
    "run_optimization",
    "scan_repository",
]
__version__ = "0.1.0"
