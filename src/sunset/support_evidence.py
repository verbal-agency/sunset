"""Bounded, recorded-first provider for declared-support evidence."""

from __future__ import annotations

import base64
import hashlib
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sunset.artifact_store import ArtifactStore
from sunset.provenance_models import ArtifactRef
from sunset.support_evidence_models import (
    SupportCaptureDiagnostic,
    SupportEvidenceCase,
    SupportEvidenceEntry,
    SupportEvidenceReceipt,
    SupportEvidenceSelection,
    SupportEvidenceSupplement,
    SUPPORT_EVIDENCE_SCHEMA_VERSION,
)
from sunset.validation_corpus_models import ValidationCorpus


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_PATH_RE = re.compile(r"^[^\x00]+$")
_EVIDENCE_CLASSES = {
    "packaging_metadata", "published_artifact", "ci_support",
    "support_documentation", "dependency_marker",
}
_SOURCE_KINDS = {"public_git", "public_registry"}
_ALLOWED_HOSTS = (
    "files.pythonhosted.org",
    "github.com",
    "patch-diff.githubusercontent.com",
    "pypi.org",
    "raw.githubusercontent.com",
)


class SupportEvidenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SupportEvidenceProvider(Protocol):
    name: str

    def fetch(self, entry: SupportEvidenceEntry, *, max_bytes: int) -> tuple[str, str, bytes | None, str | None]: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def _open_without_redirects(request: Request, timeout: int):
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


class RecordedSupportEvidenceProvider:
    """Fixture-backed support provider; it never opens a socket."""

    name = "recorded-support"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser().resolve()
        self._responses: dict[str, dict[str, Any]] = {}
        self._error: str | None = None
        try:
            raw = self.fixture_path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != SUPPORT_EVIDENCE_SCHEMA_VERSION:
                raise ValueError("fixture requires schema_version 1")
            for item in value.get("responses", []):
                if not isinstance(item, dict) or not item.get("evidence_id"):
                    raise ValueError("fixture response requires evidence_id")
                self._responses[str(item["evidence_id"])] = item
            self.fixture_digest = hashlib.sha256(raw).hexdigest()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._error = str(exc)
            self.fixture_digest = hashlib.sha256(b"").hexdigest()

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:{self.fixture_digest}"

    def fetch(self, entry: SupportEvidenceEntry, *, max_bytes: int = 65_536) -> tuple[str, str, bytes | None, str | None]:
        if self._error:
            return "failed", "Recorded support fixture is unavailable.", None, "recorded_fixture_unavailable"
        item = self._responses.get(entry.evidence_id)
        if item is None:
            return "missing", "No recorded support response exists for this entry.", None, "recorded_response_missing"
        outcome = str(item.get("outcome", "failed"))
        if outcome == "not_applicable":
            return "not_applicable", str(item.get("summary", "Evidence class is not applicable.")), None, None
        if outcome != "available":
            return outcome if outcome in {"missing", "failed", "budget_exhausted", "unsupported"} else "failed", str(item.get("summary", "Recorded support evidence is unavailable.")), None, str(item.get("error_kind")) if item.get("error_kind") else None
        try:
            if "body_base64" in item:
                raw = base64.b64decode(str(item["body_base64"]), validate=True)
            else:
                raw = str(item.get("body", "")).encode("utf-8")
        except (ValueError, TypeError):
            return "failed", "Recorded support evidence has invalid bytes.", None, "fixture_body_invalid"
        if len(raw) > max_bytes:
            return "budget_exhausted", "Recorded support evidence exceeds the byte budget.", None, "response_too_large"
        return "available", str(item.get("summary", "Recorded support evidence returned.")), raw, None


