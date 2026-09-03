from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.optimization import OptimizationError, run_optimization


ROOT = Path(__file__).parent
BASELINE = ROOT / "fixtures" / "benchmarks" / "g24-baseline-report-v1.json"
EXPERIMENTS = ROOT / "fixtures" / "benchmarks" / "g25-experiments-v1.json"


def test_preregistration_and_status_rules() -> None:
    report = run_optimization(BASELINE, EXPERIMENTS)
    assert report.selected_experiment_id == "g25-prompt-001"
    statuses = {item["experiment_id"]: item["status"] for item in report.experiments}
    assert statuses["g25-prompt-001"] == "selected"
    assert statuses["g25-threshold-002"] == "rejected"


def test_development_selection_is_split_safe() -> None:
    report = run_optimization(BASELINE, EXPERIMENTS)
    assert report.selected_experiment_id == "g25-prompt-001"
    assert report.holdout and report.holdout["status"] == "holdout_sealed"
    assert report.holdout["experiment_id"] == report.selected_experiment_id


def test_holdout_is_sealed_and_append_only() -> None:
    report = run_optimization(BASELINE, EXPERIMENTS)
    assert report.holdout["case_ids"] == sorted(report.holdout["case_ids"])
    assert report.holdout["case_ids"] == sorted(["lc-openai-embedding-skip", "lg-dataclass-version-shim", "ls-promise-error-shim", "ls-prompt-test-skip", "ls-type-alias-version-shim", "ls-union-version-shim"])


def test_optimization_error_taxonomy() -> None:
    report = run_optimization(BASELINE, EXPERIMENTS)
    rejected = {item["experiment_id"]: item.get("rejection_reason") for item in report.experiments}
    assert rejected["g25-retrieval-003"] == "malformed_trace"
    assert rejected["g25-tool-004"] == "budget_exhausted"
    assert rejected["g25-threshold-002"] == "safety_or_budget_regression"


def test_optimization_replay_is_offline(tmp_path: Path) -> None:
    first = run_optimization(BASELINE, EXPERIMENTS).to_json()
    second = run_optimization(BASELINE, EXPERIMENTS).to_json()
    assert first == second
    path = tmp_path / "optimization.json"
    path.write_text(first, encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["optimization_id"]


def test_holdout_binding_rejects_mismatch(tmp_path: Path) -> None:
    value = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
    value["experiments"][0]["holdout_digest"] = "0" * 64
    path = tmp_path / "experiments.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(OptimizationError) as exc:
        run_optimization(BASELINE, path)
    assert exc.value.code == "experiment_binding_invalid"
