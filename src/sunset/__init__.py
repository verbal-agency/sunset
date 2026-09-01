"""Sunset's deterministic discovery API."""

from sunset.models import Candidate, ScanError, ScanResult
from sunset.scanner import scan_repository
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
    "ConditionHypothesis",
    "EvidenceStatement",
    "ProofObligation",
    "ProtectedCondition",
    "ScanError",
    "ScanResult",
    "TemporalConclusion",
    "TemporalDebtCandidate",
    "TemporalEpistemicResult",
    "scan_repository",
]
__version__ = "0.1.0"
