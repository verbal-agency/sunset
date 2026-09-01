from __future__ import annotations

import asyncio
from pathlib import Path
import socket
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr
import pytest

import sunset.agent_tools as agent_tools
from sunset.agent_tool_models import ToolBudget, ToolEffect, ToolReceipt
from sunset.agent_tools import PROVENANCE_TOOL, ToolExecutionContext, create_tool_registry
from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig, assemble_prompt
from sunset.model_runtime_models import ReasoningRequest, TransientEvidence
from sunset.provenance_models import ArtifactRef
from sunset.scanner import scan_repository

from conftest import repository_snapshot


FIXTURE = Path(__file__).parent / "fixtures" / "model_runtime" / "valid-v1.json"
ARTIFACT_ID = "sha256:" + "a" * 64


def _receipt(*, invocation_id: str = "tool-receipt-v1", raw_result: bool = False) -> ToolReceipt:
    return ToolReceipt(
        tool_name="sunset_get_candidate_provenance",
        invocation_id=invocation_id,
        repository_identity_kind="local_path_sha256",
        repository_identity_value="sha256:repository",
        repository_head="abcdef",
        status="success",
        result={
            "candidate": {"candidate_id": "candidate-v1", "path": "tests/test_feature.py"},
            **({"raw": "TOP_SECRET_SOURCE", "history": "TOP_SECRET_HISTORY"} if raw_result else {}),
        },
        evidence=(
            ArtifactRef(
                artifact_id=ARTIFACT_ID,
                byte_length=42,
                digest="a" * 64,
                media_type="text/plain",
                source_kind="marker_source",
                source_locator="/private/secret/artifact-store-path",
            ),
        ),
        errors=(),
        uncertainties=(),
        effect=ToolEffect(),
        budget=ToolBudget(0, 100, 4),
    )


def _request(**kwargs: Any) -> ReasoningRequest:
    return ReasoningRequest(receipts=(_receipt(**kwargs),))


class FakeChatModel(BaseChatModel):
    response: str
    fake_name: str = "fake"
    _calls: int = PrivateAttr(default=0)

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def _llm_type(self) -> str:
        return self.fake_name

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._calls += 1
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=self.response,
                        usage_metadata={"input_tokens": 20, "output_tokens": 15, "total_tokens": 35},
                    )
                )
            ]
        )


class ThrowingChatModel(FakeChatModel):
    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        self._calls += 1
        raise TimeoutError("simulated timeout")


class CancelledChatModel(FakeChatModel):
    async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
        self._calls += 1
        raise asyncio.CancelledError


class NoUsageChatModel(FakeChatModel):
    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        self._calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])


class SlowChatModel(FakeChatModel):
    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        self._calls += 1
        time.sleep(0.02)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])


def _valid_response() -> str:
    return FIXTURE.read_text(encoding="utf-8").split('"response": ', 1)[1].rsplit(',\n  "schema_version"', 1)[0]


def test_explicit_disabled_and_recorded_modes_do_not_open_sockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("default model modes must not contact a network")

    monkeypatch.setattr(socket, "socket", no_socket)
    disabled = ModelRuntime(ModelRuntimeConfig(mode="disabled"))
    recorded = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE)))

    disabled_result = disabled.run(_request())
    recorded_result = recorded.run(_request())

    assert disabled_result.status == "disabled"
    assert disabled_result.errors[0].kind == "model_disabled"
    assert recorded_result.status == "success"
    assert recorded_result.hypothesis is not None
    assert recorded_result.usage.estimated is False


def test_model_proposals_never_dispatch_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_tools,
        "create_tool_registry",
        lambda *args, **kwargs: pytest.fail("G11 must not create or dispatch a tool registry"),
    )
    result = ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE))
    ).run(_request())

    assert result.status == "success"
    assert result.hypothesis is not None
    assert result.hypothesis.proposed_tools == ("sunset_read_evidence_excerpt",)


