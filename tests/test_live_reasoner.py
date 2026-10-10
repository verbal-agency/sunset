"""G30 — live agent reasoner (offline, with a stub model)."""

from __future__ import annotations

import json
from pathlib import Path

from sunset.agent_tool_models import ToolBudget, ToolEffect, ToolReceipt
from sunset.escalation_loop import approval_set, run_escalation_case
from sunset.live_reasoner import (
    LiveAgentReasoner,
    ModelRuntimeReasoner,
    build_prompt,
    parse_status,
    recorded_evidence,
)
from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig
from sunset.model_runtime_models import ReasoningRequest
from sunset.provenance_models import ArtifactRef


ARTIFACT_ID = "sha256:" + "a" * 64


def _request() -> ReasoningRequest:
    return ReasoningRequest(
        receipts=(
            ToolReceipt(
                tool_name="sunset_get_candidate_provenance",
                invocation_id="receipt-c1",
                repository_identity_kind="local_path_sha256",
                repository_identity_value="sha256:repository",
                repository_head="abcdef",
                status="success",
                result={"candidate_id": "c1"},
                evidence=(
                    ArtifactRef(
                        artifact_id=ARTIFACT_ID,
                        byte_length=10,
                        digest="a" * 64,
                        media_type="text/plain",
                        source_kind="marker_source",
                        source_locator="fixture:c1",
                    ),
                ),
                errors=(),
                uncertainties=(),
                effect=ToolEffect(),
                budget=ToolBudget(0, 100, 4),
            ),
        ),
        task="Determine whether the protected condition remains active.",
    )


class _StubModel:
    """Duck-typed chat model: records prompts, returns a canned response."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return type("Resp", (), {"content": self.reply})()


class _ExplodingModel:
    def invoke(self, prompt: str):
        raise RuntimeError("transport failure")


def test_parse_status_prefers_status_line() -> None:
    assert parse_status("reasoning...\nSTATUS: likely_expired") == "likely_expired"
    assert parse_status("STATUS: likely_active") == "likely_active"


def test_parse_status_single_mention() -> None:
    assert parse_status("this looks contradictory to me") == "contradictory"


def test_parse_status_ambiguous_or_absent_is_unknown() -> None:
    assert parse_status("could be likely_active or likely_expired") == "unknown"
    assert parse_status("no verdict here") == "unknown"


def test_reasoner_returns_parsed_status_and_calls_once() -> None:
    model = _StubModel("The upstream bug is fixed.\nSTATUS: likely_expired")
    reasoner = LiveAgentReasoner(model, recorded_evidence({"c1": "xfail: upstream issue #417"}))
    assert reasoner("c1") == "likely_expired"
    assert len(model.prompts) == 1
    assert "EVIDENCE:" in model.prompts[0]
    assert "issue #417" in model.prompts[0]


def test_reasoner_truncates_evidence() -> None:
    model = _StubModel("STATUS: unknown")
    reasoner = LiveAgentReasoner(model, recorded_evidence({"c1": "x" * 10_000}), max_evidence_chars=100)
    reasoner("c1")
    # evidence is truncated to exactly 100 chars (not 101)
    assert "x" * 100 in model.prompts[0]
    assert "x" * 101 not in model.prompts[0]


def test_reasoner_fails_safe_to_unknown_on_model_error() -> None:
    reasoner = LiveAgentReasoner(_ExplodingModel(), recorded_evidence({"c1": "evidence"}))
    assert reasoner("c1") == "unknown"


def test_build_prompt_is_conservative() -> None:
    prompt = build_prompt("some evidence")
    assert "never decide to remove code" in prompt
    assert "prefer unknown over guessing" in prompt


def test_model_runtime_reasoner_uses_receipts_and_preserves_result(tmp_path: Path) -> None:
    fixture = tmp_path / "expired.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "response": {
                    "assumption_status": "expired",
                    "summary": "The protected condition is no longer present.",
                    "claims": [],
                    "open_questions": [],
                    "proposed_tools": [],
                },
                "usage": {"input_tokens": 10, "output_tokens": 8},
            }
        ),
        encoding="utf-8",
    )
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture)))
    reasoner = ModelRuntimeReasoner(runtime, lambda case_id: _request() if case_id == "c1" else ReasoningRequest(receipts=()))

    assert reasoner("c1") == "likely_expired"
    assert reasoner.results["c1"].status == "success"
    assert reasoner.results["c1"].input_receipt_ids == ("receipt-c1",)

    loop_result = run_escalation_case(
        "c1",
        "likely_active",
        reasoner("c1"),
        validator=lambda _case_id: "confirmed",
        approve=approval_set({"c1"}),
    )
    assert loop_result.validation_outcome == "confirmed"
    assert loop_result.empirical_status == "likely_expired"


def test_model_runtime_reasoner_maps_runtime_failure_to_unknown(tmp_path: Path) -> None:
    fixture = tmp_path / "invalid.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "response": {"assumption_status": "not-a-status"},
            }
        ),
        encoding="utf-8",
    )
    runtime = ModelRuntime(ModelRuntimeConfig(mode="recorded", recorded_fixture_path=str(fixture)))
    reasoner = ModelRuntimeReasoner(runtime, lambda _case_id: _request())

    assert reasoner("c1") == "unknown"
    assert reasoner.results["c1"].status == "inconclusive"
