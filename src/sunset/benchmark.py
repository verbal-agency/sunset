"""Offline benchmark evaluator and opt-in LangSmith experiment export."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any
from urllib.request import Request, urlopen

from sunset.benchmark_models import BenchmarkCaseResult, BenchmarkCorpus, BenchmarkReport


class BenchmarkError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_corpus(path: str | Path) -> BenchmarkCorpus:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        corpus = BenchmarkCorpus.from_dict(value)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BenchmarkError("corpus_invalid", str(exc)) from exc
    _validate_corpus(corpus)
    return corpus


def evaluate_corpus(corpus: BenchmarkCorpus) -> BenchmarkReport:
    results = tuple(
        BenchmarkCaseResult(
            case=case,
            compact_correct=case.compact_recommendation == case.expected_recommendation,
            full_correct=case.full_recommendation == case.expected_recommendation,
        )
        for case in corpus.cases
    )
    count = len(results)
    full_accuracy = sum(item.full_correct for item in results) / count
    compact_accuracy = sum(item.compact_correct for item in results) / count
    full_citations = sum(item.case.full_citation_accuracy for item in results) / count
    compact_citations = sum(item.case.compact_citation_accuracy for item in results) / count
    reductions = tuple(
        1 - item.case.compact_input_tokens / item.case.full_input_tokens for item in results
    )
    costs = tuple(
        item.case.compact_cost_usd for item in results if item.case.compact_cost_usd is not None
    )
    semantic = tuple(item.case.semantic_score for item in results if item.case.semantic_score is not None)
    metrics: dict[str, float | int | str | None] = {
        "case_count": count,
        "full_classification_accuracy": round(full_accuracy, 4),
        "compact_classification_accuracy": round(compact_accuracy, 4),
        "classification_accuracy_drop": round(full_accuracy - compact_accuracy, 4),
        "full_citation_accuracy": round(full_citations, 4),
        "compact_citation_accuracy": round(compact_citations, 4),
        "median_input_token_reduction": round(median(reductions), 4),
        "unsupported_claim_rate": round(
            sum(item.case.compact_unsupported_claims > 0 for item in results) / count, 4
        ),
        "median_compact_latency_ms": int(median(item.case.compact_latency_ms for item in results)),
        "median_full_latency_ms": int(median(item.case.full_latency_ms for item in results)),
        "cost_availability": "available" if costs else "unavailable",
        "median_compact_cost_usd": round(median(costs), 6) if costs else None,
        "semantic_score_availability": "available" if semantic else "unavailable",
        "median_semantic_score": round(median(semantic), 4) if semantic else None,
    }
    passed = (
        metrics["median_input_token_reduction"] >= 0.5
        and metrics["classification_accuracy_drop"] <= 0.05
        and metrics["compact_citation_accuracy"] >= metrics["full_citation_accuracy"]
    )
    return BenchmarkReport(results, corpus.corpus_id, metrics, passed)


def langsmith_export(corpus: BenchmarkCorpus, report: BenchmarkReport) -> dict[str, Any]:
    """Return a data-only experiment payload suitable for explicit publication."""

    return {
        "dataset_id": corpus.corpus_id,
        "dataset_name": corpus.corpus_id,
        "description": corpus.description,
        "experiment_name": f"sunset-{corpus.corpus_id}-compact-memory",
        "results": [
            {
                "inputs": {"case_id": item.case.case_id, "source_locator": item.case.source_locator},
                "reference_outputs": {"recommendation": item.case.expected_recommendation},
                "outputs": {"recommendation": item.case.compact_recommendation},
                "feedback": [
                    {"key": "recommendation_correct", "score": float(item.compact_correct)},
                    {"key": "citation_accuracy", "score": item.case.compact_citation_accuracy},
                ],
            }
            for item in report.cases
        ],
    }


def publish_langsmith_export(
    export: dict[str, Any],
    *,
    api_key: str,
    sender: Any = None,
) -> dict[str, Any]:
    """Publish only when an invoking caller explicitly supplies credentials."""

    if not api_key:
        raise BenchmarkError("langsmith_api_key_missing", "--publish-langsmith requires --langsmith-api-key")
    return (sender or _send_langsmith_export)(export, api_key)


def _send_langsmith_export(export: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = Request(
        "https://api.smith.langchain.com/api/v1/datasets/upload-experiment",
        data=json.dumps(export, sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # nosec B310 - caller explicitly requested upload
        return json.loads(response.read().decode("utf-8"))


def _validate_corpus(corpus: BenchmarkCorpus) -> None:
    if corpus.schema_version != "1":
        raise BenchmarkError("corpus_schema_unsupported", corpus.schema_version)
    if len(corpus.cases) < 20:
        raise BenchmarkError("corpus_too_small", "benchmark corpus requires at least 20 cases")
    categories = {case.category for case in corpus.cases}
    if categories != {"expired", "active", "unknown", "contradictory"}:
        raise BenchmarkError("corpus_categories_incomplete", "all four benchmark categories are required")
    if len({case.case_id for case in corpus.cases}) != len(corpus.cases):
        raise BenchmarkError("corpus_case_ids_not_unique", "benchmark case IDs must be unique")
    for case in corpus.cases:
        if case.full_input_tokens <= 0 or case.compact_input_tokens <= 0:
            raise BenchmarkError("corpus_token_baseline_invalid", case.case_id)
        if not 0 <= case.full_citation_accuracy <= 1 or not 0 <= case.compact_citation_accuracy <= 1:
            raise BenchmarkError("corpus_citation_accuracy_invalid", case.case_id)
