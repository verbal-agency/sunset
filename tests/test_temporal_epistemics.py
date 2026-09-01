from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

from sunset.compatibility import scan_compatibility_repository
from sunset.scanner import scan_repository
from sunset.temporal_epistemics import (
    adapt_receipts,
    adapt_tool_receipt,
    build_result,
    derive_conclusion,
    normalize_candidate,
    transition_state,
    validate_transition,
)
from sunset.temporal_epistemics_models import (
    ConditionHypothesis,
    EvidenceStatement,
    ProofObligation,
    TemporalConclusion,
    TemporalDebtCandidate,
)


def _hypothesis(candidate_id: str, hypothesis_id: str, state: str = "condition_hypothesized") -> ConditionHypothesis:
    return ConditionHypothesis(hypothesis_id, candidate_id, f"condition for {hypothesis_id}", state=state)  # type: ignore[arg-type]


def _evidence(candidate_id: str, evidence_id: str, role: str, hypothesis_id: str | None = None) -> EvidenceStatement:
    return EvidenceStatement(
        evidence_id=evidence_id,
        candidate_id=candidate_id,
        source_class="historical",
        role=role,  # type: ignore[arg-type]
        statement=f"evidence {evidence_id}",
        scope="repository history only",
        freshness="head-1",
        provenance=(evidence_id,),
        hypothesis_id=hypothesis_id,
    )


def test_g15_ac01_bounded_ontology(sample_repository: Path, compatibility_repository: Path) -> None:
    marker = normalize_candidate(scan_repository(sample_repository).candidates[0])
    compatibility = scan_compatibility_repository(compatibility_repository).candidates
    shim = normalize_candidate(compatibility[3])
    guard = normalize_candidate(compatibility[0])
    unknown = normalize_candidate({"candidate_id": "dynamic", "candidate_kind": "dynamic_guard", "condition": "runtime()"})

    assert marker.family == "disabled_test" and marker.protected_condition is not None
    assert shim.family == "compatibility_shim" and shim.protected_condition is not None
    assert guard.family == "version_guard" and guard.protected_condition is not None
    assert unknown.family == "unknown"


def test_g15_ac02_hypotheses_and_evidence_roles_round_trip() -> None:
    candidate = TemporalDebtCandidate("candidate-1", "disabled_test", None, "xfail")
    hypotheses = (_hypothesis(candidate.candidate_id, "h1"), _hypothesis(candidate.candidate_id, "h2"))
    evidence = (
        _evidence(candidate.candidate_id, "e1", "support", "h1"),
        _evidence(candidate.candidate_id, "e2", "contradict", "h2"),
        _evidence(candidate.candidate_id, "e3", "establish"),
        _evidence(candidate.candidate_id, "e4", "scope_limit"),
        _evidence(candidate.candidate_id, "e5", "missing"),
    )
    result = build_result(candidate, hypotheses, evidence)
    restored = type(result).from_dict(json.loads(result.to_json()))

    assert len(restored.hypotheses) == 2
    assert {item.role for item in restored.evidence} == {"support", "contradict", "establish", "scope_limit", "missing"}
    assert restored.conclusion.non_authority is True


def test_g15_ac03_state_transitions_are_conservative() -> None:
    assert transition_state("discovered", "condition_hypothesized") == "condition_hypothesized"
    assert transition_state("condition_identified", "removal_testable") == "removal_testable"
    assert transition_state("removal_testable", "validated_in_scope") == "validated_in_scope"
    with pytest.raises(ValueError, match="human_approved"):
        validate_transition("validated_in_scope", "human_approved")
    with pytest.raises(ValueError, match="illegal"):
        validate_transition("discovered", "removal_testable")

    candidate = TemporalDebtCandidate("candidate-2", "version_guard", None, "runtime_version_guard")
    result = derive_conclusion(
        candidate,
        (_hypothesis(candidate.candidate_id, "h1", "condition_likely_expired"),),
        (_evidence(candidate.candidate_id, "e1", "support", "h1"),),
    )
    assert result.state == "condition_likely_expired"
    assert result.non_authority is True


