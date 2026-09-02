"""Recorded-first, pointer-bound Git source and patch evidence retrieval."""

from __future__ import annotations

import hashlib
from http.client import IncompleteRead
import json
from pathlib import Path
import re
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.validation_corpus_models import EvidencePointer
from sunset.git_evidence_models import GitEvidenceReceipt, GitEvidenceRequest, GitEvidenceResponse


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")
_SAFE_PATH_RE = re.compile(r"^[^\x00]+$")


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
        raw_value = item.get("body", "")
        raw = raw_value.encode("utf-8") if isinstance(raw_value, str) else bytes(raw_value)
        if len(raw) > request.max_bytes:
            return GitEvidenceResponse("budget_exhausted", "Recorded Git evidence exceeds the byte budget.", request_locator(request), error_kind="response_too_large")
        return GitEvidenceResponse("available", str(item.get("summary", "Recorded Git evidence returned.")), request_locator(request), len(raw), raw=raw)


class LiveGitEvidenceProvider:
    """Opt-in public GitHub adapter with an injected opener for testability."""

    name = "github-live"

    def __init__(self, opener: Callable[..., Any] = urlopen, allowed_hosts: tuple[str, ...] = ("github.com", "raw.githubusercontent.com"), timeout_seconds: int = 10) -> None:
        self._opener = opener
        self.allowed_hosts = tuple(sorted(set(allowed_hosts)))
        self.timeout_seconds = timeout_seconds

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:hosts={','.join(self.allowed_hosts)}:timeout={self.timeout_seconds}"

    def fetch(self, request: GitEvidenceRequest) -> GitEvidenceResponse:
        url = request_locator(request)
        if urlparse(url).hostname not in self.allowed_hosts:
            return GitEvidenceResponse("unsupported", "Git evidence host is not allowlisted.", url, error_kind="host_not_allowlisted")
        try:
            with self._opener(Request(url, headers={"Accept": "application/vnd.github+json"}), timeout=self.timeout_seconds) as response:
                raw = response.read(request.max_bytes + 1)
        except (HTTPError, URLError, OSError, IncompleteRead) as exc:
            outcome = "missing" if isinstance(exc, HTTPError) and exc.code == 404 else "failed"
            return GitEvidenceResponse(outcome, "Live Git evidence lookup failed; no condition conclusion was made.", url, error_kind=type(exc).__name__.lower())
        if not isinstance(raw, bytes):
            return GitEvidenceResponse("failed", "Live Git evidence returned a non-byte response.", url, error_kind="malformed_response")
        if len(raw) > request.max_bytes:
            return GitEvidenceResponse("budget_exhausted", "Live Git evidence exceeds the byte budget.", url, error_kind="response_too_large")
        return GitEvidenceResponse("available", "Pinned Git evidence returned.", url, len(raw), raw=raw)


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
    receipt = GitEvidenceReceipt(request, response.outcome, response.summary, response.source_locator, artifact, digest, response.byte_length, provider.name, freshness_key, response.error_kind)
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


__all__ = ["GitEvidenceError", "LiveGitEvidenceProvider", "RecordedGitEvidenceProvider", "fetch_git_evidence", "request_from_pointer"]
