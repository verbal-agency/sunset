"""Offline validation for Sunset's public, read-only historical corpus.

This module consumes only an already-recorded JSON manifest. It never clones,
contacts, imports, installs, or executes target repositories.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


PUBLIC_CORPUS_SCHEMA_VERSION = "1"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORIES = {
    "langchain": "https://github.com/langchain-ai/langchain.git",
    "langgraph": "https://github.com/langchain-ai/langgraph.git",
    "langsmith-sdk": "https://github.com/langchain-ai/langsmith-sdk.git",
}
_EXPECTED_COUNTS = {"langchain": 12, "langgraph": 4, "langsmith-sdk": 4}

CaseType = Literal["marker_removal", "shim_removal", "retained_marker", "retained_shim"]
Outcome = Literal["removed", "retained"]


class PublicCorpusError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class PublicCorpusCase:
    case_id: str
    case_type: CaseType
    collection_mode: str
    evidence_url: str
    observed_outcome: Outcome
    path: str
    pinned_head: str
    repository: str
    repository_url: str
    source_commit: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PublicCorpusCase":
        return cls(
            case_id=str(value["case_id"]),
            case_type=value["case_type"],
            collection_mode=str(value["collection_mode"]),
            evidence_url=str(value["evidence_url"]),
            observed_outcome=value["observed_outcome"],
            path=str(value["path"]),
            pinned_head=str(value["pinned_head"]),
            repository=str(value["repository"]),
            repository_url=str(value["repository_url"]),
            source_commit=str(value["source_commit"]),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "collection_mode": self.collection_mode,
            "evidence_url": self.evidence_url,
            "observed_outcome": self.observed_outcome,
            "path": self.path,
            "pinned_head": self.pinned_head,
            "repository": self.repository,
            "repository_url": self.repository_url,
            "source_commit": self.source_commit,
        }


@dataclass(frozen=True, slots=True)
class PublicCorpus:
    cases: tuple[PublicCorpusCase, ...]
    collected_at: str
    corpus_id: str
    description: str
    schema_version: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PublicCorpus":
        return cls(
            cases=tuple(PublicCorpusCase.from_dict(item) for item in value["cases"]),
            collected_at=str(value["collected_at"]),
            corpus_id=str(value["corpus_id"]),
            description=str(value["description"]),
            schema_version=str(value.get("schema_version", PUBLIC_CORPUS_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class PublicCorpusReport:
    corpus: PublicCorpus

    def to_dict(self) -> dict[str, object]:
        counts = Counter(case.repository for case in self.corpus.cases)
        outcomes = Counter(case.observed_outcome for case in self.corpus.cases)
        return {
            "cases": [case.to_dict() for case in self.corpus.cases],
            "collected_at": self.corpus.collected_at,
            "corpus_id": self.corpus.corpus_id,
            "description": self.corpus.description,
            "limitations": [
                "Records describe observed public history; they do not predict whether similar code is safe to remove.",
                "Validation reads only the saved manifest and does not contact, clone, import, install, or execute target repositories.",
            ],
            "outcome_counts": dict(sorted(outcomes.items())),
            "repository_counts": dict(sorted(counts.items())),
            "schema_version": self.corpus.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_public_corpus(path: str | Path) -> PublicCorpus:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        corpus = PublicCorpus.from_dict(value)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PublicCorpusError("public_corpus_invalid", str(exc)) from exc
    validate_public_corpus(corpus)
    return corpus


def validate_public_corpus(corpus: PublicCorpus) -> None:
    if corpus.schema_version != PUBLIC_CORPUS_SCHEMA_VERSION:
        raise PublicCorpusError("public_corpus_schema_unsupported", corpus.schema_version)
    if not corpus.collected_at.endswith("Z"):
        raise PublicCorpusError("public_corpus_timestamp_invalid", corpus.collected_at)
    if len(corpus.cases) < sum(_EXPECTED_COUNTS.values()):
        raise PublicCorpusError("public_corpus_too_small", "at least 20 records are required")
    case_ids = [case.case_id for case in corpus.cases]
    if len(set(case_ids)) != len(case_ids):
        raise PublicCorpusError("public_corpus_case_ids_not_unique", "case IDs must be unique")
    counts = Counter(case.repository for case in corpus.cases)
    if dict(counts) != _EXPECTED_COUNTS:
        raise PublicCorpusError("public_corpus_distribution_invalid", str(dict(counts)))
    removals = 0
    retained = 0
    for case in corpus.cases:
        _validate_case(case)
        removals += case.observed_outcome == "removed"
        retained += case.observed_outcome == "retained"
    if removals < 8 or retained < 8:
        raise PublicCorpusError(
            "public_corpus_outcomes_incomplete",
            "at least eight historical removals and eight retained current safeguards are required",
        )


def _validate_case(case: PublicCorpusCase) -> None:
    if case.case_type not in {"marker_removal", "shim_removal", "retained_marker", "retained_shim"}:
        raise PublicCorpusError("public_corpus_case_type_invalid", case.case_id)
    if case.repository not in _REPOSITORIES or case.repository_url != _REPOSITORIES.get(case.repository):
        raise PublicCorpusError("public_corpus_repository_unpinned", case.case_id)
    if not case.path or case.path.startswith("/") or ".." in Path(case.path).parts:
        raise PublicCorpusError("public_corpus_path_invalid", case.case_id)
    if not _SHA_RE.fullmatch(case.pinned_head) or not _SHA_RE.fullmatch(case.source_commit):
        raise PublicCorpusError("public_corpus_sha_invalid", case.case_id)
    if case.collection_mode != "public_git_read_only":
        raise PublicCorpusError("public_corpus_collection_mode_invalid", case.case_id)
    evidence_root = f"https://github.com/langchain-ai/{case.repository}"
    expected_evidence = (
        f"{evidence_root}/commit/{case.source_commit}"
        if case.case_type.endswith("removal")
        else f"{evidence_root}/blob/{case.source_commit}/{case.path}"
    )
    if case.evidence_url != expected_evidence:
        raise PublicCorpusError("public_corpus_evidence_invalid", case.case_id)
    expected_outcome = "removed" if case.case_type.endswith("removal") else "retained"
    if case.observed_outcome != expected_outcome:
        raise PublicCorpusError("public_corpus_outcome_mismatch", case.case_id)
