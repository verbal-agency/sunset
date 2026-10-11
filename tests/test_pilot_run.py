from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.cli import main
from sunset.pilot_models import PilotRequest
from sunset.pilot_service import (
    CandidateResolution,
    InvestigationSummary,
    PilotService,
    PilotServiceError,
    RecordedPilotBackend,
    ValidationSummary,
)


ROOT = Path(__file__).parent / "fixtures"
BENCHMARKS = ROOT / "benchmarks"
PILOT = ROOT / "pilot"


def _request(*, validation: bool = True) -> PilotRequest:
    value = json.loads((PILOT / "g33-request-pydantic-v1.json").read_text(encoding="utf-8"))
    value["validation"]["requested"] = validation
    return PilotRequest.from_dict(value)


def _backend() -> RecordedPilotBackend:
    return RecordedPilotBackend.from_paths(
        BENCHMARKS / "g32-natural-manifest-v2.json",
        BENCHMARKS / "g32-natural-evidence-v2.json",
        BENCHMARKS / "g32-natural-report-v2.json",
        BENCHMARKS / "g32-natural-environment-v2.json",
    )


class FakeBackend:
    def __init__(self, *, outcome: str = "confirmed", fail_validation: bool = False) -> None:
        self.events: list[str] = []
        self.validation_calls = 0
        self.outcome = outcome
        self.fail_validation = fail_validation

    def prepare(self, request: PilotRequest) -> str:
        self.events.append("prepare")
        return request.repository_ref

    def resolve(self, request: PilotRequest) -> CandidateResolution:
        self.events.append("resolve")
        return CandidateResolution("candidate-1", request.repository_ref, "temporary condition", ("evidence-1",), ("artifact-1",))

    def collect_evidence(self, request: PilotRequest, candidate: CandidateResolution) -> CandidateResolution:
        self.events.append("evidence")
        return candidate

    def investigate(self, request: PilotRequest, candidate: CandidateResolution) -> InvestigationSummary:
        self.events.append("investigate")
        return InvestigationSummary("The marker protects a temporary condition.", candidate.evidence_ids, candidate.artifact_ids, ("deployment scope",))

    def validate(self, request: PilotRequest, candidate: CandidateResolution) -> ValidationSummary:
        self.events.append("validate")
        self.validation_calls += 1
        if self.fail_validation:
            raise PilotServiceError("validation_error", "recorded validator failed")
        return ValidationSummary(self.outcome, ("validation-artifact",))


def test_pilot_run_is_single_entry_point(tmp_path: Path) -> None:
    backend = FakeBackend()
    service = PilotService(backend, store=ArtifactStore(tmp_path / "store"))
    first = service.run(_request())
    second = service.run(_request())
    assert first.status == "approval_required"
    assert first.approval is not None
    assert first.next_action == "Approve disposable validation"
    assert second.to_json() == first.to_json()
    assert backend.events == ["prepare", "resolve", "evidence", "investigate"]
    assert "validate" not in backend.events


def test_pinned_setup_and_candidate_resolution(tmp_path: Path) -> None:
    service = PilotService(_backend(), store=ArtifactStore(tmp_path / "store"))
    result = service.run(_request())
    assert result.candidate_id == "g32-cce056b765e66a08"
    assert result.repository_head == "5c1f28271295bb13034f4cf8964f74c117357d40"
    bad = _request()
    with pytest.raises(ValueError, match="full 40-character"):
        PilotRequest(bad.repository_url, "main", bad.scope, bad.candidate_path, bad.candidate_test)
    missing = PilotRequest(bad.repository_url, bad.repository_ref, bad.scope, "missing.py", bad.candidate_test)
    missing_result = PilotService(_backend(), store=ArtifactStore(tmp_path / "missing")).run(missing)
    assert missing_result.status == "error"
    assert missing_result.errors[0]["kind"] == "candidate_not_found"

    live = PilotRequest(
        bad.repository_url,
        bad.repository_ref,
        bad.scope,
        bad.candidate_path,
        bad.candidate_test,
        mode="live",
    )
    live_result = PilotService(_backend(), store=ArtifactStore(tmp_path / "live")).run(live)
    assert live_result.status == "environment_error"
    assert live_result.errors[0]["kind"] == "environment_unavailable"


def test_service_owns_stage_sequence(tmp_path: Path) -> None:
    backend = FakeBackend()
    result = PilotService(backend, store=ArtifactStore(tmp_path / "store")).run(_request(validation=False))
    assert result.status == "completed"
    assert backend.events == ["prepare", "resolve", "evidence", "investigate"]
    assert result.stage_trace == ("setup", "resolve", "evidence", "investigation", "casefile")


