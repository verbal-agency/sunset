"""G30 — live agent reasoner (offline, with a stub model)."""

from __future__ import annotations

from sunset.live_reasoner import (
    LiveAgentReasoner,
    build_prompt,
    parse_status,
    recorded_evidence,
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
