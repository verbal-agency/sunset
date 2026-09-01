"""Context-bound LangChain tools for Sunset's deterministic local evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from sunset.agent_tool_models import (
    TOOL_CONTRACT_SCHEMA_VERSION,
    InvocationTelemetry,
    ToolBudget,
    ToolEffect,
    ToolFailure,
    ToolObservation,
    ToolReceipt,
    ToolStatus,
)
from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.compatibility import scan_compatibility_repository
from sunset.git_repository import GitRepository, RepositoryError
from sunset.provenance import collect_compatibility_provenance, collect_provenance
from sunset.provenance_models import ArtifactRef, ProvenanceResult
from sunset.scanner import scan_repository


DISCOVER_TOOL = "sunset_discover_candidates"
PROVENANCE_TOOL = "sunset_get_candidate_provenance"
EXCERPT_TOOL = "sunset_read_evidence_excerpt"
TOOL_NAMES = (DISCOVER_TOOL, PROVENANCE_TOOL, EXCERPT_TOOL)

Collector = Literal["pytest", "compatibility"]


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscoverCandidatesInput(_StrictInput):
    """The target and collector are supplied by trusted application context."""


class CandidateProvenanceInput(_StrictInput):
    candidate_id: str = Field(min_length=1, description="Stable ID from candidate discovery")


class EvidenceExcerptInput(_StrictInput):
    artifact_id: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
        description="Previously granted content-addressed evidence artifact ID",
    )
    offset: int = Field(default=0, ge=0, description="Zero-based byte offset")
    length: int | None = Field(
        default=None,
        ge=1,
        description="Requested byte length; omitted means the configured per-call maximum",
    )


LOCAL_READ_ONLY_EFFECT = ToolEffect()


@dataclass(slots=True)
class ToolExecutionContext:
    """Trusted authority and deterministic budget state for one tool session."""

    target: Path
    repository: GitRepository
    repository_identity_kind: str
    repository_identity_value: str
    store: ArtifactStore
    collector: Collector
    max_tool_calls: int
    max_evidence_bytes: int
    max_excerpt_bytes: int
    policy_name: str
    granted_artifacts: dict[str, ArtifactRef] = field(default_factory=dict)
    tool_calls_used: int = 0
    evidence_bytes_used: int = 0
    telemetry: list[InvocationTelemetry] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @classmethod
    def create(
        cls,
        target: str | Path,
        *,
        store_path: str | Path,
        collector: Collector = "pytest",
        max_tool_calls: int = 12,
        max_evidence_bytes: int = 65_536,
        max_excerpt_bytes: int = 8_192,
        policy_name: str = "sunset-local-read-only-v1",
        granted_artifacts: Mapping[str, ArtifactRef] | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> ToolExecutionContext:
        if collector not in {"pytest", "compatibility"}:
            raise ValueError(f"unsupported collector: {collector}")
        if max_tool_calls < 1 or max_evidence_bytes < 0 or max_excerpt_bytes < 1:
            raise ValueError("tool and evidence budgets must be positive (cumulative bytes may be zero)")
        repository = GitRepository.open(target)
        identity_kind, identity_value = repository.repository_identity()
        resolved_target = Path(target).expanduser().resolve()
        resolved_store = Path(store_path).expanduser().resolve()
        store = artifact_store or ArtifactStore(resolved_store)
        if store.root != resolved_store:
            raise ValueError("injected artifact store does not match store_path")
        try:
            resolved_store.relative_to(repository.root)
        except ValueError:
            pass
        else:
            raise RepositoryError(
                "artifact_store_inside_repository",
                "artifact store must be outside the analyzed repository",
            )
        grants = dict(granted_artifacts or {})
        if any(key != reference.artifact_id for key, reference in grants.items()):
            raise ValueError("granted artifact mapping keys must match artifact IDs")
        return cls(
            target=resolved_target,
            repository=repository,
            repository_identity_kind=identity_kind,
            repository_identity_value=identity_value,
            store=store,
            collector=collector,
            max_tool_calls=max_tool_calls,
            max_evidence_bytes=max_evidence_bytes,
            max_excerpt_bytes=max_excerpt_bytes,
            policy_name=policy_name,
            granted_artifacts=grants,
        )

    @property
    def repository_identity(self) -> tuple[str, str]:
        return self.repository_identity_kind, self.repository_identity_value

    @property
    def evidence_bytes_remaining(self) -> int:
        return max(0, self.max_evidence_bytes - self.evidence_bytes_used)

    @property
    def tool_calls_remaining(self) -> int:
        return max(0, self.max_tool_calls - self.tool_calls_used)

    def policy_fingerprint(self) -> str:
        value = {
            "effect": LOCAL_READ_ONLY_EFFECT.to_dict(),
            "max_evidence_bytes": self.max_evidence_bytes,
            "max_excerpt_bytes": self.max_excerpt_bytes,
            "max_tool_calls": self.max_tool_calls,
            "network_mode": "offline",
            "policy_name": self.policy_name,
        }
        return hashlib.sha256(_canonical_json(value)).hexdigest()

    def invocation_id(self, tool_name: str, tool_input: Mapping[str, Any]) -> str:
        identity_kind, identity_value = self.repository_identity
        value = {
            "budget_ledger": {
                "evidence_bytes_used": self.evidence_bytes_used,
                "tool_calls_used": self.tool_calls_used,
            },
            "canonical_input": dict(tool_input),
            "collector": self.collector,
            "evidence_grants": sorted(self.granted_artifacts),
            "policy_fingerprint": self.policy_fingerprint(),
            "repository_head": self.repository.head,
            "repository_identity": {"kind": identity_kind, "value": identity_value},
            "schema_version": TOOL_CONTRACT_SCHEMA_VERSION,
            "target_prefix": self.repository.target_prefix,
            "tool_name": tool_name,
        }
        return hashlib.sha256(_canonical_json(value)).hexdigest()

    def validation_failure(
        self,
        tool_name: str,
        tool_input: object,
        error: Exception,
    ) -> ToolObservation:
        started = time.monotonic_ns()
        with self._lock:
            normalized_input = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
            invocation_id = self.invocation_id(tool_name, normalized_input)
            if self.tool_calls_remaining == 0:
                observation = self._failure(
                    tool_name,
                    normalized_input,
                    status="budget_exhausted",
                    errors=(ToolFailure("tool_call_budget_exhausted", "tool-call budget is exhausted"),),
                    invocation_id=invocation_id,
                    consume_call=False,
                )
            else:
                if isinstance(error, ValidationError):
                    failures = tuple(
                        ToolFailure(kind="input_validation_error", message=item["msg"])
                        for item in error.errors(include_url=False)
                    )
                else:
                    failures = (ToolFailure(kind="input_validation_error", message=str(error)),)
                observation = self._failure(
                    tool_name,
                    normalized_input,
                    status="error",
                    errors=failures,
                    invocation_id=invocation_id,
                )
            self._record_telemetry(observation, started, cache_reused=False)
            return observation

    def invoke(self, tool_name: str, tool_input: Mapping[str, Any]) -> ToolObservation:
        started = time.monotonic_ns()
        with self._lock:
            invocation_id = self.invocation_id(tool_name, tool_input)
            if self.tool_calls_remaining == 0:
                observation = self._failure(
                    tool_name,
                    tool_input,
                    status="budget_exhausted",
                    errors=(ToolFailure("tool_call_budget_exhausted", "tool-call budget is exhausted"),),
                    invocation_id=invocation_id,
                    consume_call=False,
                )
                self._record_telemetry(observation, started, cache_reused=False)
                return observation

            head_failure = self._head_failure()
            if head_failure is not None:
                observation = self._failure(
                    tool_name,
                    tool_input,
                    status="error",
                    errors=(head_failure,),
                    invocation_id=invocation_id,
                )
                self._record_telemetry(observation, started, cache_reused=False)
                return observation

            cacheable = tool_name in {DISCOVER_TOOL, PROVENANCE_TOOL}
            if cacheable:
                try:
                    cached = self._read_cached_receipt(invocation_id)
                except (ArtifactStoreError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    observation = self._failure(
                        tool_name,
                        tool_input,
                        status="error",
                        errors=(ToolFailure(_error_kind(exc), str(exc)),),
                        invocation_id=invocation_id,
                    )
                    self._record_telemetry(observation, started, cache_reused=False)
                    return observation
                if cached is not None:
                    self.tool_calls_used += 1
                    self._grant(cached.evidence)
                    observation = ToolObservation(receipt=cached)
                    self._record_telemetry(observation, started, cache_reused=True)
                    return observation

            self.tool_calls_used += 1
            try:
                if tool_name == DISCOVER_TOOL:
                    observation = self._discover(invocation_id)
                elif tool_name == PROVENANCE_TOOL:
                    observation = self._provenance(invocation_id, str(tool_input["candidate_id"]))
                elif tool_name == EXCERPT_TOOL:
                    observation = self._excerpt(
                        invocation_id,
                        artifact_id=str(tool_input["artifact_id"]),
                        offset=int(tool_input.get("offset", 0)),
                        length=(int(tool_input["length"]) if tool_input.get("length") is not None else None),
                    )
                else:
                    observation = self._failure(
                        tool_name,
                        tool_input,
                        status="error",
                        errors=(ToolFailure("tool_unknown", f"unknown Sunset tool: {tool_name}"),),
                        invocation_id=invocation_id,
                        consume_call=False,
                    )
            except (ArtifactStoreError, RepositoryError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                observation = self._failure(
                    tool_name,
                    tool_input,
                    status="error",
                    errors=(ToolFailure(_error_kind(exc), str(exc)),),
                    invocation_id=invocation_id,
                    consume_call=False,
                )

            if cacheable and observation.receipt.status in {"success", "partial"}:
                try:
                    self._write_cached_receipt(observation.receipt)
                except (ArtifactStoreError, OSError) as exc:
                    receipt = replace(
                        observation.receipt,
                        status="partial",
                        errors=observation.receipt.errors + (ToolFailure(_error_kind(exc), str(exc)),),
                    )
                    observation = ToolObservation(receipt=receipt)
            self._record_telemetry(observation, started, cache_reused=False)
            return observation

    def _discover(self, invocation_id: str) -> ToolObservation:
        result = (
            scan_repository(self.target)
            if self.collector == "pytest"
            else scan_compatibility_repository(self.target)
        )
        failures = tuple(ToolFailure(error.kind, error.message) for error in result.errors)
        receipt = self._receipt(
            DISCOVER_TOOL,
            invocation_id,
            status="partial" if failures else "success",
            result=result.to_dict(),
            errors=failures,
        )
        return ToolObservation(receipt=receipt)

    def _provenance(self, invocation_id: str, candidate_id: str) -> ToolObservation:
        collector = collect_provenance if self.collector == "pytest" else collect_compatibility_provenance
        result: ProvenanceResult = collector(
            self.target,
            store_path=self.store.root,
            artifact_store=self.store,
        )
        selected = next((item for item in result.candidates if item.candidate_id == candidate_id), None)
        errors = tuple(ToolFailure(error.kind, error.message) for error in result.errors)
        if selected is None:
            missing = ToolFailure("candidate_not_found", f"candidate is not present at the bound HEAD: {candidate_id}")
            receipt = self._receipt(
                PROVENANCE_TOOL,
                invocation_id,
                status="error",
                result={"candidate_id": candidate_id, "collection": result.to_dict()},
                errors=errors + (missing,),
            )
            return ToolObservation(receipt=receipt)

        uncertainties = tuple(ToolFailure(issue.kind, issue.message) for issue in selected.uncertainties)
        evidence = selected.artifacts
        self._grant(evidence)
        receipt = self._receipt(
            PROVENANCE_TOOL,
            invocation_id,
            status="partial" if errors or uncertainties else "success",
            result={
                "candidate": selected.to_dict(),
                "collection_errors": [error.to_dict() for error in result.errors],
                "introduction_provenance": {
                    "basis": "line_blame",
                    "caveat": "best-supported provenance lead; not proof of the first semantic rationale",
                },
                "repository_head": result.repository_head,
                "repository_identity": {
                    "kind": result.repository_identity_kind,
                    "value": result.repository_identity_value,
                },
                "schema_version": result.schema_version,
            },
            evidence=evidence,
            errors=errors,
            uncertainties=uncertainties,
        )
        return ToolObservation(receipt=receipt)

    def _excerpt(
        self,
        invocation_id: str,
        *,
        artifact_id: str,
        offset: int,
        length: int | None,
    ) -> ToolObservation:
        reference = self.granted_artifacts.get(artifact_id)
        if reference is None:
            return self._failure(
                EXCERPT_TOOL,
                {"artifact_id": artifact_id, "offset": offset, "length": length},
                status="error",
                errors=(ToolFailure("artifact_not_granted", "artifact ID is outside the current evidence grant"),),
                invocation_id=invocation_id,
                consume_call=False,
            )
        if self.evidence_bytes_remaining == 0:
            return self._failure(
                EXCERPT_TOOL,
                {"artifact_id": artifact_id, "offset": offset, "length": length},
                status="budget_exhausted",
                errors=(ToolFailure("evidence_byte_budget_exhausted", "evidence byte budget is exhausted"),),
                invocation_id=invocation_id,
                consume_call=False,
            )
        data = self.store.read(reference)
        if offset >= len(data):
            return self._failure(
                EXCERPT_TOOL,
                {"artifact_id": artifact_id, "offset": offset, "length": length},
                status="error",
                errors=(ToolFailure("evidence_range_invalid", "offset is outside the artifact byte range"),),
                invocation_id=invocation_id,
                consume_call=False,
            )
        requested = self.max_excerpt_bytes if length is None else length
        permitted = min(requested, self.max_excerpt_bytes)
        if permitted > self.evidence_bytes_remaining:
            return self._failure(
                EXCERPT_TOOL,
                {"artifact_id": artifact_id, "offset": offset, "length": length},
                status="budget_exhausted",
                errors=(
                    ToolFailure(
                        "evidence_byte_budget_insufficient",
                        "requested excerpt exceeds the remaining evidence byte budget",
                    ),
                ),
                invocation_id=invocation_id,
                consume_call=False,
            )
        chunk = data[offset : offset + permitted]
        end = offset + len(chunk)
        truncated = end < len(data) or requested > permitted
        debit = len(chunk)
        self.evidence_bytes_used += debit
        result = {
            "artifact_id": artifact_id,
            "byte_length": debit,
            "digest": hashlib.sha256(chunk).hexdigest(),
            "end": end,
            "offset": offset,
            "total_byte_length": len(data),
            "truncated": truncated,
        }
        receipt = self._receipt(
            EXCERPT_TOOL,
            invocation_id,
            status="success",
            result=result,
            evidence=(reference,),
            evidence_bytes_debit=debit,
        )
        return ToolObservation(receipt=receipt, transient_content=chunk.decode("utf-8", errors="replace"))

    def _head_failure(self) -> ToolFailure | None:
        try:
            current = GitRepository.open(self.target)
        except RepositoryError as exc:
            return ToolFailure(exc.code, exc.message)
        if current.root != self.repository.root or current.head != self.repository.head:
            return ToolFailure(
                "repository_head_changed",
                "target repository no longer matches the HEAD bound to this context",
            )
        return None

    def _receipt(
        self,
        tool_name: str,
        invocation_id: str,
        *,
        status: ToolStatus,
        result: dict[str, Any],
        evidence: tuple[ArtifactRef, ...] = (),
        errors: tuple[ToolFailure, ...] = (),
        uncertainties: tuple[ToolFailure, ...] = (),
        evidence_bytes_debit: int = 0,
    ) -> ToolReceipt:
        identity_kind, identity_value = self.repository_identity
        return ToolReceipt(
            tool_name=tool_name,
            invocation_id=invocation_id,
            repository_identity_kind=identity_kind,
            repository_identity_value=identity_value,
            repository_head=self.repository.head,
            status=status,
            result=result,
            evidence=evidence,
            errors=errors,
            uncertainties=uncertainties,
            effect=LOCAL_READ_ONLY_EFFECT,
            budget=ToolBudget(
                evidence_bytes_debit=evidence_bytes_debit,
                evidence_bytes_remaining=self.evidence_bytes_remaining,
                tool_calls_remaining=self.tool_calls_remaining,
            ),
            schema_version=TOOL_CONTRACT_SCHEMA_VERSION,
        )

    def _failure(
        self,
        tool_name: str,
        tool_input: Mapping[str, Any],
        *,
        status: ToolStatus,
        errors: tuple[ToolFailure, ...],
        invocation_id: str | None = None,
        consume_call: bool = True,
    ) -> ToolObservation:
        if consume_call and self.tool_calls_remaining:
            self.tool_calls_used += 1
        receipt = self._receipt(
            tool_name,
            invocation_id or self.invocation_id(tool_name, tool_input),
            status=status,
            result={},
            errors=errors,
        )
        return ToolObservation(receipt=receipt)

    def _grant(self, evidence: tuple[ArtifactRef, ...]) -> None:
        for reference in evidence:
            self.granted_artifacts[reference.artifact_id] = reference

    def _cache_view_id(self, invocation_id: str) -> str:
        return f"sunset-tool-receipt-v{TOOL_CONTRACT_SCHEMA_VERSION}-{invocation_id}"

    def _read_cached_receipt(self, invocation_id: str) -> ToolReceipt | None:
        value = self.store.read_view(self._cache_view_id(invocation_id))
        return ToolReceipt.from_dict(json.loads(value)) if value is not None else None

    def _write_cached_receipt(self, receipt: ToolReceipt) -> None:
        self.store.put_view(self._cache_view_id(receipt.invocation_id), receipt.to_json().encode("utf-8"))

    def _record_telemetry(self, observation: ToolObservation, started: int, *, cache_reused: bool) -> None:
        self.telemetry.append(
            InvocationTelemetry(
                tool_name=observation.receipt.tool_name,
                invocation_id=observation.receipt.invocation_id,
                cache_reused=cache_reused,
                duration_ms=max(0, (time.monotonic_ns() - started) // 1_000_000),
            )
        )


class _ContextBoundTool(BaseTool):
    _context: ToolExecutionContext = PrivateAttr()

    def __init__(self, *, context: ToolExecutionContext, **data: Any) -> None:
        super().__init__(**data)
        self._context = context

    def _run(self, **kwargs: Any) -> dict[str, Any]:
        return self._context.invoke(self.name, kwargs).to_dict()

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        try:
            return super().invoke(self._validate_direct_input(input), config=config, **kwargs)
        except (ValidationError, ValueError, TypeError) as exc:
            return self._context.validation_failure(self.name, input, exc).to_dict()

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        try:
            return await super().ainvoke(self._validate_direct_input(input), config=config, **kwargs)
        except (ValidationError, ValueError, TypeError) as exc:
            return self._context.validation_failure(self.name, input, exc).to_dict()

    def _validate_direct_input(self, input: Any) -> Any:
        if not isinstance(input, dict) or self.args_schema is None:
            return input
        if input.get("type") == "tool_call" and isinstance(input.get("args"), dict):
            normalized = self.args_schema.model_validate(input["args"]).model_dump()
            return {**input, "args": normalized}
        return self.args_schema.model_validate(input).model_dump()


@dataclass(frozen=True, slots=True)
class BoundToolRegistry:
    tools: tuple[BaseTool, ...]

    def by_name(self, name: str) -> BaseTool:
        return next(tool for tool in self.tools if tool.name == name)


def create_tool_registry(context: ToolExecutionContext) -> BoundToolRegistry:
    """Build exactly the local capabilities authorized by *context*."""

    effect_metadata = {
        "sunset_contract_schema_version": TOOL_CONTRACT_SCHEMA_VERSION,
        "sunset_effect": LOCAL_READ_ONLY_EFFECT.to_dict(),
    }
    definitions: tuple[tuple[str, str, type[BaseModel]], ...] = (
        (
            DISCOVER_TOOL,
            "Discover deterministic Sunset candidates at the repository HEAD bound by trusted context.",
            DiscoverCandidatesInput,
        ),
        (
            PROVENANCE_TOOL,
            "Collect or reuse local Git provenance for one previously discovered candidate ID.",
            CandidateProvenanceInput,
        ),
        (
            EXCERPT_TOOL,
            "Read a byte-bounded transient excerpt from evidence already granted by a prior receipt.",
            EvidenceExcerptInput,
        ),
    )
    return BoundToolRegistry(
        tuple(
            _ContextBoundTool(
                context=context,
                name=name,
                description=description,
                args_schema=args_schema,
                metadata=effect_metadata,
            )
            for name, description, args_schema in definitions
        )
    )


def tool_catalog() -> dict[str, Any]:
    """Return a deterministic catalog without touching a repository or store."""

    schemas: tuple[tuple[str, str, type[BaseModel]], ...] = (
        (DISCOVER_TOOL, "Discover deterministic candidates in the bound repository.", DiscoverCandidatesInput),
        (PROVENANCE_TOOL, "Collect local Git provenance for one candidate.", CandidateProvenanceInput),
        (EXCERPT_TOOL, "Read a bounded transient excerpt from granted evidence.", EvidenceExcerptInput),
    )
    return {
        "schema_version": TOOL_CONTRACT_SCHEMA_VERSION,
        "tools": [
            {
                "availability": "local",
                "description": description,
                "effect": LOCAL_READ_ONLY_EFFECT.to_dict(),
                "input_schema": schema.model_json_schema(),
                "name": name,
                "version": TOOL_CONTRACT_SCHEMA_VERSION,
            }
            for name, description, schema in schemas
        ],
    }


def tool_catalog_json() -> str:
    return json.dumps(tool_catalog(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _error_kind(error: Exception) -> str:
    if isinstance(error, (ArtifactStoreError, RepositoryError)):
        return error.code
    if isinstance(error, json.JSONDecodeError):
        return "cached_receipt_decode_failed"
    if isinstance(error, OSError):
        return "local_io_failed"
    return "tool_operation_failed"
