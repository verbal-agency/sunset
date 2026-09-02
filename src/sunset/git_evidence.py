"""Recorded-first, pointer-bound Git source and patch evidence retrieval."""

from __future__ import annotations

import hashlib
from http.client import IncompleteRead
import json
import base64
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.validation_corpus_models import EvidencePointer, ValidationCorpus
from sunset.git_evidence_models import (
    GitCaptureDiagnostic,
    GitCaptureReport,
    GitCaptureSelection,
    GitEvidenceReceipt,
    GitEvidenceRequest,
    GitEvidenceResponse,
)


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")
_SAFE_PATH_RE = re.compile(r"^[^\x00]+$")


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def _open_without_redirects(request: Request, timeout: int):
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


class GitEvidenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class GitEvidenceProvider(Protocol):
    name: str

    def fetch(self, request: GitEvidenceRequest) -> GitEvidenceResponse: ...


class RecordedGitEvidenceProvider:
    """Fixture-backed provider; it never opens a socket or invokes Git."""

    name = "recorded-git"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser().resolve()
        try:
            fixture_bytes = self.fixture_path.read_bytes()
            value = json.loads(fixture_bytes.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("fixture root must be an object")
            if value.get("schema_version") != "1" or not isinstance(value.get("responses"), list):
                raise ValueError("fixture requires schema_version 1 and responses list")
            self._responses = {}
            for item in value["responses"]:
                if not isinstance(item, dict):
                    raise ValueError("fixture response must be an object")
                key = (str(item["evidence_id"]), str(item["commit_sha"]), str(item["kind"]), item.get("path"))
                self._responses[key] = item
            self._error = None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._responses = {}
            self._error = str(exc)
            fixture_bytes = b""
        self.fixture_digest = hashlib.sha256(fixture_bytes).hexdigest()

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:{self.fixture_digest}"

    def fetch(self, request: GitEvidenceRequest) -> GitEvidenceResponse:
        if self._error:
            return GitEvidenceResponse("failed", "Recorded Git fixture is unavailable.", request_locator(request), error_kind="recorded_fixture_unavailable")
        item = self._responses.get((request.evidence_id, request.commit_sha, request.kind, request.path))
        if item is None:
            return GitEvidenceResponse("missing", "No recorded Git response exists for this pointer and kind.", request_locator(request))
        outcome = str(item.get("outcome", "failed"))
        if outcome != "available":
            return GitEvidenceResponse(outcome if outcome in {"missing", "failed", "budget_exhausted", "unsupported"} else "failed", str(item.get("summary", "Recorded Git evidence is unavailable.")), request_locator(request), error_kind=str(item.get("error_kind")) if item.get("error_kind") else None)
        if "body_base64" in item:
            try:
                raw = base64.b64decode(str(item["body_base64"]), validate=True)
            except (ValueError, TypeError):
                return GitEvidenceResponse("failed", "Recorded Git evidence has invalid base64 bytes.", request_locator(request), error_kind="fixture_body_invalid")
        else:
            raw_value = item.get("body", "")
            raw = raw_value.encode("utf-8") if isinstance(raw_value, str) else bytes(raw_value)
        if len(raw) > request.max_bytes:
            return GitEvidenceResponse("budget_exhausted", "Recorded Git evidence exceeds the byte budget.", request_locator(request), error_kind="response_too_large")
        return GitEvidenceResponse("available", str(item.get("summary", "Recorded Git evidence returned.")), request_locator(request), len(raw), raw=raw)


class LiveGitEvidenceProvider:
    """Opt-in public GitHub adapter with an injected opener for testability."""

    name = "github-live"

    def __init__(self, opener: Callable[..., Any] | None = None, allowed_hosts: tuple[str, ...] = ("github.com", "raw.githubusercontent.com", "patch-diff.githubusercontent.com"), timeout_seconds: int = 10) -> None:
        self._opener = opener or _open_without_redirects
        self.allowed_hosts = tuple(sorted(set(allowed_hosts)))
        self.timeout_seconds = timeout_seconds

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:hosts={','.join(self.allowed_hosts)}:timeout={self.timeout_seconds}"

    def fetch(self, request: GitEvidenceRequest) -> GitEvidenceResponse:
        url = request_locator(request)
        redirects = 0
        while True:
            if urlparse(url).hostname not in self.allowed_hosts:
                return GitEvidenceResponse("unsupported", "Git evidence host is not allowlisted.", url, error_kind="host_not_allowlisted", redirect_count=redirects)
            try:
                with self._opener(Request(url, headers={"Accept": "application/vnd.github+json"}), timeout=self.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    location = response.headers.get("Location") if hasattr(response, "headers") else None
                    if 300 <= status < 400 and location:
                        if redirects >= 1:
                            return GitEvidenceResponse("failed", "Live Git evidence exceeded the one-redirect bound.", url, error_kind="redirect_limit", redirect_count=redirects)
                        url = urljoin(url, location)
                        redirects += 1
                        continue
                    raw = response.read(request.max_bytes + 1)
            except HTTPError as exc:
                location = exc.headers.get("Location") if exc.headers else None
                if 300 <= exc.code < 400 and location:
                    if redirects >= 1:
                        return GitEvidenceResponse("failed", "Live Git evidence exceeded the one-redirect bound.", url, error_kind="redirect_limit", redirect_count=redirects)
                    url = urljoin(url, location)
                    redirects += 1
                    continue
                outcome = "missing" if exc.code == 404 else "failed"
                return GitEvidenceResponse(outcome, "Live Git evidence lookup failed; no condition conclusion was made.", url, error_kind=f"http_{exc.code}", redirect_count=redirects)
            except (URLError, OSError, IncompleteRead) as exc:
                return GitEvidenceResponse("failed", "Live Git evidence lookup failed; no condition conclusion was made.", url, error_kind=type(exc).__name__.lower(), redirect_count=redirects)
            if not isinstance(raw, bytes):
                return GitEvidenceResponse("failed", "Live Git evidence returned a non-byte response.", url, error_kind="malformed_response", redirect_count=redirects)
            if len(raw) > request.max_bytes:
                return GitEvidenceResponse("budget_exhausted", "Live Git evidence exceeds the byte budget.", url, error_kind="response_too_large", redirect_count=redirects)
            return GitEvidenceResponse("available", "Pinned Git evidence returned.", url, len(raw), raw=raw, redirect_count=redirects, final_source_locator=url)


def request_from_pointer(pointer: EvidencePointer, *, kind: str | None = None, max_bytes: int = 65_536) -> GitEvidenceRequest:
    if pointer.source_kind != "public_git":
        raise GitEvidenceError("unsupported_source_kind", "only public_git pointers are supported")
    if max_bytes <= 0:
        raise GitEvidenceError("budget_invalid", "max_bytes must be positive")
    if pointer.role not in {"historical_outcome", "introduction_context", "condition_evidence", "counter_evidence", "validation_scope"}:
        raise GitEvidenceError("role_unsupported", "pointer role is not supported for Git evidence")
    match = _GITHUB_RE.match(pointer.locator.split("/commit/")[0].split("/blob/")[0])
    if match is None or not _SHA_RE.fullmatch(pointer.commit_sha or ""):
        raise GitEvidenceError("pointer_invalid", "pointer must use a GitHub repository and full commit SHA")
    inferred_kind = kind or ("patch" if "/commit/" in pointer.locator else "blob")
    if inferred_kind not in {"blob", "patch"}:
        raise GitEvidenceError("kind_unsupported", inferred_kind)
    path = None
    if inferred_kind == "blob":
        marker = f"/blob/{pointer.commit_sha}/"
        if marker not in pointer.locator:
            raise GitEvidenceError("pointer_path_missing", "blob pointer must include its pinned path")
        path = pointer.locator.split(marker, 1)[1]
        if not path or path.startswith("/") or ".." in Path(path).parts or not _SAFE_PATH_RE.fullmatch(path):
            raise GitEvidenceError("path_unsafe", "blob pointer path must be relative and traversal-free")
    return GitEvidenceRequest(pointer.evidence_id, f"https://github.com/{match.group(1)}/{match.group(2)}.git", pointer.commit_sha or "", path, inferred_kind, max_bytes)


def fetch_git_evidence(pointer: EvidencePointer, provider: GitEvidenceProvider, store: ArtifactStore, *, kind: str | None = None, max_bytes: int = 65_536, freshness_key: str = "recorded-v1") -> GitEvidenceReceipt:
    request = request_from_pointer(pointer, kind=kind, max_bytes=max_bytes)
    provider_identity = getattr(provider, "cache_identity", provider.name)
    cache_id = _cache_id(request, provider_identity, freshness_key)
    cached = store.read_view(cache_id)
    if cached is not None:
        try:
            receipt = GitEvidenceReceipt.from_dict(json.loads(cached))
            if receipt.artifact is not None:
                store.read(receipt.artifact)
            return receipt
        except (TypeError, ValueError, KeyError, json.JSONDecodeError, ArtifactStoreError):
            pass
    try:
        response = provider.fetch(request)
    except (OSError, ValueError, RuntimeError) as exc:
        response = GitEvidenceResponse(
            "failed",
            "Git evidence provider failed; no condition conclusion was made.",
            request_locator(request),
            error_kind=type(exc).__name__.lower(),
        )
    artifact = None
    digest = None
    if response.raw is not None and response.outcome == "available":
        digest = hashlib.sha256(response.raw).hexdigest()
        artifact = store.put(response.raw, media_type="text/plain", source_kind=f"git_{request.kind}", source_locator=response.source_locator)
    receipt = GitEvidenceReceipt(request, response.outcome, response.summary, response.source_locator, artifact, digest, response.byte_length, provider.name, freshness_key, response.error_kind, True, response.redirect_count, response.final_source_locator)
    if response.outcome in {"available", "missing", "unsupported"}:
        store.put_view(cache_id, json.dumps(receipt.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return receipt


def request_locator(request: GitEvidenceRequest) -> str:
    match = _GITHUB_RE.match(request.repository_url)
    if match is None:
        return request.repository_url
    base = f"https://github.com/{match.group(1)}/{match.group(2)}"
    if request.kind == "patch":
        return f"{base}/commit/{request.commit_sha}.patch"
    return f"https://raw.githubusercontent.com/{match.group(1)}/{match.group(2)}/{request.commit_sha}/{request.path}"


def _cache_id(request: GitEvidenceRequest, provider: str, freshness_key: str) -> str:
    identity = json.dumps({"request": request.to_dict(), "provider": provider, "freshness_key": freshness_key, "schema": "1"}, sort_keys=True, separators=(",", ":")).encode()
    return "git-evidence-" + hashlib.sha256(identity).hexdigest()


def capture_git_evidence(
    corpus: ValidationCorpus,
    selections: tuple[str, ...],
    store: ArtifactStore,
    output_fixture: str | Path,
    *,
    max_bytes: int = 65_536,
    timeout_seconds: int = 10,
    diagnostic_output: str | Path | None = None,
) -> GitCaptureReport:
    """Capture explicitly selected real pointers and atomically record a fixture."""

    if not selections:
        raise GitEvidenceError("selection_empty", "at least one case:evidence selection is required")
    if max_bytes <= 0 or timeout_seconds <= 0:
        raise GitEvidenceError("capture_budget_invalid", "byte and timeout budgets must be positive")
    manifest_bytes = json.dumps(corpus.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    cases = {case.case_id: case for case in corpus.cases}
    chosen: list[GitCaptureSelection] = []
    seen: set[tuple[str, str]] = set()
    for value in selections:
        case_id, evidence_id = _resolve_selection(value, cases)
        if (case_id, evidence_id) in seen:
            raise GitEvidenceError("selection_invalid", f"invalid or duplicate selection: {value}")
        case = cases.get(case_id)
        if case is None:
            raise GitEvidenceError("case_not_found", case_id)
        pointer = next((item for item in case.evidence if item.evidence_id == evidence_id), None)
        if pointer is None:
            raise GitEvidenceError("evidence_not_found", value)
        request = request_from_pointer(pointer, max_bytes=max_bytes)
        pointer_digest = hashlib.sha256(json.dumps(pointer.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        chosen.append(GitCaptureSelection(case_id, evidence_id, pointer_digest, request))
        seen.add((case_id, evidence_id))

    provider = LiveGitEvidenceProvider(timeout_seconds=timeout_seconds)
    receipts: list[GitEvidenceReceipt] = []
    diagnostics: list[GitCaptureDiagnostic] = []
    fixture_responses: list[dict[str, Any]] = []
    byte_total = 0
    redirect_total = 0
    for selection in chosen:
        started = time.monotonic()
        try:
            response = provider.fetch(selection.request)
        except (OSError, ValueError, RuntimeError) as exc:
            response = GitEvidenceResponse("failed", "Git evidence provider failed; no condition conclusion was made.", request_locator(selection.request), error_kind=type(exc).__name__.lower())
        elapsed_ms = int((time.monotonic() - started) * 1000)
        redirect_total += response.redirect_count
        artifact = None
        digest = None
        if response.outcome == "available" and response.raw is not None:
            digest = hashlib.sha256(response.raw).hexdigest()
            artifact = store.put(response.raw, media_type="text/plain", source_kind=f"git_{selection.request.kind}", source_locator=response.final_source_locator or response.source_locator)
            byte_total += len(response.raw)
            entry: dict[str, Any] = {
                "evidence_id": selection.evidence_id,
                "commit_sha": selection.request.commit_sha,
                "kind": selection.request.kind,
                "path": selection.request.path,
                "outcome": "available",
                "source_locator": response.source_locator,
                "final_source_locator": response.final_source_locator or response.source_locator,
                "digest": digest,
                "byte_length": len(response.raw),
            }
            try:
                entry["body"] = response.raw.decode("utf-8")
            except UnicodeDecodeError:
                entry["body_base64"] = base64.b64encode(response.raw).decode("ascii")
            fixture_responses.append(entry)
        receipt = GitEvidenceReceipt(selection.request, response.outcome, response.summary, response.source_locator, artifact, digest, response.byte_length, provider.name, "github-live-v1", response.error_kind, True, response.redirect_count, response.final_source_locator)
        receipts.append(receipt)
        if response.outcome != "available":
            diagnostics.append(GitCaptureDiagnostic(_diagnostic_phase(response.error_kind), response.error_kind or response.outcome, response.summary, urlparse(response.source_locator).hostname, _status_from_error(response.error_kind), elapsed_ms))

    fixture_digest = None
    status: str = "verified" if len(fixture_responses) == len(chosen) else ("partial" if fixture_responses else "blocked")
    if status == "verified":
        fixture_payload = {
            "schema_version": "1",
            "capture_schema_version": "1",
            "source_manifest_digest": manifest_digest,
            "provider_policy": {"name": provider.name, "allowed_hosts": list(provider.allowed_hosts), "timeout_seconds": timeout_seconds, "max_bytes": max_bytes},
            "responses": fixture_responses,
        }
        fixture_bytes = (json.dumps(fixture_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        fixture_digest = hashlib.sha256(fixture_bytes).hexdigest()
        try:
            _atomic_write(Path(output_fixture), fixture_bytes)
        except OSError as exc:
            diagnostics.append(GitCaptureDiagnostic("fixture_write", type(exc).__name__.lower(), str(exc)))
            status = "partial"
            fixture_digest = None

    report = GitCaptureReport(manifest_digest, tuple(chosen), tuple(receipts), tuple(diagnostics), fixture_digest, len(chosen), redirect_total, byte_total, status)  # type: ignore[arg-type]
    if diagnostic_output is not None:
        _atomic_write(Path(diagnostic_output), (json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return report


def _resolve_selection(value: str, cases: dict[str, Any]) -> tuple[str, str]:
    matches = []
    for case_id in cases:
        prefix = case_id + ":"
        if value.startswith(prefix):
            evidence_id = value[len(prefix):]
            candidate = prefix + evidence_id
            if any(item.evidence_id == candidate for item in cases[case_id].evidence):
                matches.append((case_id, candidate))
    if len(matches) != 1:
        raise GitEvidenceError("selection_invalid", f"selection must be CASE_ID:EVIDENCE_ID: {value}")
    return matches[0]


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sunset-capture-", dir=path.parent)
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


def _diagnostic_phase(error_kind: str | None) -> str:
    value = (error_kind or "http").lower()
    if "timeout" in value or "urlerror" in value:
        return "connect"
    if "redirect" in value or "host" in value:
        return "redirect"
    if "budget" in value or "large" in value:
        return "budget"
    if "decode" in value or "malformed" in value:
        return "decode"
    if value.startswith("http_"):
        return "http"
    return "connect"


def _status_from_error(error_kind: str | None) -> int | None:
    if error_kind and error_kind.startswith("http_"):
        try:
            return int(error_kind.removeprefix("http_"))
        except ValueError:
            return None
    return None


__all__ = ["GitEvidenceError", "LiveGitEvidenceProvider", "RecordedGitEvidenceProvider", "capture_git_evidence", "fetch_git_evidence", "request_from_pointer"]
