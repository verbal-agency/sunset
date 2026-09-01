from __future__ import annotations

import json
from pathlib import Path
import socket
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from sunset.agent_loop import AgentLoopConfig, LocalEvidenceAgentLoop
from sunset.agent_tools import EXCERPT_TOOL, PROVENANCE_TOOL, ToolExecutionContext
from sunset.artifact_store import ArtifactStore

from conftest import repository_snapshot, run_git


def _fixture(path: Path, tool_name: str, *, questions: list[str] | None = None) -> Path:
    path.write_text(json.dumps({
        "schema_version": "1",
        "response": {
            "assumption_status": "unknown", "summary": "More local evidence may help.",
            "claims": [], "open_questions": questions or [], "proposed_tools": [tool_name],
        },
        "usage": {"input_tokens": 10, "output_tokens": 6},
    }), encoding="utf-8")
    return path


def _recorded(path: Path):
    from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig
    return ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(path)))


class _FakeChatModel(BaseChatModel):
    response: str
    fake_name: str = "fake"
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return self.fake_name

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])


def test_heuristic_loop_is_offline_read_only_and_never_constructs_model(
    renamed_repository: Path, tmp_path: Path, monkeypatch: Any
) -> None:
    before = repository_snapshot(renamed_repository)
    status = run_git(renamed_repository, "status", "--short")
    context = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no network")))

    result = LocalEvidenceAgentLoop(context, config=AgentLoopConfig(mode="heuristic")).run()

    assert result.terminal_reason == "completed"
    assert [receipt.tool_name for receipt in result.receipts] == ["sunset_discover_candidates", PROVENANCE_TOOL]
    assert not result.reasoning
    assert repository_snapshot(renamed_repository) == before
    assert run_git(renamed_repository, "status", "--short") == status


def test_recorded_hypotheses_take_distinct_bounded_local_paths(renamed_repository: Path, tmp_path: Path) -> None:
    provenance_fixture = _fixture(tmp_path / "provenance.json", PROVENANCE_TOOL)
    provenance_context = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "provenance-store")
    provenance = LocalEvidenceAgentLoop(
        provenance_context,
        config=AgentLoopConfig(mode="recorded"), runtime=_recorded(provenance_fixture),
    ).run()

    store = ArtifactStore(tmp_path / "excerpt-store")
    grant = store.put(b"recorded local evidence", media_type="text/plain", source_kind="test", source_locator="fixture")
    excerpt_context = ToolExecutionContext.create(
        renamed_repository, store_path=store.root, artifact_store=store, granted_artifacts={grant.artifact_id: grant},
    )
    excerpt_fixture = _fixture(tmp_path / "excerpt.json", EXCERPT_TOOL)
    excerpt = LocalEvidenceAgentLoop(
        excerpt_context,
        config=AgentLoopConfig(mode="recorded"), runtime=_recorded(excerpt_fixture),
    ).run()

    assert [item.tool_name for item in provenance.receipts] == ["sunset_discover_candidates", PROVENANCE_TOOL]
    assert [item.tool_name for item in excerpt.receipts] == ["sunset_discover_candidates", EXCERPT_TOOL]
    for result in (provenance, excerpt):
        later = [item for item in result.call_ledger if item.request.origin == "reasoning"]
        assert later and later[0].request.antecedent_reasoning_id == result.reasoning[0].invocation_id
        assert result.terminal_reason == "completed"


