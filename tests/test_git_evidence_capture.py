from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.git_evidence import LiveGitEvidenceProvider, RecordedGitEvidenceProvider, capture_git_evidence, fetch_git_evidence, request_from_pointer
from sunset.git_evidence_models import GitEvidenceResponse
from sunset.validation_corpus import load_validation_corpus
from sunset.validation_corpus_models import EvidencePointer


MANIFEST = Path(__file__).parent / "fixtures" / "validation_corpus" / "langchain-validation-v1.json"
REAL_FIXTURE = Path(__file__).parent / "fixtures" / "git_evidence" / "g22a-langchain-real-v1.json"
REAL_DIGEST = Path(__file__).parent / "fixtures" / "git_evidence" / "g22a-langchain-real-v1.sha256"
SHA = "0123456789abcdef0123456789abcdef01234567"


def test_capture_real_fixture_or_blocked_report(tmp_path: Path, monkeypatch) -> None:
    corpus = load_validation_corpus(MANIFEST)

    class FakeLiveProvider:
        name = "github-live"
        allowed_hosts = ("github.com", "raw.githubusercontent.com")
        def __init__(self, timeout_seconds: int = 10):
            self.timeout_seconds = timeout_seconds
        def fetch(self, request):
            body = f"real bytes for {request.evidence_id}"
            return GitEvidenceResponse("available", "captured", "https://example.invalid/pinned", len(body), body.encode())

    monkeypatch.setattr("sunset.git_evidence.LiveGitEvidenceProvider", FakeLiveProvider)
    fixture = tmp_path / "real.json"
    report = capture_git_evidence(
        corpus,
        ("lc-python39-removeprefix-shim:history", "lc-python310-aiter-shim:history"),
        ArtifactStore(tmp_path / "store"),
        fixture,
    )
    assert report.status == "verified"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["source_manifest_digest"] == report.manifest_digest
    assert len(payload["responses"]) == 2
    assert all(item["digest"] and item["byte_length"] > 0 for item in payload["responses"])


def test_capture_selection_is_manifest_bound(tmp_path: Path) -> None:
    corpus = load_validation_corpus(MANIFEST)
    with pytest.raises(Exception) as caught:
        capture_git_evidence(corpus, ("not-a-case:history",), ArtifactStore(tmp_path / "store"), tmp_path / "fixture.json")
    assert getattr(caught.value, "code", None) == "selection_invalid"


def test_capture_failure_diagnostics(tmp_path: Path, monkeypatch) -> None:
    corpus = load_validation_corpus(MANIFEST)

    class BlockedProvider:
        name = "github-live"
        allowed_hosts = ("github.com",)
        def __init__(self, timeout_seconds: int = 10):
            pass
        def fetch(self, request):
            return GitEvidenceResponse("failed", "DNS failed", "https://github.com/langchain-ai/langchain", error_kind="dns_failure")

    monkeypatch.setattr("sunset.git_evidence.LiveGitEvidenceProvider", BlockedProvider)
    fixture = tmp_path / "must-not-exist.json"
    diagnostic = tmp_path / "blocked.json"
    report = capture_git_evidence(
        corpus,
        ("lc-python39-removeprefix-shim:history",),
        ArtifactStore(tmp_path / "store"),
        fixture,
        diagnostic_output=diagnostic,
    )
    assert report.status == "blocked"
    assert not fixture.exists()
    assert json.loads(diagnostic.read_text(encoding="utf-8"))["diagnostics"][0]["phase"] == "connect"


