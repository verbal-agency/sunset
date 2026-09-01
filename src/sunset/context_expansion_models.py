"""Versioned contracts for bounded relation-based context expansion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Literal


CONTEXT_EXPANSION_SCHEMA_VERSION = "1"
RelationKind = Literal[
    "ast_parent",
    "callers",
    "callees",
    "same_commit_changes",
    "historical_variant",
    "configuration_reference",
]
RELATION_KINDS = frozenset(
    {"ast_parent", "callers", "callees", "same_commit_changes", "historical_variant", "configuration_reference"}
)
ExpansionStatus = Literal["success", "unknown", "error", "budget_exhausted", "reused"]


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True, slots=True)
class ContextExpansionRequest:
    """A capability request containing no ambient repository authority."""

    relation: RelationKind
    repository_head: str
    candidate_id: str | None = None
    path: str | None = None
    line: int | None = None
    symbol: str | None = None
    commit_id: str | None = None
    per_call_byte_budget: int = 8_192
    cumulative_byte_budget: int = 65_536
    tool_call_budget: int = 1
    wall_time_budget_ms: int = 5_000
    policy_fingerprint: str = ""
    grant_fingerprint: str = ""
    schema_version: str = CONTEXT_EXPANSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.relation not in RELATION_KINDS:
            raise ValueError(f"relation is not allowlisted: {self.relation}")
        if not self.repository_head:
            raise ValueError("repository HEAD is required")
        if not self.candidate_id and not self.symbol and not self.path:
            raise ValueError("candidate, symbol, or path identity is required")
        if self.path is not None:
            if self.path.startswith("/") or ".." in self.path.split("/") or "\\" in self.path:
                raise ValueError("path selector is not repository-relative")
        if self.line is not None and self.line < 1:
            raise ValueError("line must be positive")
        if min(self.per_call_byte_budget, self.cumulative_byte_budget, self.tool_call_budget, self.wall_time_budget_ms) < 1:
            raise ValueError("budgets must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContextExpansionRequest:
        return cls(**{key: value[key] for key in (
            "relation", "repository_head", "candidate_id", "path", "line", "symbol", "commit_id",
            "per_call_byte_budget", "cumulative_byte_budget", "tool_call_budget", "wall_time_budget_ms",
            "policy_fingerprint", "grant_fingerprint", "schema_version",
        ) if key in value})


@dataclass(frozen=True, slots=True)
class ContextExpansionReceipt:
    """Persistable relation metadata; raw source is never included."""

    invocation_id: str
    relation: RelationKind
    repository_head: str
    status: ExpansionStatus
    result: dict[str, Any]
    artifact_ids: tuple[str, ...]
    provenance: tuple[str, ...]
    scope: str
    truncated: bool
    bytes_debit: int
    bytes_remaining: int
    tool_calls_remaining: int
    errors: tuple[dict[str, str], ...] = ()
    schema_version: str = CONTEXT_EXPANSION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ids": list(self.artifact_ids),
            "bytes_debit": self.bytes_debit,
            "bytes_remaining": self.bytes_remaining,
            "errors": [dict(item) for item in self.errors],
            "invocation_id": self.invocation_id,
            "provenance": list(self.provenance),
            "relation": self.relation,
            "repository_head": self.repository_head,
            "result": self.result,
            "schema_version": self.schema_version,
            "scope": self.scope,
            "status": self.status,
            "tool_calls_remaining": self.tool_calls_remaining,
            "truncated": self.truncated,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContextExpansionReceipt:
        return cls(
            artifact_ids=_tuple(value.get("artifact_ids")),
            bytes_debit=int(value["bytes_debit"]),
            bytes_remaining=int(value["bytes_remaining"]),
            errors=tuple(dict(item) for item in value.get("errors", [])),
            invocation_id=str(value["invocation_id"]),
            provenance=_tuple(value.get("provenance")),
            relation=value["relation"],
            repository_head=str(value["repository_head"]),
            result=dict(value.get("result", {})),
            schema_version=str(value.get("schema_version", CONTEXT_EXPANSION_SCHEMA_VERSION)),
            scope=str(value["scope"]),
            status=value["status"],
            tool_calls_remaining=int(value["tool_calls_remaining"]),
            truncated=bool(value["truncated"]),
        )


@dataclass(frozen=True, slots=True)
class ContextExpansionObservation:
    """Immediate observation; transient content is intentionally optional."""

    receipt: ContextExpansionReceipt
    transient_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"receipt": self.receipt.to_dict()}
        if self.transient_content is not None:
            value["transient_content"] = self.transient_content
        return value

    def checkpoint_dict(self) -> dict[str, Any]:
        return {"receipt": self.receipt.to_dict()}
