"""Deterministic import and freezing of owner-supplied G23 decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from sunset.adjudication_models import (
    ADJUDICATION_SCHEMA_VERSION,
    AdjudicationDecision,
    AdjudicationManifest,
    ReviewerAuthority,
)
from sunset.validation_corpus import load_validation_corpus
from sunset.validation_corpus_models import ValidationCorpus


class AdjudicationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_authority(path: str | Path) -> ReviewerAuthority:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("authority must be an object")
        authority = ReviewerAuthority.from_dict(value)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise AdjudicationError("authority_invalid", str(exc)) from exc
    validate_authority(authority)
    return authority


def load_decisions(path: str | Path) -> tuple[AdjudicationDecision, ...]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("decisions"), list):
            raise TypeError("decision packet requires a decisions list")
        decisions = tuple(AdjudicationDecision.from_dict(item) for item in value["decisions"])
    except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise AdjudicationError("decisions_invalid", str(exc)) from exc
    return decisions


def load_exclusions(path: str | Path) -> tuple[dict[str, str], ...]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("excluded_cases"), list):
            raise TypeError("decision packet requires an excluded_cases list")
        if not all(isinstance(item, dict) for item in value["excluded_cases"]):
            raise TypeError("excluded_cases entries must be objects")
        exclusions = tuple({str(k): str(v) for k, v in item.items()} for item in value["excluded_cases"])
    except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise AdjudicationError("decisions_invalid", str(exc)) from exc
    return exclusions


def validate_authority(authority: ReviewerAuthority) -> None:
    if authority.schema_version != ADJUDICATION_SCHEMA_VERSION:
        raise AdjudicationError("schema_unsupported", authority.schema_version)
    if not authority.protocol_version or not authority.reviewer_id or not authority.authority_basis:
        raise AdjudicationError("authority_incomplete", "protocol, reviewer, and authority basis are required")
    if authority.review_mode != "single_reviewer":
        raise AdjudicationError("review_mode_invalid", authority.review_mode)
    if authority.second_review_status != "not_available":
        raise AdjudicationError("second_review_status_invalid", authority.second_review_status)


def source_corpus_digest(corpus: ValidationCorpus) -> str:
    canonical = json.dumps(corpus.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def evidence_ids_from_files(paths: Iterable[str | Path]) -> set[str]:
    """Collect IDs from immutable G22/G22a/G22b/G22c recorded fixtures."""
    ids: set[str] = set()
    for path in paths:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise AdjudicationError("evidence_fixture_invalid", f"{path}: {exc}") from exc
        if not isinstance(value, dict):
            raise AdjudicationError("evidence_fixture_invalid", f"{path}: fixture must be an object")
        for item in value.get("responses", []):
            if isinstance(item, dict) and item.get("evidence_id"):
                ids.add(str(item["evidence_id"]))
    return ids


def freeze_adjudication(
    corpus: ValidationCorpus,
    authority: ReviewerAuthority,
    decisions: tuple[AdjudicationDecision, ...],
    *,
    excluded_cases: tuple[dict[str, str], ...] = (),
    evidence_ids: set[str] | None = None,
    manifest_id: str = "sunset-g23-single-reviewer-v1",
    coverage_limit: str = "Five owner-reviewed cases; all remaining corpus cases explicitly excluded from this pass.",
) -> AdjudicationManifest:
    validate_authority(authority)
    if not decisions and not excluded_cases:
        raise AdjudicationError("coverage_empty", "at least one decision or exclusion is required")
    case_map = {case.case_id: case for case in corpus.cases}
    allowed_evidence = set(evidence_ids or ())
    for case in corpus.cases:
        allowed_evidence.update(item.evidence_id for item in case.evidence)
    seen: set[str] = set()
    for decision in decisions:
        _validate_decision(decision, authority, case_map, allowed_evidence, seen)
        seen.add(decision.case_id)
    excluded_ids: set[str] = set()
    for exclusion in excluded_cases:
        if set(exclusion) != {"case_id", "reason"} or not exclusion["case_id"] or not exclusion["reason"]:
            raise AdjudicationError("exclusion_invalid", "exclusions require case_id and reason")
        case_id = exclusion["case_id"]
        if case_id not in case_map:
            raise AdjudicationError("case_not_found", case_id)
        if case_id in seen or case_id in excluded_ids:
            raise AdjudicationError("duplicate_case_id", case_id)
        excluded_ids.add(case_id)
    if seen | excluded_ids != set(case_map):
        missing = sorted(set(case_map) - seen - excluded_ids)
        raise AdjudicationError("coverage_incomplete", ",".join(missing))
    unsigned = AdjudicationManifest(
        manifest_id=manifest_id,
        source_corpus_id=corpus.corpus_id,
        source_corpus_digest=source_corpus_digest(corpus),
        protocol_version=authority.protocol_version,
        reviewer_id=authority.reviewer_id,
        review_mode=authority.review_mode,
        second_review_status=authority.second_review_status,
        decisions=tuple(sorted(decisions, key=lambda item: item.case_id)),
        excluded_cases=tuple(sorted((dict(item) for item in excluded_cases), key=lambda item: item["case_id"])),
        split_identities={
            split: tuple(sorted(case.case_id for case in corpus.cases if case.split == split))
            for split in ("development", "holdout", "excluded")
        },
        coverage_limit=coverage_limit,
    )
    canonical = json.dumps(unsigned.unsigned_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical + b"\n" + b"adjudication-freeze-policy-v1").hexdigest()
    return AdjudicationManifest(
        manifest_id=unsigned.manifest_id,
        source_corpus_id=unsigned.source_corpus_id,
        source_corpus_digest=unsigned.source_corpus_digest,
        protocol_version=unsigned.protocol_version,
        reviewer_id=unsigned.reviewer_id,
        review_mode=unsigned.review_mode,
        second_review_status=unsigned.second_review_status,
        decisions=unsigned.decisions,
        excluded_cases=unsigned.excluded_cases,
        split_identities=unsigned.split_identities,
        coverage_limit=unsigned.coverage_limit,
        manifest_digest=digest,
        schema_version=unsigned.schema_version,
    )


def _validate_decision(decision: AdjudicationDecision, authority: ReviewerAuthority, case_map: dict[str, Any], allowed_evidence: set[str], seen: set[str]) -> None:
    if decision.case_id not in case_map:
        raise AdjudicationError("case_not_found", decision.case_id)
    if decision.case_id in seen:
        raise AdjudicationError("duplicate_case_id", decision.case_id)
    if decision.protocol_version != authority.protocol_version or decision.reviewer_id != authority.reviewer_id:
        raise AdjudicationError("authority_mismatch", decision.case_id)
    if not decision.protected_condition_hypothesis:
        raise AdjudicationError("hypothesis_missing", decision.case_id)
    if decision.condition_status not in {"identified", "active", "likely_expired", "unknown", "contradictory"}:
        raise AdjudicationError("condition_status_invalid", decision.case_id)
    if decision.evidence_sufficiency not in {"sufficient", "insufficient", "contradictory", "abstained"}:
        raise AdjudicationError("evidence_sufficiency_invalid", decision.case_id)
    if not decision.proof_obligations:
        raise AdjudicationError("proof_obligations_missing", decision.case_id)
    if not decision.validation_scope:
        raise AdjudicationError("validation_scope_missing", decision.case_id)
    if not decision.evidence_ids:
        raise AdjudicationError("evidence_ids_missing", decision.case_id)
    unknown = sorted(set(decision.evidence_ids) - allowed_evidence)
    if unknown:
        raise AdjudicationError("evidence_not_found", unknown[0])
    if len(set(decision.evidence_ids)) != len(decision.evidence_ids):
        raise AdjudicationError("duplicate_evidence_id", decision.case_id)
    if any(not item.startswith(f"{decision.case_id}:") for item in decision.evidence_ids):
        raise AdjudicationError("evidence_case_mismatch", decision.case_id)
    if decision.evidence_sufficiency == "abstained" and not decision.abstention_reason:
        raise AdjudicationError("abstention_reason_missing", decision.case_id)
    if decision.exclusion_reason:
        raise AdjudicationError("decision_exclusion_unexpected", decision.case_id)


__all__ = [
    "AdjudicationError", "evidence_ids_from_files", "freeze_adjudication",
    "load_authority", "load_decisions", "load_exclusions", "source_corpus_digest", "validate_authority",
]