def test_approval_token_binds_resume_and_denial_is_side_effect_free(tmp_path: Path) -> None:
    denied_backend = FakeBackend()
    denied_service = PilotService(denied_backend, store=ArtifactStore(tmp_path / "denied"))
    pending = denied_service.run(_request())
    assert pending.approval is not None
    denied = denied_service.approve(pending.run_id, pending.approval.token, decision="deny")
    assert denied.status == "denied"
    assert denied.validation_outcome is None
    assert denied_backend.validation_calls == 0

    approved_backend = FakeBackend()
    approved_service = PilotService(approved_backend, store=ArtifactStore(tmp_path / "approved"))
    pending = approved_service.run(_request())
    assert pending.approval is not None
    mismatch = approved_service.approve(pending.run_id, "wrong-token", decision="approve")
    assert mismatch.status == "approval_required"
    assert approved_backend.validation_calls == 0
    complete = approved_service.approve(pending.run_id, pending.approval.token, decision="approve")
    assert complete.status == "completed"
    assert complete.validation_outcome == "confirmed"
    assert complete.run_id == pending.run_id
    assert approved_backend.validation_calls == 1


def test_terminal_casefile_contains_required_fields(tmp_path: Path) -> None:
    service = PilotService(_backend(), store=ArtifactStore(tmp_path / "store"))
    pending = service.run(_request())
    assert pending.approval is not None
    result = service.approve(pending.run_id, pending.approval.token, decision="approve")
    assert result.case_file is not None
    case_file = result.case_file.to_dict()
    assert case_file["hypothesis"]
    assert case_file["evidence_ids"]
    assert case_file["artifact_ids"]
    assert case_file["validation_outcome"] == "confirmed"
    assert case_file["unresolved_obligations"]
    assert case_file["next_action"] == "Review bounded validation evidence"
    assert case_file["non_authority"] is True
    fixture = json.loads((PILOT / "g33-casefiles-v1.json").read_text(encoding="utf-8"))
    assert set(fixture["required_fields"]) <= set(case_file)


def test_failure_checkpoint_and_resume_preserve_artifacts(tmp_path: Path) -> None:
    backend = FakeBackend(fail_validation=True)
    service = PilotService(backend, store=ArtifactStore(tmp_path / "store"))
    pending = service.run(_request())
    assert pending.approval is not None
    failed = service.approve(pending.run_id, pending.approval.token, decision="approve")
    assert failed.status == "error"
    assert failed.evidence_ids == pending.evidence_ids
    replay = service.run(_request())
    assert replay.to_json() == failed.to_json()
    assert backend.validation_calls == 1


def test_pilot_authority_guards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("recorded pilot must not open sockets or run subprocesses")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    result = PilotService(_backend(), store=ArtifactStore(tmp_path / "store")).run(_request())
    assert result.status == "approval_required"
    assert result.non_authority is True


def test_recorded_pilot_replays_byte_identically(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    service = PilotService(_backend(), store=store)
    first = service.run(_request())
    second = service.run(_request())
    assert first.to_json() == second.to_json()
    assert store.list_views(prefix=f"sunset-pilot-v1-{first.run_id}-") == (
        f"sunset-pilot-v1-{first.run_id}-0000",
    )


def test_cli_pilot_run_and_approval(capsys, tmp_path: Path) -> None:
    store = tmp_path / "store"
    request = PILOT / "g33-request-pydantic-v1.json"
    args = [
        "pilot", "run", "--request", str(request), "--store", str(store),
        "--manifest", str(BENCHMARKS / "g32-natural-manifest-v2.json"),
        "--evidence", str(BENCHMARKS / "g32-natural-evidence-v2.json"),
        "--report", str(BENCHMARKS / "g32-natural-report-v2.json"),
        "--environment", str(BENCHMARKS / "g32-natural-environment-v2.json"),
    ]
    assert main(args) == 0
    pending = json.loads(capsys.readouterr().out)
    assert pending["status"] == "approval_required"
    approve_args = [
        "pilot", "approve", "--run-id", pending["run_id"], "--approval-token", pending["approval"]["token"],
        "--decision", "approve", "--store", str(store),
        "--manifest", str(BENCHMARKS / "g32-natural-manifest-v2.json"),
        "--evidence", str(BENCHMARKS / "g32-natural-evidence-v2.json"),
        "--report", str(BENCHMARKS / "g32-natural-report-v2.json"),
        "--environment", str(BENCHMARKS / "g32-natural-environment-v2.json"),
    ]
    assert main(approve_args) == 0
    complete = json.loads(capsys.readouterr().out)
    assert complete["status"] == "completed"
    assert complete["case_file"]["validation_outcome"] == "confirmed"
