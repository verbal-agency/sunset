"""Deterministic, read-only discovery of bounded repository-level signals."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import PurePosixPath
import re
from collections.abc import Collection

from sunset.broad_collectors_models import BROAD_COLLECTOR_SCHEMA_VERSION, BroadCandidate, BroadScanResult
from sunset.git_repository import GitRepository, RepositoryError


_SOURCE_SUFFIXES = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript"}
_CONFIG_NAMES = {"pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "package.json", ".nvmrc", ".python-version"}
_PATTERNS = (
    ("deprecation_annotation", re.compile(r"(?i)@deprecated|DeprecationWarning|deprecated\s*\("), "deprecation"),
    ("feature_flag_lifecycle", re.compile(r"(?i)feature[_-]?flag|featureFlags|isFeatureEnabled\s*\(|flagKey\b|flags\.[A-Za-z_]"), "operational"),
    ("environment_gate", re.compile(r"(?i)os\.getenv\s*\(|os\.environ\[|process\.env\b"), "operational"),
)
_CONFIG_PATTERN = re.compile(r"(?i)(requires-python|python_requires|\"engines\"|node-version|python-version|minimum[_-]?(python|node)|support(ed)?[_-]?versions?)")


_BLAME_CACHE: dict[tuple[str, str], dict[int, str]] = {}


def discover_broad_repository(target: str) -> BroadScanResult:
    """Discover broad signals without invoking Git history commands."""

    repository = GitRepository.open(target)
    candidates: list[BroadCandidate] = []
    errors: list[dict[str, object]] = []
    for path in repository.list_paths():
        pure = PurePosixPath(path)
        suffix = pure.suffix.lower()
        language = _SOURCE_SUFFIXES.get(suffix)
        is_config = pure.name in _CONFIG_NAMES or path.startswith(".github/")
        if language is None and not is_config:
            continue
        try:
            source = repository.read_text(path)
        except RepositoryError as exc:
            errors.append({"kind": exc.code, "path": path, "message": exc.message})
            continue
        lines = source.splitlines()
        discoveries: list[tuple[int, int, str, str, str | None, bool]] = []
        if language is not None:
            for line_number, line in enumerate(lines, 1):
                for signal, pattern, role in _PATTERNS:
                    match = pattern.search(line)
                    if match:
                        dynamic = signal in {"feature_flag_lifecycle", "environment_gate"} and ("getattr(" in line or "eval(" in line or "dynamic_name" in line or "[]" in line)
                        discoveries.append((line_number, match.start(), signal, role, line.strip(), dynamic))
        if is_config:
            for line_number, line in enumerate(lines, 1):
                match = _CONFIG_PATTERN.search(line)
                if match:
                    discoveries.append((line_number, match.start(), "support_constraint", "scope_limit", line.strip(), False))
        for line_number, column, signal, role, condition, dynamic in discoveries:
            candidate_id = _candidate_id(repository.head, path, line_number, column, signal, condition)
            candidates.append(BroadCandidate(candidate_id, _family(signal), language or "repository", path, line_number, column, signal, _subject(condition), condition, role, repository.head, "", dynamic, "deferred"))
    candidates.sort(key=lambda item: (item.path, item.line, item.column, item.signal, item.candidate_id))
    errors.sort(key=lambda item: (str(item.get("path", "")), int(item.get("line", -1)), int(item.get("column", -1))))
    return BroadScanResult(repository.head, tuple(candidates), tuple(errors), provenance_mode="deferred")


def enrich_broad_provenance(
    target: str,
    discovered: BroadScanResult | None = None,
    *,
    candidate_ids: Collection[str] | None = None,
) -> BroadScanResult:
    """Attach cached, file-batched blame to selected discovered candidates."""

    repository = GitRepository.open(target)
    result = discovered or discover_broad_repository(target)
    selected = set(candidate_ids) if candidate_ids is not None else {item.candidate_id for item in result.candidates}
    mappings: dict[str, dict[int, str]] = {}
    errors = list(result.errors)
    enriched: list[BroadCandidate] = []
    for candidate in result.candidates:
        if candidate.candidate_id not in selected:
            enriched.append(candidate)
            continue
        mapping = mappings.get(candidate.path)
        if mapping is None:
            cache_key = (repository.head, candidate.path)
            mapping = _BLAME_CACHE.get(cache_key)
            if mapping is None:
                try:
                    mapping = repository.blame_file(candidate.path)
                except RepositoryError as exc:
                    errors.append({"kind": exc.code, "path": candidate.path, "message": exc.message})
                    mapping = {}
                else:
                    _BLAME_CACHE[cache_key] = mapping
            mappings[candidate.path] = mapping
        if not mapping:
            enriched.append(replace(candidate, provenance_status="incomplete"))
            continue
        blame = mapping.get(candidate.line)
        if blame is None:
            errors.append({"kind": "git_blame_failed", "path": candidate.path, "message": f"Git blame returned no commit for line {candidate.line}", "line": candidate.line, "column": candidate.column})
            enriched.append(replace(candidate, provenance_status="incomplete"))
            continue
        enriched.append(BroadCandidate(candidate.candidate_id, candidate.candidate_family, candidate.language, candidate.path, candidate.line, candidate.column, candidate.signal, candidate.subject, candidate.condition, candidate.evidence_role, candidate.repository_head, blame, candidate.unsupported_dynamic, "complete"))
    enriched.sort(key=lambda item: (item.path, item.line, item.column, item.signal, item.candidate_id))
    errors.sort(key=lambda item: (str(item.get("path", "")), int(item.get("line", -1)), int(item.get("column", -1))))
    all_complete = bool(enriched) and all(item.provenance_status == "complete" for item in enriched)
    mode = "complete" if all_complete else ("partial" if any(item.provenance_status == "complete" for item in enriched) else "deferred")
    return BroadScanResult(repository.head, tuple(enriched), tuple(errors), provenance_mode=mode)


def scan_broad_repository(target: str) -> BroadScanResult:
    """Discover and fully enrich broad signals (compatibility API)."""

    return enrich_broad_provenance(target, discover_broad_repository(target))


def _family(signal: str) -> str:
    return {"deprecation_annotation": "deprecation_lifecycle", "feature_flag_lifecycle": "feature_flag", "environment_gate": "environment_gate", "support_constraint": "support_constraint"}[signal]


def _subject(condition: str | None) -> str | None:
    if not condition:
        return None
    return condition[:120]


def _candidate_id(head: str, path: str, line: int, column: int, signal: str, condition: str | None) -> str:
    value = "\0".join((BROAD_COLLECTOR_SCHEMA_VERSION, head, path, str(line), str(column), signal, condition or ""))
    return f"sunset-broad-v{BROAD_COLLECTOR_SCHEMA_VERSION}-{hashlib.sha256(value.encode()).hexdigest()[:24]}"


__all__ = ["discover_broad_repository", "enrich_broad_provenance", "scan_broad_repository"]
