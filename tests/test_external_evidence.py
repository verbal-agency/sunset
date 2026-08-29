from __future__ import annotations

import json
from pathlib import Path
import socket
from urllib.error import URLError

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.evidence_providers import RecordedEvidenceProvider
from sunset.external_evidence import assess_assumption, extract_external_references
from sunset.external_evidence_models import ExternalReference
from sunset.investigation import InvestigationConfig, investigate_candidate
from sunset.scanner import scan_repository

from conftest import repository_snapshot, run_git


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "evidence" / "recorded_responses.json"


def _reference(number: int) -> ExternalReference:
    return ExternalReference("github", f"https://github.com/sunset-fixtures/widget/issues/{number}")


def test_explicit_versioned_release_note_retains_dependency_context() -> None:
    references = extract_external_references(
        ("changelog: widget==2.4 https://docs.sunset-fixtures.test/widget/changelog",)
    )

    assert references == (
        ExternalReference(
            "release_note",
            "https://docs.sunset-fixtures.test/widget/changelog",
            dependency_name="widget",
            dependency_version="2.4",
        ),
    )


@pytest.mark.parametrize(
    ("references", "expected_status"),
    [
        ((_reference(101),), "expired"),
        ((_reference(102),), "active"),
        ((_reference(103),), "unknown"),
        ((_reference(101), ExternalReference("release_note", "https://docs.sunset-fixtures.test/widget/changelog")), "unknown"),
    ],
)
def test_recorded_provider_classifies_fixed_open_missing_and_contradictory_evidence(
    references: tuple[ExternalReference, ...],
    expected_status: str,
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path / "store")
    assessment = assess_assumption(references, RecordedEvidenceProvider(FIXTURE_PATH), store)

    assert assessment.status == expected_status
    for resolution in assessment.resolutions:
        if resolution.artifact is not None:
            assert store.read(resolution.artifact)
            assert resolution.artifact.source_locator == resolution.reference.locator


def test_recorded_provider_reports_malformed_and_failed_fixtures_as_unknown(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"responses": [{"provider": "github"}]}', encoding="utf-8")
    store = ArtifactStore(tmp_path / "store")
    malformed_assessment = assess_assumption((_reference(101),), RecordedEvidenceProvider(malformed), store)
    failed_assessment = assess_assumption((_reference(104),), RecordedEvidenceProvider(FIXTURE_PATH), store)

    assert malformed_assessment.status == "unknown"
    assert malformed_assessment.resolutions[0].error_kind == "recorded_fixture_unavailable"
    assert failed_assessment.status == "unknown"
    assert failed_assessment.resolutions[0].error_kind == "recorded_timeout"


