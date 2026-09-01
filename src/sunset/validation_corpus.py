"""Deterministic, offline audit of provenance-bound validation packets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sunset.validation_corpus_models import (
    CorpusAudit,
    ValidationCorpus,
    VALIDATION_CORPUS_SCHEMA_VERSION,
)


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_REQUIREMENTS = {
    "introduction_context", "condition_status", "counter_evidence", "validation_scope"
}
_SOURCE_KINDS = {"public_git", "recorded_artifact"}
_EVIDENCE_ROLES = {
    "historical_outcome", "introduction_context", "condition_evidence", "counter_evidence", "validation_scope"
}
_HISTORICAL_OUTCOMES = {"removed", "retained", "unknown"}
_SPLITS = {"development", "holdout", "excluded"}
_PACKET_STATES = {"unprepared", "ready_for_adjudication", "excluded"}
_REQUIREMENT_KINDS = _REQUIRED_REQUIREMENTS


class ValidationCorpusError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_validation_corpus(path: str | Path) -> ValidationCorpus:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("corpus must be a JSON object")
        corpus = ValidationCorpus.from_dict(value)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ValidationCorpusError):
            raise
        raise ValidationCorpusError("validation_corpus_invalid", str(exc)) from exc
    validate_validation_corpus(corpus)
    return corpus


def validate_validation_corpus(corpus: ValidationCorpus) -> None:
    if corpus.schema_version != VALIDATION_CORPUS_SCHEMA_VERSION:
        raise ValidationCorpusError("schema_unsupported", corpus.schema_version)
    if not corpus.corpus_id or not corpus.source_manifest_id:
        raise ValidationCorpusError("corpus_identity_missing", "corpus and source manifest IDs are required")
    case_ids = [case.case_id for case in corpus.cases]
    source_ids = [case.source_case_id for case in corpus.cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValidationCorpusError("duplicate_case_id", "case IDs must be unique")
    if len(set(source_ids)) != len(source_ids):
        raise ValidationCorpusError("duplicate_source_case_id", "source case IDs must be unique")
    for case in corpus.cases:
        _validate_case(case)


def audit_validation_corpus(corpus: ValidationCorpus, *, max_cases: int | None = None) -> CorpusAudit:
    validate_validation_corpus(corpus)
    if max_cases is not None and max_cases <= 0:
        raise ValidationCorpusError("max_cases_invalid", "max_cases must be a positive integer")
    ordered = tuple(sorted(corpus.cases, key=lambda case: case.case_id))
    processed = ordered if max_cases is None else ordered[:max_cases]
    unprocessed = () if max_cases is None else ordered[max_cases:]
    counts: dict[str, dict[str, int]] = {"split": {}, "historical_outcome": {}, "packet_state": {}}
    missing: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    for case in processed:
        _increment(counts["split"], case.split)
        _increment(counts["historical_outcome"], case.historical_outcome)
        _increment(counts["packet_state"], case.packet_state)
        for requirement in case.requirements:
            if not requirement.evidence_ids:
                missing.append({"case_id": case.case_id, "requirement_id": requirement.requirement_id, "kind": requirement.kind})
        if case.packet_state == "excluded":
            excluded.append({"case_id": case.case_id, "reason": case.exclusion_reason or ""})
    canonical = json.dumps(corpus.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    policy = b"validation-corpus-audit-policy-v1"
    digest = hashlib.sha256(canonical + b"\n" + policy).hexdigest()
    return CorpusAudit(
        corpus_digest=digest,
        corpus_id=corpus.corpus_id,
        schema_version=corpus.schema_version,
        counts={key: dict(sorted(value.items())) for key, value in counts.items()},
        missing_requirements=tuple(sorted(missing, key=lambda item: (item["case_id"], item["requirement_id"]))),
        excluded_cases=tuple(sorted(excluded, key=lambda item: item["case_id"])),
        processed_case_ids=tuple(case.case_id for case in processed),
        unprocessed_case_ids=tuple(case.case_id for case in unprocessed),
        complete=not unprocessed,
        gate_ready=False,
    )


def _validate_case(case: Any) -> None:
    if not case.case_id or not case.source_case_id or not case.candidate_family:
        raise ValidationCorpusError("case_identity_missing", case.case_id or "")
    if case.historical_outcome not in _HISTORICAL_OUTCOMES:
        raise ValidationCorpusError("historical_outcome_invalid", case.case_id)
    if case.split not in _SPLITS:
        raise ValidationCorpusError("split_invalid", case.case_id)
    if case.packet_state not in _PACKET_STATES:
        raise ValidationCorpusError("packet_state_invalid", case.case_id)
    if not case.candidate_path or case.candidate_path.startswith("/") or ".." in Path(case.candidate_path).parts:
        raise ValidationCorpusError("candidate_path_invalid", case.case_id)
    if not _SHA_RE.fullmatch(case.pinned_head):
        raise ValidationCorpusError("pinned_head_invalid", case.case_id)
    if case.split == "excluded" and case.packet_state != "excluded":
        raise ValidationCorpusError("excluded_split_state_mismatch", case.case_id)
    if case.packet_state == "excluded" and not case.exclusion_reason:
        raise ValidationCorpusError("exclusion_reason_missing", case.case_id)
    if case.packet_state != "excluded" and case.exclusion_reason is not None:
        raise ValidationCorpusError("exclusion_reason_unexpected", case.case_id)
    evidence_ids: list[str] = []
    for evidence in case.evidence:
        if not evidence.evidence_id or evidence.evidence_id in evidence_ids:
            raise ValidationCorpusError("duplicate_evidence_id", case.case_id)
        evidence_ids.append(evidence.evidence_id)
        if evidence.source_kind not in _SOURCE_KINDS:
            raise ValidationCorpusError("evidence_source_unsupported", case.case_id)
        if evidence.role not in _EVIDENCE_ROLES or not evidence.locator:
            raise ValidationCorpusError("evidence_invalid", case.case_id)
        if evidence.source_kind == "public_git" and not _SHA_RE.fullmatch(evidence.commit_sha or ""):
            raise ValidationCorpusError("evidence_commit_invalid", case.case_id)
        if evidence.source_kind == "recorded_artifact" and not evidence.artifact_id:
            raise ValidationCorpusError("evidence_artifact_missing", case.case_id)
    requirement_ids: list[str] = []
    kinds: set[str] = set()
    for requirement in case.requirements:
        if not requirement.requirement_id or requirement.requirement_id in requirement_ids:
            raise ValidationCorpusError("duplicate_requirement_id", case.case_id)
        requirement_ids.append(requirement.requirement_id)
        if requirement.kind not in _REQUIREMENT_KINDS or not requirement.proof_obligation:
            raise ValidationCorpusError("requirement_invalid", case.case_id)
        kinds.add(requirement.kind)
        if any(item not in evidence_ids for item in requirement.evidence_ids):
            raise ValidationCorpusError("evidence_reference_dangling", case.case_id)
    if case.packet_state == "unprepared" and _REQUIRED_REQUIREMENTS <= kinds:
        raise ValidationCorpusError("packet_state_invalid", case.case_id)
    if case.packet_state == "ready_for_adjudication" and not _REQUIRED_REQUIREMENTS <= kinds:
        raise ValidationCorpusError("packet_requirements_incomplete", case.case_id)


def _increment(target: dict[str, int], key: str) -> None:
    target[key] = target.get(key, 0) + 1


__all__ = ["ValidationCorpusError", "audit_validation_corpus", "load_validation_corpus", "validate_validation_corpus"]
