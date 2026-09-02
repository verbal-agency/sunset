from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.cli import main
from sunset.git_evidence import (
    GitEvidenceError,
    LiveGitEvidenceProvider,
    RecordedGitEvidenceProvider,
    fetch_git_evidence,
    request_from_pointer,
)
from sunset.validation_corpus_models import EvidencePointer


FIXTURE = Path(__file__).parent / "fixtures" / "git_evidence" / "g22-recorded.json"
SHA = "0123456789abcdef0123456789abcdef01234567"


def _pointer(evidence_id: str, locator: str, role: str = "historical_outcome") -> EvidencePointer:
    return EvidencePointer(evidence_id, "public_git", role, locator, SHA)


def test_g22_ac01_pointer_bound_requests() -> None:
    pointer = _pointer("fixture:blob", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py")
    request = request_from_pointer(pointer)
    assert request.kind == "blob"
    assert request.path == "src/compat.py"
    assert request.repository_url.endswith("widget.git")
    with pytest.raises(GitEvidenceError, match="traversal"):
        request_from_pointer(_pointer("bad", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/../secret"))
    with pytest.raises(GitEvidenceError, match="only public_git"):
        request_from_pointer(EvidencePointer("recorded", "recorded_artifact", "historical_outcome", "artifact:1"))
    with pytest.raises(GitEvidenceError, match="GitHub"):
        request_from_pointer(_pointer("host", f"https://git.example.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py"))
    with pytest.raises(GitEvidenceError, match="positive"):
        request_from_pointer(pointer, max_bytes=0)
    with pytest.raises(GitEvidenceError, match="role"):
        request_from_pointer(EvidencePointer("bad-role", "public_git", "unsupported", pointer.locator, SHA))


def test_g22_ac02_recorded_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("recorded Git evidence must remain offline")

    monkeypatch.setattr("socket.socket", forbidden)
    store = ArtifactStore(tmp_path / "store")
    provider = RecordedGitEvidenceProvider(FIXTURE)
    blob = fetch_git_evidence(_pointer("fixture:blob", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py"), provider, store)
    patch = fetch_git_evidence(_pointer("fixture:patch", f"https://github.com/sunset-fixtures/widget/commit/{SHA}"), provider, store)
    missing = fetch_git_evidence(_pointer("fixture:missing", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/missing.py"), provider, store)
    assert blob.outcome == patch.outcome == "available"
    assert blob.artifact and store.read(blob.artifact).startswith(b"def compatibility")
    assert patch.artifact and b"diff --git" in store.read(patch.artifact)
    wrong_path = fetch_git_evidence(_pointer("fixture:blob", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/other.py"), provider, store)
    assert wrong_path.outcome == "missing" and wrong_path.artifact is None
    assert missing.outcome == "missing" and missing.artifact is None
    contradiction_source = fetch_git_evidence(_pointer("fixture:contradict-source", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py"), provider, store)
    contradiction_patch = fetch_git_evidence(_pointer("fixture:contradict-patch", f"https://github.com/sunset-fixtures/widget/commit/{SHA}"), provider, store)
    assert contradiction_source.outcome == contradiction_patch.outcome == "available"
    assert contradiction_source.artifact and contradiction_patch.artifact
    assert store.read(contradiction_source.artifact) != store.read(contradiction_patch.artifact)


def test_g22_ac03_explicit_live_boundary(tmp_path: Path) -> None:
    calls: list[object] = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit):
            assert limit == 65_537
            return b"pinned source"

    def opener(request, timeout):
        calls.append(request)
        assert request.full_url.startswith("https://raw.githubusercontent.com/")
        assert timeout == 10
        return Response()

    pointer = _pointer("fixture:blob", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py")
    result = fetch_git_evidence(pointer, LiveGitEvidenceProvider(opener=opener), ArtifactStore(tmp_path / "live"))
    assert result.outcome == "available"
    assert len(calls) == 1


def test_g22_ac04_replay_and_budgets(tmp_path: Path) -> None:
    class CountingProvider(RecordedGitEvidenceProvider):
        calls = 0
        def fetch(self, request):
            self.calls += 1
            return super().fetch(request)

    provider = CountingProvider(FIXTURE)
    pointer = _pointer("fixture:blob", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py")
    store = ArtifactStore(tmp_path / "store")
    first = fetch_git_evidence(pointer, provider, store)
    second = fetch_git_evidence(pointer, provider, store)
    assert first.to_dict() == second.to_dict()
    assert provider.calls == 1
    oversized = fetch_git_evidence(_pointer("fixture:oversize", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py"), CountingProvider(FIXTURE), ArtifactStore(tmp_path / "small"), max_bytes=3)
    assert oversized.outcome == "budget_exhausted" and oversized.artifact is None
    changed_fixture = tmp_path / "changed.json"
    changed_fixture.write_text(FIXTURE.read_text(encoding="utf-8").replace("removeprefix('x')", "removeprefix('y')"), encoding="utf-8")
    changed = fetch_git_evidence(pointer, CountingProvider(changed_fixture), store)
    assert changed.outcome == "available" and changed.artifact != first.artifact


def test_g22_adversarial_failures(tmp_path: Path) -> None:
    class TimeoutProvider:
        name = "timeout"
        def fetch(self, request):
            raise TimeoutError("timed out")

    # Provider exceptions are converted into structured uncertainty, not conclusions.
    result = fetch_git_evidence(_pointer("timeout", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py"), TimeoutProvider(), ArtifactStore(tmp_path / "timeout"))
    assert result.outcome == "failed" and result.artifact is None

    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schema_version":"1","responses":[null]}', encoding="utf-8")
    provider = RecordedGitEvidenceProvider(malformed)
    result = provider.fetch(request_from_pointer(_pointer("bad", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py")))
    assert result.outcome == "failed" and result.error_kind == "recorded_fixture_unavailable"

    class BadResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit): return "not bytes"

    result = LiveGitEvidenceProvider(opener=lambda request, timeout: BadResponse()).fetch(
        request_from_pointer(_pointer("bad-live", f"https://github.com/sunset-fixtures/widget/blob/{SHA}/src/compat.py"))
    )
    assert result.outcome == "failed" and result.error_kind == "malformed_response"


def test_g22_ac05_cli_and_privacy(tmp_path: Path, capsys) -> None:
    manifest = Path(__file__).parent / "fixtures" / "validation_corpus" / "langchain-validation-v1.json"
    exit_code = main(["git-evidence", "fetch", "--manifest", str(manifest), "--case-id", "lc-stale-xfail", "--evidence-id", "lc-stale-xfail:history", "--store", str(tmp_path / "store"), "--fixture", str(FIXTURE)])
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["outcome"] == "missing"
    assert "raw" not in output and "credentials" not in json.dumps(output).lower()


def test_g22_ac06_verification() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["schema_version"] == "1"
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G22-pinned-git-evidence-ingestion.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert all(f"G22-AC0{i}" in text for i in range(1, 7))