def test_recorded_replay_is_byte_identical_and_accepts_a_real_g10_receipt(
    renamed_repository: Path,
    tmp_path: Path,
) -> None:
    before = repository_snapshot(renamed_repository)
    context = ToolExecutionContext.create(renamed_repository, store_path=tmp_path / "store")
    candidate_id = scan_repository(renamed_repository).candidates[0].candidate_id
    receipt = ToolReceipt.from_dict(
        create_tool_registry(context).by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})["receipt"]
    )
    fixture = tmp_path / "real-receipt.json"
    fixture.write_text(
        json_text(
            {
                "schema_version": "1",
                "response": {"assumption_status": "unknown", "summary": "Local evidence is incomplete.", "claims": [], "open_questions": ["What external condition applies?"], "proposed_tools": []},
                "usage": {"input_tokens": 12, "output_tokens": 8},
            }
        ),
        encoding="utf-8",
    )
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture)))
    request = ReasoningRequest(receipts=(receipt,))

    first = runtime.run(request)
    second = runtime.run(request)

    assert first.status == "success"
    assert first.to_json() == second.to_json()
    assert repository_snapshot(renamed_repository) == before


def test_two_injected_base_chat_models_preserve_one_domain_contract() -> None:
    first = FakeChatModel(response=_valid_response(), fake_name="first")
    second = FakeChatModel(response=_valid_response(), fake_name="second")
    first_runtime = ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:first"), first)
    second_runtime = ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:second"), second)

    first_result = first_runtime.run(_request())
    second_result = second_runtime.run(_request())

    assert first_result.status == second_result.status == "success"
    assert first_result.hypothesis == second_result.hypothesis
    assert first_result.provider_identity == "fake:first"
    assert second_result.provider_identity == "fake:second"
    assert first.calls == second.calls == 1
    assert "AIMessage" not in first_result.to_json()


def test_recorded_output_validation_contains_bad_citations_tools_and_shapes(tmp_path: Path) -> None:
    cases = [
        {"response": {"assumption_status": "unknown", "summary": "x", "claims": [{"kind": "supporting", "summary": "x", "citations": ["sha256:" + "b" * 64]}], "open_questions": [], "proposed_tools": []}},
        {"response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": ["rm_everything"]}},
        {"response": {"assumption_status": "unsafe", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": []}},
        {"response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": [], "extra": "no"}},
        {"response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": ["x" * 1_201], "proposed_tools": []}},
    ]
    for index, value in enumerate(cases):
        fixture = tmp_path / f"invalid-{index}.json"
        fixture.write_text(json_text({"schema_version": "1", **value}), encoding="utf-8")
        runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture)))
        result = runtime.run(_request())
        assert result.status == "inconclusive"
        assert result.hypothesis is None
        assert result.errors[0].kind == "model_output_invalid"


def test_prompt_is_compact_and_transient_is_never_persisted() -> None:
    request = _request(raw_result=True)
    prompt = assemble_prompt(
        request,
        transient_evidence=(TransientEvidence(ARTIFACT_ID, "ALLOWED_TRANSIENT_EXCERPT"),),
    )

    assert "ALLOWED_TRANSIENT_EXCERPT" in prompt
    assert "TOP_SECRET_SOURCE" not in prompt
    assert "TOP_SECRET_HISTORY" not in prompt
    assert "/private/secret/artifact-store-path" not in prompt
    assert "source_locator" not in prompt


def test_transient_scope_and_prompt_budget_are_enforced() -> None:
    with pytest.raises(ValueError, match="not granted"):
        assemble_prompt(_request(), transient_evidence=(TransientEvidence("sha256:" + "b" * 64, "no"),))
    with pytest.raises(ValueError, match="exceeds"):
        assemble_prompt(_request(), transient_evidence=(TransientEvidence(ARTIFACT_ID, "x" * 9_000),))
    runtime = ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE), max_input_tokens=1)
    )
    result = runtime.run(_request())
    assert result.status == "budget_exhausted"
    assert result.errors[0].kind == "input_token_budget_exhausted"
    malformed = ModelRuntime(ModelRuntimeConfig(mode="disabled")).run(
        _request(), transient_evidence=(TransientEvidence(ARTIFACT_ID, 3),)  # type: ignore[arg-type]
    )
    assert malformed.status == "error"
    assert malformed.errors[0].kind == "prompt_input_invalid"


def test_live_mode_requires_explicit_injected_model() -> None:
    with pytest.raises(ValueError, match="injected"):
        ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="provider:model"))
    with pytest.raises(ValueError, match="unsupported"):
        ModelRuntimeConfig(mode="implicit")  # type: ignore[arg-type]


