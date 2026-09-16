"""G30 — live-model injection factory (offline; error paths need no provider package)."""

from __future__ import annotations

import importlib.util

import pytest

from sunset.live_model import LiveModelError, build_chat_model, supported_providers


def test_supported_providers() -> None:
    assert set(supported_providers()) == {"anthropic", "openai"}


def test_unsupported_provider_fails_before_reading_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-be-read")
    with pytest.raises(LiveModelError) as exc:
        build_chat_model("bogus", "some-model")
    assert exc.value.code == "provider_unsupported"


def test_model_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with pytest.raises(LiveModelError) as exc:
        build_chat_model("anthropic", "")
    assert exc.value.code == "model_required"


def test_credential_absent_before_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LiveModelError) as exc:
        build_chat_model("anthropic", "claude-model")
    assert exc.value.code == "credential_absent"


def test_custom_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LiveModelError) as exc:
        build_chat_model("openai", "gpt-model", api_key_env="MY_KEY")
    # names the custom env var, and does not fall back to auto-discovery
    assert exc.value.code == "credential_absent"
    assert "MY_KEY" in exc.value.message


@pytest.mark.skipif(
    importlib.util.find_spec("langchain_anthropic") is not None,
    reason="provider package installed; missing-package path not exercised",
)
def test_missing_provider_package_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with pytest.raises(LiveModelError) as exc:
        build_chat_model("anthropic", "claude-model")
    assert exc.value.code == "provider_not_installed"
    assert "uv sync --extra live" in exc.value.message
