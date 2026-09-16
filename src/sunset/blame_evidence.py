"""Authenticated, exact-SHA line-blame evidence with a recorded-first default.

The default provider replays a committed fixture and never opens a socket. The
live provider is an opt-in GitHub GraphQL blame adapter that requires an
explicitly host-supplied credential and an allowlisted host. It never discovers
an ambient/environment credential, never persists the token, and returns an
``incomplete`` provenance status (never a guessed commit) when access is
unavailable.
"""

from __future__ import annotations

import hashlib
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from sunset.blame_evidence_models import (
    BLAME_CAPTURE_SCHEMA_VERSION,
    BlameCaptureReport,
    BlameReceipt,
    BlameRequest,
    BlameResponse,
    provenance_status_for,
)

_GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_PATH_RE = re.compile(r"^[^\x00]+$")

_BLAME_QUERY = (
    "query($owner:String!,$name:String!,$oid:GitObjectID!,$path:String!){"
    "repository(owner:$owner,name:$name){object(oid:$oid){... on Commit{"
    "blame(path:$path){ranges{startingLine endingLine commit{oid committedDate messageHeadline}}}}}}}"
)

_DEFAULT_OPENER = build_opener()


class BlameEvidenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BlameProvider(Protocol):
    name: str

    def blame(self, request: BlameRequest) -> BlameResponse: ...


def permalink(request: BlameRequest) -> str:
    match = _GITHUB_RE.match(request.repository_url)
    if match is None:
        return request.repository_url
    return (
        f"https://github.com/{match.group(1)}/{match.group(2)}"
        f"/blob/{request.commit_sha}/{request.path}#L{request.line}"
    )


def validate_request(request: BlameRequest) -> tuple[str, str]:
    """Return (owner, name) or raise for an unsupported/unsafe request."""

    match = _GITHUB_RE.match(request.repository_url)
    if match is None:
        raise BlameEvidenceError("repository_unsupported", "only github.com repositories are supported")
    if not _SHA_RE.fullmatch(request.commit_sha):
        raise BlameEvidenceError("commit_invalid", "an exact 40-hex commit SHA is required")
    if request.line < 1:
        raise BlameEvidenceError("line_invalid", "line must be 1-based and positive")
    path = request.path
    if not path or path.startswith("/") or ".." in Path(path).parts or not _SAFE_PATH_RE.fullmatch(path):
        raise BlameEvidenceError("path_unsafe", "path must be relative and traversal-free")
    return match.group(1), match.group(2)


