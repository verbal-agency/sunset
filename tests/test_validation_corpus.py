from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.cli import main
from sunset.validation_corpus import ValidationCorpusError, audit_validation_corpus, load_validation_corpus


FIXTURE = Path(__file__).parent / "fixtures" / "validation_corpus" / "langchain-validation-v1.json"
PUBLIC_FIXTURE = Path(__file__).parent / "fixtures" / "public_corpus" / "langchain-ecosystem-v1.json"


def _payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object], name: str = "case.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_g21_ac01_schema_integrity(tmp_path: Path) -> None:
    corpus = load_validation_corpus(FIXTURE)
    assert len(corpus.cases) == 20
    malformed = _payload()
    malformed["cases"][0]["packet_state"] = "adjudicated"  # type: ignore[index]
    with pytest.raises(ValidationCorpusError) as exc_info:
        load_validation_corpus(_write_payload(tmp_path, malformed))
    assert exc_info.value.code == "packet_state_invalid"

    duplicate = _payload()
    duplicate["cases"][1]["case_id"] = duplicate["cases"][0]["case_id"]  # type: ignore[index]
    with pytest.raises(ValidationCorpusError) as exc_info:
        load_validation_corpus(_write_payload(tmp_path, duplicate, "duplicate.json"))
    assert exc_info.value.code == "duplicate_case_id"


def test_g21_ac02_provenance_and_non_inference() -> None:
    corpus = load_validation_corpus(FIXTURE)
    public = json.loads(PUBLIC_FIXTURE.read_text(encoding="utf-8"))
    assert {case.source_case_id for case in corpus.cases} == {item["case_id"] for item in public["cases"]}
    assert {case.historical_outcome for case in corpus.cases} == {"removed", "retained"}
    assert all(not hasattr(case, "condition_state") for case in corpus.cases)
    assert all("model_prediction" not in case.to_dict() for case in corpus.cases)
    assert all("prediction" not in case.to_dict() for case in corpus.cases)


def test_g21_ac03_split_and_exclusion_control(tmp_path: Path) -> None:
    corpus = load_validation_corpus(FIXTURE)
    assert {case.split for case in corpus.cases} == {"development", "holdout"}
    assert all(case.packet_state != "excluded" for case in corpus.cases)
    leaked = _payload()
    leaked["cases"][0]["prediction"] = "eligible"  # type: ignore[index]
    with pytest.raises(ValidationCorpusError):
        load_validation_corpus(_write_payload(tmp_path, leaked, "leaked.json"))

    excluded = _payload()
    excluded["cases"][0]["split"] = "excluded"  # type: ignore[index]
    excluded["cases"][0]["packet_state"] = "excluded"  # type: ignore[index]
    excluded["cases"][0]["exclusion_reason"] = "source unavailable"  # type: ignore[index]
    assert audit_validation_corpus(load_validation_corpus(_write_payload(tmp_path, excluded, "excluded.json"))).excluded_cases


def test_g21_ac04_deterministic_audit(capsys) -> None:
    corpus = load_validation_corpus(FIXTURE)
    first = audit_validation_corpus(corpus)
    second = audit_validation_corpus(corpus)
    assert first.to_json() == second.to_json()
    assert first.complete is True
    assert first.gate_ready is False
    limited = audit_validation_corpus(corpus, max_cases=3)
    assert limited.complete is False
    assert len(limited.processed_case_ids) == 3
    assert len(limited.unprocessed_case_ids) == 17
    assert main(["validation-corpus", "audit", "--manifest", str(FIXTURE)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["gate_ready"] is False
    assert report["counts"]["split"] == {"development": 14, "holdout": 6}


def test_g21_ac05_offline_safety_and_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("validation corpus audit must remain offline")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    corpus = load_validation_corpus(FIXTURE)
    first = audit_validation_corpus(corpus)
    changed = _payload()
    changed["corpus_id"] = "sunset-validation-v2"
    second = audit_validation_corpus(load_validation_corpus(_write_payload(tmp_path, changed, "changed.json")))
    assert first.corpus_digest != second.corpus_digest
    assert "payload" not in first.to_json().lower()
    assert "credential" not in first.to_json().lower()


def test_g21_ac06_verification() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["schema_version"] == "1"
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G21-validation-corpus-protocol.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert all(f"G21-AC0{i}" in text for i in range(1, 7))
    validation_doc = Path(__file__).parents[1] / "docs" / "VALIDATION.md"
    assert "not contain protected-condition ground truth" in validation_doc.read_text(encoding="utf-8")