def test_recorded_identity_changes_with_receipt_model_config_and_transient() -> None:
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE)))
    request = _request()
    base = runtime.invocation_id(request)

    assert runtime.invocation_id(request) == base
    assert runtime.invocation_id(_request(invocation_id="changed-receipt")) != base
    assert runtime.invocation_id(request, (TransientEvidence(ARTIFACT_ID, "different"),)) != base
    assert ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE), prompt_version="next")
    ).invocation_id(request) != base
    assert ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE), max_output_tokens=999)
    ).invocation_id(request) != base
    assert ModelRuntime(
        ModelRuntimeConfig(mode="recorded", model_identity="different-recorded-label", recorded_fixture_path=str(FIXTURE))
    ).invocation_id(request) != base
    assert ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(FIXTURE), output_schema_version="next")
    ).invocation_id(request) != base


def test_malformed_missing_and_throwing_providers_are_structured_sync_and_async(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{bad", encoding="utf-8")
    malformed_runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(malformed)))
    missing_runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(tmp_path / "missing.json")))
    throwing = ThrowingChatModel(response="{}")
    live_runtime = ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:throw"), throwing)
    cancelled = CancelledChatModel(response="{}")
    cancelled_runtime = ModelRuntime(ModelRuntimeConfig(mode="live", model_identity="fake:cancelled"), cancelled)

    malformed_result = malformed_runtime.run(_request())
    missing_result = missing_runtime.run(_request())
    async_result = asyncio.run(live_runtime.arun(_request()))
    cancelled_result = asyncio.run(cancelled_runtime.arun(_request()))

    assert malformed_result.status == "error"
    assert malformed_result.errors[0].kind == "recorded_response_invalid"
    assert missing_result.status == "error"
    assert missing_result.errors[0].kind == "recorded_fixture_unavailable"
    assert async_result.status == "error"
    assert async_result.errors[0].kind == "model_timeout"
    assert cancelled_result.status == "error"
    assert cancelled_result.errors[0].kind in {"model_cancelled", "model_provider_failed"}


def test_usage_limit_and_cost_unavailability_are_explicit(tmp_path: Path) -> None:
    fixture = tmp_path / "over-budget.json"
    fixture.write_text(
        json_text(
            {
                "schema_version": "1",
                "response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": []},
                "usage": {"input_tokens": 2, "output_tokens": 99},
            }
        ),
        encoding="utf-8",
    )
    result = ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture), max_output_tokens=10)
    ).run(_request())

    assert result.status == "budget_exhausted"
    assert result.usage.cost_usd is None
    assert result.usage.estimated is False


def test_provider_cost_budget_is_enforced(tmp_path: Path) -> None:
    fixture = tmp_path / "cost-budget.json"
    fixture.write_text(
        json_text(
            {
                "schema_version": "1",
                "response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": []},
                "usage": {"input_tokens": 2, "output_tokens": 3, "cost_usd": 1.25},
            }
        ),
        encoding="utf-8",
    )
    result = ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture), max_cost_usd=1.0)
    ).run(_request())

    assert result.status == "budget_exhausted"
    assert result.errors[0].kind == "model_cost_budget_exhausted"
    assert result.usage.cost_usd == 1.25


def test_invalid_provider_usage_is_contained(tmp_path: Path) -> None:
    fixture = tmp_path / "invalid-usage.json"
    fixture.write_text(
        json_text(
            {
                "schema_version": "1",
                "response": {"assumption_status": "unknown", "summary": "x", "claims": [], "open_questions": [], "proposed_tools": []},
                "usage": {"input_tokens": "not-a-number", "output_tokens": 3},
            }
        ),
        encoding="utf-8",
    )
    result = ModelRuntime(
        ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture))
    ).run(_request())

    assert result.status == "inconclusive"
    assert result.errors[0].kind == "provider_usage_invalid"


def test_missing_provider_usage_uses_a_labeled_estimate() -> None:
    model = NoUsageChatModel(response=_valid_response())
    result = ModelRuntime(
        ModelRuntimeConfig(mode="live", model_identity="fake:no-usage"), model
    ).run(_request())

    assert result.status == "success"
    assert result.usage.estimated is True
    assert result.usage.cost_usd is None


def test_configured_live_timeout_is_contained() -> None:
    model = SlowChatModel(response=_valid_response())
    result = ModelRuntime(
        ModelRuntimeConfig(mode="live", model_identity="fake:slow", timeout_seconds=0.001), model
    ).run(_request())

    assert result.status == "error"
    assert result.errors[0].kind == "model_timeout"


def json_text(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
