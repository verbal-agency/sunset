from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from sunset.agent_dispatch import DeterministicToolDispatcher, ToolRequest
from sunset.agent_tool_models import ToolReceipt
from sunset.agent_tools import PROVENANCE_TOOL, ToolExecutionContext, create_tool_registry
from sunset.external_agent_tools import (
    EXTERNAL_READ_RECORDED_EFFECT,
    RESOLVE_EXTERNAL_REFERENCE_TOOL,
    ExplicitGitHubProvider,
    ExternalEvidenceContext,
    RecordedExternalEvidenceProvider,
    create_external_tool_registry,
)
from sunset.external_evidence_models import ExternalReference
from sunset.scanner import scan_repository

from conftest import run_git


FIXTURE = Path(__file__).parent / "fixtures" / "evidence" / "recorded_responses.json"


def _local_receipt(repository: Path, store: Path) -> tuple[ToolExecutionContext, ToolReceipt]:
    context = ToolExecutionContext.create(repository, store_path=store)
    candidate_id = scan_repository(repository).candidates[0].candidate_id
    receipt = ToolReceipt.from_dict(create_tool_registry(context).by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})["receipt"])
    return context, receipt


def _add_explicit_reference(repository: Path) -> None:
    path = repository / "tests" / "test_markers.py"
    path.write_text(
        "import pytest\n\n@pytest.mark.xfail(reason='https://github.com/sunset-fixtures/widget/issues/101')\ndef test_external(): pass\n",
        encoding="utf-8",
    )
    run_git(repository, "add", "tests/test_markers.py")
    run_git(repository, "commit", "-qm", "use explicit external reference")


def test_recorded_external_tool_requires_extracted_reference_and_is_offline(
    renamed_repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_explicit_reference(renamed_repository)
    local, receipt = _local_receipt(renamed_repository, tmp_path / "store")
    context = ExternalEvidenceContext.from_receipts(
        local, (receipt,), provider=RecordedExternalEvidenceProvider(FIXTURE), mode="recorded", allowed_hosts=("github.com",),
    )
    assert context.references
    dispatcher = DeterministicToolDispatcher(
        create_external_tool_registry(context), allowed_effects=(EXTERNAL_READ_RECORDED_EFFECT.to_dict(),)
    )
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("recorded mode is offline")))
    reference_id = next(iter(context.references))
    completed = dispatcher.dispatch(ToolRequest(RESOLVE_EXTERNAL_REFERENCE_TOOL, {"reference_id": reference_id}, "reasoning", "reason-1"))
    unknown = dispatcher.dispatch(ToolRequest(RESOLVE_EXTERNAL_REFERENCE_TOOL, {"reference_id": "external-ref-v1-" + "0" * 20}, "reasoning", "reason-1"))
    malformed = dispatcher.dispatch(ToolRequest(RESOLVE_EXTERNAL_REFERENCE_TOOL, {"locator": "https://github.com"}, "reasoning", "reason-1"))

    assert completed.status == "completed" and completed.receipt is not None
    assert completed.receipt.result["outcome"] == "supports_expired"
    assert completed.receipt.evidence and local.store.read(completed.receipt.evidence[0])
    assert unknown.status == "completed" and unknown.receipt is not None
    assert unknown.receipt.status == "error"
    assert unknown.receipt.errors[0].kind == "unknown_reference"
    assert malformed.status == "rejected"


def test_recorded_outcomes_and_rate_budget_remain_structured(renamed_repository: Path, tmp_path: Path) -> None:
    local = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    fixed = ExternalReference("github", "https://github.com/sunset-fixtures/widget/issues/101")
    active = ExternalReference("github", "https://github.com/sunset-fixtures/widget/issues/102")
    failed = ExternalReference("github", "https://github.com/sunset-fixtures/widget/issues/104")
    values = iter((0.0, 0.0, 0.0))
    context = ExternalEvidenceContext(
        local, {item.reference_id: item for item in (fixed, active, failed)}, RecordedExternalEvidenceProvider(FIXTURE), "recorded", ("github.com",),
        max_requests=3, min_request_interval_seconds=1.0, clock=lambda: next(values),
    )
    first = context.invoke(fixed.reference_id)
    rate_limited = context.invoke(active.reference_id)
    assert first.receipt.result["outcome"] == "supports_expired"
    assert rate_limited.receipt.status == "error"
    assert rate_limited.receipt.errors[0].kind == "rate_limited"

    release = ExternalReference("release_note", "https://docs.sunset-fixtures.test/widget/changelog", "widget", "2.4")
    release_context = ExternalEvidenceContext(
        local, {release.reference_id: release}, RecordedExternalEvidenceProvider(FIXTURE), "recorded", ("docs.sunset-fixtures.test",),
    )
    release_receipt = release_context.invoke(release.reference_id).receipt
    assert release_receipt.result["outcome"] == "supports_active"
    assert release_receipt.result["reference"]["dependency_name"] == "widget"
    assert release_receipt.result["reference"]["dependency_version"] == "2.4"

    with pytest.raises(ValueError, match="host allowlist"):
        ExternalEvidenceContext(local, {release.reference_id: release}, RecordedExternalEvidenceProvider(FIXTURE), "recorded", ("github.com",))


def test_live_provider_uses_only_supplied_credential_and_enforces_response_size() -> None:
    calls: list[Any] = []

    class _Response:
        def __enter__(self): return self
        def __exit__(self, *args: Any) -> None: return None
        def read(self, limit: int) -> bytes:
            assert limit == 65
            return b'{"state":"closed"}'

    def opener(request: Any, timeout: int) -> _Response:
        calls.append(request)
        assert "Bearer supplied-secret" in request.get_header("Authorization")
        return _Response()

    provider = ExplicitGitHubProvider("supplied-secret", opener=opener)
    response = provider.resolve(ExternalReference("github", "https://github.com/org/repo/issues/9"), max_response_bytes=64)
    assert response.outcome == "supports_expired"
    assert response.raw == b'{"state":"closed"}'
    assert len(calls) == 1
