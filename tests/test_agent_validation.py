from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time
from typing import Any

import pytest

from sunset.agent_tool_models import ToolReceipt
from sunset.agent_tools import PROVENANCE_TOOL, ToolExecutionContext, create_tool_registry
from sunset.agent_validation import AgentValidationGate, ValidationApproval, build_validation_plan
from sunset.scanner import scan_repository
from sunset.validation_models import ValidationResult

from conftest import repository_snapshot, run_git


def _repository(tmp_path: Path, body: str = "assert True") -> tuple[Path, str]:
    repository = tmp_path / "repository"; (repository / "tests").mkdir(parents=True)
    run_git(repository, "init", "-q"); run_git(repository, "config", "user.email", "sunset@example.test"); run_git(repository, "config", "user.name", "Sunset Tests")
    (repository / "tests" / "test_marker.py").write_text(
        f"import pytest\n\n@pytest.mark.xfail(reason='upstream')\ndef test_candidate():\n    {body}\n", encoding="utf-8"
    )
    run_git(repository, "add", "."); run_git(repository, "commit", "-qm", "fixture")
    return repository, scan_repository(repository).candidates[0].candidate_id


def _context_and_receipt(repository: Path, store: Path) -> tuple[ToolExecutionContext, ToolReceipt]:
    context = ToolExecutionContext.create(repository, store_path=store)
    candidate_id = scan_repository(repository).candidates[0].candidate_id
    receipt = ToolReceipt.from_dict(create_tool_registry(context).by_name(PROVENANCE_TOOL).invoke({"candidate_id": candidate_id})["receipt"])
    return context, receipt


def _approval(plan_id: str, decision: str = "approve", *, expires_at: float | None = None) -> ValidationApproval:
    return ValidationApproval("human-decision-1", plan_id, decision, expires_at if expires_at is not None else time.time() + 60)  # type: ignore[arg-type]


def test_plan_is_deterministic_reviewable_and_receipt_derived(tmp_path: Path) -> None:
    repository, _ = _repository(tmp_path)
    context, receipt = _context_and_receipt(repository, tmp_path / "store")
    first = build_validation_plan(context, (receipt,))
    second = build_validation_plan(context, (receipt,))

    assert first == second
    assert first.candidate_id == receipt.result["candidate"]["candidate_id"]
    assert first.repository_head == context.repository.head
    assert first.evidence_receipt_ids == (receipt.invocation_id,)
    assert first.validation_config["repeat_count"] == 2


@pytest.mark.parametrize("decision", [None, "deny"])
def test_no_valid_approval_never_invokes_validator_or_changes_target(tmp_path: Path, decision: str | None) -> None:
    repository, _ = _repository(tmp_path)
    before = repository_snapshot(repository), run_git(repository, "status", "--short")
    context, receipt = _context_and_receipt(repository, tmp_path / "store")
    calls: list[dict[str, Any]] = []

    def validator(*args: Any, **kwargs: Any) -> ValidationResult:
        calls.append(kwargs); raise AssertionError("validator must not run")

    gate = AgentValidationGate(context, (receipt,), validator=validator)
    approval = _approval(gate.plan.plan_id, decision) if decision is not None else None
    result = gate.run(approval)
    assert result.status == ("awaiting_approval" if decision is None else "denied")
    assert calls == []
    assert (repository_snapshot(repository), run_git(repository, "status", "--short")) == before


def test_expired_malformed_and_wrong_plan_approval_are_contained(tmp_path: Path) -> None:
    repository, _ = _repository(tmp_path)
    context, receipt = _context_and_receipt(repository, tmp_path / "store")
    calls = 0

    def validator(*args: Any, **kwargs: Any) -> ValidationResult:
        nonlocal calls; calls += 1; raise AssertionError("validator must not run")

    expired_gate = AgentValidationGate(context, (receipt,), validator=validator, clock=lambda: 10.0)
    expired = expired_gate.run(_approval(expired_gate.plan.plan_id, expires_at=9.0))
    wrong_context, wrong_receipt = _context_and_receipt(repository, tmp_path / "wrong-store")
    wrong_gate = AgentValidationGate(wrong_context, (wrong_receipt,), validator=validator)
    wrong = wrong_gate.run(_approval("validation-plan-v1-wrong"))
    assert expired.status == "approval_expired"
    assert wrong.status == "approval_incompatible"
    assert calls == 0


def test_changed_head_invalidates_approved_plan_before_validator_runs(tmp_path: Path) -> None:
    repository, _ = _repository(tmp_path)
    context, receipt = _context_and_receipt(repository, tmp_path / "store")
    calls = 0

    def validator(*args: Any, **kwargs: Any) -> ValidationResult:
        nonlocal calls; calls += 1; raise AssertionError("validator must not run")

    gate = AgentValidationGate(context, (receipt,), validator=validator)
    (repository / "README.md").write_text("changed\n", encoding="utf-8")
    run_git(repository, "add", "README.md"); run_git(repository, "commit", "-qm", "change reviewed head")
    result = gate.run(_approval(gate.plan.plan_id))
    assert result.status == "approval_incompatible"
    assert result.errors[0].kind == "approval_repository_changed"
    assert calls == 0


def test_approved_gate_delegates_to_g06_and_replay_does_not_repeat(tmp_path: Path) -> None:
    repository, candidate_id = _repository(tmp_path)
    before = repository_snapshot(repository), run_git(repository, "status", "--short")
    context, receipt = _context_and_receipt(repository, tmp_path / "store")
    calls: list[dict[str, Any]] = []

    def validator(*args: Any, **kwargs: Any) -> ValidationResult:
        calls.append(kwargs)
        from sunset.validation import validate_candidate
        return validate_candidate(*args, **kwargs)

    gate = AgentValidationGate(context, (receipt,), validator=validator)
    approved = gate.run(_approval(gate.plan.plan_id))
    replayed = AgentValidationGate(context, (receipt,), validator=validator).run(_approval(gate.plan.plan_id))

    assert approved.status == replayed.status == "validated"
    assert approved.validation is not None and approved.validation.status == "confirmed"
    assert approved.validation.candidate_id == candidate_id
    assert len(calls) == 1
    assert (repository_snapshot(repository), run_git(repository, "status", "--short")) == before


@pytest.mark.parametrize("status", ["confirmed", "still_failing", "flaky", "environment_error", "inconclusive"])
def test_gate_preserves_g06_result_classes_and_excludes_raw_output(tmp_path: Path, status: str) -> None:
    repository, _ = _repository(tmp_path)
    context, receipt = _context_and_receipt(repository, tmp_path / "store")
    base = ValidationResult(True, receipt.result["candidate"]["candidate_id"], "pytest", None, (), context.repository.head, (), "inconclusive")

    def validator(*args: Any, **kwargs: Any) -> ValidationResult:
        return replace(base, status=status)  # type: ignore[arg-type]

    gate = AgentValidationGate(context, (receipt,), validator=validator)
    result = gate.run(_approval(gate.plan.plan_id))
    assert result.validation is not None and result.validation.status == status
    assert "stdout" not in result.to_json().lower()
    views = "".join(path.read_text(encoding="utf-8") for path in (context.store.root / "views").glob("sunset-agent-validation*.json"))
    assert "stdout" not in views.lower()
