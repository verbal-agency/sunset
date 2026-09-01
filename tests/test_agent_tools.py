from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import socket
from typing import Any, TypedDict

from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
import pytest

import sunset.agent_tools as agent_tools
import sunset.git_repository as git_repository
from sunset.agent_tool_models import ToolReceipt
from sunset.agent_tools import (
    DISCOVER_TOOL,
    EXCERPT_TOOL,
    PROVENANCE_TOOL,
    TOOL_NAMES,
    ToolExecutionContext,
    create_tool_registry,
    tool_catalog,
)
from sunset.artifact_store import ArtifactStore
from sunset.git_repository import RepositoryError
from sunset.provenance import collect_provenance
from sunset.scanner import scan_repository

from conftest import repository_snapshot, run_git


def _context(repository: Path, store: Path, **kwargs: Any) -> ToolExecutionContext:
    return ToolExecutionContext.create(repository, store_path=store, **kwargs)


def _receipt(output: dict[str, Any]) -> dict[str, Any]:
    return output["receipt"]


def _candidate_id(repository: Path) -> str:
    return scan_repository(repository).candidates[0].candidate_id


def test_registry_is_typed_exact_and_effect_declared(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    registry = create_tool_registry(_context(renamed_repository, tmp_path / "store"))

    assert tuple(tool.name for tool in registry.tools) == TOOL_NAMES
    assert all(isinstance(tool, BaseTool) for tool in registry.tools)
    assert all(tool.metadata["sunset_contract_schema_version"] == "1" for tool in registry.tools)
    assert all(
        tool.metadata["sunset_effect"]
        == {
            "approval_required": False,
            "effect_class": "local_read_only",
            "network_access": False,
            "target_code_execution": False,
            "target_writes": False,
        }
        for tool in registry.tools
    )
    forbidden = {"repository", "target", "store", "url", "command", "credential", "network_mode"}
    assert all(forbidden.isdisjoint(tool.get_input_schema().model_fields) for tool in registry.tools)
    assert [item["name"] for item in tool_catalog()["tools"]] == list(TOOL_NAMES)


def test_discovery_preserves_domain_output_and_cached_receipt(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "store"
    first_context = _context(sample_repository, store_path)
    first = create_tool_registry(first_context).by_name(DISCOVER_TOOL).invoke({})
    second_context = _context(sample_repository, store_path)
    second = create_tool_registry(second_context).by_name(DISCOVER_TOOL).invoke({})

    assert _receipt(first)["result"] == scan_repository(sample_repository).to_dict()
    assert _receipt(first)["status"] == "partial"
    assert _receipt(first) == _receipt(second)
    assert first_context.telemetry[-1].cache_reused is False
    assert second_context.telemetry[-1].cache_reused is True


def test_provenance_preserves_candidate_and_reuses_raw_artifacts(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "store"
    candidate_id = _candidate_id(renamed_repository)
    context = _context(renamed_repository, store_path)
    output = create_tool_registry(context).by_name(PROVENANCE_TOOL).invoke(
        {"candidate_id": candidate_id}
    )
    domain = collect_provenance(renamed_repository, store_path=store_path)
    selected = next(item for item in domain.candidates if item.candidate_id == candidate_id)
    writes = context.store.artifact_write_count

    recreated = _context(renamed_repository, store_path)
    repeated = create_tool_registry(recreated).by_name(PROVENANCE_TOOL).invoke(
        {"candidate_id": candidate_id}
    )

    assert _receipt(output)["result"]["candidate"] == selected.to_dict()
    assert _receipt(output)["result"]["introduction_provenance"]["basis"] == "line_blame"
    assert _receipt(output)["evidence"] == [item.to_dict() for item in selected.artifacts]
    assert set(context.granted_artifacts) == {item.artifact_id for item in selected.artifacts}
    assert _receipt(output) == _receipt(repeated)
    assert recreated.store.artifact_write_count == 0
    assert writes == len(selected.artifacts)


def test_bound_authority_is_offline_read_only_and_target_immutable(
    renamed_repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_sentinel = tmp_path / "target-module-imported"
    (renamed_repository / "tests" / "test_import_guard.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(import_sentinel)!r}).write_text('imported', encoding='utf-8')\n",
        encoding="utf-8",
    )
    run_git(renamed_repository, "add", "tests/test_import_guard.py")
    run_git(renamed_repository, "commit", "-qm", "add import guard fixture")
    before = repository_snapshot(renamed_repository)
    status_before = run_git(renamed_repository, "status", "--short")
    context = _context(renamed_repository, tmp_path / "store")
    tool = create_tool_registry(context).by_name(DISCOVER_TOOL)

    def no_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is outside the G10 tool effect")

    monkeypatch.setattr(socket, "socket", no_socket)
    output = tool.invoke({"repository": str(tmp_path), "command": "pytest"})
    successful = tool.invoke({})

    assert _receipt(output)["status"] == "error"
    assert _receipt(output)["errors"][0]["kind"] == "input_validation_error"
    assert _receipt(successful)["status"] == "success"
    assert not import_sentinel.exists()
    assert repository_snapshot(renamed_repository) == before
    assert run_git(renamed_repository, "status", "--short") == status_before


def test_tool_processes_are_limited_to_read_only_git(
    renamed_repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(renamed_repository, tmp_path / "store")
    registry = create_tool_registry(context)
    real_run = git_repository.subprocess.run
    observed: list[tuple[str, ...]] = []

    def guarded_run(command: list[str], **kwargs: Any):
        normalized = tuple(command)
        observed.append(normalized)
        assert normalized[0] == "git"
        assert not {"add", "apply", "checkout", "clean", "commit", "push", "reset", "restore"}.intersection(
            normalized
        )
        return real_run(command, **kwargs)

    monkeypatch.setattr(git_repository.subprocess, "run", guarded_run)
    registry.by_name(DISCOVER_TOOL).invoke({})
    registry.by_name(PROVENANCE_TOOL).invoke({"candidate_id": _candidate_id(renamed_repository)})

    assert observed


def test_store_inside_target_is_rejected(renamed_repository: Path) -> None:
    with pytest.raises(RepositoryError, match="artifact store must be outside") as stopped:
        ToolExecutionContext.create(
            renamed_repository,
            store_path=renamed_repository / ".sunset",
        )
    assert stopped.value.code == "artifact_store_inside_repository"


def test_excerpt_enforces_grants_ranges_truncation_and_cumulative_budget(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    context = _context(
        renamed_repository,
        tmp_path / "store",
        max_evidence_bytes=9,
        max_excerpt_bytes=6,
    )
    registry = create_tool_registry(context)
    provenance = registry.by_name(PROVENANCE_TOOL).invoke(
        {"candidate_id": _candidate_id(renamed_repository)}
    )
    artifact = _receipt(provenance)["evidence"][0]
    excerpt_tool = registry.by_name(EXCERPT_TOOL)
    invalid_range = excerpt_tool.invoke(
        {"artifact_id": artifact["artifact_id"], "offset": artifact["byte_length"] + 1}
    )
    first = excerpt_tool.invoke({"artifact_id": artifact["artifact_id"], "offset": 0, "length": 20})
    over_budget = excerpt_tool.invoke({"artifact_id": artifact["artifact_id"], "offset": 6, "length": 4})
    second = excerpt_tool.invoke({"artifact_id": artifact["artifact_id"], "offset": 6, "length": 3})
    exhausted = excerpt_tool.invoke({"artifact_id": artifact["artifact_id"], "offset": 0, "length": 1})
    ungranted = excerpt_tool.invoke({"artifact_id": "sha256:" + "0" * 64, "offset": 0})
    cross_store = ArtifactStore(tmp_path / "other-store").put(
        b"other evidence",
        media_type="text/plain",
        source_kind="test",
        source_locator="other-store",
    )
    cross_store_result = excerpt_tool.invoke({"artifact_id": cross_store.artifact_id, "offset": 0})
    traversal = excerpt_tool.invoke({"artifact_id": "../../etc/passwd", "offset": 0})

    first_receipt = _receipt(first)
    second_receipt = _receipt(second)
    assert first["transient_content"]
    assert first_receipt["result"]["byte_length"] == 6
    assert first_receipt["result"]["end"] == 6
    assert first_receipt["result"]["truncated"] is True
    assert first_receipt["result"]["digest"] == hashlib.sha256(
        first["transient_content"].encode("utf-8")
    ).hexdigest()
    assert second_receipt["result"]["byte_length"] == 3
    assert second_receipt["budget"]["evidence_bytes_remaining"] == 0
    assert _receipt(over_budget)["status"] == "budget_exhausted"
    assert "transient_content" not in over_budget
    assert _receipt(exhausted)["status"] == "budget_exhausted"
    assert _receipt(ungranted)["errors"][0]["kind"] == "artifact_not_granted"
    assert _receipt(cross_store_result)["errors"][0]["kind"] == "artifact_not_granted"
    assert _receipt(invalid_range)["errors"][0]["kind"] == "evidence_range_invalid"
    assert _receipt(traversal)["errors"][0]["kind"] == "input_validation_error"
    assert "transient_content" not in ungranted
    assert "transient_content" not in exhausted


class _CheckpointState(TypedDict):
    receipt: dict[str, Any]


def test_receipt_round_trip_and_langgraph_checkpoint_exclude_transient_content(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    context = _context(renamed_repository, tmp_path / "store", max_excerpt_bytes=64)
    registry = create_tool_registry(context)
    provenance = registry.by_name(PROVENANCE_TOOL).invoke(
        {"candidate_id": _candidate_id(renamed_repository)}
    )
    artifact_id = _receipt(provenance)["evidence"][0]["artifact_id"]
    observation = registry.by_name(EXCERPT_TOOL).invoke(
        {"artifact_id": artifact_id, "offset": 0, "length": 32}
    )
    receipt = ToolReceipt.from_dict(_receipt(observation))
    checkpointer = InMemorySaver()
    builder = StateGraph(_CheckpointState)
    builder.add_node("persist", lambda state: state)
    builder.add_edge(START, "persist")
    builder.add_edge("persist", END)
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "g10-checkpoint"}}
    graph.invoke({"receipt": receipt.to_dict()}, config=config)
    checkpoint = checkpointer.get(config)

    assert observation["transient_content"]
    assert receipt.to_dict() == _receipt(observation)
    assert receipt.to_json() == ToolReceipt.from_dict(json.loads(receipt.to_json())).to_json()
    serialized = json.dumps(checkpoint, default=str, sort_keys=True)
    assert observation["transient_content"] not in receipt.to_json()
    assert observation["transient_content"] not in serialized
    assert "transient_content" not in serialized


def test_partial_and_supported_failures_are_structured_in_sync_and_async(
    shallow_repository: Path,
    tmp_path: Path,
) -> None:
    context = _context(shallow_repository, tmp_path / "store")
    registry = create_tool_registry(context)
    candidate_id = _candidate_id(shallow_repository)
    partial = registry.by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})
    missing = asyncio.run(
        registry.by_name(PROVENANCE_TOOL).ainvoke({"candidate_id": "missing-candidate"})
    )
    invalid = asyncio.run(registry.by_name(EXCERPT_TOOL).ainvoke({"artifact_id": "not-an-id"}))

    assert _receipt(partial)["status"] == "partial"
    assert _receipt(partial)["uncertainties"]
    assert _receipt(missing)["status"] == "error"
    assert any(item["kind"] == "candidate_not_found" for item in _receipt(missing)["errors"])
    assert _receipt(invalid)["status"] == "error"
    assert _receipt(invalid)["errors"][0]["kind"] == "input_validation_error"


def test_tool_call_budget_contains_sync_and_async_invocation(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    context = _context(renamed_repository, tmp_path / "store", max_tool_calls=1)
    tool = create_tool_registry(context).by_name(DISCOVER_TOOL)

    first = tool.invoke({})
    exhausted = asyncio.run(tool.ainvoke({}))

    assert _receipt(first)["status"] == "success"
    assert _receipt(exhausted)["status"] == "budget_exhausted"
    assert _receipt(exhausted)["errors"][0]["kind"] == "tool_call_budget_exhausted"


def test_missing_and_corrupt_artifacts_return_structured_errors(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    context = _context(renamed_repository, tmp_path / "store")
    registry = create_tool_registry(context)
    provenance = registry.by_name(PROVENANCE_TOOL).invoke(
        {"candidate_id": _candidate_id(renamed_repository)}
    )
    reference = context.granted_artifacts[_receipt(provenance)["evidence"][0]["artifact_id"]]
    path = context.store.artifact_path(reference)
    path.unlink()
    missing = registry.by_name(EXCERPT_TOOL).invoke({"artifact_id": reference.artifact_id})

    context.store.put(
        b"replacement",
        media_type=reference.media_type,
        source_kind=reference.source_kind,
        source_locator=reference.source_locator,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"corrupt")
    corrupt = asyncio.run(registry.by_name(EXCERPT_TOOL).ainvoke({"artifact_id": reference.artifact_id}))

    assert _receipt(missing)["errors"][0]["kind"] == "artifact_missing"
    assert _receipt(corrupt)["errors"][0]["kind"] == "artifact_integrity_error"
    assert "transient_content" not in missing
    assert "transient_content" not in corrupt


def test_identity_invalidation_matrix(
    renamed_repository: Path,
    compatibility_repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _context(renamed_repository, tmp_path / "base")
    same = _context(renamed_repository, tmp_path / "base")
    policy = _context(renamed_repository, tmp_path / "policy", policy_name="different-policy")
    consumed = _context(renamed_repository, tmp_path / "consumed")
    consumed.tool_calls_used = 1
    grant_store = ArtifactStore(tmp_path / "grant-artifact")
    grant = grant_store.put(b"grant", media_type="text/plain", source_kind="test", source_locator="test")
    scoped = _context(
        renamed_repository,
        tmp_path / "scoped",
        granted_artifacts={grant.artifact_id: grant},
    )
    compatibility = _context(
        compatibility_repository,
        tmp_path / "compatibility",
        collector="compatibility",
    )
    target_scope = _context(renamed_repository / "tests", tmp_path / "target-scope")
    original = base.invocation_id(DISCOVER_TOOL, {})

    assert same.invocation_id(DISCOVER_TOOL, {}) == original
    assert policy.invocation_id(DISCOVER_TOOL, {}) != original
    assert consumed.invocation_id(DISCOVER_TOOL, {}) != original
    assert scoped.invocation_id(DISCOVER_TOOL, {}) != original
    assert compatibility.invocation_id(DISCOVER_TOOL, {}) != original
    assert target_scope.invocation_id(DISCOVER_TOOL, {}) != original

    previous_schema = agent_tools.TOOL_CONTRACT_SCHEMA_VERSION
    monkeypatch.setattr(agent_tools, "TOOL_CONTRACT_SCHEMA_VERSION", "test-next")
    assert base.invocation_id(DISCOVER_TOOL, {}) != original
    monkeypatch.setattr(agent_tools, "TOOL_CONTRACT_SCHEMA_VERSION", previous_schema)

    run_git(renamed_repository, "commit", "--allow-empty", "-qm", "advance head")
    changed_head = _context(renamed_repository, tmp_path / "head")
    assert changed_head.invocation_id(DISCOVER_TOOL, {}) != original


def test_context_detects_bound_head_change_as_structured_failure(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    context = _context(renamed_repository, tmp_path / "store")
    run_git(renamed_repository, "commit", "--allow-empty", "-qm", "advance head")

    output = create_tool_registry(context).by_name(DISCOVER_TOOL).invoke({})

    assert _receipt(output)["status"] == "error"
    assert _receipt(output)["errors"][0]["kind"] == "repository_head_changed"
