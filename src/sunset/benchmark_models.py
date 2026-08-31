"""Versioned, deterministic contracts for Sunset benchmark evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal


BENCHMARK_SCHEMA_VERSION = "1"
Recommendation = Literal["eligible_for_human_cleanup", "retain", "inconclusive"]


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    category: Literal["expired", "active", "unknown", "contradictory"]
    compact_citation_accuracy: float
    compact_input_tokens: int
    compact_latency_ms: int
    compact_recommendation: Recommendation
    compact_unsupported_claims: int
    expected_recommendation: Recommendation
    full_citation_accuracy: float
    full_input_tokens: int
    full_latency_ms: int
    full_recommendation: Recommendation
    source_locator: str
    semantic_score: float | None = None
    compact_cost_usd: float | None = None
    full_cost_usd: float | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BenchmarkCase:
        return cls(
            case_id=str(value["case_id"]),
            category=value["category"],
            compact_citation_accuracy=float(value["compact_citation_accuracy"]),
            compact_cost_usd=_optional_float(value.get("compact_cost_usd")),
            compact_input_tokens=int(value["compact_input_tokens"]),
            compact_latency_ms=int(value["compact_latency_ms"]),
            compact_recommendation=value["compact_recommendation"],
            compact_unsupported_claims=int(value["compact_unsupported_claims"]),
            expected_recommendation=value["expected_recommendation"],
            full_citation_accuracy=float(value["full_citation_accuracy"]),
            full_cost_usd=_optional_float(value.get("full_cost_usd")),
            full_input_tokens=int(value["full_input_tokens"]),
            full_latency_ms=int(value["full_latency_ms"]),
            full_recommendation=value["full_recommendation"],
            semantic_score=_optional_float(value.get("semantic_score")),
            source_locator=str(value["source_locator"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "compact_citation_accuracy": self.compact_citation_accuracy,
            "compact_cost_usd": self.compact_cost_usd,
            "compact_input_tokens": self.compact_input_tokens,
            "compact_latency_ms": self.compact_latency_ms,
            "compact_recommendation": self.compact_recommendation,
            "compact_unsupported_claims": self.compact_unsupported_claims,
            "expected_recommendation": self.expected_recommendation,
            "full_citation_accuracy": self.full_citation_accuracy,
            "full_cost_usd": self.full_cost_usd,
            "full_input_tokens": self.full_input_tokens,
            "full_latency_ms": self.full_latency_ms,
            "full_recommendation": self.full_recommendation,
            "semantic_score": self.semantic_score,
            "source_locator": self.source_locator,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkCorpus:
    cases: tuple[BenchmarkCase, ...]
    corpus_id: str
    description: str
    schema_version: str = BENCHMARK_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BenchmarkCorpus:
        return cls(
            cases=tuple(BenchmarkCase.from_dict(item) for item in value["cases"]),
            corpus_id=str(value["corpus_id"]),
            description=str(value["description"]),
            schema_version=str(value.get("schema_version", BENCHMARK_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkCaseResult:
    case: BenchmarkCase
    compact_correct: bool
    full_correct: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case.case_id,
            "category": self.case.category,
            "compact_citation_accuracy": self.case.compact_citation_accuracy,
            "compact_correct": self.compact_correct,
            "compact_input_tokens": self.case.compact_input_tokens,
            "compact_recommendation": self.case.compact_recommendation,
            "compact_unsupported_claims": self.case.compact_unsupported_claims,
            "expected_recommendation": self.case.expected_recommendation,
            "full_citation_accuracy": self.case.full_citation_accuracy,
            "full_correct": self.full_correct,
            "full_input_tokens": self.case.full_input_tokens,
            "full_recommendation": self.case.full_recommendation,
            "source_locator": self.case.source_locator,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    cases: tuple[BenchmarkCaseResult, ...]
    corpus_id: str
    metrics: dict[str, float | int | str | None]
    scn_06_passed: bool
    schema_version: str = BENCHMARK_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "cases": [case.to_dict() for case in self.cases],
            "corpus_id": self.corpus_id,
            "limitations": [
                "Token values are estimated context measurements, not provider-billed tokens.",
                "Semantic and cost metrics are unavailable unless a case records them.",
                "The committed corpus is manually adjudicated regression data, not a production prevalence study.",
            ],
            "metrics": self.metrics,
            "schema_version": self.schema_version,
            "scn_06": {
                "classification_accuracy_drop_limit": 0.05,
                "citation_accuracy_must_not_decline": True,
                "median_input_token_reduction_minimum": 0.5,
                "passed": self.scn_06_passed,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        metrics = self.metrics
        verdict = "PASS" if self.scn_06_passed else "FAIL"
        lines = [
            f"# Sunset benchmark: {self.corpus_id}",
            "",
            f"SCN-06 verdict: **{verdict}**",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
        for key in (
            "case_count", "full_classification_accuracy", "compact_classification_accuracy",
            "classification_accuracy_drop", "full_citation_accuracy", "compact_citation_accuracy",
            "median_input_token_reduction", "unsupported_claim_rate", "median_compact_latency_ms",
            "cost_availability", "semantic_score_availability",
        ):
            lines.append(f"| {key} | {metrics[key]} |")
        lines.extend(("", "## Limitations", ""))
        lines.extend(f"- {item}" for item in self.to_dict()["limitations"])
        return "\n".join(lines) + "\n"


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
