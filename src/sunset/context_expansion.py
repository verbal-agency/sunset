"""Bounded, read-only relation expansion over a committed repository HEAD."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import PurePosixPath
import time
from typing import Any, Iterable

from sunset.context_expansion_models import (
    CONTEXT_EXPANSION_SCHEMA_VERSION,
    RELATION_KINDS,
    ContextExpansionObservation,
    ContextExpansionReceipt,
    ContextExpansionRequest,
)
from sunset.git_repository import GitRepository, RepositoryError


CONFIG_SUFFIXES = frozenset({".cfg", ".conf", ".ini", ".json", ".toml", ".yaml", ".yml", ".env"})


class ContextExpansionError(ValueError):
    """A deterministic request or repository-boundary failure."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(slots=True)
class ContextExpansionContext:
    repository: GitRepository
    repository_identity_kind: str
    repository_identity_value: str
    max_tool_calls: int = 12
    max_result_bytes: int = 65_536
    max_wall_time_ms: int = 5_000
    policy_name: str = "sunset-context-expansion-v1"
    grant_fingerprint: str = ""
    tool_calls_used: int = 0
    result_bytes_used: int = 0
    _cache: dict[str, ContextExpansionReceipt] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if min(self.max_tool_calls, self.max_result_bytes, self.max_wall_time_ms) < 1:
            raise ValueError("context expansion budgets must be positive")

    @classmethod
    def create(
        cls,
        target: str,
        *,
        max_tool_calls: int = 12,
        max_result_bytes: int = 65_536,
        max_wall_time_ms: int = 5_000,
        policy_name: str = "sunset-context-expansion-v1",
        grant_fingerprint: str = "",
    ) -> ContextExpansionContext:
        repository = GitRepository.open(target)
        identity_kind, identity_value = repository.repository_identity()
        return cls(repository, identity_kind, identity_value, max_tool_calls, max_result_bytes, max_wall_time_ms, policy_name, grant_fingerprint)

    @property
    def policy_fingerprint(self) -> str:
        value = {"max_result_bytes": self.max_result_bytes, "max_tool_calls": self.max_tool_calls, "max_wall_time_ms": self.max_wall_time_ms, "policy_name": self.policy_name, "schema_version": CONTEXT_EXPANSION_SCHEMA_VERSION}
        return hashlib.sha256(_canonical(value)).hexdigest()

    @property
    def bytes_remaining(self) -> int:
        return max(0, self.max_result_bytes - self.result_bytes_used)

    @property
    def calls_remaining(self) -> int:
        return max(0, self.max_tool_calls - self.tool_calls_used)

    def expand(self, request: ContextExpansionRequest) -> ContextExpansionObservation:
        started = time.monotonic_ns()
        key = self._cache_key(request)
        cached = self._cache.get(key)
        if cached is not None:
            return ContextExpansionObservation(_replace_budget(cached, self.bytes_remaining, self.calls_remaining, status="reused"))
        try:
            self._validate_binding(request)
        except ContextExpansionError as exc:
            return self._failure(request, key, exc.kind, exc.message)
        if self.calls_remaining == 0 or request.tool_call_budget > self.calls_remaining or request.cumulative_byte_budget > self.max_result_bytes:
            return self._budget_failure(request, key)
        self.tool_calls_used += 1
        if (time.monotonic_ns() - started) // 1_000_000 > min(self.max_wall_time_ms, request.wall_time_budget_ms):
            return self._budget_failure(request, key)
        try:
            result, scope, provenance = self._resolve(request)
        except ContextExpansionError as exc:
            receipt = self._failure(request, key, exc.kind, exc.message, consume=False)
            return receipt
        except (RepositoryError, OSError, SyntaxError, UnicodeDecodeError) as exc:
            return self._failure(request, key, "relation_read_error", str(exc), consume=False)
        if (time.monotonic_ns() - started) // 1_000_000 > min(self.max_wall_time_ms, request.wall_time_budget_ms):
            return self._budget_failure(request, key, consume=False)
        payload = {"references": result}
        data = _canonical(payload)
        limit = min(request.per_call_byte_budget, request.cumulative_byte_budget, self.bytes_remaining)
        truncated = False
        if len(data) > limit:
            references = list(result)
            while references and len(_canonical({"references": references})) > limit:
                references.pop()
            payload = {"references": references}
            data = _canonical(payload)
            truncated = len(references) != len(result)
        if not result:
            payload["proof_obligation"] = f"Resolve relation {request.relation} at the bound HEAD within scope {scope}."
            data = _canonical(payload)
        if len(data) > limit:
            return self._budget_failure(request, key, consume=False)
        self.result_bytes_used += len(data)
        status = "success" if result else "unknown"
        receipt = ContextExpansionReceipt(
            invocation_id=key,
            relation=request.relation,
            repository_head=self.repository.head,
            status=status,
            result=payload,
            artifact_ids=(),
            provenance=provenance,
            scope=scope,
            truncated=truncated,
            bytes_debit=len(data),
            bytes_remaining=self.bytes_remaining,
            tool_calls_remaining=self.calls_remaining,
        )
        self._cache[key] = receipt
        return ContextExpansionObservation(receipt)

    def _validate_binding(self, request: ContextExpansionRequest) -> None:
        if request.relation not in RELATION_KINDS:
            raise ContextExpansionError("relation_not_allowlisted", "relation is outside the six-name catalog")
        if request.repository_head != self.repository.head:
            raise ContextExpansionError("repository_head_mismatch", "request HEAD does not match the bound repository")
        if request.schema_version != CONTEXT_EXPANSION_SCHEMA_VERSION:
            raise ContextExpansionError("schema_mismatch", "request schema is not supported by the bound context")
        if request.policy_fingerprint and request.policy_fingerprint != self.policy_fingerprint:
            raise ContextExpansionError("policy_mismatch", "request policy does not match the bound context")
        if request.grant_fingerprint and request.grant_fingerprint != self.grant_fingerprint:
            raise ContextExpansionError("grant_mismatch", "request grant does not match the bound context")
        if request.path is not None and not request.path:
            raise ContextExpansionError("path_invalid", "path selector is empty")
        if request.path is not None and request.path not in self.repository.list_paths():
            raise ContextExpansionError("path_not_found", "path is not present at the bound HEAD")

    def _resolve(self, request: ContextExpansionRequest) -> tuple[list[dict[str, Any]], str, tuple[str, ...]]:
        scope = f"repository:{self.repository.head}"
        provenance = (f"head:{self.repository.head}",)
        if request.relation == "ast_parent":
            return _ast_parent(self.repository, request), scope, provenance
        if request.relation in {"callers", "callees"}:
            return _call_relation(self.repository, request), scope, provenance
        if request.relation == "same_commit_changes":
            return _same_commit_changes(self.repository, request), "history", provenance
        if request.relation == "historical_variant":
            return _historical_variants(self.repository, request), "history", provenance
        return _configuration_references(self.repository, request), "configuration", provenance

    def _cache_key(self, request: ContextExpansionRequest) -> str:
        value = {"request": request.to_dict(), "head": self.repository.head, "identity": [self.repository_identity_kind, self.repository_identity_value], "policy": self.policy_fingerprint, "grant": self.grant_fingerprint}
        return hashlib.sha256(_canonical(value)).hexdigest()

    def _failure(self, request: ContextExpansionRequest, key: str, kind: str, message: str, *, consume: bool = True) -> ContextExpansionObservation:
        if consume and self.calls_remaining:
            self.tool_calls_used += 1
        receipt = ContextExpansionReceipt(key, request.relation, self.repository.head, "error", {}, (), (), "none", False, 0, self.bytes_remaining, self.calls_remaining, ({"kind": kind, "message": message},))
        return ContextExpansionObservation(receipt)

    def _budget_failure(self, request: ContextExpansionRequest, key: str, *, consume: bool = True) -> ContextExpansionObservation:
        if consume and self.calls_remaining:
            self.tool_calls_used += 1
        receipt = ContextExpansionReceipt(key, request.relation, self.repository.head, "budget_exhausted", {}, (), (), "none", False, 0, self.bytes_remaining, self.calls_remaining, ({"kind": "budget_exhausted", "message": "context expansion budget is exhausted"},))
        return ContextExpansionObservation(receipt)


