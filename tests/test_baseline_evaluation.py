from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.baseline_evaluation import BaselineEvaluationError, evaluate_baseline, load_reference_cases


ROOT = Path(__file__).parent
MANIFEST = ROOT / "fixtures" / "adjudication" / "g23-frozen-manifest-v1.json"
TRACES = ROOT / "fixtures" / "benchmarks" / "g24-recorded-traces-v1.json"
REFERENCES = ROOT / "fixtures" / "benchmarks" / "g24-reference-cases-v1.json"


def test_g24_pairs_and_trace_schema() -> None:
    report = evaluate_baseline(MANIFEST, TRACES, REFERENCES)
    pairs = {(item["case_id"], item["mode"]) for item in report.traces}
    assert len(pairs) == 40
    assert report.metrics["case_count"] == 20
    assert {item["mode"] for item in report.traces} == {"heuristic", "agentic_recorded"}


def test_g24_reference_cases_are_pinned_and_unscored() -> None:
    references = load_reference_cases(REFERENCES)
    assert len(references) == 6
    assert all(item["commit_sha"] in item["source_url"] for item in references)
    report = evaluate_baseline(MANIFEST, TRACES, REFERENCES)
    assert report.metrics["reference_case_count"] == 6
    assert "reference_case_count" in report.metrics
    assert "reference_only" in " ".join(report.limitations)


def test_g24_manifest_binding_and_limitation() -> None:
    report = evaluate_baseline(MANIFEST, TRACES, REFERENCES)
    assert report.manifest_digest == "626d7356f20f8b0948e3450ea5c6b02988601a83685bf7670ca3cd70b751f648"
    assert any("single-reviewer" in item for item in report.limitations)
    assert len(report.split_identities["development"]) == 14
    assert len(report.split_identities["holdout"]) == 6


def test_g24_conservative_outcomes() -> None:
    report = evaluate_baseline(MANIFEST, TRACES, REFERENCES)
    agentic = report.metrics["modes"]["agentic_recorded"]
    assert agentic["run_status_counts"]["budget_exhausted"] == 1
    assert agentic["run_status_counts"]["malformed_trace"] == 1
    assert agentic["unsupported_claim_rate"] > 0
    assert agentic["condition_accuracy"] < 1
    assert all(item["run_status"] == "excluded" for item in report.traces if item["case_id"] in {"lc-openai-embedding-skip"})


def test_g24_replay_is_offline_and_byte_stable(tmp_path: Path) -> None:
    first = evaluate_baseline(MANIFEST, TRACES, REFERENCES).to_json()
    second = evaluate_baseline(MANIFEST, TRACES, REFERENCES).to_json()
    assert first == second
    output = tmp_path / "report.json"
    output.write_text(first, encoding="utf-8")
    assert json.loads(output.read_text(encoding="utf-8"))["evaluation_id"]


def test_unknown_evidence_is_rejected(tmp_path: Path) -> None:
    value = json.loads(TRACES.read_text(encoding="utf-8"))
    value["traces"][0]["evidence_ids"] = ["not-a-real-evidence-id"]
    path = tmp_path / "traces.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(BaselineEvaluationError) as exc:
        evaluate_baseline(MANIFEST, path, REFERENCES)
    assert exc.value.code == "evidence_case_mismatch"
