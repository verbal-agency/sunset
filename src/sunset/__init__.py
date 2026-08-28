"""Sunset's deterministic discovery API."""

from sunset.models import Candidate, ScanError, ScanResult
from sunset.scanner import scan_repository

__all__ = ["Candidate", "ScanError", "ScanResult", "scan_repository"]
__version__ = "0.1.0"

