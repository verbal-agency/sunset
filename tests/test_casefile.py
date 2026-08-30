from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.casefile import build_case_file
from sunset.casefile_models import CaseFileError
from sunset.cli import main
from sunset.investigation_models import InvestigationResult, LedgerEntry, TokenBaseline
from sunset.validation_models import CommandRun, EnvironmentManifest, ValidationResult


def _investigation(
    artifact_id: str,
    *,
    assumption_status: str = "expired",
    ledger_kind: str = "fact",
    evidence_ids: tuple[str, ...] | None = None,
) -> InvestigationResult:
    return InvestigationResult(
        assumption_status=assumption_status,
        candidate_id="sunset-v1-casefile",
        checkpoint_id="checkpoint",
        collector="pytest",
        errors=(),
        ledger=(
            LedgerEntry(
                claim_id="rationale",
                kind=ledger_kind,
                statement="The recorded rationale supports a bounded conclusion.",
                evidence_ids=evidence_ids if evidence_ids is not None else (artifact_id,),
                node="summarize_core",
            ),
        ),
        open_questions=("A maintainer must still assess downstream callers.",),
        repository_head="a" * 40,
        run_id="run",
        selected_evidence=(),
        status="inconclusive",
        token_baseline=TokenBaseline(100, 20, 40),
        token_usage=(),
    )


def _validation(artifact, *, status: str = "confirmed") -> ValidationResult:
    return ValidationResult(
        approved=True,
        candidate_id="sunset-v1-casefile",
        collector="pytest",
        environment=EnvironmentManifest(artifact=artifact, fingerprint="fixture"),
        errors=(),
        repository_head="a" * 40,
        runs=(
            CommandRun(
                command=("python", "-m", "pytest"),
                phase="narrow",
                attempt=1,
                return_code=0 if status == "confirmed" else 1,
                output=artifact,
            ),
        ),
        status=status,
    )


def test_casefile_reloads_citations_and_renders_required_safety_boundary(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    artifact = store.put(b"recorded raw evidence", media_type="text/plain", source_kind="fixture", source_locator="fixture")

    result = build_case_file(_investigation(artifact.artifact_id), store_path=store.root, validation=_validation(artifact))

    assert result.recommendation == "eligible_for_human_cleanup"
    assert result.claims[0].citations[0].artifact_id == artifact.artifact_id
    assert result.claims[0].citations[0].digest == artifact.digest
    rendered_json = result.to_dict()
    assert rendered_json["validation_status"] == "confirmed"
    assert rendered_json["claims"][0]["citations"][0]["artifact_id"] == artifact.artifact_id
    markdown = result.to_markdown()
    assert artifact.artifact_id in markdown
    assert "not proof that deletion is safe" in markdown
    assert "No target repository was changed" in markdown


@pytest.mark.parametrize(
    ("assumption_status", "ledger_kind", "validation_status", "expected"),
    [
        ("active", "fact", "confirmed", "retain"),
        ("unknown", "fact", "confirmed", "inconclusive"),
        ("expired", "contradiction", "confirmed", "inconclusive"),
        ("expired", "fact", "still_failing", "retain"),
    ],
)
def test_skeptical_review_blocks_unsafe_eligibility(
    tmp_path: Path,
    assumption_status: str,
    ledger_kind: str,
    validation_status: str,
    expected: str,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    artifact = store.put(b"recorded raw evidence", media_type="text/plain", source_kind="fixture", source_locator="fixture")

    result = build_case_file(
        _investigation(artifact.artifact_id, assumption_status=assumption_status, ledger_kind=ledger_kind),
        store_path=store.root,
        validation=_validation(artifact, status=validation_status),
    )

    assert result.recommendation == expected
    assert any(finding.blocking for finding in result.review_findings)
    if ledger_kind == "contradiction":
        assert any(finding.kind == "evidence_conflict" for finding in result.review_findings)


def test_uncited_or_missing_material_claim_refuses_to_render(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    artifact = store.put(b"recorded raw evidence", media_type="text/plain", source_kind="fixture", source_locator="fixture")

    with pytest.raises(CaseFileError, match="no cited artifact") as uncited:
        build_case_file(_investigation(artifact.artifact_id, evidence_ids=()), store_path=store.root)
    with pytest.raises(CaseFileError, match="cannot resolve") as missing:
        build_case_file(
            _investigation("sha256:" + "0" * 64),
            store_path=store.root,
        )

    assert uncited.value.code == "claim_uncited"
    assert missing.value.code == "citation_unresolved"


def test_tampered_raw_artifact_refuses_to_render(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    artifact = store.put(b"recorded raw evidence", media_type="text/plain", source_kind="fixture", source_locator="fixture")
    store.artifact_path(artifact).write_bytes(b"tampered evidence")

    with pytest.raises(CaseFileError, match="artifact_integrity_error") as failure:
        build_case_file(_investigation(artifact.artifact_id), store_path=store.root)

    assert failure.value.code == "citation_unresolved"


def test_casefile_cli_reads_saved_results_without_network_or_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    artifact = store.put(b"recorded raw evidence", media_type="text/plain", source_kind="fixture", source_locator="fixture")
    investigation_path = tmp_path / "investigation.json"
    validation_path = tmp_path / "validation.json"
    investigation_path.write_text(_investigation(artifact.artifact_id).to_json(), encoding="utf-8")
    validation_path.write_text(_validation(artifact).to_json(), encoding="utf-8")

    def no_network(*args, **kwargs):
        raise AssertionError("casefile must not access the network")

    monkeypatch.setattr("socket.create_connection", no_network)
    exit_code = main(
        [
            "casefile", "--investigation-result", str(investigation_path),
            "--validation-result", str(validation_path), "--store", str(store.root),
            "--format", "markdown",
        ]
    )

    rendered = capsys.readouterr().out
    assert exit_code == 0
    assert "# Sunset case file" in rendered
    assert artifact.artifact_id in rendered


def test_casefile_cli_returns_structured_error_for_uncited_claim(tmp_path: Path, capsys) -> None:
    investigation_path = tmp_path / "investigation.json"
    investigation_path.write_text(_investigation("sha256:" + "0" * 64, evidence_ids=()).to_json(), encoding="utf-8")

    exit_code = main(
        ["casefile", "--investigation-result", str(investigation_path), "--store", str(tmp_path / "store")]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["kind"] == "claim_uncited"