def test_g15_ac04_scope_and_proof_obligations_are_retained() -> None:
    candidate = TemporalDebtCandidate("candidate-3", "compatibility_shim", None, "import_fallback")
    obligation = ProofObligation(
        "po-1", candidate.candidate_id, "Check customer runtime inventory", "Upstream EOL does not establish deployment absence.",
        "production and customer environments", owner="maintainer", validation_can_address=False,
    )
    evidence = _evidence(candidate.candidate_id, "eol", "support", "h1")
    conclusion = derive_conclusion(candidate, (_hypothesis(candidate.candidate_id, "h1", "condition_likely_expired"),), (evidence,), (obligation,))

    assert conclusion.state == "condition_likely_expired"
    assert conclusion.proof_obligation_ids == ("po-1",)
    assert evidence.scope == "repository history only"


def test_g15_ac05_receipts_adapt_without_raw_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("G15 must stay offline")))
    receipt = {
        "invocation_id": "invoke-1",
        "tool_name": "sunset_collect_provenance",
        "status": "success",
        "repository_head": "a" * 40,
        "result": {
            "candidate": {"candidate_id": "candidate-4", "candidate_kind": "import_fallback"},
            "introduction_provenance": {"basis": "line_blame", "caveat": "not proof"},
            "raw": "DO_NOT_COPY",
        },
        "evidence": [{"artifact_id": "sha256:" + "b" * 64}],
        "errors": [],
        "uncertainties": [{"kind": "shallow_history", "message": "history is incomplete"}],
    }
    statements = adapt_tool_receipt(receipt)
    serialized = json.dumps([item.to_dict() for item in statements], sort_keys=True)

    assert statements[0].source_class == "historical"
    assert statements[0].role == "scope_limit"
    assert "DO_NOT_COPY" not in serialized
    assert any(item.role == "scope_limit" for item in statements)


def test_g15_ac05_temporal_module_has_no_execution_authority() -> None:
    source = Path(__file__).parents[1].joinpath("src", "sunset", "temporal_epistemics.py").read_text(encoding="utf-8")
    assert "urlopen" not in source
    assert "subprocess" not in source
    assert "validate_candidate" not in source


def test_g15_ac06_external_validation_and_failure_adapters_are_structured() -> None:
    receipts = (
        {
            "invocation_id": "external-1", "tool_name": "sunset_resolve_external_reference", "status": "success",
            "repository_head": "c" * 40, "result": {"outcome": "supports_expired", "summary": "upstream fixed", "freshness_key": "recorded-v1"},
            "evidence": [], "errors": [], "uncertainties": [],
        },
        {
            "invocation_id": "validation-1", "tool_name": "sunset_validation", "status": "success",
            "repository_head": "c" * 40, "result": {"status": "confirmed"}, "evidence": [], "errors": [], "uncertainties": [],
        },
        {
            "status": "validated",
            "plan": {"plan_id": "plan-1", "candidate_id": "candidate-5", "repository_head": "c" * 40, "evidence_receipt_ids": ["external-1"]},
            "validation": {"status": "confirmed", "repository_head": "c" * 40},
        },
        {
            "invocation_id": "failure-1", "tool_name": "sunset_resolve_external_reference", "status": "error",
            "repository_head": "c" * 40, "result": {}, "evidence": [], "errors": [{"message": "provider unavailable"}], "uncertainties": [],
        },
    )
    statements = adapt_receipts(receipts, candidate_id="candidate-5")

    assert [item.source_class for item in statements] == ["external", "validation", "validation", "external"]
    assert statements[0].role == "support"
    assert statements[1].role == "scope_limit"
    assert statements[2].role == "scope_limit"
    assert statements[3].role == "missing"
    assert all(item.provenance for item in statements)


def test_contradiction_and_missing_evidence_are_successful_conservative_outcomes() -> None:
    candidate = TemporalDebtCandidate("candidate-6", "disabled_test", None, "xfail")
    hypothesis = _hypothesis(candidate.candidate_id, "h1", "condition_likely_expired")
    contradiction = _evidence(candidate.candidate_id, "e-contradict", "contradict", "h1")
    support = _evidence(candidate.candidate_id, "e-support", "support", "h1")
    assert derive_conclusion(candidate, (hypothesis,), (support, contradiction)).state == "contradictory_evidence"
    missing = _evidence(candidate.candidate_id, "e-missing", "missing", "h1")
    assert derive_conclusion(candidate, (hypothesis,), (missing,)).state == "insufficient_evidence"


@pytest.mark.parametrize("state", ["contradictory_evidence", "insufficient_evidence", "unvalidatable"])
def test_g15_ac03_conservative_terminal_states_round_trip(state: str) -> None:
    conclusion = TemporalConclusion("candidate-7", state, (), (), (), ())  # type: ignore[arg-type]
    assert TemporalConclusion.from_dict(conclusion.to_dict()).state == state