def test_interrupted_checkpoint_resumes_without_repeating_completed_call(renamed_repository: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    first_context = ToolExecutionContext.create(renamed_repository, store_path=store)
    interrupted = LocalEvidenceAgentLoop(
        first_context, config=AgentLoopConfig(interrupt_after_steps=1)
    ).run()
    assert interrupted.terminal_reason == "interrupted"
    assert [item.tool_name for item in interrupted.receipts] == ["sunset_discover_candidates"]

    resumed_context = ToolExecutionContext.create(renamed_repository, store_path=store)
    resumed = LocalEvidenceAgentLoop(resumed_context).run(run_id=interrupted.run_id)
    assert resumed.terminal_reason == "completed"
    assert [item.tool_name for item in resumed.receipts] == ["sunset_discover_candidates", PROVENANCE_TOOL]
    assert [item.tool_name for item in resumed_context.telemetry] == [PROVENANCE_TOOL]


def test_checkpoint_rejects_changed_policy_and_trace_excludes_raw_excerpt(renamed_repository: Path, tmp_path: Path) -> None:
    fixture = _fixture(tmp_path / "excerpt.json", EXCERPT_TOOL)
    store = ArtifactStore(tmp_path / "store")
    grant = store.put(b"TOP_SECRET_LOCAL_EXCERPT", media_type="text/plain", source_kind="test", source_locator="fixture")
    context = ToolExecutionContext.create(renamed_repository, store_path=store.root, artifact_store=store, granted_artifacts={grant.artifact_id: grant})
    result = LocalEvidenceAgentLoop(context, config=AgentLoopConfig(mode="recorded"), runtime=_recorded(fixture)).run()
    assert "TOP_SECRET_LOCAL_EXCERPT" not in result.to_json()
    checkpoint_text = "".join(path.read_text(encoding="utf-8") for path in (store.root / "views").glob("sunset-agent-loop*.json"))
    assert "TOP_SECRET_LOCAL_EXCERPT" not in checkpoint_text

    changed = ToolExecutionContext.create(renamed_repository, store_path=store.root, max_tool_calls=3)
    try:
        LocalEvidenceAgentLoop(changed, config=AgentLoopConfig(mode="recorded"), runtime=_recorded(fixture)).run(run_id=result.run_id)
    except ValueError as exc:
        assert "context policy" in str(exc)
    else:
        raise AssertionError("changed policy must not reuse a checkpoint")

    extra = store.put(b"other", media_type="text/plain", source_kind="test", source_locator="extra")
    changed_grants = ToolExecutionContext.create(
        renamed_repository, store_path=store.root, artifact_store=store,
        granted_artifacts={grant.artifact_id: grant, extra.artifact_id: extra},
    )
    try:
        LocalEvidenceAgentLoop(changed_grants, config=AgentLoopConfig(mode="recorded"), runtime=_recorded(fixture)).run(run_id=result.run_id)
    except ValueError as exc:
        assert "grant scope" in str(exc)
    else:
        raise AssertionError("changed grant scope must not reuse a checkpoint")

    changed_model_fixture = _fixture(tmp_path / "changed-model.json", EXCERPT_TOOL, questions=["new prompt input"])
    original_grants = {grant.artifact_id: grant}
    changed_model_context = ToolExecutionContext.create(
        renamed_repository, store_path=store.root, artifact_store=store, granted_artifacts=original_grants,
    )
    try:
        LocalEvidenceAgentLoop(changed_model_context, config=AgentLoopConfig(mode="recorded"), runtime=_recorded(changed_model_fixture)).run(run_id=result.run_id)
    except ValueError as exc:
        assert "model or loop configuration" in str(exc)
    else:
        raise AssertionError("changed model identity must not reuse a checkpoint")

    (renamed_repository / "README.md").write_text("changed head\n", encoding="utf-8")
    run_git(renamed_repository, "add", "README.md")
    run_git(renamed_repository, "commit", "-qm", "change fixture head")
    changed_head = ToolExecutionContext.create(
        renamed_repository, store_path=store.root, artifact_store=store, granted_artifacts=original_grants,
    )
    try:
        LocalEvidenceAgentLoop(changed_head, config=AgentLoopConfig(mode="recorded"), runtime=_recorded(fixture)).run(run_id=result.run_id)
    except ValueError as exc:
        assert "repository identity or HEAD" in str(exc)
    else:
        raise AssertionError("changed HEAD must not reuse a checkpoint")


def test_iteration_walltime_and_tool_budgets_have_explicit_terminals(renamed_repository: Path, tmp_path: Path) -> None:
    iteration = LocalEvidenceAgentLoop(
        ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "iteration"),
        config=AgentLoopConfig(max_iterations=1),
    ).run()
    call_budget = LocalEvidenceAgentLoop(
        ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "call-budget"),
        config=AgentLoopConfig(max_tool_calls=1),
    ).run()
    clock_values = iter((0.0, 0.0, 2.0))
    walltime = LocalEvidenceAgentLoop(
        ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "walltime"),
        config=AgentLoopConfig(max_wall_time_seconds=1.0),
        clock=lambda: next(clock_values),
    ).run()

    assert iteration.terminal_reason == "iteration_budget_exhausted"
    assert call_budget.terminal_reason == "tool_budget_exhausted"
    assert walltime.terminal_reason == "wall_time_exhausted"
    assert all(item.errors[-1].kind == item.terminal_reason for item in (iteration, call_budget, walltime))


def test_two_live_adapters_use_the_same_agent_contract(renamed_repository: Path, tmp_path: Path) -> None:
    response = json.dumps({"assumption_status": "unknown", "summary": "Need provenance.", "claims": [], "open_questions": [], "proposed_tools": [PROVENANCE_TOOL]})
    from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig
    first_model, second_model = _FakeChatModel(response=response, fake_name="one"), _FakeChatModel(response=response, fake_name="two")
    results = []
    for index, model in enumerate((first_model, second_model)):
        runtime = ModelRuntime(ModelRuntimeConfig(mode="live", model_identity=f"fake:{index}"), model)
        context = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / f"store-{index}")
        results.append(LocalEvidenceAgentLoop(context, config=AgentLoopConfig(mode="live"), runtime=runtime).run())
    assert [item.terminal_reason for item in results] == ["completed", "completed"]
    assert [[receipt.tool_name for receipt in item.receipts] for item in results] == [
        ["sunset_discover_candidates", PROVENANCE_TOOL], ["sunset_discover_candidates", PROVENANCE_TOOL],
    ]
    assert first_model.calls == second_model.calls == 2
