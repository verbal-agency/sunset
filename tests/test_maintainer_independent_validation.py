from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.independent_validation import (
    IndependentValidationError,
    build_report,
    digest,
    report_json,
    validate_manifest,
    validate_negative_cases,
    validate_runs,
)
from sunset.pilot_models import PilotRequest
from sunset.pilot_service import InvestigationSummary, PilotService, RecordedPilotBackend


ROOT = Path(__file__).parent / "fixtures"
BENCHMARKS = ROOT / "benchmarks"
PILOT = ROOT / "pilot"


def _load(name: str) -> dict:
    return json.loads((BENCHMARKS / name).read_text(encoding="utf-8"))


def _backend() -> RecordedPilotBackend:
    return RecordedPilotBackend.from_paths(
        BENCHMARKS / "g32-natural-manifest-v2.json",
        BENCHMARKS / "g32-natural-evidence-v2.json",
        BENCHMARKS / "g32-natural-report-v2.json",
        BENCHMARKS / "g32-natural-environment-v2.json",
    )


def _request(*, validation: bool) -> PilotRequest:
    value = json.loads((PILOT / "g33-request-pydantic-v1.json").read_text(encoding="utf-8"))
    value["validation"]["requested"] = validation
    return PilotRequest.from_dict(value)


class _HeuristicBackend(RecordedPilotBackend):
    def investigate(self, request: PilotRequest, candidate):  # type: ignore[no-untyped-def]
        return InvestigationSummary(
            hypothesis=f"Heuristic marker-condition hypothesis: {candidate.hypothesis}",
            evidence_ids=candidate.evidence_ids,
            artifact_ids=candidate.artifact_ids,
            unresolved_obligations=("Protected condition remains unadjudicated.",),
        )


def test_g37_manifest_and_receipts_are_exact_sha_and_complete() -> None:
    manifest = _load("g37-independent-manifest-v1.json")
    runs = _load("g37-independent-runs-v1.json")
    cases = validate_manifest(manifest)
    receipts = validate_runs(runs, (case["case_id"] for case in cases))
    assert len(cases) == 9
    assert {run["mode"] for run in receipts} == {"heuristic", "agentic_recorded"}
    assert all(run["target_unchanged"] is True for run in receipts)
    assert all(case["label_provenance"] != "human_adjudicated" for case in cases)


def test_g37_report_binds_inputs_and_preserves_label_limits() -> None:
    manifest = _load("g37-independent-manifest-v1.json")
    runs = _load("g37-independent-runs-v1.json")
    report = _load("g37-independent-report-v1.json")
    assert report["manifest_digest"] == digest(manifest)
    assert report["run_digest"] == digest(runs)
    assert report["mechanical_correctness"]["complete_receipts"] == 18
    assert report["mechanical_correctness"]["target_unchanged_receipts"] == 18
    assert report["historical_agreement"]["label_provenance"] == "historical_proxy"
    assert report["non_authority"] is True
    text = report_json(report).lower()
    assert "human-confirmed" not in text
    assert "safe-to-remove" not in text
    assert any("not proof" in item.lower() for item in report["limitations"])
    assert report["negative_case_coverage"]["contradictory"] == "contradictory_evidence"


def test_g37_report_rebuilds_byte_identically() -> None:
    manifest = _load("g37-independent-manifest-v1.json")
    runs = _load("g37-independent-runs-v1.json")
    rebuilt = build_report(
        manifest,
        runs,
        g32_report=_load("g32-natural-report-v2.json"),
        g34_cases=_load("../backtest/g34-cases-v1.json"),
        g34_runs=_load("../backtest/g34-runs-v1.json"),
        replay_byte_identical=True,
    )
    stored = _load("g37-independent-report-v1.json")
    assert report_json(rebuilt) == report_json(stored)
    assert report_json(json.loads(report_json(rebuilt))) == report_json(rebuilt)


def test_g37_g33_paths_execute_heuristic_and_recorded_agentic_without_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The service is the G33 single-entry boundary; the recorded backend makes
    # this test offline and prevents target checkout access.
    def forbidden(*args, **kwargs):
        raise AssertionError("recorded G37 replay must not open sockets or run subprocesses")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    heuristic_backend = _HeuristicBackend.from_paths(
        BENCHMARKS / "g32-natural-manifest-v2.json",
        BENCHMARKS / "g32-natural-evidence-v2.json",
        BENCHMARKS / "g32-natural-report-v2.json",
        BENCHMARKS / "g32-natural-environment-v2.json",
    )
    heuristic = PilotService(heuristic_backend, store=ArtifactStore(tmp_path / "heuristic"))
    heuristic_result = heuristic.run(_request(validation=False))
    assert heuristic_result.status == "completed"
    assert heuristic_result.stage_trace == ("setup", "resolve", "evidence", "investigation", "casefile")

    agentic = PilotService(_backend(), store=ArtifactStore(tmp_path / "agentic"))
    pending = agentic.run(_request(validation=True))
    assert pending.status == "approval_required"
    assert pending.approval is not None
    approved = agentic.approve(pending.run_id, pending.approval.token, decision="approve")
    assert approved.status == "completed"
    assert approved.validation_outcome == "confirmed"
    assert approved.case_file is not None and approved.case_file.non_authority is True


def test_g37_fail_closed_cases_and_reviewer_boundary(tmp_path: Path) -> None:
    manifest = _load("g37-independent-manifest-v1.json")
    moving = json.loads(json.dumps(manifest))
    moving["cases"][0]["pinned_ref"] = "main"
    with pytest.raises(IndependentValidationError) as moving_error:
        validate_manifest(moving)
    assert moving_error.value.code == "pinned_ref_invalid"

    runs = _load("g37-independent-runs-v1.json")
    malformed = json.loads(json.dumps(runs))
    malformed["runs"][0]["stage_trace"] = ["setup"]
    with pytest.raises(IndependentValidationError) as malformed_error:
        validate_runs(malformed, (case["case_id"] for case in manifest["cases"]))
    assert malformed_error.value.code == "stage_trace_incomplete"

    live = _backend()
    result = PilotService(live, store=ArtifactStore(tmp_path / "live-guard")).run(
        PilotRequest(
            "https://github.com/langchain-ai/langchain",
            "5c1f28271295bb13034f4cf8964f74c117357d40",
            "libs/core/tests/unit_tests",
            "utils/test_function_calling.py",
            "test_convert_to_openai_function_nested_v2",
            mode="live",
        )
    )
    assert live is not None
    assert result.status == "environment_error"


def test_g37_negative_matrix_covers_contradiction_and_holdout_rules() -> None:
    negative = json.loads((BENCHMARKS / "g37-independent-negative-v1.json").read_text(encoding="utf-8"))
    cases = validate_negative_cases(negative)
    assert {case["kind"] for case in cases} == {
        "contradictory", "malformed", "moving_ref", "unavailable_runtime", "holdout",
    }
    assert negative["cases"][0]["evidence_roles"] == ["support", "contradict"]
