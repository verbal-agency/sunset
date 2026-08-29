"""Versioned models for a bounded, local-only Sunset investigation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any


INVESTIGATION_SCHEMA_VERSION = "1"
CLAIM_KINDS = frozenset({"fact", "inference", "contradiction", "unknown", "rejected_hypothesis"})


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    claim_id: str
    kind: str
    statement: str
    evidence_ids: tuple[str, ...]
    node: str

    def __post_init__(self) -> None:
        if self.kind not in CLAIM_KINDS:
            raise ValueError(f"unsupported ledger claim kind: {self.kind}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceSelection:
    artifact_id: str
    byte_length: int
    source_kind: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TokenUsage:
    node: str
    input_tokens: int
    output_tokens: int
    estimated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TokenBaseline:
    full_context_tokens: int
    working_memory_tokens: int
    raw_artifact_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InvestigationError:
    kind: str
    message: str
    node: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InvestigationResult:
    candidate_id: str
    checkpoint_id: str
    collector: str
    errors: tuple[InvestigationError, ...]
    ledger: tuple[LedgerEntry, ...]
    open_questions: tuple[str, ...]
    repository_head: str
    run_id: str
    selected_evidence: tuple[EvidenceSelection, ...]
    status: str
    token_baseline: TokenBaseline
    token_usage: tuple[TokenUsage, ...]
    schema_version: str = INVESTIGATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "checkpoint_id": self.checkpoint_id,
            "collector": self.collector,
            "errors": [item.to_dict() for item in self.errors],
            "ledger": [item.to_dict() for item in self.ledger],
            "open_questions": list(self.open_questions),
            "repository_head": self.repository_head,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "selected_evidence": [item.to_dict() for item in self.selected_evidence],
            "status": self.status,
            "token_baseline": self.token_baseline.to_dict(),
            "token_usage": [item.to_dict() for item in self.token_usage],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
