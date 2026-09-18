"""G32 — evidence enrichment (offline, pure AST + composition)."""

from __future__ import annotations

from sunset.evidence_enrichment import build_enriched_evidence, extract_marker_source

SOURCE = '''\
import pytest


@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.xfail(reason="Refactors to make in 0.3")
def test_thing(x):
    assert do_thing(x) == x


def test_untouched():
    assert True
'''


def test_extracts_reason_line_and_source() -> None:
    m = extract_marker_source(SOURCE, "test_thing")
    assert m is not None
    assert m.reason == "Refactors to make in 0.3"
    assert m.xfail_line == 5  # the @pytest.mark.xfail line
    assert "def test_thing" in m.source
    assert "do_thing" in m.source


def test_missing_function_returns_none() -> None:
    assert extract_marker_source(SOURCE, "nope") is None


def test_non_xfail_function_has_no_reason() -> None:
    m = extract_marker_source(SOURCE, "test_untouched")
    assert m is not None
    assert m.reason is None
    assert m.xfail_line is None


def test_syntax_error_returns_none() -> None:
    assert extract_marker_source("def (:", "x") is None


def test_build_enriched_evidence_composes_all_parts() -> None:
    m = extract_marker_source(SOURCE, "test_thing")
    ev = build_enriched_evidence(
        package="langchain-core", version="1.6.3",
        node="utils/test_utils.py::test_thing", marker=m,
        blame="abc123 (2024-09-01) add xfail",
    )
    assert "langchain-core 1.6.3" in ev
    assert "Refactors to make in 0.3" in ev
    assert "abc123 (2024-09-01)" in ev
    assert "def test_thing" in ev
    assert "still in force" in ev


def test_source_is_truncated() -> None:
    m = extract_marker_source(SOURCE, "test_thing")
    ev = build_enriched_evidence(
        package="p", version="1", node="n", marker=m, max_source_chars=10,
    )
    # only 10 chars of the test source appear
    assert "def test_t" in ev
    assert "assert do_thing" not in ev


def test_enrichment_comparison_finding() -> None:
    """The recorded thin-vs-rich comparison: richer static evidence did not reduce
    abstention or improve definite-call accuracy, and neither run's agent found the
    one genuinely expired marker (only the clone did)."""
    import json
    from pathlib import Path

    data = json.loads(Path("tests/fixtures/benchmarks/g30-enrichment-comparison-v1.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    definite = {"likely_active", "likely_expired"}
    thin_abstain = sum(1 for c in cases if c["thin"] == "unknown")
    rich_abstain = sum(1 for c in cases if c["rich"] == "unknown")
    thin_correct = sum(1 for c in cases if c["thin"] in definite and c["thin"] == c["empirical"])
    rich_correct = sum(1 for c in cases if c["rich"] in definite and c["rich"] == c["empirical"])

    assert thin_abstain == rich_abstain == 7          # no reduction in abstention
    assert thin_correct == rich_correct == 1          # definite-call accuracy unchanged
    # the one genuinely expired marker was never called expired by the agent
    expired = [c for c in cases if c["empirical"] == "likely_expired"]
    assert len(expired) == 1
    assert expired[0]["thin"] != "likely_expired" and expired[0]["rich"] != "likely_expired"
