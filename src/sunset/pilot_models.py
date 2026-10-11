"""Typed contracts for the single-entry Sunset pilot workflow."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Literal


PILOT_SCHEMA_VERSION = "1"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RUN_STATUSES = {
    "created", "running", "approval_required", "completed", "denied",
    "inconclusive", "contradictory", "environment_error", "unvalidatable", "error",
}
_TERMINAL_STATUSES = _RUN_STATUSES - {"created", "running", "approval_required"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_relative(value: str, field: str) -> None:
    from pathlib import PurePosixPath

    path = PurePosixPath(value)
    if not value or value.startswith("/") or ".." in path.parts:
        raise ValueError(f"{field} must be a repository-relative path")


@dataclass(frozen=True, slots=True)
class PilotRequest:
    repository_url: str
    repository_ref: str
    scope: str
    candidate_path: str
    candidate_test: str
    mode: Literal["recorded", "live"] = "recorded"
    validation_requested: bool = False
    schema_version: str = PILOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PILOT_SCHEMA_VERSION:
            raise ValueError("unsupported pilot request schema")
        if not self.repository_url.startswith("https://"):
            raise ValueError("repository URL must use HTTPS")
        if not _SHA_RE.fullmatch(self.repository_ref):
            raise ValueError("repository ref must be a full 40-character commit SHA")
        _safe_relative(self.scope, "scope")
        _safe_relative(self.candidate_path, "candidate_path")
        if not self.candidate_test or "::" in self.candidate_test:
            raise ValueError("candidate test must be a single test name")
        if self.mode not in {"recorded", "live"}:
            raise ValueError("mode must be recorded or live")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PilotRequest":
        try:
            repository = value["repository"]
            candidate = value["candidate"]
            validation = value.get("validation", {})
            return cls(
                repository_url=str(repository["url"]),
                repository_ref=str(repository.get("ref", repository.get("sha"))),
                scope=str(value["scope"]),
                candidate_path=str(candidate["path"]),
                candidate_test=str(candidate["test"]),
                mode=str(value.get("mode", "recorded")),  # type: ignore[arg-type]
                validation_requested=bool(validation.get("requested", False)),
                schema_version=str(value.get("schema_version", PILOT_SCHEMA_VERSION)),
            )
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"invalid pilot request: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": {"url": self.repository_url, "ref": self.repository_ref},
            "scope": self.scope,
            "candidate": {"path": self.candidate_path, "test": self.candidate_test},
            "mode": self.mode,
            "validation": {"requested": self.validation_requested},
        }

    def digest(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class PilotApprovalToken:
    token: str
    run_id: str
    request_digest: str
    validation_config_digest: str
    expires_at: float
    schema_version: str = PILOT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "token": self.token,
            "run_id": self.run_id,
            "request_digest": self.request_digest,
            "validation_config_digest": self.validation_config_digest,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PilotApprovalToken":
        return cls(
            token=str(value["token"]),
            run_id=str(value["run_id"]),
            request_digest=str(value["request_digest"]),
            validation_config_digest=str(value["validation_config_digest"]),
            expires_at=float(value["expires_at"]),
            schema_version=str(value.get("schema_version", PILOT_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class PilotCaseFile:
    hypothesis: str
    evidence_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    validation_outcome: str | None
    unresolved_obligations: tuple[str, ...]
    next_action: str
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis,
            "evidence_ids": list(self.evidence_ids),
            "artifact_ids": list(self.artifact_ids),
            "validation_outcome": self.validation_outcome,
            "unresolved_obligations": list(self.unresolved_obligations),
            "next_action": self.next_action,
            "non_authority": self.non_authority,
        }


@dataclass(frozen=True, slots=True)
class PilotSetupReceipt:
    """Stable, non-authoritative receipts for clone and runtime preparation."""

    checkout: dict[str, Any]
    environment: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkout": dict(self.checkout),
            "environment": dict(self.environment),
        }


@dataclass(frozen=True, slots=True)
class PilotResult:
    run_id: str
    status: str
    request: PilotRequest
    repository_head: str
    candidate_id: str | None
    hypothesis: str
    evidence_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    validation_outcome: str | None
    unresolved_obligations: tuple[str, ...]
    approval: PilotApprovalToken | None
    next_action: str
    errors: tuple[dict[str, str], ...] = ()
    case_file: PilotCaseFile | None = None
    stage_trace: tuple[str, ...] = ()
    non_authority: bool = True
    setup_receipt: PilotSetupReceipt | None = None
    schema_version: str = PILOT_SCHEMA_VERSION
    revision: int = 0

    def __post_init__(self) -> None:
        if self.status not in _RUN_STATUSES:
            raise ValueError(f"unsupported pilot status: {self.status}")
        if not self.non_authority:
            raise ValueError("pilot results are non-authoritative")
        if self.status == "approval_required" and self.approval is None:
            raise ValueError("approval_required result must include a token")
        if self.status in _TERMINAL_STATUSES and self.approval is not None and self.status != "denied":
            raise ValueError("terminal result cannot retain an active approval token")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "status": self.status,
            "request": self.request.to_dict(),
            "repository_head": self.repository_head,
            "candidate_id": self.candidate_id,
            "hypothesis": self.hypothesis,
            "evidence_ids": list(self.evidence_ids),
            "artifact_ids": list(self.artifact_ids),
            "validation_outcome": self.validation_outcome,
            "unresolved_obligations": list(self.unresolved_obligations),
            "approval": self.approval.to_dict() if self.approval else None,
            "next_action": self.next_action,
            "errors": [dict(item) for item in self.errors],
            "case_file": self.case_file.to_dict() if self.case_file else None,
            "stage_trace": list(self.stage_trace),
            "non_authority": self.non_authority,
            "setup_receipt": self.setup_receipt.to_dict() if self.setup_receipt else None,
            "revision": self.revision,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PilotResult":
        approval = value.get("approval")
        case_file = value.get("case_file")
        setup = value.get("setup_receipt")
        cf = PilotCaseFile(
            hypothesis=str(case_file["hypothesis"]),
            evidence_ids=tuple(case_file.get("evidence_ids", ())),
            artifact_ids=tuple(case_file.get("artifact_ids", ())),
            validation_outcome=case_file.get("validation_outcome"),
            unresolved_obligations=tuple(case_file.get("unresolved_obligations", ())),
            next_action=str(case_file["next_action"]),
            non_authority=bool(case_file.get("non_authority", True)),
        ) if case_file else None
        return cls(
            run_id=str(value["run_id"]),
            status=str(value["status"]),
            request=PilotRequest.from_dict(value["request"]),
            repository_head=str(value.get("repository_head", "")),
            candidate_id=str(value["candidate_id"]) if value.get("candidate_id") is not None else None,
            hypothesis=str(value.get("hypothesis", "")),
            evidence_ids=tuple(value.get("evidence_ids", ())),
            artifact_ids=tuple(value.get("artifact_ids", ())),
            validation_outcome=value.get("validation_outcome"),
            unresolved_obligations=tuple(value.get("unresolved_obligations", ())),
            approval=PilotApprovalToken.from_dict(approval) if approval else None,
            next_action=str(value.get("next_action", "")),
            errors=tuple(dict(item) for item in value.get("errors", ())),
            case_file=cf,
            stage_trace=tuple(value.get("stage_trace", ())),
            non_authority=bool(value.get("non_authority", True)),
            setup_receipt=PilotSetupReceipt(
                checkout=dict(setup["checkout"]),
                environment=dict(setup["environment"]),
            ) if setup else None,
            schema_version=str(value.get("schema_version", PILOT_SCHEMA_VERSION)),
            revision=int(value.get("revision", 0)),
        )


__all__ = [
    "PilotApprovalToken",
    "PilotCaseFile",
    "PilotRequest",
    "PilotResult",
    "PilotSetupReceipt",
    "PILOT_SCHEMA_VERSION",
]
