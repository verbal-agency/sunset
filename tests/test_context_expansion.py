from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

import sunset.context_expansion as expansion_module
from sunset.context_expansion import ContextExpansionContext
from sunset.context_expansion_models import ContextExpansionRequest


def _request(context: ContextExpansionContext, relation: str, **kwargs: object) -> ContextExpansionRequest:
    return ContextExpansionRequest(
        relation=relation, repository_head=context.repository.head,
        policy_fingerprint=context.policy_fingerprint, grant_fingerprint=context.grant_fingerprint,
        **kwargs,
    )  # type: ignore[arg-type]


def _context(sample_repository: Path, **kwargs: object) -> ContextExpansionContext:
    return ContextExpansionContext.create(sample_repository, **kwargs)


def test_g17_ac01_allowlisted_relations(sample_repository: Path) -> None:
    context = _context(sample_repository)
    for relation in ("ast_parent", "callers", "callees", "same_commit_changes", "historical_variant", "configuration_reference"):
        request = _request(context, relation, path="tests/test_markers.py", line=10, symbol="test_expected_failure", commit_id=context.repository.head)
        assert request.relation == relation
        assert context.expand(request).receipt.status in {"success", "unknown"}
    with pytest.raises(ValueError, match="not allowlisted"):
        ContextExpansionRequest(relation="shell", repository_head="head", path="tests/test_markers.py")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="repository-relative"):
        ContextExpansionRequest(relation="ast_parent", repository_head="head", path="../secret.py")


def test_g17_ac02_scoped_receipts(sample_repository: Path) -> None:
    context = _context(sample_repository)
    observation = context.expand(_request(context, "ast_parent", path="tests/test_markers.py", line=10))
    receipt = observation.receipt
    assert receipt.status == "success"
    assert receipt.repository_head == context.repository.head
    assert receipt.provenance == (f"head:{context.repository.head}",)
    assert receipt.scope.startswith("repository:")
    assert receipt.truncated is False
    assert observation.transient_content is None
    assert "import pytest" not in json.dumps(observation.checkpoint_dict())


def test_g17_ac03_bounded_behavior(sample_repository: Path) -> None:
    context = _context(sample_repository, max_result_bytes=1, max_tool_calls=1)
    observation = context.expand(_request(context, "ast_parent", path="tests/test_markers.py", line=10, per_call_byte_budget=1, cumulative_byte_budget=1))
    assert observation.receipt.status == "budget_exhausted"
    assert context.tool_calls_used == 1
    assert context.expand(_request(context, "ast_parent", path="tests/test_markers.py", line=10)).receipt.status == "budget_exhausted"


def test_g17_ac03_wall_time_policy(sample_repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(sample_repository, max_wall_time_ms=1)
    ticks = iter((0, 2_000_000))
    monkeypatch.setattr(expansion_module.time, "monotonic_ns", lambda: next(ticks))
    result = context.expand(_request(context, "ast_parent", path="tests/test_markers.py", line=10))
    assert result.receipt.status == "budget_exhausted"


def test_g17_ac04_replay_and_invalidation(sample_repository: Path) -> None:
    context = _context(sample_repository)
    request = _request(context, "ast_parent", path="tests/test_markers.py", line=10)
    first = context.expand(request)
    calls = context.tool_calls_used
    second = context.expand(request)
    assert first.receipt.status == "success"
    assert second.receipt.status == "reused"
    assert context.tool_calls_used == calls
    changed_head = ContextExpansionRequest.from_dict(request.to_dict() | {"repository_head": "different-head"})
    assert context.expand(changed_head).receipt.errors[0]["kind"] == "repository_head_mismatch"
    changed_policy = ContextExpansionRequest.from_dict(request.to_dict() | {"policy_fingerprint": "different-policy"})
    assert context.expand(changed_policy).receipt.errors[0]["kind"] == "policy_mismatch"
    changed_schema = ContextExpansionRequest.from_dict(request.to_dict() | {"schema_version": "99"})
    assert context.expand(changed_schema).receipt.errors[0]["kind"] == "schema_mismatch"


def test_g17_ac05_authority_safety(sample_repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("expansion must be offline")))
    before = {path.relative_to(sample_repository).as_posix(): path.read_bytes() for path in sample_repository.rglob("*") if path.is_file() and ".git" not in path.parts}
    context = _context(sample_repository)
    result = context.expand(_request(context, "configuration_reference", symbol="legacy-runtime"))
    assert result.receipt.status == "unknown"
    after = {path.relative_to(sample_repository).as_posix(): path.read_bytes() for path in sample_repository.rglob("*") if path.is_file() and ".git" not in path.parts}
    assert before == after
    missing_path = context.expand(_request(context, "ast_parent", path="src/not-present.py", line=1))
    assert missing_path.receipt.errors[0]["kind"] == "path_not_found"


def test_g17_ac06_verification(sample_repository: Path) -> None:
    context = _context(sample_repository)
    missing = context.expand(_request(context, "callers", symbol="does_not_exist"))
    assert missing.receipt.status == "unknown"
    assert "proof_obligation" in missing.receipt.result
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G17-controlled-context-expansion.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert all(f"G17-AC0{i}" in text for i in range(1, 7))
    fixture = Path(__file__).parent / "fixtures" / "context_expansion" / "g17-cases.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert len(payload["cases"]) == 5
