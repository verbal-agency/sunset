"""Recorded-first, explicitly credentialed external-evidence agent tools."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from sunset.agent_tool_models import ToolBudget, ToolEffect, ToolFailure, ToolObservation, ToolReceipt
from sunset.agent_tools import BoundToolRegistry, ToolExecutionContext
from sunset.artifact_store import ArtifactStore
from sunset.external_evidence import extract_external_references
from sunset.external_evidence_models import ExternalReference


RESOLVE_EXTERNAL_REFERENCE_TOOL = "sunset_resolve_external_reference"
EXTERNAL_TOOL_NAMES = (RESOLVE_EXTERNAL_REFERENCE_TOOL,)
EXTERNAL_READ_RECORDED_EFFECT = ToolEffect(effect_class="external_read", network_access=False)
EXTERNAL_READ_LIVE_EFFECT = ToolEffect(effect_class="external_read", network_access=True)


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResolveExternalReferenceInput(_StrictInput):
    reference_id: str = Field(pattern=r"^external-ref-v1-[0-9a-f]{20}$")


@dataclass(frozen=True, slots=True)
class ExternalProviderResponse:
    outcome: Literal["supports_active", "supports_expired", "missing", "failed"]
    summary: str
    source_locator: str
    raw: bytes | None = None
    error_kind: str | None = None


class ExternalEvidenceProvider(Protocol):
    name: str

    def resolve(self, reference: ExternalReference, *, max_response_bytes: int) -> ExternalProviderResponse: ...


class RecordedExternalEvidenceProvider:
    """Deterministic fixture provider; it never opens a socket."""

    name = "recorded"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser().resolve()
        try:
            value = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            records = value["responses"]
            if not isinstance(records, list):
                raise ValueError("fixture responses must be a list")
            self._records = {(str(item["provider"]), str(item["locator"])): item for item in records if isinstance(item, dict)}
            self._error: str | None = None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._records = {}
            self._error = str(exc)

    def resolve(self, reference: ExternalReference, *, max_response_bytes: int) -> ExternalProviderResponse:
        if self._error is not None:
            return ExternalProviderResponse("failed", "Recorded provider fixture is unavailable.", str(self.fixture_path), error_kind="recorded_fixture_unavailable")
        item = self._records.get((reference.provider, reference.locator))
        if item is None:
            return ExternalProviderResponse("missing", "No recorded response exists for this explicit reference.", reference.locator)
        outcome = str(item.get("outcome", "failed"))
        if outcome not in {"supports_active", "supports_expired"}:
            return ExternalProviderResponse(
                "missing" if outcome == "missing" else "failed",
                str(item.get("summary", "Recorded provider response was unavailable.")), reference.locator,
                error_kind=str(item.get("error_kind")) if item.get("error_kind") else None,
            )
        raw = _canonical(item)
        if len(raw) > max_response_bytes:
            return ExternalProviderResponse("failed", "Recorded response exceeds the configured byte budget.", reference.locator, error_kind="response_too_large")
        return ExternalProviderResponse(outcome, str(item.get("summary", "Recorded evidence was returned.")), reference.locator, raw=raw)


class ExplicitGitHubProvider:
    """A live adapter that accepts a supplied token and never reads environment state."""

    name = "github-live-explicit"

    def __init__(self, token: str, opener: Callable[..., Any] = urlopen) -> None:
        if not token:
            raise ValueError("live GitHub provider requires a supplied credential")
        self._token = token
        self._opener = opener

    def resolve(self, reference: ExternalReference, *, max_response_bytes: int) -> ExternalProviderResponse:
        api_url = _github_api_url(reference)
        if api_url is None:
            return ExternalProviderResponse("failed", "Reference is not a supported GitHub issue or pull request.", reference.locator, error_kind="unsupported_reference")
        try:
            request = Request(api_url, headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self._token}"})
            with self._opener(request, timeout=10) as response:  # noqa: S310 - explicit opt-in adapter
                raw = response.read(max_response_bytes + 1)
        except (HTTPError, URLError, OSError) as exc:
            return ExternalProviderResponse("failed", "Live GitHub lookup failed; no expiry conclusion was made.", reference.locator, error_kind=type(exc).__name__.lower())
        if len(raw) > max_response_bytes:
            return ExternalProviderResponse("failed", "Live response exceeds the configured byte budget.", reference.locator, error_kind="response_too_large")
        try:
            state = str(json.loads(raw).get("state", ""))
        except json.JSONDecodeError:
            return ExternalProviderResponse("failed", "Live GitHub returned malformed JSON.", reference.locator, error_kind="malformed_response")
        if state not in {"open", "closed"}:
            return ExternalProviderResponse("failed", "Live GitHub response did not contain a usable state.", reference.locator, error_kind="malformed_response")
        return ExternalProviderResponse("supports_active" if state == "open" else "supports_expired", f"Live GitHub reports the reference as {state}.", reference.locator, raw=raw)


@dataclass(slots=True)
class ExternalEvidenceContext:
    """Trusted provider authority layered beside, never inside, G10 context."""

    local: ToolExecutionContext
    references: dict[str, ExternalReference]
    provider: ExternalEvidenceProvider
    mode: Literal["recorded", "live"]
    allowed_hosts: tuple[str, ...]
    max_requests: int = 6
    max_response_bytes: int = 32_768
    min_request_interval_seconds: float = 0.0
    freshness_key: str = "recorded-v1"
    credential_identity: str | None = None
    clock: Callable[[], float] = time.monotonic
    requests_used: int = 0
    response_bytes_used: int = 0
    _last_request_at: float | None = field(default=None, repr=False)

    @classmethod
    def from_receipts(
        cls, local: ToolExecutionContext, receipts: tuple[ToolReceipt, ...], *, provider: ExternalEvidenceProvider,
        mode: Literal["recorded", "live"], allowed_hosts: tuple[str, ...], credential_identity: str | None = None,
        **kwargs: Any,
    ) -> ExternalEvidenceContext:
        texts: list[str] = []
        for receipt in receipts:
            for reference in receipt.evidence:
                try:
                    texts.append(local.store.read(reference).decode("utf-8", errors="replace"))
                except OSError:
                    continue
        refs = extract_external_references(tuple(texts))
        return cls(local, {item.reference_id: item for item in refs}, provider, mode, tuple(sorted(set(allowed_hosts))), credential_identity=credential_identity, **kwargs)

    def __post_init__(self) -> None:
        if self.max_requests < 1 or self.max_response_bytes < 1 or self.min_request_interval_seconds < 0:
            raise ValueError("external request, byte, and interval limits must be valid")
        if self.mode == "live" and not self.credential_identity:
            raise ValueError("live external context requires an explicit credential identity")
        if any(urlparse(reference.locator).hostname not in self.allowed_hosts for reference in self.references.values()):
            raise ValueError("all external references must be in the explicit host allowlist")

    @property
    def effect(self) -> ToolEffect:
        return EXTERNAL_READ_LIVE_EFFECT if self.mode == "live" else EXTERNAL_READ_RECORDED_EFFECT

    @property
    def requests_remaining(self) -> int:
        return max(0, self.max_requests - self.requests_used)

    @property
    def response_bytes_remaining(self) -> int:
        return max(0, self.max_response_bytes - self.response_bytes_used)

    def policy_fingerprint(self) -> str:
        credential_digest = hashlib.sha256((self.credential_identity or "").encode()).hexdigest() if self.credential_identity else None
        return hashlib.sha256(_canonical({"allowed_hosts": self.allowed_hosts, "credential_identity_digest": credential_digest, "freshness_key": self.freshness_key, "max_requests": self.max_requests, "max_response_bytes": self.max_response_bytes, "min_request_interval_seconds": self.min_request_interval_seconds, "mode": self.mode, "provider": self.provider.name, "references": sorted(self.references), "schema": "1"})).hexdigest()

    def invoke(self, reference_id: str) -> ToolObservation:
        reference = self.references.get(reference_id)
        invocation_id = hashlib.sha256(_canonical({"head": self.local.repository.head, "policy": self.policy_fingerprint(), "reference": reference_id, "used": [self.requests_used, self.response_bytes_used]})).hexdigest()
        if reference is None:
            return self._failure(reference_id, invocation_id, "unknown_reference", "reference is outside the extracted grant")
        if self.requests_remaining == 0 or self.response_bytes_remaining == 0:
            return self._failure(reference_id, invocation_id, "external_budget_exhausted", "external request or byte budget is exhausted", status="budget_exhausted", consume=False)
        now = self.clock()
        if self._last_request_at is not None and now - self._last_request_at < self.min_request_interval_seconds:
            return self._failure(reference_id, invocation_id, "rate_limited", "external request is rate limited by policy", consume=False)
        self.requests_used += 1
        self._last_request_at = now
        response = self.provider.resolve(reference, max_response_bytes=self.response_bytes_remaining)
        artifact = None
        debit = 0
        if response.raw is not None:
            debit = len(response.raw)
            if debit > self.response_bytes_remaining:
                return self._failure(reference_id, invocation_id, "response_too_large", "provider response exceeds remaining byte budget", consume=False)
            artifact = self.local.store.put(response.raw, media_type="application/json", source_kind=f"external_{reference.provider}_response", source_locator=response.source_locator)
            self.response_bytes_used += debit
        receipt = self._receipt(reference_id, invocation_id, response, artifact, debit)
        return ToolObservation(receipt=receipt)

    def _failure(self, reference_id: str, invocation_id: str, kind: str, message: str, *, status: Literal["error", "budget_exhausted"] = "error", consume: bool = True) -> ToolObservation:
        if consume and self.requests_remaining:
            self.requests_used += 1
        response = ExternalProviderResponse("failed", message, self.references.get(reference_id, ExternalReference("github", "https://github.com/invalid/invalid/issues/0")).locator, error_kind=kind)
        return ToolObservation(receipt=self._receipt(reference_id, invocation_id, response, None, 0, status=status))

    def _receipt(self, reference_id: str, invocation_id: str, response: ExternalProviderResponse, artifact: Any, debit: int, *, status: Literal["success", "error", "budget_exhausted"] = "success") -> ToolReceipt:
        kind, value = self.local.repository_identity
        reference = self.references.get(reference_id)
        return ToolReceipt(
            tool_name=RESOLVE_EXTERNAL_REFERENCE_TOOL, invocation_id=invocation_id,
            repository_identity_kind=kind, repository_identity_value=value, repository_head=self.local.repository.head,
            status=status, result={"outcome": response.outcome, "reference": reference.to_dict() if reference else {"reference_id": reference_id}, "summary": response.summary, "source_locator": response.source_locator, "error_kind": response.error_kind, "freshness_key": self.freshness_key, "provider": self.provider.name},
            evidence=(artifact,) if artifact is not None else (),
            errors=(ToolFailure(response.error_kind, response.summary),) if response.error_kind else (), uncertainties=(), effect=self.effect,
            budget=ToolBudget(evidence_bytes_debit=debit, evidence_bytes_remaining=self.response_bytes_remaining, tool_calls_remaining=self.requests_remaining),
        )


class _ExternalTool(BaseTool):
    _context: ExternalEvidenceContext = PrivateAttr()

    def __init__(self, *, context: ExternalEvidenceContext, **data: Any) -> None:
        super().__init__(**data); self._context = context

    def _run(self, **kwargs: Any) -> dict[str, Any]:
        return self._context.invoke(str(kwargs["reference_id"])).to_dict()

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        try:
            normalized = self.args_schema.model_validate(input).model_dump()  # type: ignore[union-attr]
        except (ValidationError, TypeError, ValueError) as exc:
            return self._context._failure("", "invalid", "input_validation_error", str(exc)).to_dict()
        return super().invoke(normalized, config=config, **kwargs)


def create_external_tool_registry(context: ExternalEvidenceContext) -> BoundToolRegistry:
    return BoundToolRegistry((_ExternalTool(
        context=context, name=RESOLVE_EXTERNAL_REFERENCE_TOOL,
        description="Resolve one pre-extracted, candidate-linked external reference through the bound provider.",
        args_schema=ResolveExternalReferenceInput,
        metadata={"sunset_contract_schema_version": "1", "sunset_effect": context.effect.to_dict()},
    ),))


def _github_api_url(reference: ExternalReference) -> str | None:
    if reference.provider != "github" or not reference.locator.startswith("https://github.com/"):
        return None
    parts = reference.locator.removeprefix("https://github.com/").rstrip("/").split("/")
    if len(parts) != 4 or parts[2] not in {"issues", "pull"} or not parts[3].isdigit():
        return None
    return f"https://api.github.com/repos/{parts[0]}/{parts[1]}/issues/{parts[3]}"


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
