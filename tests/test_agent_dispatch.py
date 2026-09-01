from __future__ import annotations

from pathlib import Path
from typing import Any

from sunset.agent_dispatch import DeterministicToolDispatcher, ToolRequest
from sunset.agent_tools import DISCOVER_TOOL, PROVENANCE_TOOL, ToolExecutionContext, create_tool_registry


def test_dispatcher_allows_only_typed_local_registry(renamed_repository: Path, tmp_path: Path) -> None:
    context = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    registry = create_tool_registry(context)
    dispatcher = DeterministicToolDispatcher(registry)

    unknown = dispatcher.dispatch(ToolRequest("shell", {}, "initial"))
    malformed = dispatcher.dispatch(ToolRequest(PROVENANCE_TOOL, {}, "initial"))
    missing_antecedent = dispatcher.dispatch(ToolRequest(DISCOVER_TOOL, {}, "reasoning"))
    successful = dispatcher.dispatch(ToolRequest(DISCOVER_TOOL, {}, "initial"))

    assert unknown.status == "rejected" and unknown.error is not None
    assert unknown.error.kind == "tool_not_allowlisted"
    assert malformed.status == "rejected" and malformed.error is not None
    assert malformed.error.kind == "tool_input_invalid"
    assert missing_antecedent.status == "rejected"
    assert successful.status == "completed"
    assert successful.receipt is not None
    assert successful.receipt.tool_name == DISCOVER_TOOL


def test_dispatcher_rejects_effect_changes_and_reuses_completed_receipt(
    renamed_repository: Path, tmp_path: Path
) -> None:
    context = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    registry = create_tool_registry(context)
    dispatcher = DeterministicToolDispatcher(registry)
    request = ToolRequest(DISCOVER_TOOL, {}, "initial")
    first = dispatcher.dispatch(request)
    assert first.receipt is not None

    reused = dispatcher.dispatch(request, completed={request.key: first.receipt})
    assert reused.status == "reused"
    assert context.tool_calls_used == 1

    tool = registry.by_name(DISCOVER_TOOL)
    tool.metadata["sunset_effect"] = {"effect_class": "external_read"}
    rejected = dispatcher.dispatch(ToolRequest(DISCOVER_TOOL, {}, "initial"))
    assert rejected.status == "rejected" and rejected.error is not None
    assert rejected.error.kind == "tool_effect_rejected"
    assert context.tool_calls_used == 1
