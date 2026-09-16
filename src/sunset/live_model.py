"""Explicit application-boundary factory for a live chat model.

This is glue at the trusted entry point, **not** part of the credential-agnostic
core. It reads an API key only from an explicitly named environment variable and
constructs a LangChain ``BaseChatModel`` for injection into the G11 model runtime.

Nothing in the default or test path imports this module or a provider package.
The core (`model_runtime`, `escalation_loop`) never discovers a credential; a
caller must explicitly build a model here and inject it. Provider packages are the
optional ``live`` extra (`uv sync --extra live`).
"""

from __future__ import annotations

import importlib
import importlib.util
import os
from typing import Any

# provider -> (module, class, default api-key env var)
_PROVIDERS: dict[str, tuple[str, str, str]] = {
    "anthropic": ("langchain_anthropic", "ChatAnthropic", "ANTHROPIC_API_KEY"),
    "openai": ("langchain_openai", "ChatOpenAI", "OPENAI_API_KEY"),
}


class LiveModelError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_env_file(path: str | os.PathLike[str] = ".env", *, override: bool = False) -> tuple[str, ...]:
    """Load KEY=VALUE lines from a .env file into os.environ (explicit boundary).

    Dependency-free. Existing environment values win unless ``override``. Returns
    the names of the keys it set (never their values). No-op if the file is absent.
    """

    file_path = os.fspath(path)
    if not os.path.exists(file_path):
        return ()
    set_names: list[str] = []
    with open(file_path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if not name or not value:
                continue
            if override or name not in os.environ:
                os.environ[name] = value
                set_names.append(name)
    return tuple(set_names)


def supported_providers() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


def build_chat_model(
    provider: str,
    model: str,
    *,
    api_key_env: str | None = None,
    **model_kwargs: Any,
) -> Any:
    """Construct a live chat model for injection. Never called by default/test paths.

    Fails closed with a structured error for an unsupported provider, an absent
    credential (checked before any import), or a missing provider package. The API
    key value is read from the named env var and passed straight to the client; it
    is never logged, stored, or returned.
    """

    if provider not in _PROVIDERS:
        raise LiveModelError("provider_unsupported", f"provider must be one of {supported_providers()}")
    if not model:
        raise LiveModelError("model_required", "an explicit model identifier is required")

    module_name, class_name, default_env = _PROVIDERS[provider]
    key_env = api_key_env or default_env
    api_key = os.environ.get(key_env)
    if not api_key:
        raise LiveModelError("credential_absent", f"set {key_env} (host-supplied); no credential is auto-discovered")

    if importlib.util.find_spec(module_name) is None:
        dist = module_name.replace("_", "-")
        raise LiveModelError("provider_not_installed", f"install the 'live' extra: uv sync --extra live ({dist})")

    module = importlib.import_module(module_name)
    chat_class = getattr(module, class_name)
    return chat_class(model=model, api_key=api_key, **model_kwargs)


__all__ = ["LiveModelError", "build_chat_model", "load_env_file", "supported_providers"]
