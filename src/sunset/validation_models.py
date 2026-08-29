"""Versioned contracts for approval-gated, disposable validation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal

from sunset.provenance_models import ArtifactRef


VALIDATION_SCHEMA_VERSION = "1"
VALIDATION_STATUSES = frozenset(
    {
        "approval_required",
        "confirmed",
        "still_failing",
        "flaky",
        "environment_error",
        "inconclusive",
    }
)


@dataclass(frozen=True, slots=True)
class ValidationError:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CommandRun:
    command: tuple[str, ...]
    phase: Literal["narrow", "broader"]
    attempt: int
    return_code: int | None
    output: ArtifactRef
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "phase": self.phase,
            "attempt": self.attempt,
            "return_code": self.return_code,
            "output": self.output.to_dict(),
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentManifest:
    artifact: ArtifactRef
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {"artifact": self.artifact.to_dict(), "fingerprint": self.fingerprint}


@dataclass(frozen=True, slots=True)
class ValidationResult:
    approved: bool
    candidate_id: str
    collector: str
    environment: EnvironmentManifest | None
    errors: tuple[ValidationError, ...]
    repository_head: str
    runs: tuple[CommandRun, ...]
    status: Literal[
        "approval_required",
        "confirmed",
        "still_failing",
        "flaky",
        "environment_error",
        "inconclusive",
    ]
    schema_version: str = VALIDATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in VALIDATION_STATUSES:
            raise ValueError(f"unsupported validation status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "candidate_id": self.candidate_id,
            "collector": self.collector,
            "environment": self.environment.to_dict() if self.environment else None,
            "errors": [item.to_dict() for item in self.errors],
            "repository_head": self.repository_head,
            "runs": [item.to_dict() for item in self.runs],
            "schema_version": self.schema_version,
            "status": self.status,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True, slots=True)
class CommandExecution:
    return_code: int | None
    stderr: bytes
    stdout: bytes
    timed_out: bool = False
