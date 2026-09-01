from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sunset.artifact_store import ArtifactStore
from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig
from sunset.model_runtime_models import TransientEvidence
from sunset.reasoning_graph import ReasoningGraph

from test_model_runtime import ARTIFACT_ID, FIXTURE, FakeChatModel, _request, _valid_response


def test_graph_reuses_completed_result_without_reinvoking_live_model(tmp_path: Path) -> None:
    model = FakeChatModel(response=_valid_response())
    graph = ReasoningGraph(
        ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:cached"), model),
        ArtifactStore(tmp_path / "store"),
    )
    request = _request()

    first = graph.run(request, transient_evidence=(TransientEvidence(ARTIFACT_ID, "TRANSIENT_DO_NOT_CHECKPOINT"),))
    second = graph.run(request, transient_evidence=(TransientEvidence(ARTIFACT_ID, "TRANSIENT_DO_NOT_CHECKPOINT"),))
    checkpoint = graph.store.read_view(f"sunset-reasoning-v1-{first.invocation_id}")

    assert first.to_dict() == second.to_dict()
    assert model.calls == 1
    assert [entry.cache_reused for entry in graph.telemetry] == [False, True]
    assert "cache_reused" not in first.to_json()
    assert "latency_ms" not in first.to_json()
    assert checkpoint is not None
    assert "TRANSIENT_DO_NOT_CHECKPOINT" not in checkpoint.decode("utf-8")
    assert "transient_evidence" not in checkpoint.decode("utf-8")
    assert "proposed_tools" in first.to_dict()["hypothesis"]


def test_graph_async_path_and_identity_invalidation(tmp_path: Path) -> None:
    model = FakeChatModel(response=_valid_response())
    graph = ReasoningGraph(
        ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:async"), model),
        ArtifactStore(tmp_path / "store"),
    )

    first = asyncio.run(graph.arun(_request()))
    changed = asyncio.run(graph.arun(_request(invocation_id="another-receipt")))

    assert first.status == changed.status == "success"
    assert first.invocation_id != changed.invocation_id
    assert model.calls == 2


def test_cached_checkpoint_decode_failure_reinvokes_and_stays_structured(tmp_path: Path) -> None:
    model = FakeChatModel(response=_valid_response())
    graph = ReasoningGraph(
        ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:decode"), model),
        ArtifactStore(tmp_path / "store"),
    )
    request = _request()
    invocation_id = graph.runtime.invocation_id(request)
    graph.store.put_view(f"sunset-reasoning-v1-{invocation_id}", b"not-json")

    result = graph.run(request)

    assert result.status == "error"
    assert result.hypothesis is not None
    assert result.errors[-1].kind == "view_conflict"
    assert model.calls == 1