def test_real_fixture_replays_offline(tmp_path: Path, monkeypatch) -> None:
    corpus = load_validation_corpus(MANIFEST)

    class FakeLiveProvider:
        name = "github-live"
        allowed_hosts = ("github.com", "raw.githubusercontent.com")
        def __init__(self, timeout_seconds: int = 10):
            pass
        def fetch(self, request):
            return GitEvidenceResponse("available", "captured", "https://raw.githubusercontent.com/pinned", 6, b"source")

    monkeypatch.setattr("sunset.git_evidence.LiveGitEvidenceProvider", FakeLiveProvider)
    fixture = tmp_path / "real.json"
    store = ArtifactStore(tmp_path / "store")
    capture_git_evidence(corpus, ("lc-stream-error-xfail:history",), store, fixture)
    # Re-open through G22's recorded provider contract; this path must not need
    # the live provider or any network access.
    from sunset.git_evidence import RecordedGitEvidenceProvider
    pointer = next(case for case in corpus.cases if case.case_id == "lc-stream-error-xfail").evidence[0]
    receipt = fetch_git_evidence(pointer, RecordedGitEvidenceProvider(fixture), store)
    assert receipt.outcome == "available"
    assert receipt.artifact and store.read(receipt.artifact) == b"source"


def test_committed_real_fixture_is_manifest_bound(tmp_path: Path, monkeypatch) -> None:
    corpus = load_validation_corpus(MANIFEST)
    payload = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    assert REAL_DIGEST.read_text(encoding="utf-8").startswith(hashlib.sha256(REAL_FIXTURE.read_bytes()).hexdigest())
    canonical = json.dumps(corpus.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert payload["source_manifest_digest"] == hashlib.sha256(canonical).hexdigest()
    assert {item["evidence_id"] for item in payload["responses"]} == {
        "lc-python39-removeprefix-shim:history",
        "lc-python310-aiter-shim:history",
        "lc-stream-error-xfail:history",
    }
    monkeypatch.setattr("socket.socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("replay must be offline")))
    store = ArtifactStore(tmp_path / "store")
    provider = RecordedGitEvidenceProvider(REAL_FIXTURE)
    entries = {item["evidence_id"]: item for item in payload["responses"]}
    for case_id in ("lc-python39-removeprefix-shim", "lc-python310-aiter-shim", "lc-stream-error-xfail"):
        case = next(case for case in corpus.cases if case.case_id == case_id)
        receipt = fetch_git_evidence(case.evidence[0], provider, store, max_bytes=262144)
        assert receipt.outcome == "available"
        assert receipt.artifact is not None
        assert receipt.digest == entries[case.evidence[0].evidence_id]["digest"]
        assert receipt.byte_length == entries[case.evidence[0].evidence_id]["byte_length"]


def test_redirect_allowlist_and_bounds() -> None:
    calls: list[str] = []

    class Response:
        def __init__(self, status, location=None, body=b""):
            self.status = status
            self.headers = {"Location": location} if location else {}
            self.body = body
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit): return self.body

    def opener(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            return Response(302, "https://patch-diff.githubusercontent.com/raw/pinned.patch")
        return Response(200, body=b"patch")

    pointer = EvidencePointer("redirect", "public_git", "historical_outcome", f"https://github.com/o/r/commit/{SHA}", SHA)
    response = LiveGitEvidenceProvider(opener=opener).fetch(request_from_pointer(pointer))
    assert response.outcome == "available"
    assert response.redirect_count == 1
    assert response.final_source_locator == calls[-1]
    assert calls[0].startswith("https://github.com/") and calls[1].startswith("https://patch-diff.githubusercontent.com/")

    def rejected(request, timeout):
        return Response(302, "https://evil.example/payload")

    response = LiveGitEvidenceProvider(opener=rejected).fetch(request_from_pointer(pointer))
    assert response.outcome == "unsupported" and response.error_kind == "host_not_allowlisted"


def test_capture_contract() -> None:
    payload = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    assert payload["capture_schema_version"] == "1"
    assert payload["provider_policy"]["max_bytes"] == 262144
    assert len(payload["responses"]) == 3
    for response in payload["responses"]:
        assert response["outcome"] == "available"
        assert len(response["digest"]) == 64
        assert response["byte_length"] > 0
