from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.natural_corpus import (
    NaturalCorpusError,
    assemble_natural_report,
    audit_natural_corpus,
    derive_case_id,
    load_environment_recipes,
    load_evidence_records,
    load_natural_manifest,
    load_natural_report,
    report_json,
    validate_natural_report,
)


ROOT = Path(__file__).parent / "fixtures" / "benchmarks"
MANIFEST = ROOT / "g32-natural-manifest-v2.json"
ENVIRONMENT = ROOT / "g32-natural-environment-v2.json"
EVIDENCE = ROOT / "g32-natural-evidence-v2.json"
REPORT = ROOT / "g32-natural-report-v2.json"


def _inputs():
    return (
        load_natural_manifest(MANIFEST),
        load_environment_recipes(ENVIRONMENT),
        load_evidence_records(EVIDENCE),
        load_natural_report(REPORT),
    )


def test_manifest_binds_exact_refs_and_ids(tmp_path: Path) -> None:
    manifest, _, _, _ = _inputs()
    assert all(len(case.pinned_ref) == 40 for case in manifest.cases)
    assert all(case.case_id == derive_case_id(case.repository_url, case.pinned_ref, case.candidate_selector) for case in manifest.cases)
    malformed = manifest.to_dict()
    malformed["cases"][0]["pinned_ref"] = "main"  # type: ignore[index]
    path = tmp_path / "moving.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(NaturalCorpusError) as exc_info:
        load_natural_manifest(path)
    assert exc_info.value.code == "pinned_ref_invalid"


def test_environment_recipe_is_recorded_or_excluded() -> None:
    manifest, environments, evidence, _ = _inputs()
    audit = audit_natural_corpus(manifest, environments, evidence)
    assert audit.status == "passed"
    assert len(audit.eligible_case_ids) == 9
    assert all(case.environment_id in environments for case in manifest.cases if case.status == "ready")
    missing = dict(environments)
    missing.pop("langchain-core-py312-v1")
    rejected = audit_natural_corpus(manifest, missing, evidence)
    assert rejected.status == "rejected"
    assert "environment_missing:g32-589db1fd98e48fd5" in rejected.errors


def test_vetted_disposable_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, environments, evidence, report = _inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("natural corpus audit must not clone, network, or execute code")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    audit = audit_natural_corpus(manifest, environments, evidence, report=report)
    assert audit.status == "passed"
    assert manifest.allowed_repository_urls == ("https://github.com/langchain-ai/langchain",)
    assert report["recall_audit"]["cases"][0]["target_unchanged"] is True


def test_non_conclusive_outcomes_are_not_labels() -> None:
    manifest, _, _, report = _inputs()
    malformed = json.loads(json.dumps(report))
    item = next(case for case in malformed["cases"] if case["case_id"] == "g32-589db1fd98e48fd5")
    item["validation_outcome"] = "flaky"
    item["empirical_status"] = "likely_active"
    errors = validate_natural_report(malformed, manifest)
    assert "empirical_status_mismatch:g32-589db1fd98e48fd5" in errors


def test_split_audit_rejects_holdout_tuning() -> None:
    manifest, environments, evidence, _ = _inputs()
    holdout = next(case.case_id for case in manifest.cases if case.split == "holdout")
    audit = audit_natural_corpus(manifest, environments, evidence, holdout_tuning_case_ids=(holdout,))
    assert audit.status == "rejected"
    assert "holdout_tuning_case_id_present" in audit.errors


def test_natural_report_contains_bias_and_recall_audit() -> None:
    manifest, _, _, report = _inputs()
    assert validate_natural_report(report, manifest) == ()
    assert report["selection_bias"]
    assert report["unsupported_claims"]
    assert report["recall_audit"]["status"] == "executed"
    assert report["recall_audit"]["sample_case_ids"] == ["g32-83ad2c68381b36e9"]


def test_recorded_report_assembly_binds_source_cases() -> None:
    manifest, _, _, _ = _inputs()
    source = json.loads((ROOT / "g30-natural-report-v1.json").read_text(encoding="utf-8"))
    recall = {"status": "executed", "sample_case_ids": ["g32-83ad2c68381b36e9"]}
    assembled = assemble_natural_report(manifest, source, recall_audit=recall)
    assert len(assembled["cases"]) == 9
    assert {item["source_case_id"] for item in assembled["cases"]} == {case.source_case_id for case in manifest.cases}
    assert validate_natural_report(assembled, manifest) == ()


def test_recorded_report_replays_byte_identically(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, environments, evidence, report = _inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("recorded corpus replay must remain offline")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    first = report_json(report)
    second = report_json(json.loads(first))
    assert first == second
    assert audit_natural_corpus(manifest, environments, evidence, report=report).to_json() == audit_natural_corpus(manifest, environments, evidence, report=report).to_json()