class RecordedBlameProvider:
    """Fixture-backed provider; it never opens a socket or invokes Git."""

    name = "recorded-blame"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser().resolve()
        try:
            fixture_bytes = self.fixture_path.read_bytes()
            value = json.loads(fixture_bytes.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("fixture root must be an object")
            if value.get("schema_version") != "1" or not isinstance(value.get("responses"), list):
                raise ValueError("fixture requires schema_version 1 and responses list")
            self._responses: dict[tuple[str, str, str, int], dict[str, Any]] = {}
            for item in value["responses"]:
                if not isinstance(item, dict):
                    raise ValueError("fixture response must be an object")
                key = (str(item["repository_url"]), str(item["commit_sha"]), str(item["path"]), int(item["line"]))
                self._responses[key] = item
            self._error: str | None = None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._responses = {}
            self._error = str(exc)
            fixture_bytes = b""
        self.fixture_digest = hashlib.sha256(fixture_bytes).hexdigest()

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:{self.fixture_digest}"

    def blame(self, request: BlameRequest) -> BlameResponse:
        locator = permalink(request)
        if self._error:
            return BlameResponse("failed", "Recorded blame fixture is unavailable.", locator, error_kind="recorded_fixture_unavailable")
        item = self._responses.get((request.repository_url, request.commit_sha, request.path, request.line))
        if item is None:
            return BlameResponse("missing", "No recorded blame exists for this line.", locator)
        outcome = str(item.get("outcome", "failed"))
        if outcome != "complete":
            valid = outcome if outcome in {"missing", "incomplete", "unsupported", "failed"} else "failed"
            return BlameResponse(valid, str(item.get("summary", "Recorded blame is unavailable.")), locator, error_kind=item.get("error_kind"))
        commit = str(item.get("introducing_commit", ""))
        if not _SHA_RE.fullmatch(commit):
            return BlameResponse("incomplete", "Recorded blame commit is malformed.", locator, error_kind="fixture_commit_invalid")
        return BlameResponse(
            "complete",
            str(item.get("summary", "Recorded blame returned.")),
            str(item.get("source_locator", locator)),
            introducing_commit=commit,
            committed_date=item.get("committed_date"),
            message_headline=item.get("message_headline"),
        )


class GitHubBlameProvider:
    """Opt-in GitHub GraphQL blame adapter with an explicit, host-supplied token.

    The token is passed in by trusted application code; this provider never reads
    ``os.environ`` or any other ambient source, and never stores or serializes the
    token. When the token is absent the provider fails closed to ``unsupported``.
    """

    name = "github-blame-live"

    def __init__(
        self,
        token: str | None,
        *,
        opener: Callable[..., Any] | None = None,
        allowed_hosts: tuple[str, ...] = ("api.github.com",),
        graphql_url: str = "https://api.github.com/graphql",
        timeout_seconds: int = 10,
    ) -> None:
        # Held only to build a per-request Authorization header; never persisted.
        self._token = token or None
        self._opener = opener or _DEFAULT_OPENER.open
        self.allowed_hosts = tuple(sorted(set(allowed_hosts)))
        self.graphql_url = graphql_url
        self.timeout_seconds = timeout_seconds

    @property
    def cache_identity(self) -> str:
        return f"{self.name}:hosts={','.join(self.allowed_hosts)}:timeout={self.timeout_seconds}"

    def blame(self, request: BlameRequest) -> BlameResponse:
        locator = permalink(request)
        try:
            owner, name = validate_request(request)
        except BlameEvidenceError as exc:
            return BlameResponse("unsupported", exc.message, locator, error_kind=exc.code)
        if urlparse(self.graphql_url).hostname not in self.allowed_hosts:
            return BlameResponse("unsupported", "Blame host is not allowlisted.", locator, error_kind="host_not_allowlisted")
        if self._token is None:
            return BlameResponse("unsupported", "No host-supplied credential; blame was not attempted.", locator, error_kind="credential_absent")

        payload = json.dumps(
            {"query": _BLAME_QUERY, "variables": {"owner": owner, "name": name, "oid": request.commit_sha, "path": request.path}}
        ).encode("utf-8")
        http_request = Request(
            self.graphql_url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "sunset-blame-evidence",
            },
        )
        try:
            with self._opener(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            outcome = "unsupported" if exc.code in {401, 403} else "failed"
            return BlameResponse(outcome, "Live blame lookup failed; no provenance conclusion was made.", locator, error_kind=f"http_{exc.code}")
        except (URLError, OSError, IncompleteRead) as exc:
            return BlameResponse("failed", "Live blame lookup failed; no provenance conclusion was made.", locator, error_kind=type(exc).__name__.lower())
        return _parse_blame_payload(raw, request, locator)


def _parse_blame_payload(raw: Any, request: BlameRequest, locator: str) -> BlameResponse:
    if not isinstance(raw, (bytes, bytearray)):
        return BlameResponse("failed", "Live blame returned a non-byte response.", locator, error_kind="malformed_response")
    try:
        document = json.loads(bytes(raw).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return BlameResponse("failed", "Live blame returned malformed JSON.", locator, error_kind="malformed_response")
    if not isinstance(document, dict) or document.get("errors"):
        return BlameResponse("failed", "Live blame returned a GraphQL error.", locator, error_kind="graphql_error")
    try:
        obj = document["data"]["repository"]["object"]
    except (KeyError, TypeError):
        return BlameResponse("failed", "Live blame response was structurally invalid.", locator, error_kind="malformed_response")
    if obj is None:
        return BlameResponse("missing", "Repository, commit, or path was not found at the pinned head.", locator, error_kind="object_not_found")
    ranges = (obj.get("blame") or {}).get("ranges")
    if not isinstance(ranges, list) or not ranges:
        return BlameResponse("incomplete", "Blame returned no ranges; provenance is incomplete.", locator, error_kind="no_blame_ranges")
    for entry in ranges:
        try:
            start = int(entry["startingLine"])
            end = int(entry["endingLine"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= request.line <= end:
            commit = entry.get("commit") or {}
            oid = str(commit.get("oid", ""))
            if not _SHA_RE.fullmatch(oid):
                return BlameResponse("incomplete", "Blame range lacked a valid commit oid.", locator, error_kind="commit_oid_invalid")
            return BlameResponse(
                "complete",
                "Authenticated exact-SHA blame resolved the line.",
                locator,
                introducing_commit=oid,
                committed_date=commit.get("committedDate"),
                message_headline=commit.get("messageHeadline"),
            )
    return BlameResponse("missing", "No blame range covered the requested line.", locator, error_kind="line_out_of_range")


def fetch_blame_evidence(request: BlameRequest, provider: BlameProvider, *, freshness_key: str = "recorded-v1") -> BlameReceipt:
    try:
        response = provider.blame(request)
    except (OSError, ValueError, RuntimeError) as exc:
        response = BlameResponse("failed", "Blame provider failed; no provenance conclusion was made.", permalink(request), error_kind=type(exc).__name__.lower())
    return _receipt(request, response, provider.name, freshness_key)


def capture_blame_evidence(
    requests: tuple[BlameRequest, ...],
    token: str | None,
    output_fixture: str | Path,
    *,
    opener: Callable[..., Any] | None = None,
    timeout_seconds: int = 10,
    freshness_key: str = "github-blame-v1",
    diagnostic_output: str | Path | None = None,
) -> BlameCaptureReport:
    """Capture line-blame for an explicit request set and record a fixture.

    The fixture is written only when every request resolves ``complete`` so a
    partial capture never masquerades as verified provenance. The token is never
    written to the fixture, receipts, or diagnostic report.
    """

    if not requests:
        raise BlameEvidenceError("selection_empty", "at least one blame request is required")
    if timeout_seconds <= 0:
        raise BlameEvidenceError("capture_budget_invalid", "timeout must be positive")
    seen: set[tuple[str, str, str, int]] = set()
    for request in requests:
        key = (request.repository_url, request.commit_sha, request.path, request.line)
        if key in seen:
            raise BlameEvidenceError("selection_duplicate", f"duplicate blame request: {key}")
        seen.add(key)

    provider = GitHubBlameProvider(token, opener=opener, timeout_seconds=timeout_seconds)
    receipts: list[BlameReceipt] = []
    fixture_responses: list[dict[str, Any]] = []
    complete = 0
    for request in requests:
        response = provider.blame(request)
        receipt = _receipt(request, response, provider.name, freshness_key)
        receipts.append(receipt)
        if response.outcome == "complete":
            complete += 1
            fixture_responses.append(
                {
                    "subject_id": request.subject_id,
                    "repository_url": request.repository_url,
                    "commit_sha": request.commit_sha,
                    "path": request.path,
                    "line": request.line,
                    "outcome": "complete",
                    "introducing_commit": response.introducing_commit,
                    "committed_date": response.committed_date,
                    "message_headline": response.message_headline,
                    "source_locator": response.source_locator,
                }
            )

    status = "verified" if complete == len(requests) else ("partial" if complete else "blocked")
    fixture_digest: str | None = None
    if status == "verified":
        fixture_payload = {
            "schema_version": "1",
            "capture_schema_version": BLAME_CAPTURE_SCHEMA_VERSION,
            "provider_policy": {"name": provider.name, "allowed_hosts": list(provider.allowed_hosts), "timeout_seconds": timeout_seconds},
            "responses": fixture_responses,
        }
        fixture_bytes = (json.dumps(fixture_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        fixture_digest = hashlib.sha256(fixture_bytes).hexdigest()
        try:
            _atomic_write(Path(output_fixture), fixture_bytes)
        except OSError:
            status = "partial"
            fixture_digest = None

    report = BlameCaptureReport(provider.name, tuple(receipts), fixture_digest, len(requests), complete, status)
    if diagnostic_output is not None:
        _atomic_write(Path(diagnostic_output), (json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return report


def _receipt(request: BlameRequest, response: BlameResponse, provider_name: str, freshness_key: str) -> BlameReceipt:
    return BlameReceipt(
        request=request,
        outcome=response.outcome,
        provenance_status=provenance_status_for(response.outcome),
        summary=response.summary,
        source_locator=response.source_locator,
        introducing_commit=response.introducing_commit,
        committed_date=response.committed_date,
        message_headline=response.message_headline,
        provider=provider_name,
        freshness_key=freshness_key,
        error_kind=response.error_kind,
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sunset-blame-", dir=path.parent)
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
    "BlameEvidenceError",
    "BlameProvider",
    "GitHubBlameProvider",
    "RecordedBlameProvider",
    "capture_blame_evidence",
    "fetch_blame_evidence",
    "permalink",
    "validate_request",
]
