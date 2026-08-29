"""Bounded LangGraph investigations over existing local Git provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from sunset.artifact_store import ArtifactStore
from sunset.git_repository import GitRepository
from sunset.investigation_models import (
    INVESTIGATION_SCHEMA_VERSION,
    EvidenceSelection,
    InvestigationError,
    InvestigationResult,
    LedgerEntry,
    TokenBaseline,
    TokenUsage,
)
from sunset.provenance import collect_compatibility_provenance, collect_provenance
from sunset.provenance_models import ArtifactRef, CandidateProvenance
from sunset.scanner import scan_repository
from sunset.compatibility import scan_compatibility_repository


_STAGES = ("load_provenance", "retrieve_core", "summarize_core", "expand_history", "finalize")
_RATIONALE_PATTERN = re.compile(
    r"(?:issue\s*#?\d+|bug\s*#?\d+|workaround|compatib|temporary|upstream|reason)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class InvestigationConfig:
    max_input_tokens: int = 100_000
    max_output_tokens: int = 8_000
    interrupt_after: str | None = None

    def fingerprint(self) -> str:
        value = json.dumps(
            {
                "schema_version": INVESTIGATION_SCHEMA_VERSION,
                "max_input_tokens": self.max_input_tokens,
                "max_output_tokens": self.max_output_tokens,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


class _State(TypedDict):
    candidate_id: str
    collector: str
    repository_head: str
    run_id: str
    next_node: str
    status: str
    config: dict[str, Any]
    provenance: NotRequired[dict[str, Any]]
    candidate: NotRequired[dict[str, Any]]
    ledger: list[dict[str, Any]]
    selected_evidence: list[dict[str, Any]]
    open_questions: list[str]
    token_usage: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    raw_artifact_bytes: int
    checkpoint_ref: str
    needs_history: bool
    rationale_cues: list[str]


def investigate_candidate(
    target: str | Path,
    *,
    store_path: str | Path,
    candidate_id: str,
    collector: Literal["pytest", "compatibility"] = "pytest",
    config: InvestigationConfig | None = None,
    artifact_store: ArtifactStore | None = None,
) -> InvestigationResult:
    """Run or resume one bounded investigation without external evidence."""

    config = config or InvestigationConfig()
    if config.interrupt_after is not None and config.interrupt_after not in _STAGES:
        raise ValueError(f"unsupported interrupt stage: {config.interrupt_after}")
    repository = GitRepository.open(target)
    identity_kind, identity_value = repository.repository_identity()
    run_id = _run_id(identity_kind, identity_value, repository.head, collector, candidate_id, config)
    store = artifact_store or ArtifactStore(store_path)
    if store.root != Path(store_path).expanduser().resolve():
        raise ValueError("injected artifact store does not match store_path")
    state = _load_latest_checkpoint(store, run_id)
    if state is not None and state["status"] in {"inconclusive", "error"}:
        return _result_from_state(state)
    if state is None:
        state = {
            "candidate_id": candidate_id,
            "collector": collector,
            "repository_head": repository.head,
            "run_id": run_id,
            "next_node": "load_provenance",
            "status": "running",
            "config": asdict(config),
            "ledger": [],
            "selected_evidence": [],
            "open_questions": [],
            "token_usage": [],
            "errors": [],
            "raw_artifact_bytes": 0,
            "checkpoint_ref": "",
            "needs_history": False,
            "rationale_cues": [],
        }
    else:
        state["status"] = "running"
        state["config"] = asdict(config)

    runner = _InvestigationRunner(target, store, config)
    graph = _build_graph(runner)
    final_state = graph.invoke(state)
    return _result_from_state(final_state)


class _InvestigationRunner:
    def __init__(self, target: str | Path, store: ArtifactStore, config: InvestigationConfig) -> None:
        self.target = target
        self.store = store
        self.config = config

    def load_provenance(self, state: _State) -> _State:
        collector = state["collector"]
        collect = collect_provenance if collector == "pytest" else collect_compatibility_provenance
        scan = scan_repository if collector == "pytest" else scan_compatibility_repository
        provenance = collect(self.target, store_path=self.store.root, artifact_store=self.store)
        candidate_provenance = next(
            (item for item in provenance.candidates if item.candidate_id == state["candidate_id"]),
            None,
        )
        candidate = next(
            (item for item in scan(self.target).candidates if item.candidate_id == state["candidate_id"]),
            None,
        )
        if candidate_provenance is None or candidate is None:
            return self._failure(
                state,
                "load_provenance",
                "candidate_not_found",
                "candidate was not available in the committed snapshot",
            )
        return self._finish(
            state,
            "load_provenance",
            "retrieve_core",
            {
                "candidate": candidate.to_dict(),
                "provenance": candidate_provenance.to_dict(),
                "ledger": [
                    _ledger(
                        state,
                        "fact",
                        "Candidate provenance is anchored to the committed repository HEAD.",
                        tuple(artifact.artifact_id for artifact in candidate_provenance.artifacts),
                        "load_provenance",
                    )
                ],
                "open_questions": [],
            },
        )

    def retrieve_core(self, state: _State) -> _State:
        provenance = _provenance_from_state(state)
        references = {item.source_kind: item for item in provenance.artifacts}
        selected = [references["marker_source"]]
        if "blame_commit_patch" in references:
            selected.append(references["blame_commit_patch"])
        return self._retrieve(state, "retrieve_core", "summarize_core", selected, "core provenance evidence")

    def summarize_core(self, state: _State) -> _State:
        candidate = state["candidate"]
        provenance = _provenance_from_state(state)
        cues = tuple(state["rationale_cues"])
        entries = list(state["ledger"])
        entries.append(
            _ledger(
                state,
                "fact",
                f"The candidate condition is {candidate.get('condition') or candidate.get('marker_kind') or candidate.get('candidate_kind')}.",
                tuple(item["artifact_id"] for item in state["selected_evidence"]),
                "summarize_core",
            )
        )
        entries.append(
            _ledger(
                state,
                "inference",
                f"Blame commit {provenance.blame_commit} is a provenance lead, not proof of the first semantic rationale.",
                tuple(item["artifact_id"] for item in state["selected_evidence"]),
                "summarize_core",
            )
        )
        questions = list(state["open_questions"])
        questions.append("Which external assumption originally justified this candidate, and does it still hold?")
        for uncertainty in provenance.uncertainties:
            entries.append(
                _ledger(
                    state,
                    "unknown",
                    uncertainty.message,
                    (),
                    "summarize_core",
                )
            )
        if not cues:
            entries.append(
                _ledger(
                    state,
                    "unknown",
                    "Core source and blame-patch evidence contains no bounded rationale cue; focused history will be retrieved once.",
                    tuple(item["artifact_id"] for item in state["selected_evidence"]),
                    "summarize_core",
                )
            )
        return self._finish(
            state,
            "summarize_core",
            "expand_history",
            {"ledger": entries, "open_questions": questions, "needs_history": not bool(cues)},
        )

    def expand_history(self, state: _State) -> _State:
        if not state["needs_history"]:
            return self._finish(state, "expand_history", "finalize", {})
        provenance = _provenance_from_state(state)
        history = next(item for item in provenance.artifacts if item.source_kind == "focused_history")
        return self._retrieve(
            state,
            "expand_history",
            "finalize",
            [history],
            "adaptive rationale-history expansion",
        )

    def finalize(self, state: _State) -> _State:
        entries = [
            *state["ledger"],
            _ledger(
                state,
                "rejected_hypothesis",
                "Age, blame, and local history alone do not prove that removal is safe.",
                tuple(item["artifact_id"] for item in state["selected_evidence"]),
                "finalize",
            ),
            _ledger(
                state,
                "unknown",
                "External issue, release-note, and dependency evidence has not been verified in this local-only investigation.",
                (),
                "finalize",
            ),
        ]
        return self._finish(state, "finalize", "", {"ledger": entries}, terminal_status="inconclusive")

    def _retrieve(
        self,
        state: _State,
        stage: str,
        next_node: str,
        references: list[ArtifactRef],
        reason: str,
    ) -> _State:
        selected = list(state["selected_evidence"])
        raw_bytes = state["raw_artifact_bytes"]
        cues = list(state["rationale_cues"])
        for reference in references:
            if any(item["artifact_id"] == reference.artifact_id for item in selected):
                continue
            data = self.store.read(reference)
            raw_bytes += len(data)
            if stage == "retrieve_core":
                for cue in _rationale_cues((data.decode("utf-8", errors="replace"),)):
                    if cue not in cues:
                        cues.append(cue)
            selected.append(
                asdict(
                    EvidenceSelection(
                        artifact_id=reference.artifact_id,
                        byte_length=reference.byte_length,
                        source_kind=reference.source_kind,
                        reason=reason,
                    )
                )
            )
        return self._finish(
            state,
            stage,
            next_node,
            {
                "selected_evidence": selected,
                "raw_artifact_bytes": raw_bytes,
                "rationale_cues": cues[:3],
            },
        )

    def _finish(
        self,
        state: _State,
        stage: str,
        next_node: str,
        updates: dict[str, Any],
        *,
        terminal_status: str | None = None,
    ) -> _State:
        result = {**state, **updates}
        usage = _token_usage(stage, state, updates)
        result["token_usage"] = [*state["token_usage"], asdict(usage)]
        if _token_total(result, "input_tokens") > self.config.max_input_tokens:
            return self._failure(result, stage, "input_token_budget_exceeded", "estimated input-token budget was exceeded")
        if _token_total(result, "output_tokens") > self.config.max_output_tokens:
            return self._failure(result, stage, "output_token_budget_exceeded", "estimated output-token budget was exceeded")
        result["next_node"] = next_node
        result["status"] = terminal_status or (
            "interrupted" if self.config.interrupt_after == stage else "running"
        )
        self._checkpoint(result, stage)
        return result

    def _failure(self, state: _State, stage: str, kind: str, message: str) -> _State:
        result = {**state}
        result["errors"] = [*state["errors"], asdict(InvestigationError(kind, message, stage))]
        result["status"] = "error"
        result["next_node"] = ""
        self._checkpoint(result, stage)
        return result

    def _checkpoint(self, state: _State, stage: str) -> None:
        checkpoint_id = _checkpoint_id(state["run_id"], stage)
        state["checkpoint_ref"] = checkpoint_id
        self.store.put_view(checkpoint_id, _json_bytes(state))

def _build_graph(runner: _InvestigationRunner):
    graph = StateGraph(_State)
    graph.add_node("load_provenance", runner.load_provenance)
    graph.add_node("retrieve_core", runner.retrieve_core)
    graph.add_node("summarize_core", runner.summarize_core)
    graph.add_node("expand_history", runner.expand_history)
    graph.add_node("finalize", runner.finalize)
    graph.add_conditional_edges(START, _next_node, {stage: stage for stage in _STAGES})
    for stage in _STAGES:
        graph.add_conditional_edges(stage, _next_node, {**{item: item for item in _STAGES}, "end": END})
    return graph.compile()


def _next_node(state: _State) -> str:
    return state["next_node"] if state["status"] == "running" and state["next_node"] else "end"


def _load_latest_checkpoint(store: ArtifactStore, run_id: str) -> _State | None:
    for stage in reversed(_STAGES):
        data = store.read_view(_checkpoint_id(run_id, stage))
        if data is not None:
            return json.loads(data)
    return None


def _run_id(
    identity_kind: str,
    identity_value: str,
    head: str,
    collector: str,
    candidate_id: str,
    config: InvestigationConfig,
) -> str:
    value = "\0".join(
        (
            "sunset-investigation-run-v1", identity_kind, identity_value, head,
            collector, candidate_id, config.fingerprint(),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _checkpoint_id(run_id: str, stage: str) -> str:
    return f"sunset-investigation-v{INVESTIGATION_SCHEMA_VERSION}-{run_id}-{stage}"


def _provenance_from_state(state: _State) -> CandidateProvenance:
    return CandidateProvenance.from_dict(state["provenance"])


def _ledger(
    state: _State,
    kind: str,
    statement: str,
    evidence_ids: tuple[str, ...],
    node: str,
) -> dict[str, Any]:
    identity = "\0".join((state["run_id"], kind, statement, node, *evidence_ids))
    claim_id = f"ledger-v1-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"
    return asdict(LedgerEntry(claim_id, kind, statement, evidence_ids, node))


def _rationale_cues(values: tuple[str, ...]) -> tuple[str, ...]:
    cues: list[str] = []
    for value in values:
        for match in _RATIONALE_PATTERN.finditer(value):
            cue = match.group(0).lower()
            if cue not in cues:
                cues.append(cue)
            if len(cues) == 3:
                return tuple(cues)
    return tuple(cues)


def _working_memory(state: _State) -> bytes:
    compact = {
        "candidate_id": state["candidate_id"],
        "candidate": state.get("candidate", {}),
        "ledger": state["ledger"],
        "open_questions": state["open_questions"],
        "selected_evidence": state["selected_evidence"],
    }
    return _json_bytes(compact)


def _token_usage(stage: str, state: _State, updates: dict[str, Any]) -> TokenUsage:
    return TokenUsage(
        node=stage,
        input_tokens=_estimate_tokens(_working_memory(state)),
        output_tokens=_estimate_tokens(_json_bytes(updates)),
    )


def _token_total(state: _State, field: str) -> int:
    return sum(int(item[field]) for item in state["token_usage"])


def _estimate_tokens(data: bytes) -> int:
    return math.ceil(len(data) / 4)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _result_from_state(state: _State) -> InvestigationResult:
    working = _working_memory(state)
    baseline = TokenBaseline(
        full_context_tokens=math.ceil(state["raw_artifact_bytes"] / 4),
        working_memory_tokens=_estimate_tokens(working),
        raw_artifact_bytes=state["raw_artifact_bytes"],
    )
    return InvestigationResult(
        candidate_id=state["candidate_id"],
        checkpoint_id=state["checkpoint_ref"],
        collector=state["collector"],
        errors=tuple(InvestigationError(**item) for item in state["errors"]),
        ledger=tuple(LedgerEntry(**item) for item in state["ledger"]),
        open_questions=tuple(state["open_questions"]),
        repository_head=state["repository_head"],
        run_id=state["run_id"],
        selected_evidence=tuple(EvidenceSelection(**item) for item in state["selected_evidence"]),
        status=state["status"],
        token_baseline=baseline,
        token_usage=tuple(TokenUsage(**item) for item in state["token_usage"]),
    )
