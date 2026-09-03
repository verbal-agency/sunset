from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.adjudication import (
    AdjudicationError,
    evidence_ids_from_files,
    freeze_adjudication,
    load_authority,
    load_decisions,
    load_exclusions,
)
from sunset.validation_corpus import load_validation_corpus


ROOT = Path(__file__).parent
CORPUS = ROOT / "fixtures" / "validation_corpus" / "langchain-validation-v1.json"
AUTHORITY = ROOT / "fixtures" / "adjudication" / "g23-authority-v1.json"
DECISIONS = ROOT / "fixtures" / "adjudication" / "g23-decisions-v1.json"
EVIDENCE = (
    ROOT / "fixtures" / "git_evidence" / "g22a-langchain-real-v1.json",
    ROOT / "fixtures" / "git_evidence" / "g22b-langchain-support-v1.json",
    ROOT / "fixtures" / "git_evidence" / "g22c-langgraph-support-v1.json",
)


def test_g23_freezes_single_reviewer_manifest_with_explicit_coverage() -> None:
    corpus = load_validation_corpus(CORPUS)
    authority = load_authority(AUTHORITY)
    decisions = load_decisions(DECISIONS)
    exclusions = load_exclusions(DECISIONS)
    frozen = freeze_adjudication(
        corpus,
        authority,
        decisions,
        excluded_cases=exclusions,
        evidence_ids=evidence_ids_from_files(EVIDENCE),
    )

    assert len(frozen.decisions) == 5
    assert len(frozen.excluded_cases) == 15
    assert frozen.review_mode == "single_reviewer"
    assert frozen.second_review_status == "not_available"
    assert frozen.manifest_digest and len(frozen.manifest_digest) == 64
    assert set(frozen.split_identities) == {"development", "holdout", "excluded"}
    assert len(frozen.split_identities["development"]) + len(frozen.split_identities["holdout"]) == 20
    assert {item.condition_status for item in frozen.decisions} == {"likely_expired", "unknown", "active"}
    assert all(item.proof_obligations for item in frozen.decisions)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value["decisions"].append(value["decisions"][0].copy()), "duplicate_case_id"),
        (lambda value: value["decisions"][0].update({"evidence_ids": ["missing"]}), "evidence_not_found"),
        (lambda value: value["decisions"][0].update({"historical_outcome": "removed"}), "decisions_invalid"),
        (lambda value: value["decisions"][0].update({"proof_obligations": []}), "proof_obligations_missing"),
        (lambda value: value["decisions"][0].update({"evidence_ids": ["lc-stream-cache-xfail:history"]}), "evidence_case_mismatch"),
    ],
)
def test_g23_rejects_malformed_or_unsafe_decisions(tmp_path: Path, mutation, code: str) -> None:
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    mutation(payload)
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    corpus = load_validation_corpus(CORPUS)
    authority = load_authority(AUTHORITY)
    if code == "decisions_invalid":
        with pytest.raises(AdjudicationError, match="unknown decision field") as caught:
            load_decisions(path)
    else:
        with pytest.raises(AdjudicationError) as caught:
            freeze_adjudication(
                corpus,
                authority,
                load_decisions(path),
                excluded_cases=load_exclusions(DECISIONS),
                evidence_ids=evidence_ids_from_files(EVIDENCE),
            )
    assert caught.value.code == code


def test_g23_rejects_incomplete_coverage(tmp_path: Path) -> None:
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    payload["excluded_cases"] = payload["excluded_cases"][:-1]
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AdjudicationError) as caught:
        freeze_adjudication(
            load_validation_corpus(CORPUS),
            load_authority(AUTHORITY),
            load_decisions(path),
            excluded_cases=load_exclusions(path),
            evidence_ids=evidence_ids_from_files(EVIDENCE),
        )
    assert caught.value.code == "coverage_incomplete"


def test_g23_preserves_contradictory_status_and_exclusion_reason(tmp_path: Path) -> None:
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    payload["decisions"][0]["condition_status"] = "contradictory"
    payload["decisions"][0]["evidence_sufficiency"] = "contradictory"
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    frozen = freeze_adjudication(
        load_validation_corpus(CORPUS),
        load_authority(AUTHORITY),
        load_decisions(path),
        excluded_cases=load_exclusions(path),
        evidence_ids=evidence_ids_from_files(EVIDENCE),
    )
    decision = next(item for item in frozen.decisions if item.case_id == "lc-python39-removeprefix-shim")
    assert decision.condition_status == "contradictory"
    assert decision.evidence_sufficiency == "contradictory"
    assert any(item["reason"] == "not_adjudicated_in_this_pass" for item in frozen.excluded_cases)
