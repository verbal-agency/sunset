from __future__ import annotations

import json
from pathlib import Path
import socket

import pytest

from sunset.artifact_store import ArtifactStore
from sunset.operational_evidence import OperationalEvidenceContext, RecordedOperationalProvider, receipt_to_evidence_edge
from sunset.operational_evidence_models import OperationalQuery, PrivacyPolicy
from sunset.operational_evidence_models import OperationalEvidenceReceipt


FIXTURE = Path(__file__).parent / "fixtures" / "operational_evidence" / "g18-recorded.json"


def _context(tmp_path: Path) -> OperationalEvidenceContext:
    provider = RecordedOperationalProvider(FIXTURE)
    return OperationalEvidenceContext(ArtifactStore(tmp_path / "store"), {source: provider for source in ("support_policy", "deployment_inventory", "configuration", "contract", "runtime_telemetry")}, PrivacyPolicy("test", ("customer_count",)), now="2026-09-01T12:00:00+00:00")


def _query(source: str, locator: str, *, mode: str = "recorded", **kwargs: object) -> OperationalQuery:
    return OperationalQuery(source, locator, "candidate-1", "claim-1", "production", mode=mode, **kwargs)  # type: ignore[arg-type]


def test_g18_ac01_provider_boundary(tmp_path: Path) -> None:
    context = _context(tmp_path)
    result = context.invoke(_query("support_policy", "policy://support/python"))
    assert result.status == "success"
    with pytest.raises(ValueError, match="unsupported operational source"):
        OperationalQuery("jira", "jira://x", "candidate-1", scope="production")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-broad"):
        OperationalQuery("configuration", "config://*", "candidate-1", scope="production")  # type: ignore[arg-type]


def test_g18_ac02_scope_and_freshness(tmp_path: Path) -> None:
    context = _context(tmp_path)
    result = context.invoke(_query("deployment_inventory", "inventory://production/python"))
    assert result.freshness is not None
    assert result.provenance
    assert result.scope == "production"
    assert result.artifact_ids
    assert result.redacted_fields == ("customer_count",)
    assert OperationalEvidenceReceipt.from_dict(json.loads(result.to_json())).invocation_id == result.invocation_id


def test_g18_ac03_recorded_first_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("recorded mode must be offline")))
    result = _context(tmp_path).invoke(_query("support_policy", "policy://support/python"))
    assert result.effect["network_access"] is False
    assert '"minimum"' not in result.to_json()


def test_g18_ac04_contradictions_and_gaps(tmp_path: Path) -> None:
    context = _context(tmp_path)
    contradiction = context.invoke(_query("runtime_telemetry", "telemetry://python/legacy"))
    missing = context.invoke(_query("contract", "contract://unknown"))
    assert contradiction.status == "contradictory_evidence"
    assert missing.status == "unknown"
    assert missing.errors
    assert missing.proof_obligations
    edge = receipt_to_evidence_edge(contradiction, "claim-1")
    assert edge.role == "contradict"
    assert edge.artifact_ids


def test_g18_ac05_live_containment(tmp_path: Path) -> None:
    opener_called = False
    def opener(*args: object, **kwargs: object) -> object:
        nonlocal opener_called
        opener_called = True
        raise AssertionError("injected opener should not run when host is not allowlisted")
    from sunset.operational_evidence import ExplicitLiveOperationalProvider
    provider = ExplicitLiveOperationalProvider("credential", opener)
    context = OperationalEvidenceContext(ArtifactStore(tmp_path / "store"), {"support_policy": provider}, PrivacyPolicy("live"), mode="live", allowed_hosts=("allowed.example",))
    result = context.invoke(_query("support_policy", "https://blocked.example/policy", mode="live"))
    assert result.status == "error"
    assert opener_called is False

    class Response:
        def __enter__(self) -> Response:
            return self
        def __exit__(self, *args: object) -> None:
            return None
        def read(self, limit: int) -> bytes:
            return b'{"outcome":"supports_active","summary":"ok"}'
    live = OperationalEvidenceContext(ArtifactStore(tmp_path / "live-store"), {"support_policy": ExplicitLiveOperationalProvider("credential", lambda *args, **kwargs: Response())}, PrivacyPolicy("live"), mode="live", allowed_hosts=("allowed.example",))
    allowed = live.invoke(_query("support_policy", "https://allowed.example/policy", mode="live", credential_identity="credential-1"))
    assert allowed.status == "success"
    assert allowed.effect["network_access"] is True


def test_g18_ac06_verification() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert len(payload["responses"]) == 4
    goal = Path(__file__).parents[1] / "docs" / "goals" / "G18-operational-internal-evidence.md"
    text = goal.read_text(encoding="utf-8")
    assert "## Execution contract" in text
    assert all(f"G18-AC0{i}" in text for i in range(1, 7))
