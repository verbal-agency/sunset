"""Deterministic comparative evaluation and predeclared release gating."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Iterable

from sunset.calibration_models import BenchmarkCase, EvaluationRun, MetricRecord, ReleaseGateResult, ReleaseThreshold


class CalibrationError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def evaluate_release(cases: Iterable[BenchmarkCase], runs: Iterable[EvaluationRun], threshold: ReleaseThreshold) -> ReleaseGateResult:
    cases = tuple(cases)
    runs = tuple(runs)
    if len({case.case_id for case in cases}) != len(cases):
        raise CalibrationError("duplicate_case_id", "duplicate benchmark case IDs are not allowed")
    if not threshold.threshold_id:
        raise CalibrationError("threshold_missing", "release thresholds must be declared before evaluation")
    by_case = {case.case_id: case for case in cases}
    if any(run.case_id not in by_case for run in runs):
        raise CalibrationError("run_case_unknown", "evaluation run references an unknown case")
    metrics: list[MetricRecord] = []
    reasons: list[str] = []
    for mode in ("heuristic", "agentic"):
        mode_runs = tuple(run for run in runs if run.mode == mode)
        valid = tuple(run for run in mode_runs if by_case[run.case_id].label.valid and run.excluded_reason is None)
        exclusions = tuple(run.excluded_reason or "invalid_label" for run in mode_runs if run not in valid)
        denominator = len(valid)
        condition_accuracy = sum(run.observed_condition_state == by_case[run.case_id].label.condition_state for run in valid) / denominator if denominator else None
        contradiction_recall = sum(run.contradiction_detected == bool(by_case[run.case_id].label.contradictions) for run in valid) / denominator if denominator else None
        proof_quality = sum(bool(set(by_case[run.case_id].label.proof_obligations) <= set(run.proof_obligations)) for run in valid) / denominator if denominator else None
        citation_accuracy = sum(run.citation_accuracy for run in valid) / denominator if denominator else None
        unsupported_rate = sum(run.unsupported_claims > 0 for run in valid) / denominator if denominator else None
        false_risk = sum(run.observed_recommendation == "eligible_for_human_cleanup" and by_case[run.case_id].historical_outcome != "removed" for run in valid) / denominator if denominator else None
        for name, value in (("condition_accuracy", condition_accuracy), ("contradiction_recall", contradiction_recall), ("proof_obligation_quality", proof_quality), ("citation_accuracy", citation_accuracy), ("unsupported_claim_rate", unsupported_rate), ("false_removal_risk", false_risk)):
            metrics.append(MetricRecord(name, mode, round(value, 4) if value is not None else None, denominator, exclusions, "labeled cases only"))
        for name, value in (("median_cost_usd", _median(run.cost_usd for run in valid)), ("median_latency_ms", _median(run.latency_ms for run in valid))):
            metrics.append(MetricRecord(name, mode, value, denominator, exclusions, "provider cost may be unavailable" if name == "median_cost_usd" else "measured"))
        if denominator / len(cases) < threshold.minimum_coverage:
            reasons.append(f"{mode} coverage below threshold")
        if condition_accuracy is None or condition_accuracy < threshold.minimum_condition_accuracy:
            reasons.append(f"{mode} condition accuracy below threshold")
        if false_risk is not None and false_risk > threshold.maximum_false_removal_risk:
            reasons.append(f"{mode} false-removal risk exceeds threshold")
        if unsupported_rate is not None and unsupported_rate > threshold.maximum_unsupported_claim_rate:
            reasons.append(f"{mode} unsupported-claim rate exceeds threshold")
    inconclusive = any(metric.denominator == 0 for metric in metrics if metric.name == "condition_accuracy")
    if inconclusive:
        reasons.append("required labeled coverage is unavailable")
    evaluation_id = hashlib.sha256(_canonical({"cases": [case.to_dict() for case in cases], "runs": [run.to_dict() for run in runs], "threshold": threshold.to_dict()})).hexdigest()
    return ReleaseGateResult(evaluation_id, threshold, tuple(metrics), not reasons and not inconclusive, inconclusive, tuple(reasons))


def _median(values: Iterable[float | int | None]) -> float | int | None:
    numbers = sorted(value for value in values if value is not None)
    if not numbers:
        return None
    middle = len(numbers) // 2
    return numbers[middle] if len(numbers) % 2 else (numbers[middle - 1] + numbers[middle]) / 2


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


__all__ = ["CalibrationError", "evaluate_release"]
