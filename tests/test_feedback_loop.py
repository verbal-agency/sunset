"""G31 — empirical feedback eligibility, leakage, and offline comparison."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
from typing import Any

import pytest

from sunset.feedback_loop import audit_feedback_packet, load_feedback_packet, run_feedback_comparison


ROOT = Path(__file__).parent / "fixtures" / "benchmarks"
PACKET = ROOT / "g31-feedback-development-v1.json"
INVALID_HOLDOUT = ROOT / "g31-feedback-holdout-invalid-v1.json"
REPORT = ROOT / "g31-feedback-report-v1.json"


def test_eligibility_excludes_non_conclusive() -> None:
    packet = load_feedback_packet(PACKET)
    audit = audit_feedback_packet(packet)

    assert audit.status == "passed"
    assert audit.eligible_case_ids == ("cache-stream", "optional-param", "pydantic-v2-nested", "stream-error-cb")
    assert audit.excluded_case_ids == ("inconclusive-case",)
    assert audit.exclusions["inconclusive-case"] == "non_conclusive_or_mismatched_empirical_outcome"


def test_leakage_gate_rejects_holdout_without_running_prototype() -> None:
    packet = load_feedback_packet(INVALID_HOLDOUT)
    report = run_feedback_comparison(packet)

    assert report.audit.status == "rejected"
    assert report.mechanisms == ()
    assert any(error.startswith("holdout_") for error in report.audit.errors)
    assert report.recommendation == "reject"


def test_mechanism_report_compares_baselines() -> None:
    packet = load_feedback_packet(PACKET)
    report = run_feedback_comparison(packet)
    expected = json.loads(REPORT.read_text(encoding="utf-8"))
    by_id = {item.mechanism_id: item for item in report.mechanisms}

    assert report.to_dict()["packet_digest"] == expected["packet_digest"]
    assert report.recommendation == expected["recommendation"]
    assert report.audit.to_dict()["eligible_case_ids"] == expected["audit"]["eligible_case_ids"]
    for mechanism_id, metrics in expected["mechanisms"].items():
        assert {key: by_id[mechanism_id].metrics[key] for key in metrics} == metrics
    exemplar = {item.case_id: item.proposed_status for item in by_id["exemplar_memory"].cases}
    assert exemplar["stream-error-cb"] == "likely_active"
    assert exemplar["cache-stream"] == "likely_active"


def test_feedback_cannot_authorize_or_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("feedback exploration must not open sockets")

    def no_subprocess(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("feedback exploration must not execute subprocesses")

    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.setattr(subprocess, "run", no_subprocess)
    report = run_feedback_comparison(load_feedback_packet(PACKET))
    encoded = json.dumps(report.to_dict(), sort_keys=True)

    assert report.recommendation == "defer"
    assert "approve" not in encoded
    assert "cleanup" in encoded  # limitation documents the forbidden authority
    assert "target" not in encoded


def test_recorded_feedback_replays_byte_identically() -> None:
    packet = load_feedback_packet(PACKET)
    first = run_feedback_comparison(packet).to_json()
    second = run_feedback_comparison(packet).to_json()
    assert first == second


def test_unknown_mechanism_is_rejected_without_side_effect() -> None:
    packet = load_feedback_packet(PACKET)
    report = run_feedback_comparison(packet, mechanisms=("baseline", "not-registered"))
    assert report.audit.status == "rejected"
    assert "unknown_mechanism:not-registered" in report.audit.errors
    assert report.mechanisms == ()
