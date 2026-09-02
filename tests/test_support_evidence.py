from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.support_evidence import (
    RecordedSupportEvidenceProvider,
    SupportEvidenceError,
    capture_support_evidence,
    load_support_selection,
    validate_support_selection,
)
from sunset.validation_corpus import load_validation_corpus


ROOT = Path(__file__).parent
CORPUS = ROOT / "fixtures" / "validation_corpus" / "langchain-validation-v1.json"
SELECTION = ROOT / "fixtures" / "support_evidence" / "g22b-selection-v1.json"
REAL_FIXTURE = ROOT / "fixtures" / "git_evidence" / "g22b-langchain-support-v1.json"


def test_supplement_binding_and_rejection() -> None:
    corpus = load_validation_corpus(CORPUS)
    selection = load_support_selection(SELECTION)
    validate_support_selection(selection, corpus)

    invalid = selection.__class__(
        selection.supplement_id,
        selection.schema_version,
        selection.selection_status,
        selection.owner_approval_required,
        selection.g21_manifest_id,
        "0" * 64,
        selection.repository,
        selection.repository_url,
        selection.pinned_head,
        selection.published_release,
        selection.cases,
    )
    with pytest.raises(SupportEvidenceError) as caught:
        validate_support_selection(invalid, corpus)
    assert caught.value.code == "manifest_mismatch"


class FakeProvider:
    name = "fake-support"
    allowed_hosts = ("github.com", "pypi.org")

    def __init__(self, outcomes: dict[str, tuple[str, str, bytes | None, str | None]] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.calls: list[str] = []

    def fetch(self, entry, *, max_bytes):
        self.calls.append(entry.evidence_id)
        return self.outcomes.get(entry.evidence_id, ("available", "captured", entry.evidence_id.encode(), None))


def test_support_bundle_capture_and_offline_replay(tmp_path: Path) -> None:
    corpus = load_validation_corpus(CORPUS)
    selection = load_support_selection(SELECTION)
    provider = FakeProvider()
    fixture = tmp_path / "support.json"
    report = capture_support_evidence(corpus, selection, ArtifactStore(tmp_path / "store"), fixture, provider=provider)
    assert report.status == "verified"
    assert fixture.exists()
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert len(payload["responses"]) == 12
    assert sum(item["outcome"] == "not_applicable" for item in payload["responses"]) == 2
    recorded = RecordedSupportEvidenceProvider(fixture)
    captured = [r for r in report.receipts if r.outcome == "available"]
    assert captured
    outcome, _, raw, _ = recorded.fetch(captured[0].entry)
    assert outcome == "available" and raw == captured[0].entry.evidence_id.encode()


def test_support_failure_diagnostics_do_not_write_verified_fixture(tmp_path: Path) -> None:
    corpus = load_validation_corpus(CORPUS)
    selection = load_support_selection(SELECTION)
    first = next(entry.evidence_id for case in selection.cases for entry in case.entries if entry.status == "capture")
    provider = FakeProvider({first: ("missing", "not found", None, "http_404")})
    fixture = tmp_path / "must-not-exist.json"
    diagnostic = tmp_path / "blocked.json"
    report = capture_support_evidence(corpus, selection, ArtifactStore(tmp_path / "store"), fixture, provider=provider, diagnostic_output=diagnostic)
    assert report.status == "partial"
    assert not fixture.exists()
    assert json.loads(diagnostic.read_text(encoding="utf-8"))["diagnostics"][0]["error_kind"] == "http_404"


def test_support_transport_host_and_budget_guards() -> None:
    corpus = load_validation_corpus(CORPUS)
    selection = load_support_selection(SELECTION)
    entry = next(entry for case in selection.cases for entry in case.entries if entry.source_kind == "public_git")
    from sunset.support_evidence import LiveSupportEvidenceProvider

    class Response:
        status = 200
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit): return b"0123456789"

    calls = []
    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return Response()

    provider = LiveSupportEvidenceProvider(opener=opener, allowed_hosts=("raw.githubusercontent.com",))
    outcome, _, _, error = provider.fetch(entry, max_bytes=4)
    assert outcome == "budget_exhausted" and error == "response_too_large"
    assert len(calls) == 1


def test_support_fixture_replays_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    selection = load_support_selection(SELECTION)
    provider = RecordedSupportEvidenceProvider(REAL_FIXTURE)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("replay must be offline")))
    for case in selection.cases:
        for entry in case.entries:
            if entry.status == "not_applicable":
                continue
            outcome, _, raw, error = provider.fetch(entry, max_bytes=1_200_000)
            assert outcome == "available", error
            assert raw


def test_real_support_bundle_capture_or_blocked_report() -> None:
    payload = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert payload["g21_manifest_digest"] == load_support_selection(SELECTION).g21_manifest_digest
    assert len(payload["responses"]) == 12
    assert all(item["outcome"] in {"available", "not_applicable"} for item in payload["responses"])
