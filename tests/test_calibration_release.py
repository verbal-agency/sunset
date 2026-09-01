from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.calibration import CalibrationError, evaluate_release
from sunset.calibration_models import BenchmarkCase, EvaluationRun, ExpectedConditionLabel, ReleaseThreshold


FIXTURE = Path(__file__).parent / "fixtures" / "calibration" / "g20-cases.json"


def _cases() -> tuple[BenchmarkCase, ...]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return tuple(BenchmarkCase.from_dict(item) for item in payload["cases"])


def _runs(mode: str) -> tuple[EvaluationRun, ...]:
    return (
        EvaluationRun("expired-1", mode, "condition_likely_expired", "eligible_for_human_cleanup", False, ("customer inventory",), 1.0, 0, 0.01, 10, f"trace-{mode}-1"),
        EvaluationRun("active-1", mode, "condition_likely_active", "retain", True, (), 1.0, 0, 0.01, 12, f"trace-{mode}-2"),
    )


def test_g20_ac01_case_integrity() -> None:
    cases = _cases()
    assert BenchmarkCase.from_dict(cases[0].to_dict()).to_dict() == cases[0].to_dict()
    assert cases[0].label.evidence_scope == ("external", "operational")


def test_g20_ac02_comparable_evaluation() -> None:
    threshold = ReleaseThreshold("t1", minimum_coverage=1.0, minimum_condition_accuracy=1.0)
    result = evaluate_release(_cases(), _runs("heuristic") + _runs("agentic"), threshold)
    assert {metric.mode for metric in result.metrics} == {"heuristic", "agentic"}
    assert all(metric.denominator == 2 for metric in result.metrics)


def test_g20_ac03_calibration_and_risk_metrics() -> None:
    result = evaluate_release(_cases(), _runs("agentic"), ReleaseThreshold("t1"))
    names = {metric.name for metric in result.metrics}
    assert {"condition_accuracy", "contradiction_recall", "proof_obligation_quality", "citation_accuracy", "unsupported_claim_rate", "false_removal_risk", "median_cost_usd", "median_latency_ms"} <= names


def test_g20_ac04_threshold_gate() -> None:
    result = evaluate_release(_cases(), _runs("heuristic") + _runs("agentic"), ReleaseThreshold("t1", minimum_condition_accuracy=1.0))
    assert result.passed is True
    invalid = BenchmarkCase("invalid", "unknown", "unknown", ExpectedConditionLabel("x", "y", valid=False), "unknown")
    incomplete = evaluate_release((invalid,), (), ReleaseThreshold("t2", minimum_coverage=1.0))
    assert incomplete.inconclusive is True
    with pytest.raises(CalibrationError, match="duplicate"):
        evaluate_release(_cases() + (_cases()[0],), _runs("agentic"), ReleaseThreshold("t3"))


def test_g20_ac05_replay_and_privacy() -> None:
    threshold = ReleaseThreshold("t1")
    first = evaluate_release(_cases(), _runs("agentic"), threshold)
    second = evaluate_release(_cases(), _runs("agentic"), threshold)
    assert first.to_json() == second.to_json()
    assert "credential" not in first.to_json().lower()
    assert "payload" not in first.to_json().lower()


def test_g20_ac06_verification() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G20-calibration-release.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert all(f"G20-AC0{i}" in text for i in range(1, 7))
