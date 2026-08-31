from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from sunset.benchmark import (
    BenchmarkError,
    evaluate_corpus,
    langsmith_export,
    load_corpus,
    publish_langsmith_export,
)
from sunset.benchmark_models import BenchmarkCorpus
from sunset.cli import main


CORPUS_PATH = Path(__file__).parent / "fixtures" / "benchmarks" / "corpus-v1.json"


def test_corpus_is_balanced_and_scored_against_scn_06() -> None:
    corpus = load_corpus(CORPUS_PATH)
    report = evaluate_corpus(corpus)

    assert len(corpus.cases) == 20
    assert {case.category for case in corpus.cases} == {"expired", "active", "unknown", "contradictory"}
    assert report.scn_06_passed
    assert report.metrics["median_input_token_reduction"] == 0.6
    assert report.metrics["classification_accuracy_drop"] == 0.0
    assert report.metrics["cost_availability"] == "unavailable"
    assert report.metrics["semantic_score_availability"] == "unavailable"
    assert "SCN-06 verdict: **PASS**" in report.to_markdown()


def test_threshold_failure_is_reported_without_hiding_accuracy_or_citations() -> None:
    corpus = load_corpus(CORPUS_PATH)
    failed = BenchmarkCorpus(
        cases=tuple(
            replace(
                case,
                compact_citation_accuracy=0.9,
                compact_input_tokens=600,
                compact_recommendation="inconclusive",
            )
            for case in corpus.cases
        ),
        corpus_id=corpus.corpus_id,
        description=corpus.description,
    )

    report = evaluate_corpus(failed)

    assert not report.scn_06_passed
    assert report.metrics["median_input_token_reduction"] == 0.4286
    assert report.metrics["compact_citation_accuracy"] == 0.9


def test_langsmith_export_is_data_only_and_publish_is_explicit() -> None:
    corpus = load_corpus(CORPUS_PATH)
    export = langsmith_export(corpus, evaluate_corpus(corpus))
    sent: list[tuple[dict[str, object], str]] = []

    def fake_sender(value, api_key):
        sent.append((value, api_key))
        return {"url": "https://smith.example.test/experiment"}

    response = publish_langsmith_export(export, api_key="test-key", sender=fake_sender)

    assert response["url"].startswith("https://smith")
    assert sent == [(export, "test-key")]
    assert len(export["results"]) == 20
    assert "artifact" not in json.dumps(export)
    with pytest.raises(BenchmarkError, match="requires --langsmith-api-key"):
        publish_langsmith_export(export, api_key="", sender=fake_sender)


def test_benchmark_cli_is_local_by_default_and_writes_requested_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    export_path = tmp_path / "langsmith-export.json"

    def no_network(*args, **kwargs):
        raise AssertionError("default benchmark must not access the network")

    monkeypatch.setattr("socket.create_connection", no_network)
    exit_code = main(
        [
            "benchmark", "--corpus", str(CORPUS_PATH), "--langsmith-export", str(export_path),
            "--format", "markdown",
        ]
    )

    assert exit_code == 0
    assert "SCN-06 verdict: **PASS**" in capsys.readouterr().out
    assert len(json.loads(export_path.read_text(encoding="utf-8"))["results"]) == 20


def test_benchmark_cli_rejects_publish_without_explicit_credential(capsys) -> None:
    exit_code = main(["benchmark", "--corpus", str(CORPUS_PATH), "--publish-langsmith"])

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["error"]["kind"] == "langsmith_api_key_missing"
