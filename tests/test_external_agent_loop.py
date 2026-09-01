from __future__ import annotations

import json
from pathlib import Path

from sunset.agent_loop import AgentLoopConfig, LocalEvidenceAgentLoop
from sunset.agent_tool_models import ToolReceipt
from sunset.agent_tools import PROVENANCE_TOOL, ToolExecutionContext, create_tool_registry
from sunset.external_agent_tools import RESOLVE_EXTERNAL_REFERENCE_TOOL, ExternalEvidenceContext, RecordedExternalEvidenceProvider
from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig
from sunset.scanner import scan_repository

from conftest import run_git


FIXTURE = Path(__file__).parent / "fixtures" / "evidence" / "recorded_responses.json"


def _add_explicit_reference(repository: Path) -> None:
    path = repository / "tests" / "test_markers.py"
    path.write_text(
        "import pytest\n\n@pytest.mark.xfail(reason='https://github.com/sunset-fixtures/widget/issues/101')\ndef test_external(): pass\n",
        encoding="utf-8",
    )
    run_git(repository, "add", "tests/test_markers.py")
    run_git(repository, "commit", "-qm", "use explicit external reference")


def test_recorded_external_tool_runs_inside_bounded_g12_loop(renamed_repository: Path, tmp_path: Path) -> None:
    _add_explicit_reference(renamed_repository)
    local = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    candidate_id = scan_repository(renamed_repository).candidates[0].candidate_id
    provenance = ToolReceipt.from_dict(create_tool_registry(local).by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})["receipt"])
    external = ExternalEvidenceContext.from_receipts(
        local, (provenance,), provider=RecordedExternalEvidenceProvider(FIXTURE), mode="recorded", allowed_hosts=("github.com",),
    )
    provider_fixture = tmp_path / "provider.json"
    provider_fixture.write_text(json.dumps({"responses": [{"provider": "github", "locator": "https://github.com/sunset-fixtures/widget/issues/101", "outcome": "supports_expired", "summary": "Closed upstream.", "body": "TOP_SECRET_PROVIDER_BODY"}]}), encoding="utf-8")
    external = ExternalEvidenceContext.from_receipts(
        local, (provenance,), provider=RecordedExternalEvidenceProvider(provider_fixture), mode="recorded", allowed_hosts=("github.com",),
    )
    fixture = tmp_path / "model.json"
    fixture.write_text(json.dumps({"schema_version": "1", "response": {"assumption_status": "unknown", "summary": "Resolve the explicit upstream reference.", "claims": [], "open_questions": [], "proposed_tools": [RESOLVE_EXTERNAL_REFERENCE_TOOL]}, "usage": {"input_tokens": 10, "output_tokens": 5}}), encoding="utf-8")
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture), allowed_tool_names=(RESOLVE_EXTERNAL_REFERENCE_TOOL,)))

    result = LocalEvidenceAgentLoop(
        local, config=AgentLoopConfig(mode="recorded"), runtime=runtime, external_context=external, seed_receipts=(provenance,),
    ).run()

    external_receipts = [item for item in result.receipts if item.tool_name == RESOLVE_EXTERNAL_REFERENCE_TOOL]
    assert result.terminal_reason == "completed"
    assert len(external_receipts) == 1
    assert external_receipts[0].result["outcome"] == "supports_expired"
    calls = [item for item in result.call_ledger if item.request.tool_name == RESOLVE_EXTERNAL_REFERENCE_TOOL]
    assert calls[0].request.antecedent_reasoning_id == result.reasoning[0].invocation_id
    assert "TOP_SECRET_PROVIDER_BODY" not in result.to_json()
    views = "".join(path.read_text(encoding="utf-8") for path in (local.store.root / "views").glob("sunset-agent-loop*.json"))
    assert "TOP_SECRET_PROVIDER_BODY" not in views


def test_external_policy_identity_rejects_incompatible_resume(renamed_repository: Path, tmp_path: Path) -> None:
    local = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    candidate_id = scan_repository(renamed_repository).candidates[0].candidate_id
    provenance = ToolReceipt.from_dict(create_tool_registry(local).by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})["receipt"])
    one = ExternalEvidenceContext.from_receipts(local, (provenance,), provider=RecordedExternalEvidenceProvider(FIXTURE), mode="recorded", allowed_hosts=("github.com",), freshness_key="one")
    fixture = tmp_path / "model.json"
    fixture.write_text(json.dumps({"schema_version": "1", "response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": [RESOLVE_EXTERNAL_REFERENCE_TOOL]}}), encoding="utf-8")
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture), allowed_tool_names=(RESOLVE_EXTERNAL_REFERENCE_TOOL,)))
    result = LocalEvidenceAgentLoop(local, config=AgentLoopConfig(mode="recorded", interrupt_after_steps=1), runtime=runtime, external_context=one, seed_receipts=(provenance,)).run()
    two = ExternalEvidenceContext.from_receipts(local, (provenance,), provider=RecordedExternalEvidenceProvider(FIXTURE), mode="recorded", allowed_hosts=("github.com",), freshness_key="two")
    try:
        LocalEvidenceAgentLoop(local, config=AgentLoopConfig(mode="recorded"), runtime=runtime, external_context=two, seed_receipts=(provenance,)).run(run_id=result.run_id)
    except ValueError as exc:
        assert "context policy" in str(exc)
    else:
        raise AssertionError("changed provider freshness must invalidate the checkpoint")


def test_interrupted_external_action_resumes_without_repeating_provider_call(renamed_repository: Path, tmp_path: Path) -> None:
    _add_explicit_reference(renamed_repository)
    local = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    candidate_id = scan_repository(renamed_repository).candidates[0].candidate_id
    provenance = ToolReceipt.from_dict(create_tool_registry(local).by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})["receipt"])

    class _CountingRecorded(RecordedExternalEvidenceProvider):
        calls = 0
        def resolve(self, *args, **kwargs):
            self.calls += 1
            return super().resolve(*args, **kwargs)

    provider = _CountingRecorded(FIXTURE)
    external = ExternalEvidenceContext.from_receipts(local, (provenance,), provider=provider, mode="recorded", allowed_hosts=("github.com",))
    fixture = tmp_path / "model.json"
    fixture.write_text(json.dumps({"schema_version": "1", "response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": [RESOLVE_EXTERNAL_REFERENCE_TOOL]}}), encoding="utf-8")
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture), allowed_tool_names=(RESOLVE_EXTERNAL_REFERENCE_TOOL,)))
    interrupted = LocalEvidenceAgentLoop(local, config=AgentLoopConfig(mode="recorded", interrupt_after_steps=2), runtime=runtime, external_context=external, seed_receipts=(provenance,)).run()
    assert interrupted.terminal_reason == "interrupted"
    assert provider.calls == 1

    resumed = LocalEvidenceAgentLoop(local, config=AgentLoopConfig(mode="recorded"), runtime=runtime, external_context=external, seed_receipts=(provenance,)).run(run_id=interrupted.run_id)
    assert resumed.terminal_reason == "completed"
    assert provider.calls == 1
