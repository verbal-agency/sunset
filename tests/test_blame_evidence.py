"""G28 — authenticated exact-SHA line-blame evidence.

All tests are offline: the recorded provider replays a committed fixture and the
live provider is exercised through an injected opener. No test opens a socket.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from sunset.blame_evidence import (
    BlameEvidenceError,
    GitHubBlameProvider,
    RecordedBlameProvider,
    capture_blame_evidence,
    fetch_blame_evidence,
    permalink,
    validate_request,
)
from sunset.blame_evidence_models import BlameRequest

FIXTURE = Path(__file__).parent / "fixtures" / "blame_evidence" / "openclaw-g27-blame-v1.json"
REPO = "https://github.com/openclaw/openclaw"
SHA = "0965053fe6b9341776df147a6934b7485c60b5ca"
RUN_INSPECTOR = "ui/src/e2e/activity-run-inspector.e2e.test.ts"
RUN_INSPECTOR_COMMIT = "7ab5d99a6c3c2bd72a23b08cb0a7a6ad7b68899d"


def _request(path: str = RUN_INSPECTOR, line: int = 22, subject: str = "s1") -> BlameRequest:
    return BlameRequest(subject, REPO, SHA, path, line)


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _graphql_ok(oid: str, start: int, end: int, *, date: str = "2026-08-11T00:00:00Z", headline: str = "feat(ui): add durable run inspector") -> bytes:
    return json.dumps(
        {"data": {"repository": {"object": {"blame": {"ranges": [
            {"startingLine": start, "endingLine": end, "commit": {"oid": oid, "committedDate": date, "messageHeadline": headline}}
        ]}}}}}
    ).encode("utf-8")


def _opener_returning(body: bytes):
    calls: list[dict] = []

    def opener(request, timeout=None):  # noqa: ANN001
        calls.append({"url": request.full_url, "body": request.data})
        return _FakeResponse(body)

    opener.calls = calls  # type: ignore[attr-defined]
    return opener


# --- recorded provider -------------------------------------------------------

def test_recorded_provider_resolves_known_line() -> None:
    provider = RecordedBlameProvider(FIXTURE)
    response = provider.blame(_request())
    assert response.outcome == "complete"
    assert response.provenance_status == "complete"
    assert response.introducing_commit == RUN_INSPECTOR_COMMIT
    assert response.message_headline == "feat(ui): add durable run inspector"


def test_recorded_provider_missing_line_is_incomplete() -> None:
    provider = RecordedBlameProvider(FIXTURE)
    response = provider.blame(_request(line=999))
    assert response.outcome == "missing"
    assert response.provenance_status == "incomplete"
    assert response.introducing_commit is None


def test_recorded_provider_unavailable_fixture(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    provider = RecordedBlameProvider(missing)
    response = provider.blame(_request())
    assert response.outcome == "failed"
    assert response.error_kind == "recorded_fixture_unavailable"


def test_recorded_provider_all_four_candidates_distinct() -> None:
    provider = RecordedBlameProvider(FIXTURE)
    payload = json.loads(FIXTURE.read_bytes())
    commits = set()
    for item in payload["responses"]:
        response = provider.blame(BlameRequest("s", item["repository_url"], item["commit_sha"], item["path"], item["line"]))
        assert response.outcome == "complete"
        commits.add(response.introducing_commit)
    assert len(commits) == len(payload["responses"]) == 4


# --- live provider (injected opener) ----------------------------------------

def test_live_provider_resolves_line() -> None:
    opener = _opener_returning(_graphql_ok(RUN_INSPECTOR_COMMIT, 20, 25))
    provider = GitHubBlameProvider("tok", opener=opener)
    response = provider.blame(_request())
    assert response.outcome == "complete"
    assert response.introducing_commit == RUN_INSPECTOR_COMMIT
    assert len(opener.calls) == 1


def test_live_provider_selects_range_covering_line() -> None:
    body = json.dumps({"data": {"repository": {"object": {"blame": {"ranges": [
        {"startingLine": 1, "endingLine": 10, "commit": {"oid": "a" * 40, "committedDate": "d", "messageHeadline": "one"}},
        {"startingLine": 11, "endingLine": 30, "commit": {"oid": "b" * 40, "committedDate": "d", "messageHeadline": "two"}},
    ]}}}}}).encode("utf-8")
    provider = GitHubBlameProvider("tok", opener=_opener_returning(body))
    response = provider.blame(_request(line=22))
    assert response.outcome == "complete"
    assert response.introducing_commit == "b" * 40


def test_live_provider_line_out_of_range_is_missing() -> None:
    provider = GitHubBlameProvider("tok", opener=_opener_returning(_graphql_ok("c" * 40, 1, 5)))
    response = provider.blame(_request(line=22))
    assert response.outcome == "missing"
    assert response.provenance_status == "incomplete"


def test_live_provider_object_not_found_is_missing() -> None:
    body = json.dumps({"data": {"repository": {"object": None}}}).encode("utf-8")
    provider = GitHubBlameProvider("tok", opener=_opener_returning(body))
    response = provider.blame(_request())
    assert response.outcome == "missing"
    assert response.error_kind == "object_not_found"


def test_live_provider_graphql_error_is_failed() -> None:
    body = json.dumps({"errors": [{"message": "boom"}]}).encode("utf-8")
    provider = GitHubBlameProvider("tok", opener=_opener_returning(body))
    response = provider.blame(_request())
    assert response.outcome == "failed"
    assert response.error_kind == "graphql_error"


def test_live_provider_credential_absent_does_not_read_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "env-token-should-be-ignored")
    monkeypatch.setenv("GH_TOKEN", "env-token-should-be-ignored")

    def exploding_opener(request, timeout=None):  # noqa: ANN001
        raise AssertionError("network must not be attempted without a host-supplied token")

    provider = GitHubBlameProvider(None, opener=exploding_opener)
    response = provider.blame(_request())
    assert response.outcome == "unsupported"
    assert response.error_kind == "credential_absent"
    assert response.provenance_status == "incomplete"


def test_live_provider_host_not_allowlisted() -> None:
    def exploding_opener(request, timeout=None):  # noqa: ANN001
        raise AssertionError("must not contact a non-allowlisted host")

    provider = GitHubBlameProvider("tok", opener=exploding_opener, graphql_url="https://evil.example/graphql")
    response = provider.blame(_request())
    assert response.outcome == "unsupported"
    assert response.error_kind == "host_not_allowlisted"


def test_validate_request_rejects_bad_inputs() -> None:
    with pytest.raises(BlameEvidenceError):
        validate_request(BlameRequest("s", "https://gitlab.com/a/b", SHA, "x.ts", 1))
    with pytest.raises(BlameEvidenceError):
        validate_request(BlameRequest("s", REPO, "not-a-sha", "x.ts", 1))
    with pytest.raises(BlameEvidenceError):
        validate_request(BlameRequest("s", REPO, SHA, "../escape.ts", 1))
    with pytest.raises(BlameEvidenceError):
        validate_request(BlameRequest("s", REPO, SHA, "x.ts", 0))


def test_permalink_shape() -> None:
    assert permalink(_request()) == f"https://github.com/openclaw/openclaw/blob/{SHA}/{RUN_INSPECTOR}#L22"


# --- capture -----------------------------------------------------------------

def _multi_opener():
    def opener(request, timeout=None):  # noqa: ANN001
        variables = json.loads(request.data.decode("utf-8"))["variables"]
        path, line = variables["path"], None
        # deterministic per-path commit
        oid = ("d" if "session-feed" in path else "e") * 40
        return _FakeResponse(_graphql_ok(oid, 1, 1000, headline=f"headline for {path}"))

    return opener


def test_capture_writes_fixture_and_replays(tmp_path: Path) -> None:
    requests = (
        BlameRequest("s1", REPO, SHA, "ui/src/e2e/activity-session-feed.capture.e2e.test.ts", 22),
        BlameRequest("s2", REPO, SHA, "ui/src/e2e/tool-titles.e2e.test.ts", 199),
    )
    out = tmp_path / "cap.json"
    report = capture_blame_evidence(requests, "tok", out, opener=_multi_opener())
    assert report.status == "verified"
    assert report.complete_count == 2
    assert out.exists()
    # replay resolves the same commit the capture recorded
    recorded = RecordedBlameProvider(out)
    replayed = recorded.blame(requests[0])
    assert replayed.outcome == "complete"
    assert replayed.introducing_commit == "d" * 40
    # byte-identical re-capture
    out2 = tmp_path / "cap2.json"
    report2 = capture_blame_evidence(requests, "tok", out2, opener=_multi_opener())
    assert out.read_bytes() == out2.read_bytes()
    assert report.fixture_digest == report2.fixture_digest


def test_capture_partial_does_not_write_fixture(tmp_path: Path) -> None:
    def opener(request, timeout=None):  # noqa: ANN001
        return _FakeResponse(json.dumps({"data": {"repository": {"object": None}}}).encode("utf-8"))

    out = tmp_path / "cap.json"
    report = capture_blame_evidence((_request(),), "tok", out, opener=opener)
    assert report.status == "blocked"
    assert report.fixture_digest is None
    assert not out.exists()


def test_capture_rejects_duplicate_requests(tmp_path: Path) -> None:
    with pytest.raises(BlameEvidenceError):
        capture_blame_evidence((_request(), _request()), "tok", tmp_path / "x.json", opener=_multi_opener())


def test_token_never_serialized(tmp_path: Path) -> None:
    secret = "super-secret-token-123"
    out = tmp_path / "cap.json"
    report = capture_blame_evidence(
        (BlameRequest("s", REPO, SHA, "ui/src/e2e/tool-titles.e2e.test.ts", 199),),
        secret,
        out,
        opener=_multi_opener(),
    )
    assert secret not in json.dumps(report.to_dict())
    assert secret.encode("utf-8") not in out.read_bytes()


def test_fetch_blame_evidence_wraps_provider() -> None:
    provider = RecordedBlameProvider(FIXTURE)
    receipt = fetch_blame_evidence(_request(), provider)
    assert receipt.outcome == "complete"
    assert receipt.provenance_status == "complete"
    assert receipt.introducing_commit == RUN_INSPECTOR_COMMIT
    assert "token" not in receipt.to_dict()
