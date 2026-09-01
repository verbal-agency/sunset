"""Versioned contracts for candidate-linked operational evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any, Literal


OPERATIONAL_EVIDENCE_SCHEMA_VERSION = "1"
OperationalSource = Literal["support_policy", "deployment_inventory", "configuration", "contract", "runtime_telemetry"]
OPERATIONAL_SOURCES = frozenset({"support_policy", "deployment_inventory", "configuration", "contract", "runtime_telemetry"})
OperationalMode = Literal["recorded", "live"]
OperationalStatus = Literal["success", "unknown", "contradictory_evidence", "error", "budget_exhausted", "reused"]


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True, slots=True)
class PrivacyPolicy:
    policy_id: str
    redacted_fields: tuple[str, ...] = ()
    allow_raw_artifact: bool = True
    schema_version: str = OPERATIONAL_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("privacy policy ID is required")

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "redacted_fields": list(self.redacted_fields), "allow_raw_artifact": self.allow_raw_artifact, "schema_version": self.schema_version}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PrivacyPolicy:
        return cls(str(value["policy_id"]), _tuple(value.get("redacted_fields")), bool(value.get("allow_raw_artifact", True)), str(value.get("schema_version", OPERATIONAL_EVIDENCE_SCHEMA_VERSION)))


@dataclass(frozen=True, slots=True)
class FreshnessMetadata:
    observed_at: str
    max_age_seconds: int
    freshness_key: str
    schema_version: str = OPERATIONAL_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.observed_at or self.max_age_seconds < 0 or not self.freshness_key:
            raise ValueError("freshness metadata is invalid")

    def is_fresh(self, *, now: str | None = None) -> bool:
        try:
            observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
            current = datetime.fromisoformat((now or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00"))
        except ValueError:
            return False
        return (current - observed).total_seconds() <= self.max_age_seconds

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FreshnessMetadata:
        return cls(str(value["observed_at"]), int(value["max_age_seconds"]), str(value["freshness_key"]), str(value.get("schema_version", OPERATIONAL_EVIDENCE_SCHEMA_VERSION)))


@dataclass(frozen=True, slots=True)
class OperationalQuery:
    source: OperationalSource
    locator: str
    candidate_id: str
    claim_id: str | None = None
    scope: str = ""
    mode: OperationalMode = "recorded"
    host: str | None = None
    credential_identity: str | None = None
    per_request_bytes: int = 32_768
    request_budget: int = 1
    wall_time_budget_ms: int = 5_000
    schema_version: str = OPERATIONAL_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.source not in OPERATIONAL_SOURCES:
            raise ValueError(f"unsupported operational source: {self.source}")
        if not self.locator or any(token in self.locator for token in ("*", "?")):
            raise ValueError("operational locator must be explicit and non-broad")
        if not self.candidate_id or not self.scope:
            raise ValueError("candidate and scope are required")
        if self.mode not in {"recorded", "live"}:
            raise ValueError(f"unsupported operational mode: {self.mode}")
        if min(self.per_request_bytes, self.request_budget, self.wall_time_budget_ms) < 1:
            raise ValueError("operational budgets must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OperationalQuery:
        return cls(**{key: value[key] for key in (
            "source", "locator", "candidate_id", "claim_id", "scope", "mode", "host",
            "credential_identity", "per_request_bytes", "request_budget", "wall_time_budget_ms", "schema_version"
        ) if key in value})


@dataclass(frozen=True, slots=True)
class OperationalEvidenceReceipt:
    invocation_id: str
    query: OperationalQuery
    status: OperationalStatus
    outcome: str
    summary: str
    source_identity: str
    scope: str
    freshness: FreshnessMetadata | None
    artifact_ids: tuple[str, ...]
    provenance: tuple[str, ...]
    redacted_fields: tuple[str, ...]
    proof_obligations: tuple[str, ...]
    effect: dict[str, Any]
    errors: tuple[dict[str, str], ...]
    bytes_debit: int
    requests_remaining: int
    bytes_remaining: int
    schema_version: str = OPERATIONAL_EVIDENCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ids": list(self.artifact_ids), "bytes_debit": self.bytes_debit,
            "bytes_remaining": self.bytes_remaining, "effect": self.effect,
            "errors": [dict(item) for item in self.errors], "freshness": self.freshness.to_dict() if self.freshness else None,
            "invocation_id": self.invocation_id, "outcome": self.outcome, "provenance": list(self.provenance), "query": self.query.to_dict(),
            "redacted_fields": list(self.redacted_fields), "proof_obligations": list(self.proof_obligations), "requests_remaining": self.requests_remaining,
            "schema_version": self.schema_version, "scope": self.scope, "source_identity": self.source_identity,
            "status": self.status, "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OperationalEvidenceReceipt:
        freshness = value.get("freshness")
        return cls(
            invocation_id=str(value["invocation_id"]), query=OperationalQuery.from_dict(value["query"]),
            status=value["status"], outcome=str(value["outcome"]), summary=str(value["summary"]),
            source_identity=str(value["source_identity"]), scope=str(value["scope"]),
            freshness=FreshnessMetadata.from_dict(freshness) if freshness else None,
            artifact_ids=_tuple(value.get("artifact_ids")), provenance=_tuple(value.get("provenance")),
            redacted_fields=_tuple(value.get("redacted_fields")), proof_obligations=_tuple(value.get("proof_obligations")), effect=dict(value["effect"]),
            errors=tuple(dict(item) for item in value.get("errors", [])), bytes_debit=int(value["bytes_debit"]),
            requests_remaining=int(value["requests_remaining"]), bytes_remaining=int(value["bytes_remaining"]),
            schema_version=str(value.get("schema_version", OPERATIONAL_EVIDENCE_SCHEMA_VERSION)),
        )


__all__ = ["FreshnessMetadata", "OperationalEvidenceReceipt", "OperationalQuery", "OperationalSource", "PrivacyPolicy"]
