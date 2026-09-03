"""Versioned contracts for split-safe optimization experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

OPTIMIZATION_SCHEMA_VERSION = "1"
Component = Literal["prompt", "retrieval", "tool_policy", "threshold"]
ExperimentStatus = Literal["preregistered", "evaluated_development", "selected", "rejected", "holdout_sealed", "inconclusive"]


@dataclass(frozen=True, slots=True)
class Experiment:
    experiment_id: str
    corpus_digest: str
    holdout_digest: str
    component: Component
    change_id: str
    budget: int
    development_case_ids: tuple[str, ...]
    development: dict[str, Any]
    metrics: dict[str, Any]
    holdout: dict[str, Any] | None
    status: ExperimentStatus
    rejection_reason: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Experiment":
        required = {"experiment_id", "corpus_digest", "holdout_digest", "component", "change_id", "budget", "development_case_ids", "development", "status"}
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"missing experiment field: {missing[0]}")
        unknown = set(value) - required - {"holdout", "rejection_reason"}
        if unknown:
            raise ValueError(f"unknown experiment field: {sorted(unknown)[0]}")
        development = dict(value["development"])
        return cls(str(value["experiment_id"]), str(value["corpus_digest"]), str(value["holdout_digest"]), value["component"], str(value["change_id"]), int(value["budget"]), tuple(str(item) for item in value["development_case_ids"]), development, dict(value.get("metrics", development)), dict(value["holdout"]) if value.get("holdout") is not None else None, value["status"], str(value["rejection_reason"]) if value.get("rejection_reason") is not None else None)

    def to_dict(self) -> dict[str, Any]:
        result = {"experiment_id": self.experiment_id, "corpus_digest": self.corpus_digest, "holdout_digest": self.holdout_digest, "component": self.component, "change_id": self.change_id, "budget": self.budget, "development_case_ids": list(self.development_case_ids), "metrics": self.metrics, "development": self.development, "status": self.status}
        if self.holdout is not None:
            result["holdout"] = self.holdout
        if self.rejection_reason is not None:
            result["rejection_reason"] = self.rejection_reason
        return result


@dataclass(frozen=True, slots=True)
class OptimizationReport:
    optimization_id: str
    corpus_digest: str
    holdout_digest: str
    selected_experiment_id: str | None
    experiments: tuple[dict[str, Any], ...]
    holdout: dict[str, Any] | None
    limitations: tuple[str, ...]
    schema_version: str = OPTIMIZATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {"optimization_id": self.optimization_id, "corpus_digest": self.corpus_digest, "holdout_digest": self.holdout_digest, "selected_experiment_id": self.selected_experiment_id, "experiments": [dict(item) for item in self.experiments], "holdout": self.holdout, "limitations": list(self.limitations), "schema_version": self.schema_version}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = ["Experiment", "OptimizationReport", "OPTIMIZATION_SCHEMA_VERSION"]