def _ast_parent(repository: GitRepository, request: ContextExpansionRequest) -> list[dict[str, Any]]:
    if not request.path or request.line is None:
        return []
    tree = ast.parse(repository.read_text(request.path), filename=request.path)
    nodes = [node for node in ast.walk(tree) if hasattr(node, "lineno") and getattr(node, "end_lineno", node.lineno) >= request.line >= node.lineno]
    nodes.sort(key=lambda node: (getattr(node, "end_lineno", node.lineno) - node.lineno, node.col_offset))
    if len(nodes) < 2:
        return []
    parent = nodes[1]
    return [{"path": request.path, "line": parent.lineno, "kind": type(parent).__name__}]


def _call_relation(repository: GitRepository, request: ContextExpansionRequest) -> list[dict[str, Any]]:
    if not request.symbol:
        return []
    target = request.symbol.rsplit(".", 1)[-1]
    references: list[dict[str, Any]] = []
    for path in repository.list_python_files():
        try:
            tree = ast.parse(repository.read_text(path), filename=path)
        except (SyntaxError, UnicodeDecodeError):
            # A malformed unrelated file cannot manufacture a relation; keep
            # the bounded query deterministic and return the evidence found in
            # parseable files.
            continue
        definitions: list[tuple[str, ast.AST]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions.append((node.name, node))
        if request.relation == "callees":
            for name, node in definitions:
                if name != target:
                    continue
                for call in ast.walk(node):
                    if isinstance(call, ast.Call):
                        called = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id if isinstance(call.func, ast.Name) else None
                        if called:
                            references.append({"path": path, "line": call.lineno, "symbol": called})
        else:
            for call in ast.walk(tree):
                if isinstance(call, ast.Call):
                    called = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id if isinstance(call.func, ast.Name) else None
                    if called == target:
                        references.append({"path": path, "line": call.lineno, "symbol": request.symbol})
    return sorted(references, key=lambda item: (item["path"], item["line"], item["symbol"]))


def _same_commit_changes(repository: GitRepository, request: ContextExpansionRequest) -> list[dict[str, Any]]:
    if not request.path or not request.commit_id:
        return []
    data = repository.commit_patch_bytes(request.commit_id, request.path).decode("utf-8", errors="replace")
    return [{"commit_id": request.commit_id, "path": request.path, "changed": bool(data)}]


def _historical_variants(repository: GitRepository, request: ContextExpansionRequest) -> list[dict[str, Any]]:
    if not request.path:
        return []
    raw = repository.history_bytes(request.path)
    values: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        parts = line.split("\0")
        if len(parts) >= 6 and len(parts[0]) >= 7:
            values.append({"commit_id": parts[0], "parent_ids": parts[1].split(), "author": parts[2], "timestamp": parts[4], "subject": parts[5]})
    return values


def _configuration_references(repository: GitRepository, request: ContextExpansionRequest) -> list[dict[str, Any]]:
    token = request.symbol or request.path
    if not token:
        return []
    references: list[dict[str, Any]] = []
    for path in repository.list_paths():
        pure = PurePosixPath(path)
        if pure.suffix.lower() not in CONFIG_SUFFIXES:
            continue
        text = repository.read_text(path)
        for line_number, line in enumerate(text.splitlines(), 1):
            if token in line:
                references.append({"path": path, "line": line_number, "token": token})
    return references


def _replace_budget(receipt: ContextExpansionReceipt, bytes_remaining: int, calls_remaining: int, *, status: str) -> ContextExpansionReceipt:
    return ContextExpansionReceipt(receipt.invocation_id, receipt.relation, receipt.repository_head, status, receipt.result, receipt.artifact_ids, receipt.provenance, receipt.scope, receipt.truncated, 0, bytes_remaining, calls_remaining, receipt.errors)


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


__all__ = ["ContextExpansionContext", "ContextExpansionError"]