class LiveSupportEvidenceProvider:
    """Opt-in HTTPS provider for explicitly declared GitHub and PyPI URLs."""

    name = "support-live"

    def __init__(
        self,
        opener: Callable[..., Any] | None = None,
        *,
        allowed_hosts: tuple[str, ...] = _ALLOWED_HOSTS,
        timeout_seconds: int = 10,
    ) -> None:
        self._opener = opener or _open_without_redirects
        self.allowed_hosts = tuple(sorted(set(allowed_hosts)))
        self.timeout_seconds = timeout_seconds

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:hosts={','.join(self.allowed_hosts)}:timeout={self.timeout_seconds}"

    def fetch(self, entry: SupportEvidenceEntry, *, max_bytes: int = 65_536) -> tuple[str, str, bytes | None, str | None]:
        if entry.status != "capture" or not entry.locator:
            return "not_applicable", "Evidence entry does not request capture.", None, None
        url = entry.locator
        redirects = 0
        while True:
            host = (urlparse(url).hostname or "").lower()
            if urlparse(url).scheme != "https" or host not in self.allowed_hosts:
                return "unsupported", "Support evidence host is not allowlisted.", None, "host_not_allowlisted"
            headers = {"Accept": "application/json"} if entry.source_kind == "public_registry" else {"Accept": "text/plain, application/json"}
            try:
                with self._opener(Request(url, headers=headers), timeout=self.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    location = response.headers.get("Location") if hasattr(response, "headers") else None
                    if 300 <= status < 400 and location:
                        if redirects >= 1:
                            return "failed", "Support evidence exceeded the one-redirect bound.", None, "redirect_limit"
                        url = urljoin(url, location)
                        redirects += 1
                        continue
                    raw = response.read(max_bytes + 1)
            except HTTPError as exc:
                location = exc.headers.get("Location") if exc.headers else None
                if 300 <= exc.code < 400 and location:
                    if redirects >= 1:
                        return "failed", "Support evidence exceeded the one-redirect bound.", None, "redirect_limit"
                    url = urljoin(url, location)
                    redirects += 1
                    continue
                return ("missing" if exc.code == 404 else "failed", "Support evidence lookup failed; no support conclusion was made.", None, f"http_{exc.code}")
            except (URLError, OSError, IncompleteRead) as exc:
                return "failed", "Support evidence lookup failed; no support conclusion was made.", None, type(exc).__name__.lower()
            if not isinstance(raw, bytes):
                return "failed", "Support evidence returned a non-byte response.", None, "malformed_response"
            if len(raw) > max_bytes:
                return "budget_exhausted", "Support evidence exceeds the byte budget.", None, "response_too_large"
            return "available", "Declared support evidence returned.", raw, None


def load_support_selection(path: str | Path) -> SupportEvidenceSelection:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("support selection must be an object")
        selection = SupportEvidenceSelection.from_dict(value)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SupportEvidenceError("selection_invalid", str(exc)) from exc
    return selection


def validate_support_selection(selection: SupportEvidenceSelection, corpus: ValidationCorpus) -> None:
    if selection.schema_version != SUPPORT_EVIDENCE_SCHEMA_VERSION:
        raise SupportEvidenceError("schema_unsupported", selection.schema_version)
    if selection.selection_status != "owner_approved" or selection.owner_approval_required:
        raise SupportEvidenceError("selection_not_approved", "owner-approved selections are required before capture")
    canonical = json.dumps(corpus.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_digest = hashlib.sha256(canonical).hexdigest()
    if selection.g21_manifest_id != corpus.corpus_id or selection.g21_manifest_digest != expected_digest:
        raise SupportEvidenceError("manifest_mismatch", "supplement is not bound to the supplied G21 corpus")
    if not _SHA_RE.fullmatch(selection.pinned_head):
        raise SupportEvidenceError("pinned_head_invalid", selection.pinned_head)
    corpus_cases = {case.case_id: case for case in corpus.cases}
    seen_cases: set[str] = set()
    seen_entries: set[str] = set()
    for selected in selection.cases:
        case = corpus_cases.get(selected.case_id)
        if case is None:
            raise SupportEvidenceError("case_not_found", selected.case_id)
        if selected.case_id in seen_cases:
            raise SupportEvidenceError("duplicate_case_id", selected.case_id)
        seen_cases.add(selected.case_id)
        if selected.candidate_path != case.candidate_path or selection.pinned_head != case.pinned_head or selection.repository != case.repository:
            raise SupportEvidenceError("case_binding_mismatch", selected.case_id)
        classes: set[str] = set()
        for entry in selected.entries:
            if entry.evidence_id in seen_entries:
                raise SupportEvidenceError("duplicate_evidence_id", entry.evidence_id)
            seen_entries.add(entry.evidence_id)
            if entry.case_id != selected.case_id or entry.evidence_class not in _EVIDENCE_CLASSES:
                raise SupportEvidenceError("entry_binding_invalid", entry.evidence_id)
            classes.add(entry.evidence_class)
            _validate_entry(entry, case.pinned_head)
        if classes != _EVIDENCE_CLASSES:
            missing = sorted(_EVIDENCE_CLASSES - classes)
            raise SupportEvidenceError("evidence_class_incomplete", ",".join(missing))
    if not seen_cases:
        raise SupportEvidenceError("selection_empty", "at least one case is required")


def _validate_entry(entry: SupportEvidenceEntry, pinned_head: str) -> None:
    if entry.status not in {"capture", "not_applicable"} or not entry.description:
        raise SupportEvidenceError("entry_invalid", entry.evidence_id)
    if entry.status == "not_applicable":
        if not entry.reason or any(item is not None for item in (entry.source_kind, entry.locator, entry.commit_sha, entry.path, entry.release_identity)):
            raise SupportEvidenceError("not_applicable_invalid", entry.evidence_id)
        return
    if entry.source_kind not in _SOURCE_KINDS or not entry.locator:
        raise SupportEvidenceError("source_invalid", entry.evidence_id)
    parsed = urlparse(entry.locator)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        raise SupportEvidenceError("host_not_allowlisted", entry.evidence_id)
    if entry.source_kind == "public_git":
        if not _SHA_RE.fullmatch(entry.commit_sha or "") or entry.commit_sha != pinned_head:
            raise SupportEvidenceError("commit_binding_invalid", entry.evidence_id)
        if not entry.path or entry.path.startswith("/") or ".." in Path(entry.path).parts or not _SAFE_PATH_RE.fullmatch(entry.path):
            raise SupportEvidenceError("path_invalid", entry.evidence_id)
    else:
        if not entry.release_identity:
            raise SupportEvidenceError("release_identity_missing", entry.evidence_id)


def capture_support_evidence(
    corpus: ValidationCorpus,
    selection: SupportEvidenceSelection,
    store: ArtifactStore,
    output_fixture: str | Path,
    *,
    provider: SupportEvidenceProvider | None = None,
    max_bytes: int = 65_536,
    timeout_seconds: int = 10,
    diagnostic_output: str | Path | None = None,
) -> SupportEvidenceSupplement:
    if max_bytes <= 0 or timeout_seconds <= 0:
        raise SupportEvidenceError("capture_budget_invalid", "byte and timeout budgets must be positive")
    validate_support_selection(selection, corpus)
    provider = provider or LiveSupportEvidenceProvider(timeout_seconds=timeout_seconds)
    selection_digest = hashlib.sha256(json.dumps(selection.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    entries = tuple(entry for case in selection.cases for entry in case.entries)
    receipts: list[SupportEvidenceReceipt] = []
    diagnostics: list[SupportCaptureDiagnostic] = []
    responses: list[dict[str, Any]] = []
    for entry in entries:
        if entry.status == "not_applicable":
            receipts.append(SupportEvidenceReceipt(entry, "not_applicable", entry.reason or entry.description, None, provider=getattr(provider, "name", "recorded-support"), freshness_key=entry.freshness_scope or "declared-v1"))
            responses.append({"evidence_id": entry.evidence_id, "entry": entry.to_dict(), "outcome": "not_applicable", "summary": entry.reason or entry.description})
            continue
        try:
            outcome, summary, raw, error_kind = provider.fetch(entry, max_bytes=max_bytes)
        except (OSError, ValueError, RuntimeError) as exc:
            outcome, summary, raw, error_kind = "failed", "Support evidence provider failed; no support conclusion was made.", None, type(exc).__name__.lower()
        artifact: ArtifactRef | None = None
        digest: str | None = None
        if outcome == "available" and raw is not None:
            digest = hashlib.sha256(raw).hexdigest()
            artifact = store.put(raw, media_type="application/json" if entry.source_kind == "public_registry" else "text/plain", source_kind=f"support_{entry.evidence_class}", source_locator=entry.locator or "")
            response: dict[str, Any] = {"evidence_id": entry.evidence_id, "entry": entry.to_dict(), "outcome": "available", "summary": summary, "source_locator": entry.locator, "digest": digest, "byte_length": len(raw)}
            try:
                response["body"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                response["body_base64"] = base64.b64encode(raw).decode("ascii")
            responses.append(response)
        receipts.append(SupportEvidenceReceipt(entry, outcome, summary, entry.locator, artifact, digest, len(raw) if raw is not None else 0, getattr(provider, "name", "support-live"), entry.freshness_scope or "declared-v1", error_kind))
        if outcome != "available":
            diagnostics.append(SupportCaptureDiagnostic("transport", error_kind or outcome, summary, (urlparse(entry.locator or "").hostname or None), int(error_kind.removeprefix("http_")) if error_kind and error_kind.startswith("http_") and error_kind.removeprefix("http_").isdigit() else None))
            responses.append({"evidence_id": entry.evidence_id, "entry": entry.to_dict(), "outcome": outcome, "summary": summary, "error_kind": error_kind})
    failed = [receipt for receipt in receipts if receipt.outcome not in {"available", "not_applicable"}]
    status = "verified" if not failed else ("partial" if any(item.outcome == "available" for item in receipts) else "blocked")
    fixture_digest: str | None = None
    if status == "verified":
        payload = {
            "schema_version": SUPPORT_EVIDENCE_SCHEMA_VERSION,
            "supplement_id": selection.supplement_id,
            "g21_manifest_digest": selection.g21_manifest_digest,
            "selection_digest": selection_digest,
            "provider_policy": {"name": getattr(provider, "name", "support-live"), "allowed_hosts": list(getattr(provider, "allowed_hosts", _ALLOWED_HOSTS)), "timeout_seconds": timeout_seconds, "max_bytes": max_bytes},
            "responses": responses,
        }
        fixture_bytes = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        fixture_digest = hashlib.sha256(fixture_bytes).hexdigest()
        _atomic_write(Path(output_fixture), fixture_bytes)
    result = SupportEvidenceSupplement(selection.supplement_id, selection.g21_manifest_digest, selection_digest, tuple(receipts), tuple(diagnostics), status, fixture_digest)
    if diagnostic_output is not None:
        _atomic_write(Path(diagnostic_output), (json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return result


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sunset-support-", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


__all__ = [
    "LiveSupportEvidenceProvider",
    "RecordedSupportEvidenceProvider",
    "SupportEvidenceError",
    "capture_support_evidence",
    "load_support_selection",
    "validate_support_selection",
]
