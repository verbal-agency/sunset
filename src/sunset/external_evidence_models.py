"""Versioned contracts for Sunset's external-assumption evidence boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Literal

from sunset.provenance_models import ArtifactRef


EXTERNAL_EVIDENCE_SCHEMA_VERSION = "1"
ASSUMPTION_STATUSES = frozenset({"active", "expired", "unknown"})
PROVIDER_OUTCOMES = frozenset({"supports_active", "supports_expired", "missing", "failed"})


@dataclass(frozen=True, slots=True)
class ExternalReference:
    """An explicit, local-source reference that can be resolved by one provider."""

    provider: Literal["github", "release_note"]
    locator: str
    dependency_name: str | None = None
    dependency_version: str | None = None

    @property
    def reference_id(self) -> str:
        digest = hashlib.sha256(
            f"{self.provider}\0{self.locator}\0{self.dependency_name}\0{self.dependency_version}".encode("utf-8")
        ).hexdigest()
        return f"external-ref-v{EXTERNAL_EVIDENCE_SCHEMA_VERSION}-{digest[:20]}"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "provider": self.provider,
            "locator": self.locator,
            "dependency_name": self.dependency_name,
            "dependency_version": self.dependency_version,
            "reference_id": self.reference_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ExternalReference:
        return cls(
            provider=value["provider"],
            locator=str(value["locator"]),
            dependency_name=value.get("dependency_name"),
            dependency_version=value.get("dependency_version"),
        )


@dataclass(frozen=True, slots=True)
class ProviderResolution:
    """A normalized provider response whose raw payload is stored separately."""

    reference: ExternalReference
    outcome: Literal["supports_active", "supports_expired", "missing", "failed"]
    summary: str
    source_locator: str
    artifact: ArtifactRef | None = None
    error_kind: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in PROVIDER_OUTCOMES:
            raise ValueError(f"unsupported provider outcome: {self.outcome}")
        if self.outcome in {"supports_active", "supports_expired"} and self.artifact is None:
            raise ValueError("supporting evidence must retain a raw artifact reference")

    def to_dict(self) -> dict[str, Any]:
        value = {
            "reference": self.reference.to_dict(),
            "outcome": self.outcome,
            "summary": self.summary,
            "source_locator": self.source_locator,
            "error_kind": self.error_kind,
        }
        value["artifact"] = self.artifact.to_dict() if self.artifact else None
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProviderResolution:
        artifact = value.get("artifact")
        return cls(
            reference=ExternalReference.from_dict(value["reference"]),
            outcome=value["outcome"],
            summary=str(value["summary"]),
            source_locator=str(value["source_locator"]),
            artifact=ArtifactRef.from_dict(artifact) if artifact else None,
            error_kind=value.get("error_kind"),
        )


@dataclass(frozen=True, slots=True)
class AssumptionAssessment:
    status: Literal["active", "expired", "unknown"]
    resolutions: tuple[ProviderResolution, ...]

    def __post_init__(self) -> None:
        if self.status not in ASSUMPTION_STATUSES:
            raise ValueError(f"unsupported assumption status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "resolutions": [item.to_dict() for item in self.resolutions]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
