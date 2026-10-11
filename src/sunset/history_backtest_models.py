"""Versioned contracts for the G34 historical removal backtest.

Labels here come only from git history (what maintainers did), never from agent
or clone output. See docs/goals/G34-historical-removal-backtest.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Literal

BACKTEST_SCHEMA_VERSION = "1"

EventClass = Literal["marker_only_removal", "fix_with_removal", "retained"]
EVENT_CLASSES: tuple[str, ...] = ("marker_only_removal", "fix_with_removal", "retained")
Split = Literal["development", "holdout"]
SPLITS: tuple[str, ...] = ("development", "holdout")

# Maintainer-derived expectation at the as-of commit. ``retained`` has none: not
# being removed is weak evidence (the marker may be stale but unremoved).
MAINTAINER_EXPECTATION: dict[str, str | None] = {
    "marker_only_removal": "likely_expired",
    "fix_with_removal": "likely_active",
    "retained": None,
}

EXCLUSION_REASONS: tuple[str, ...] = (
    "test_missing_at_child",
    "test_modified",
    "marker_edited",
    "partial_marker_removal",
    "parse_error",
    "test_missing_at_head",
    "marker_changed_by_head",
    "outside_eligibility_window",
    "not_sampled",
)


class BacktestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class MarkerRecord:
    kind: str
    text: str
    reason: str | None
    line: int

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "text": self.text, "reason": self.reason, "line": self.line}


@dataclass(frozen=True, slots=True)
class HistoricalEvent:
    event_id: str
    repository: str
    event_class: EventClass
    test_path: str
    test_qualname: str
    markers: tuple[str, ...]
    marker_kinds: tuple[str, ...]
    as_of_sha: str  # parent commit (or the retained snapshot commit): the only commit evidence may use
    as_of_date: str
    outcome_sha: str  # child commit (or HEAD for retained): never visible to a reasoner
    outcome_date: str
    touched_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "repository": self.repository,
            "event_class": self.event_class,
            "test_path": self.test_path,
            "test_qualname": self.test_qualname,
            "markers": list(self.markers),
            "marker_kinds": list(self.marker_kinds),
            "as_of_sha": self.as_of_sha,
            "as_of_date": self.as_of_date,
            "outcome_sha": self.outcome_sha,
            "outcome_date": self.outcome_date,
            "touched_files": list(self.touched_files),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HistoricalEvent":
        return cls(
            event_id=value["event_id"],
            repository=value["repository"],
            event_class=value["event_class"],
            test_path=value["test_path"],
            test_qualname=value["test_qualname"],
            markers=tuple(value["markers"]),
            marker_kinds=tuple(value["marker_kinds"]),
            as_of_sha=value["as_of_sha"],
            as_of_date=value["as_of_date"],
            outcome_sha=value["outcome_sha"],
            outcome_date=value["outcome_date"],
            touched_files=tuple(value.get("touched_files", ())),
        )


@dataclass(frozen=True, slots=True)
class Exclusion:
    reason: str
    repository: str
    commit: str
    test_path: str
    test_qualname: str

    def to_dict(self) -> dict[str, str]:
        return {
            "reason": self.reason,
            "repository": self.repository,
            "commit": self.commit,
            "test_path": self.test_path,
            "test_qualname": self.test_qualname,
        }


@dataclass(frozen=True, slots=True)
class MiningResult:
    repository: str
    head_sha: str
    horizon_days: int
    commits_scanned: int
    merge_commits_skipped: int
    events: tuple[HistoricalEvent, ...]
    exclusions: tuple[Exclusion, ...]
    retained_candidates_total: int = 0
    schema_version: str = BACKTEST_SCHEMA_VERSION

    @property
    def mined_total(self) -> int:
        return len(self.events) + len(self.exclusions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "head_sha": self.head_sha,
            "horizon_days": self.horizon_days,
            "commits_scanned": self.commits_scanned,
            "merge_commits_skipped": self.merge_commits_skipped,
            "retained_candidates_total": self.retained_candidates_total,
            "counts": {
                "included": len(self.events),
                "excluded": len(self.exclusions),
                "mined_total": self.mined_total,
                "by_class": {c: sum(1 for e in self.events if e.event_class == c) for c in EVENT_CLASSES},
                "by_exclusion": {
                    r: sum(1 for x in self.exclusions if x.reason == r)
                    for r in sorted({x.reason for x in self.exclusions})
                },
            },
            "events": [e.to_dict() for e in self.events],
            "exclusions": [x.to_dict() for x in self.exclusions],
        }


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One piece of case evidence and the single commit it was derived from."""

    kind: str
    derived_from_sha: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "derived_from_sha": self.derived_from_sha, "text": self.text}


@dataclass(frozen=True, slots=True)
class BacktestCase:
    case_id: str
    event_id: str
    repository: str
    event_class: EventClass
    split: Split
    as_of_sha: str
    test_path: str
    test_qualname: str
    marker_kinds: tuple[str, ...]
    evidence: tuple[EvidenceItem, ...]
    evidence_digest: str

    @property
    def evidence_text(self) -> str:
        return "\n".join(item.text for item in self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "event_id": self.event_id,
            "repository": self.repository,
            "event_class": self.event_class,
            "split": self.split,
            "as_of_sha": self.as_of_sha,
            "test_path": self.test_path,
            "test_qualname": self.test_qualname,
            "marker_kinds": list(self.marker_kinds),
            "evidence": [item.to_dict() for item in self.evidence],
            "evidence_digest": self.evidence_digest,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BacktestCase":
        return cls(
            case_id=value["case_id"],
            event_id=value["event_id"],
            repository=value["repository"],
            event_class=value["event_class"],
            split=value["split"],
            as_of_sha=value["as_of_sha"],
            test_path=value["test_path"],
            test_qualname=value["test_qualname"],
            marker_kinds=tuple(value["marker_kinds"]),
            evidence=tuple(EvidenceItem(i["kind"], i["derived_from_sha"], i["text"]) for i in value["evidence"]),
            evidence_digest=value["evidence_digest"],
        )


@dataclass(frozen=True, slots=True)
class CaseRun:
    """Recorded outcome of evaluating one case (reasoners + clone check)."""

    case_id: str
    heuristic_status: str
    agent_status: str | None
    clone_outcome: str | None
    clone_note: str | None = None
    lookback_days_still_stale: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "heuristic_status": self.heuristic_status,
            "agent_status": self.agent_status,
            "clone_outcome": self.clone_outcome,
            "clone_note": self.clone_note,
            "lookback_days_still_stale": self.lookback_days_still_stale,
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CaseRun":
        return cls(
            case_id=value["case_id"],
            heuristic_status=value["heuristic_status"],
            agent_status=value.get("agent_status"),
            clone_outcome=value.get("clone_outcome"),
            clone_note=value.get("clone_note"),
            lookback_days_still_stale=value.get("lookback_days_still_stale"),
            extras=dict(value.get("extras", {})),
        )


__all__ = [
    "BACKTEST_SCHEMA_VERSION",
    "BacktestCase",
    "BacktestError",
    "CaseRun",
    "EVENT_CLASSES",
    "EXCLUSION_REASONS",
    "EventClass",
    "EvidenceItem",
    "Exclusion",
    "HistoricalEvent",
    "MAINTAINER_EXPECTATION",
    "MarkerRecord",
    "MiningResult",
    "SPLITS",
    "Split",
    "canonical_json",
    "digest",
]
