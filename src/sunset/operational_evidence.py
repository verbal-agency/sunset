"""Recorded-first operational evidence with explicit privacy and live gates."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sunset.artifact_store import ArtifactStore
from sunset.claim_evidence_models import EvidenceEdge
from sunset.operational_evidence_models import (
    FreshnessMetadata, OPERATIONAL_EVIDENCE_SCHEMA_VERSION, OPERATIONAL_SOURCES,
    OperationalEvidenceReceipt, OperationalQuery, PrivacyPolicy,
)


class OperationalProviderResponse(Protocol):
    outcome: str
    summary: str
    source_identity: str
    raw: bytes | None
    freshness: FreshnessMetadata | None
    error_kind: str | None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    outcome: str
    summary: str
    source_identity: str
    raw: bytes | None = None
    freshness: FreshnessMetadata | None = None
    error_kind: str | None = None


class RecordedOperationalProvider:
    """Fixture-backed provider that never reads credentials or opens sockets."""

    name = "recorded"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser().resolve()
        try:
            payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            records = payload["responses"]
            if not isinstance(records, list):
                raise ValueError("responses must be a list")
            self._records = {(str(item["source"]), str(item["locator"])): item for item in records if isinstance(item, dict)}
            self._error = None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._records = {}
            self._error = str(exc)

    def resolve(self, query: OperationalQuery, *, max_bytes: int) -> ProviderResponse:
        if self._error:
            return ProviderResponse("unknown", "Recorded operational fixture is unavailable.", str(self.fixture_path), error_kind="recorded_fixture_unavailable")
        item = self._records.get((query.source, query.locator))
        if item is None:
            return ProviderResponse("unknown", "No recorded operational response exists for this query.", query.locator, error_kind="evidence_missing")
        raw = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() if item.get("payload") is not None else None
        if raw is not None and len(raw) > max_bytes:
            return ProviderResponse("unknown", "Recorded operational response exceeds the byte budget.", query.locator, error_kind="response_too_large")
        freshness = _freshness(item)
        return ProviderResponse(str(item.get("outcome", "unknown")), str(item.get("summary", "Recorded operational evidence.")), str(item.get("source_identity", query.locator)), raw, freshness, str(item["error_kind"]) if item.get("error_kind") else None)


class ExplicitLiveOperationalProvider:
    """Injected opener boundary; it never discovers ambient credentials."""

    name = "live-explicit"

    def __init__(self, credential: str, opener: Callable[..., Any] = urlopen) -> None:
        if not credential:
            raise ValueError("live provider requires an explicit credential")
        self.credential = credential
        self.opener = opener

    def resolve(self, query: OperationalQuery, *, max_bytes: int) -> ProviderResponse:
        try:
            request = Request(query.locator, headers={"Authorization": f"Bearer {self.credential}", "Accept": "application/json"})
            with self.opener(request, timeout=query.wall_time_budget_ms / 1000) as response:
                raw = response.read(max_bytes + 1)
        except Exception as exc:  # provider boundary turns all transport failures into evidence
            return ProviderResponse("unknown", "Live operational lookup failed.", query.locator, error_kind=type(exc).__name__.lower())
        if len(raw) > max_bytes:
            return ProviderResponse("unknown", "Live response exceeds the byte budget.", query.locator, error_kind="response_too_large")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ProviderResponse("unknown", "Live response was malformed JSON.", query.locator, raw=raw, error_kind="malformed_response")
        return ProviderResponse(str(payload.get("outcome", "unknown")), str(payload.get("summary", "Live operational evidence.")), query.locator, raw, _freshness(payload), payload.get("error_kind"))


@dataclass(slots=True)
class OperationalEvidenceContext:
    store: ArtifactStore
    providers: dict[str, Any]
    privacy: PrivacyPolicy
    mode: str = "recorded"
    allowed_hosts: tuple[str, ...] = ()
    max_requests: int = 6
    max_response_bytes: int = 65_536
    now: str | None = None
    requests_used: int = 0
    response_bytes_used: int = 0
    _cache: dict[str, OperationalEvidenceReceipt] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.mode not in {"recorded", "live"} or self.max_requests < 1 or self.max_response_bytes < 1:
            raise ValueError("invalid operational evidence policy")
        if self.mode == "live" and not self.allowed_hosts:
            raise ValueError("live mode requires an explicit host allowlist")

    @property
    def requests_remaining(self) -> int:
        return max(0, self.max_requests - self.requests_used)

    @property
    def bytes_remaining(self) -> int:
        return max(0, self.max_response_bytes - self.response_bytes_used)

    def invoke(self, query: OperationalQuery) -> OperationalEvidenceReceipt:
        key = self._key(query)
        if key in self._cache:
            cached = self._cache[key]
            return _replace(cached, status="reused", requests_remaining=self.requests_remaining, bytes_remaining=self.bytes_remaining)
        try:
            self._validate(query)
        except ValueError as exc:
            return self._error(query, key, "policy_rejected", str(exc), consume=False)
        if self.requests_remaining == 0 or self.bytes_remaining == 0 or query.per_request_bytes > self.bytes_remaining:
            return self._error(query, key, "budget_exhausted", "operational evidence budget is exhausted", status="budget_exhausted", consume=False)
        provider = self.providers.get(query.source)
        self.requests_used += 1
        response = provider.resolve(query, max_bytes=min(query.per_request_bytes, self.bytes_remaining))
        artifact_ids: tuple[str, ...] = ()
        debit = 0
        if response.raw is not None:
            if self.privacy.allow_raw_artifact:
                artifact = self.store.put(response.raw, media_type="application/json", source_kind=f"operational_{query.source}", source_locator=query.locator)
                artifact_ids = (artifact.artifact_id,)
                debit = len(response.raw)
                self.response_bytes_used += debit
        freshness = response.freshness
        if freshness is not None and not freshness.is_fresh(now=self.now):
            response = ProviderResponse("unknown", "Operational evidence is stale.", response.source_identity, response.raw, freshness, "stale_evidence")
        status = "success" if response.outcome in {"supports_active", "supports_expired", "support", "contradict"} and response.error_kind is None else "unknown"
        if response.outcome == "contradictory":
            status = "contradictory_evidence"
        obligations = (f"Confirm redacted fields: {', '.join(self.privacy.redacted_fields)}",) if self.privacy.redacted_fields and response.outcome == "unknown" else ()
        receipt = OperationalEvidenceReceipt(key, query, status, response.outcome, response.summary, response.source_identity, query.scope, freshness, artifact_ids, (f"source:{response.source_identity}",), tuple(self.privacy.redacted_fields), obligations, {"mode": self.mode, "network_access": self.mode == "live", "target_writes": False, "target_code_execution": False}, (({"kind": response.error_kind, "message": response.summary},) if response.error_kind else ()), debit, self.requests_remaining, self.bytes_remaining)
        self._cache[key] = receipt
        return receipt

    def _validate(self, query: OperationalQuery) -> None:
        if query.source not in OPERATIONAL_SOURCES or query.source not in self.providers:
            raise ValueError("operational source is not configured")
        if self.mode != query.mode:
            raise ValueError("query mode does not match context mode")
        if self.mode == "live":
            host = urlparse(query.locator).hostname
            if host not in self.allowed_hosts:
                raise ValueError("host is not allowlisted")
            if not query.credential_identity:
                raise ValueError("credential identity is required for live evidence")

    def _key(self, query: OperationalQuery) -> str:
        value = {"query": query.to_dict(), "mode": self.mode, "privacy": self.privacy.to_dict(), "providers": sorted(self.providers), "allowed_hosts": self.allowed_hosts}
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _error(self, query: OperationalQuery, key: str, kind: str, message: str, *, status: str = "error", consume: bool = True) -> OperationalEvidenceReceipt:
        if consume and self.requests_remaining:
            self.requests_used += 1
        return OperationalEvidenceReceipt(key, query, status, "unknown", message, query.locator, query.scope, None, (), (f"query:{query.locator}",), tuple(self.privacy.redacted_fields), (), {"mode": self.mode, "network_access": False, "target_writes": False, "target_code_execution": False}, (({"kind": kind, "message": message},)), 0, self.requests_remaining, self.bytes_remaining)


def receipt_to_evidence_edge(receipt: OperationalEvidenceReceipt, claim_id: str) -> EvidenceEdge:
    role = "contradict" if receipt.status == "contradictory_evidence" or receipt.outcome in {"contradict", "supports_expired"} else "support" if receipt.status == "success" else "missing"
    freshness = receipt.freshness.freshness_key if receipt.freshness else "unknown"
    return EvidenceEdge(f"edge:{receipt.invocation_id}", claim_id, receipt.invocation_id, role, "operational", receipt.scope, freshness, receipt.artifact_ids, receipt.provenance)  # type: ignore[arg-type]


def _freshness(item: dict[str, Any]) -> FreshnessMetadata | None:
    if not item.get("observed_at"):
        return None
    return FreshnessMetadata(str(item["observed_at"]), int(item.get("max_age_seconds", 0)), str(item.get("freshness_key", "recorded-v1")))


def _replace(receipt: OperationalEvidenceReceipt, **changes: Any) -> OperationalEvidenceReceipt:
    from dataclasses import replace
    return replace(receipt, **changes)


__all__ = ["ExplicitLiveOperationalProvider", "OperationalEvidenceContext", "ProviderResponse", "RecordedOperationalProvider", "receipt_to_evidence_edge"]