def _external_repository(tmp_path: Path, references: tuple[str, ...]) -> tuple[Path, str]:
    repository = tmp_path / "external-repository"
    (repository / "tests").mkdir(parents=True)
    run_git(repository, "init", "-q")
    run_git(repository, "config", "user.email", "sunset@example.test")
    run_git(repository, "config", "user.name", "Sunset Tests")
    reason = " | ".join(references)
    (repository / "tests" / "test_external.py").write_text(
        "import pytest\n\n"
        f"@pytest.mark.xfail(reason={reason!r})\n"
        "def test_external():\n"
        "    pass\n",
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-qm", "add externally documented marker")
    return repository, scan_repository(repository).candidates[0].candidate_id


def test_investigation_records_external_artifact_and_remains_inconclusive(tmp_path: Path) -> None:
    repository, candidate_id = _external_repository(tmp_path, (_reference(101).locator,))
    snapshot_before = repository_snapshot(repository)
    result = investigate_candidate(
        repository,
        store_path=tmp_path / "store",
        candidate_id=candidate_id,
        config=InvestigationConfig(evidence_mode="recorded", recorded_fixture_path=str(FIXTURE_PATH)),
    )

    assert result.status == "inconclusive"
    assert result.assumption_status == "expired"
    assert any(item.source_kind == "recorded_github_response" for item in result.selected_evidence)
    assert any(entry.node == "verify_external" and entry.evidence_ids for entry in result.ledger)
    assert "recommend removal" not in result.to_json().lower()
    assert repository_snapshot(repository) == snapshot_before


def test_unavailable_live_credentials_are_unknown_and_default_mode_never_uses_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, candidate_id = _external_repository(tmp_path, (_reference(101).locator,))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def forbid_network(*args, **kwargs):
        raise AssertionError("Sunset should not create a socket")

    monkeypatch.setattr(socket, "socket", forbid_network)
    offline = investigate_candidate(repository, store_path=tmp_path / "offline", candidate_id=candidate_id)
    live = investigate_candidate(
        repository,
        store_path=tmp_path / "live",
        candidate_id=candidate_id,
        config=InvestigationConfig(evidence_mode="live"),
    )

    assert offline.assumption_status == "unknown"
    assert live.assumption_status == "unknown"
    assert any("requires GITHUB_TOKEN" in entry.statement for entry in live.ledger)
    assert any(entry.kind == "fact" for entry in live.ledger)


def test_missing_recorded_fixture_is_visible_uncertainty(tmp_path: Path) -> None:
    repository, candidate_id = _external_repository(tmp_path, (_reference(101).locator,))
    result = investigate_candidate(
        repository,
        store_path=tmp_path / "store",
        candidate_id=candidate_id,
        config=InvestigationConfig(evidence_mode="recorded"),
    )

    assert result.assumption_status == "unknown"
    assert any("requires --recorded-evidence" in entry.statement for entry in result.ledger)


def test_live_network_failure_is_unknown_without_losing_local_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, candidate_id = _external_repository(tmp_path, (_reference(101).locator,))
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fail_request(*args, **kwargs):
        raise URLError("offline for test")

    monkeypatch.setattr("sunset.evidence_providers.urlopen", fail_request)
    result = investigate_candidate(
        repository,
        store_path=tmp_path / "store",
        candidate_id=candidate_id,
        config=InvestigationConfig(evidence_mode="live"),
    )

    assert result.assumption_status == "unknown"
    assert any("lookup failed" in entry.statement for entry in result.ledger)
    assert any(entry.kind == "fact" for entry in result.ledger)


def test_changed_recorded_input_invalidates_the_view_but_reuses_identical_artifact(tmp_path: Path) -> None:
    repository, candidate_id = _external_repository(tmp_path, (_reference(101).locator,))
    fixture = tmp_path / "responses.json"
    fixture.write_bytes(FIXTURE_PATH.read_bytes())
    store = ArtifactStore(tmp_path / "store")
    config = InvestigationConfig(evidence_mode="recorded", recorded_fixture_path=str(fixture))
    first = investigate_candidate(repository, store_path=store.root, candidate_id=candidate_id, config=config, artifact_store=store)
    writes_before = store.artifact_write_count
    views_before = store.view_write_count
    repeated = investigate_candidate(repository, store_path=store.root, candidate_id=candidate_id, config=config, artifact_store=store)
    assert repeated.run_id == first.run_id
    assert store.artifact_write_count == writes_before
    assert store.view_write_count == views_before
    fixture_value = json.loads(fixture.read_text(encoding="utf-8"))
    fixture_value["responses"].append(
        {"provider": "github", "locator": "https://github.com/sunset-fixtures/widget/issues/999", "outcome": "missing"}
    )
    fixture.write_text(json.dumps(fixture_value), encoding="utf-8")
    second = investigate_candidate(
        repository,
        store_path=store.root,
        candidate_id=candidate_id,
        config=InvestigationConfig(evidence_mode="recorded", recorded_fixture_path=str(fixture)),
        artifact_store=store,
    )

    assert first.run_id != second.run_id
    assert first.checkpoint_id != second.checkpoint_id
    assert store.artifact_write_count == writes_before
    assert store.view_write_count > views_before
