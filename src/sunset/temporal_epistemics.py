"""Deterministic normalization and conservative inference for temporal debt."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

from sunset.temporal_epistemics_models import (
    CANDIDATE_FAMILIES,
    CONDITION_STATES,
    EVIDENCE_ROLES,
    ConditionHypothesis,
    ConditionState,
    EvidenceRole,
    EvidenceSource,
    EvidenceStatement,
    ProofObligation,
    ProtectedCondition,
    TemporalConclusion,
    TemporalDebtCandidate,
    TemporalEpistemicResult,
)


_ORDER = {
    "discovered": 0,
    "condition_hypothesized": 1,
    "condition_identified": 2,
    "condition_likely_expired": 3,
    "condition_likely_active": 3,
    "removal_testable": 4,
    "validated_in_scope": 5,
}
_TERMINALS = {"validated_in_scope", "contradictory_evidence", "insufficient_evidence", "unvalidatable"}


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        if isinstance(result, Mapping):
            return dict(result)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"expected a mapping or serializable domain object, got {type(value).__name__}")


def _stable_id(prefix: str, value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:20]}"


def _source_candidate(data: dict[str, Any]) -> tuple[str, str]:
    marker = str(data.get("marker_kind") or "")
    candidate_kind = str(data.get("candidate_kind") or "")
    if marker in {"xfail", "skip", "skipif"}:
        return "disabled_test", marker
    if candidate_kind == "import_fallback":
        return "compatibility_shim", candidate_kind
    if candidate_kind in {"runtime_version_guard", "dependency_version_guard"}:
        return "version_guard", candidate_kind
    if candidate_kind in {"feature_flag", "feature_flag_like"}:
        return "feature_flag_like", candidate_kind
    return "unknown", candidate_kind or marker or "unknown"


def normalize_candidate(value: Any, *, source_receipt_ids: Iterable[str] = ()) -> TemporalDebtCandidate:
    """Map an existing deterministic candidate into the bounded ontology."""

    data = _dict(value)
    family_value = data.get("family")
    source_kind = str(data.get("source_kind") or "")
    if family_value in CANDIDATE_FAMILIES:
        family = str(family_value)
        source_kind = source_kind or str(data.get("candidate_kind") or data.get("marker_kind") or family)
    else:
        family, inferred_source = _source_candidate(data)
        source_kind = source_kind or inferred_source
    candidate_id = str(data.get("candidate_id") or "unknown-candidate")
    condition: ProtectedCondition | None = None
    marker = str(data.get("marker_kind") or source_kind)
    expression = str(data["condition"]) if data.get("condition") is not None else None
    if family == "disabled_test":
        reason = str(data.get("reason") or "")
        suffix = f" Reason: {reason}" if reason else ""
        condition = ProtectedCondition(
            kind=marker,
            statement=f"The {marker} marker protects against a condition represented by the test's disabled state.{suffix}",
            expression=expression,
            protected_symbols=tuple(filter(None, [str(data.get("qualified_name")) if data.get("qualified_name") else None])),
        )
    elif family == "version_guard":
        subject = str(data["subject"]) if data.get("subject") is not None else None
        operator = str(data["comparator"]) if data.get("comparator") is not None else None
        threshold = str(data["threshold"]) if data.get("threshold") is not None else None
        statement = expression or " ".join(item for item in (subject, operator, threshold) if item) or "A version-dependent behavior is guarded."
        condition = ProtectedCondition(
            kind=source_kind,
            statement=statement,
            expression=expression or statement,
            subject=subject,
            operator=operator,
            threshold=threshold,
            protected_symbols=tuple(str(item) for item in data.get("protected_imports", ()) or ()),
        )
    elif family == "compatibility_shim":
        protected = tuple(str(item) for item in data.get("protected_imports", ()) or ())
        fallback = tuple(str(item) for item in data.get("fallback_imports", ()) or ())
        statement = expression or "A fallback import preserves compatibility with an older API or runtime."
        condition = ProtectedCondition(
            kind=source_kind,
            statement=statement,
            expression=expression,
            protected_symbols=protected + fallback,
        )
    elif family == "feature_flag_like":
        condition = ProtectedCondition(
            kind="feature_flag_like",
            statement=expression or "A feature-flag-like condition selects an alternate behavior.",
            expression=expression,
        )
    return TemporalDebtCandidate(
        candidate_id=candidate_id,
        family=family,  # type: ignore[arg-type]
        protected_condition=condition,
        source_kind=source_kind,
        path=str(data["path"]) if data.get("path") is not None else None,
        line=int(data["line"]) if data.get("line") is not None else None,
        source_receipt_ids=tuple(str(item) for item in source_receipt_ids),
        schema_version=str(data.get("schema_version", "1")),
    )


def validate_transition(current: ConditionState, requested: ConditionState) -> None:
    """Reject status jumps that would turn evidence into authority."""

    if current not in CONDITION_STATES or requested not in CONDITION_STATES:
        raise ValueError("unknown condition state")
    if requested == "human_approved":
        raise ValueError("G15 cannot create human_approved")
    if current in _TERMINALS:
        if requested != current:
            raise ValueError(f"terminal state {current} cannot transition to {requested}")
        return
    if requested in {"contradictory_evidence", "insufficient_evidence", "unvalidatable"}:
        return
    if current == "discovered" and requested in {"condition_hypothesized"}:
        return
    if current == "condition_hypothesized" and requested in {"condition_identified", "condition_likely_expired", "condition_likely_active"}:
        return
    if current == "condition_identified" and requested in {"condition_likely_expired", "condition_likely_active", "removal_testable"}:
        return
    if current in {"condition_likely_expired", "condition_likely_active"} and requested == "removal_testable":
        return
    if current == "removal_testable" and requested in {"validated_in_scope", "unvalidatable"}:
        return
    raise ValueError(f"illegal condition transition: {current} -> {requested}")


def transition_state(current: ConditionState, requested: ConditionState) -> ConditionState:
    validate_transition(current, requested)
    return requested


def _receipt_data(receipt: Any) -> dict[str, Any]:
    data = _dict(receipt)
    # Only checkpoint-safe fields are read.  In particular, transient excerpts
    # and arbitrary raw payload keys never enter an epistemic statement.
    return {
        "invocation_id": str(data.get("invocation_id") or "unknown"),
        "tool_name": str(data.get("tool_name") or "unknown"),
        "status": str(data.get("status") or "error"),
        "result": dict(data.get("result") or {}) if isinstance(data.get("result"), Mapping) else {},
        "errors": tuple(data.get("errors") or ()),
        "uncertainties": tuple(data.get("uncertainties") or ()),
        "repository_head": str(data.get("repository_head") or "unknown"),
        "evidence": tuple(data.get("evidence") or ()),
    }


def adapt_tool_receipt(receipt: Any, *, candidate_id: str | None = None) -> tuple[EvidenceStatement, ...]:
    """Adapt a G10/G12/G13 checkpoint-safe receipt without reading raw bodies."""

    data = _receipt_data(receipt)
    result = data["result"]
    candidate = result.get("candidate") if isinstance(result.get("candidate"), Mapping) else {}
    cid = candidate_id or str(candidate.get("candidate_id") or result.get("candidate_id") or "unknown-candidate")
    rid = data["invocation_id"]
    tool = data["tool_name"]
    source: EvidenceSource = "historical" if "provenance" in tool else "external" if "external" in tool or "reference" in result else "static"
    if "validation" in tool:
        source = "validation"
    artifact_ids = tuple(
        str(item.get("artifact_id")) for item in data["evidence"] if isinstance(item, Mapping) and item.get("artifact_id")
    )
    statements: list[EvidenceStatement] = []
    outcome = str(result.get("outcome") or "")
    if source == "external" and outcome in {"supports_active", "supports_expired"}:
        statement = str(result.get("summary") or f"External evidence reports {outcome}.")
        statements.append(EvidenceStatement(
            evidence_id=f"receipt:{rid}", candidate_id=cid, source_class=source, role="support",
            statement=statement, scope="the explicitly referenced upstream source", freshness=str(result.get("freshness_key") or "recorded"),
            provenance=(rid,), artifact_ids=artifact_ids,
        ))
    elif source == "validation":
        validation_status = str(result.get("status") or "unknown")
        statements.append(EvidenceStatement(
            evidence_id=f"receipt:{rid}", candidate_id=cid, source_class=source, role="scope_limit",
            statement=f"Disposable validation result is {validation_status}; it covers only the reviewed experiment.",
            scope="the reviewed disposable environment and configured test commands", freshness=data["repository_head"],
            provenance=(rid,), artifact_ids=artifact_ids,
        ))
    elif data["status"] in {"success", "partial"} and result:
        if source == "historical":
            statement = "Git provenance identifies a best-supported introduction lead; it is not proof of the first semantic rationale."
            role: EvidenceRole = "scope_limit"
            scope = "the repository history and blamed source line"
        else:
            statement = f"The deterministic {tool} receipt records candidate-linked repository evidence."
            role = "support"
            scope = "the bound repository HEAD"
        statements.append(EvidenceStatement(
            evidence_id=f"receipt:{rid}", candidate_id=cid, source_class=source, role=role,
            statement=statement, scope=scope, freshness=data["repository_head"], provenance=(rid,), artifact_ids=artifact_ids,
        ))
    else:
        errors = [str(item.get("message") if isinstance(item, Mapping) else item) for item in data["errors"]]
        statements.append(EvidenceStatement(
            evidence_id=f"receipt:{rid}", candidate_id=cid, source_class=source, role="missing",
            statement="The receipt did not provide usable evidence: " + ("; ".join(errors) or "provider or tool failure"),
            scope="the bound investigation", freshness=data["repository_head"], provenance=(rid,), artifact_ids=artifact_ids,
        ))
    for index, uncertainty in enumerate(data["uncertainties"]):
        message = str(uncertainty.get("message") if isinstance(uncertainty, Mapping) else uncertainty)
        statements.append(EvidenceStatement(
            evidence_id=f"receipt:{rid}:uncertainty:{index}", candidate_id=cid, source_class=source, role="scope_limit",
            statement=message or "The receipt contains an unresolved uncertainty.", scope="the bound investigation",
            freshness=data["repository_head"], provenance=(rid,), artifact_ids=artifact_ids,
        ))
    return tuple(statements)


def adapt_receipts(receipts: Iterable[Any], *, candidate_id: str | None = None) -> tuple[EvidenceStatement, ...]:
    statements: list[EvidenceStatement] = []
    for receipt in receipts:
        raw = _dict(receipt)
        if isinstance(raw.get("plan"), Mapping) and "status" in raw:
            statements.extend(adapt_validation_result(raw, candidate_id=candidate_id))
            continue
        statements.extend(adapt_tool_receipt(receipt, candidate_id=candidate_id))
    return tuple(statements)


def adapt_validation_result(value: Any, *, candidate_id: str | None = None) -> tuple[EvidenceStatement, ...]:
    """Adapt a G14 agent-validation result without importing its framework."""

    data = _dict(value)
    plan = data.get("plan") if isinstance(data.get("plan"), Mapping) else {}
    cid = candidate_id or str(plan.get("candidate_id") or "unknown-candidate")
    plan_id = str(plan.get("plan_id") or "unknown-plan")
    validation = data.get("validation") if isinstance(data.get("validation"), Mapping) else None
    gate_status = str(data.get("status") or "unknown")
    validation_status = str(validation.get("status")) if validation is not None else gate_status
    head = str((validation or {}).get("repository_head") or plan.get("repository_head") or "unknown")
    role: EvidenceRole = "scope_limit" if validation is not None else "missing"
    statement = (
        f"G14 disposable validation result is {validation_status}; it covers only the reviewed experiment."
        if validation is not None
        else f"G14 validation gate is {gate_status}; no experiment result is available."
    )
    provenance = tuple(str(item) for item in plan.get("evidence_receipt_ids", ()) or ()) + (plan_id,)
    return (
        EvidenceStatement(
            evidence_id=f"validation:{plan_id}", candidate_id=cid, source_class="validation", role=role,
            statement=statement, scope="the reviewed disposable environment and configured test commands",
            freshness=head, provenance=provenance,
        ),
    )


def derive_conclusion(
    candidate: TemporalDebtCandidate,
    hypotheses: Iterable[ConditionHypothesis],
    evidence: Iterable[EvidenceStatement],
    proof_obligations: Iterable[ProofObligation] = (),
) -> TemporalConclusion:
    """Derive a conservative non-authoritative status from normalized inputs."""

    hypotheses = tuple(hypotheses)
    evidence = tuple(evidence)
    obligations = tuple(proof_obligations)
    if any(item.candidate_id != candidate.candidate_id for item in hypotheses + tuple(evidence) + tuple(obligations)):
        raise ValueError("all epistemic records must belong to the candidate")
    evidence_ids = tuple(item.evidence_id for item in evidence)
    contradiction_ids = tuple(item.evidence_id for item in evidence if item.role == "contradict")
    if not hypotheses:
        state: ConditionState = "insufficient_evidence"
        return TemporalConclusion(candidate.candidate_id, state, (), evidence_ids, contradiction_ids, tuple(item.obligation_id for item in obligations))
    by_hypothesis: dict[str, set[EvidenceRole]] = {}
    for item in evidence:
        by_hypothesis.setdefault(item.hypothesis_id or "", set()).add(item.role)
    if any(bool(roles & {"support", "establish"}) and "contradict" in roles for roles in by_hypothesis.values()):
        state = "contradictory_evidence"
    elif contradiction_ids and not any(item.role in {"support", "establish"} for item in evidence):
        state = "contradictory_evidence"
    elif any(item.state == "unvalidatable" for item in hypotheses):
        state = "unvalidatable"
    elif any(item.state == "validated_in_scope" for item in hypotheses):
        state = "validated_in_scope"
    else:
        states = {item.state for item in hypotheses}
        if "human_approved" in states:
            # Approval is an external authority boundary, never an inference
            # emitted by this deterministic epistemic layer.
            state = "insufficient_evidence"
        elif "condition_likely_expired" in states and "condition_likely_active" in states:
            # Competing hypotheses are ambiguity, not contradiction, until
            # evidence actually supports incompatible claims.
            supported_hypotheses = {
                item.hypothesis_id
                for item in evidence
                if item.role in {"support", "establish"} and item.hypothesis_id
            }
            state = "contradictory_evidence" if len(supported_hypotheses) >= 2 else "insufficient_evidence"
        elif any(item.role == "missing" for item in evidence) and not any(item.role in {"support", "establish"} for item in evidence):
            state = "insufficient_evidence"
        elif any(
            item.state in {"condition_identified", "condition_likely_expired", "condition_likely_active", "removal_testable"}
            and not any(
                evidence_item.hypothesis_id == item.hypothesis_id and evidence_item.role in {"support", "establish"}
                for evidence_item in evidence
            )
            for item in hypotheses
        ):
            state = "insufficient_evidence"
        else:
            ranked = sorted(states, key=lambda item: _ORDER.get(item, -1), reverse=True)
            state = ranked[0] if ranked else "insufficient_evidence"
    return TemporalConclusion(
        candidate_id=candidate.candidate_id,
        state=state,  # type: ignore[arg-type]
        hypothesis_ids=tuple(item.hypothesis_id for item in hypotheses),
        evidence_ids=evidence_ids,
        contradiction_ids=contradiction_ids,
        proof_obligation_ids=tuple(item.obligation_id for item in obligations),
    )


def build_result(
    candidate: TemporalDebtCandidate,
    hypotheses: Iterable[ConditionHypothesis],
    evidence: Iterable[EvidenceStatement],
    proof_obligations: Iterable[ProofObligation] = (),
    *,
    errors: Iterable[str] = (),
    source_receipt_ids: Iterable[str] = (),
) -> TemporalEpistemicResult:
    hypotheses = tuple(hypotheses)
    evidence = tuple(evidence)
    obligations = tuple(proof_obligations)
    return TemporalEpistemicResult(
        candidate=candidate,
        hypotheses=hypotheses,
        evidence=evidence,
        proof_obligations=obligations,
        conclusion=derive_conclusion(candidate, hypotheses, evidence, obligations),
        errors=tuple(str(item) for item in errors),
        source_receipt_ids=tuple(str(item) for item in source_receipt_ids),
    )
