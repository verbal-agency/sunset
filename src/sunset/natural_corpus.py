"""Replay-safe contracts and audits for natural, clone-runnable corpora.

The corpus layer does not clone repositories or execute tests. It proves that a
recorded run was allowed to do so: every case is tied to an immutable commit,
candidate selector, evidence digest, environment recipe, split, and bounded
execution policy. Live collection remains the responsibility of the existing
Git-evidence and disposable-validation seams.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Literal

from sunset.escalation_loop_models import empirical_status_for


NATURAL_CORPUS_SCHEMA_VERSION = "2"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_SPLITS = {"development", "holdout"}
_CASE_STATUSES = {"ready", "excluded"}
_OUTCOMES = {"confirmed", "still_failing", "flaky", "environment_error", "inconclusive"}
_EMPIRICAL = {"likely_active", "likely_expired", "not_adjudicated"}
_CONDITION_STATUSES = {"likely_active", "likely_expired", "unknown", "contradictory"}


class NaturalCorpusError(ValueError):
    """A malformed or unsafe natural-corpus artifact."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require_digest(value: str, field: str) -> None:
    if not _DIGEST_RE.fullmatch(value):
        raise NaturalCorpusError("digest_invalid", f"{field} must be a 64-character lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class CandidateSelector:
    path: str
    test: str
    marker_kind: str = "xfail"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CandidateSelector":
        unknown = set(value) - {"path", "test", "marker_kind"}
        if unknown:
            raise NaturalCorpusError("selector_field_unknown", sorted(unknown)[0])
        return cls(str(value["path"]), str(value["test"]), str(value.get("marker_kind", "xfail")))

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "test": self.test, "marker_kind": self.marker_kind}


@dataclass(frozen=True, slots=True)
class NaturalCase:
    case_id: str
    source_case_id: str
    repository_url: str
    pinned_ref: str
    candidate_selector: CandidateSelector
    split: Literal["development", "holdout"]
    evidence_digests: tuple[str, ...]
    environment_id: str
    status: Literal["ready", "excluded"] = "ready"
    exclusion_reason: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NaturalCase":
        unknown = set(value) - {
            "case_id", "source_case_id", "repository_url", "pinned_ref", "candidate_selector",
            "split", "evidence_digests", "environment_id", "status", "exclusion_reason",
        }
        if unknown:
            raise NaturalCorpusError("case_field_unknown", sorted(unknown)[0])
        status = str(value.get("status", "ready"))
        split = str(value["split"])
        return cls(
            case_id=str(value["case_id"]),
            source_case_id=str(value["source_case_id"]),
            repository_url=str(value["repository_url"]),
            pinned_ref=str(value["pinned_ref"]),
            candidate_selector=CandidateSelector.from_dict(value["candidate_selector"]),
            split=split,  # type: ignore[arg-type]
            evidence_digests=tuple(str(item) for item in value.get("evidence_digests", ())),
            environment_id=str(value["environment_id"]),
            status=status,  # type: ignore[arg-type]
            exclusion_reason=str(value["exclusion_reason"]) if value.get("exclusion_reason") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "case_id": self.case_id,
            "source_case_id": self.source_case_id,
            "repository_url": self.repository_url,
            "pinned_ref": self.pinned_ref,
            "candidate_selector": self.candidate_selector.to_dict(),
            "split": self.split,
            "evidence_digests": list(self.evidence_digests),
            "environment_id": self.environment_id,
            "status": self.status,
        }
        if self.exclusion_reason is not None:
            value["exclusion_reason"] = self.exclusion_reason
        return value


@dataclass(frozen=True, slots=True)
class NaturalManifest:
    corpus_id: str
    allowed_repository_urls: tuple[str, ...]
    split_commitment: str
    cases: tuple[NaturalCase, ...]
    budgets: dict[str, int]
    schema_version: str = NATURAL_CORPUS_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NaturalManifest":
        unknown = set(value) - {
            "schema_version", "corpus_id", "allowed_repository_urls", "split_commitment", "cases", "budgets",
        }
        if unknown:
            raise NaturalCorpusError("manifest_field_unknown", sorted(unknown)[0])
        return cls(
            corpus_id=str(value["corpus_id"]),
            allowed_repository_urls=tuple(str(item) for item in value["allowed_repository_urls"]),
            split_commitment=str(value["split_commitment"]),
            cases=tuple(NaturalCase.from_dict(item) for item in value["cases"]),
            budgets={str(key): int(item) for key, item in dict(value["budgets"]).items()},
            schema_version=str(value.get("schema_version", NATURAL_CORPUS_SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "allowed_repository_urls": list(self.allowed_repository_urls),
            "split_commitment": self.split_commitment,
            "cases": [case.to_dict() for case in self.cases],
            "budgets": dict(sorted(self.budgets.items())),
        }

    def digest(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class EnvironmentRecipe:
    environment_id: str
    repository_url: str
    pinned_ref: str
    python: str
    install_commands: tuple[tuple[str, ...], ...]
    test_command: tuple[str, ...]
    dependency_digest: str
    packages: dict[str, str]
    budgets: dict[str, int]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EnvironmentRecipe":
        unknown = set(value) - {
            "environment_id", "repository_url", "pinned_ref", "python", "install_commands",
            "test_command", "dependency_digest", "packages", "budgets",
        }
        if unknown:
            raise NaturalCorpusError("environment_field_unknown", sorted(unknown)[0])
        return cls(
            environment_id=str(value["environment_id"]),
            repository_url=str(value["repository_url"]),
            pinned_ref=str(value["pinned_ref"]),
            python=str(value["python"]),
            install_commands=tuple(tuple(str(part) for part in command) for command in value["install_commands"]),
            test_command=tuple(str(part) for part in value["test_command"]),
            dependency_digest=str(value["dependency_digest"]),
            packages={str(key): str(item) for key, item in dict(value["packages"]).items()},
            budgets={str(key): int(item) for key, item in dict(value["budgets"]).items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "repository_url": self.repository_url,
            "pinned_ref": self.pinned_ref,
            "python": self.python,
            "install_commands": [list(command) for command in self.install_commands],
            "test_command": list(self.test_command),
            "dependency_digest": self.dependency_digest,
            "packages": dict(sorted(self.packages.items())),
            "budgets": dict(sorted(self.budgets.items())),
        }


@dataclass(frozen=True, slots=True)
class NaturalAudit:
    status: Literal["passed", "rejected"]
    manifest_digest: str
    eligible_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    errors: tuple[str, ...]
    selection_bias: tuple[str, ...]
    non_authority: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "manifest_digest": self.manifest_digest,
            "eligible_case_ids": list(self.eligible_case_ids),
            "excluded_case_ids": list(self.excluded_case_ids),
            "errors": list(self.errors),
            "selection_bias": list(self.selection_bias),
            "non_authority": self.non_authority,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def derive_case_id(repository_url: str, pinned_ref: str, selector: CandidateSelector) -> str:
    """Derive an ID from immutable repository and candidate identity."""

    return "g32-" + _digest(
        {"repository_url": repository_url, "pinned_ref": pinned_ref, "candidate_selector": selector.to_dict()}
    )[:16]


def load_natural_manifest(path: str | Path) -> NaturalManifest:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        manifest = NaturalManifest.from_dict(value)
        validate_natural_manifest(manifest)
        return manifest
    except NaturalCorpusError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise NaturalCorpusError("manifest_invalid", str(exc)) from exc


def load_environment_recipes(path: str | Path) -> dict[str, EnvironmentRecipe]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if value.get("schema_version") != NATURAL_CORPUS_SCHEMA_VERSION:
            raise NaturalCorpusError("environment_schema_unsupported", str(value.get("schema_version")))
        recipes = tuple(EnvironmentRecipe.from_dict(item) for item in value["environments"])
    except NaturalCorpusError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise NaturalCorpusError("environment_invalid", str(exc)) from exc
    result = {recipe.environment_id: recipe for recipe in recipes}
    if len(result) != len(recipes):
        raise NaturalCorpusError("environment_duplicate", "environment IDs must be unique")
    for recipe in recipes:
        _validate_environment(recipe)
    return result


def load_evidence_records(path: str | Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        records = tuple(dict(item) for item in value["records"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise NaturalCorpusError("evidence_invalid", str(exc)) from exc
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        case_id = str(record.get("case_id", ""))
        record_digest = str(record.get("record_digest", ""))
        if not case_id or case_id in result:
            raise NaturalCorpusError("evidence_duplicate", case_id)
        unsigned = {key: item for key, item in record.items() if key != "record_digest"}
        if _digest(unsigned) != record_digest:
            raise NaturalCorpusError("evidence_digest_mismatch", case_id)
        result[case_id] = record
    return result


def load_natural_report(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NaturalCorpusError("report_invalid", str(exc)) from exc
    if not isinstance(value, dict):
        raise NaturalCorpusError("report_invalid", "report must be an object")
    return value


def validate_natural_manifest(manifest: NaturalManifest) -> None:
    if manifest.schema_version != NATURAL_CORPUS_SCHEMA_VERSION:
        raise NaturalCorpusError("manifest_schema_unsupported", manifest.schema_version)
    if not manifest.corpus_id or not manifest.allowed_repository_urls:
        raise NaturalCorpusError("manifest_identity_missing", "corpus ID and allowlist are required")
    _require_digest(manifest.split_commitment, "split_commitment")
    if any(not url.startswith("https://") for url in manifest.allowed_repository_urls):
        raise NaturalCorpusError("repository_url_invalid", "only HTTPS repository URLs may be allowlisted")
    for key in ("max_cases", "max_packages", "max_network_bytes", "timeout_seconds"):
        if manifest.budgets.get(key, 0) <= 0:
            raise NaturalCorpusError("budget_invalid", key)
    ids: set[str] = set()
    source_ids: set[str] = set()
    for case in manifest.cases:
        if case.case_id in ids:
            raise NaturalCorpusError("case_id_duplicate", case.case_id)
        if case.source_case_id in source_ids:
            raise NaturalCorpusError("source_case_id_duplicate", case.source_case_id)
        ids.add(case.case_id)
        source_ids.add(case.source_case_id)
        if not _SHA_RE.fullmatch(case.pinned_ref):
            raise NaturalCorpusError("pinned_ref_invalid", case.case_id)
        if case.case_id != derive_case_id(case.repository_url, case.pinned_ref, case.candidate_selector):
            raise NaturalCorpusError("case_id_not_derived", case.case_id)
        if case.repository_url not in manifest.allowed_repository_urls:
            raise NaturalCorpusError("repository_not_vetted", case.repository_url)
        if not case.candidate_selector.path or case.candidate_selector.path.startswith("/") or ".." in Path(case.candidate_selector.path).parts:
            raise NaturalCorpusError("candidate_path_invalid", case.case_id)
        if not case.candidate_selector.test or case.split not in _SPLITS:
            raise NaturalCorpusError("candidate_or_split_invalid", case.case_id)
        if case.status not in _CASE_STATUSES:
            raise NaturalCorpusError("case_status_invalid", case.case_id)
        if case.status == "excluded" and not case.exclusion_reason:
            raise NaturalCorpusError("exclusion_reason_missing", case.case_id)
        if case.status == "ready" and case.exclusion_reason is not None:
            raise NaturalCorpusError("exclusion_reason_unexpected", case.case_id)
        for digest in case.evidence_digests:
            _require_digest(digest, f"evidence_digests:{case.case_id}")


def audit_natural_corpus(
    manifest: NaturalManifest,
    environments: dict[str, EnvironmentRecipe],
    evidence: dict[str, dict[str, Any]],
    *,
    report: dict[str, Any] | None = None,
    holdout_tuning_case_ids: Iterable[str] = (),
    holdout_tuning_artifact_digests: Iterable[str] = (),
) -> NaturalAudit:
    """Audit corpus eligibility without cloning, networking, or running code."""

    validate_natural_manifest(manifest)
    errors: list[str] = []
    eligible: list[str] = []
    excluded: list[str] = []
    holdout_ids = {case.case_id for case in manifest.cases if case.split == "holdout"}
    if holdout_ids.intersection(set(holdout_tuning_case_ids)):
        errors.append("holdout_tuning_case_id_present")
    if tuple(holdout_tuning_artifact_digests):
        errors.append("holdout_tuning_artifact_present")
    for case in manifest.cases:
        if case.status == "excluded":
            excluded.append(case.case_id)
            continue
        recipe = environments.get(case.environment_id)
        if recipe is None:
            errors.append(f"environment_missing:{case.case_id}")
            continue
        if recipe.repository_url != case.repository_url or recipe.pinned_ref != case.pinned_ref:
            errors.append(f"environment_identity_mismatch:{case.case_id}")
            continue
        if not all(digest in {str(item.get("record_digest", "")) for item in evidence.values()} for digest in case.evidence_digests):
            errors.append(f"evidence_missing:{case.case_id}")
            continue
        eligible.append(case.case_id)
    if not eligible:
        errors.append("no_eligible_cases")
    if report is not None:
        errors.extend(validate_natural_report(report, manifest))
    return NaturalAudit(
        status="passed" if not errors else "rejected",
        manifest_digest=manifest.digest(),
        eligible_case_ids=tuple(sorted(eligible)),
        excluded_case_ids=tuple(sorted(excluded)),
        errors=tuple(sorted(set(errors))),
        selection_bias=(
            "The corpus contains only public markers with reproducible dependency and test environments.",
            "Clone-runnable candidates are a selected subset and do not estimate repository-wide recall.",
        ),
    )


def validate_natural_report(report: dict[str, Any], manifest: NaturalManifest) -> tuple[str, ...]:
    errors: list[str] = []
    if report.get("schema_version") != NATURAL_CORPUS_SCHEMA_VERSION:
        errors.append("report_schema_unsupported")
    if report.get("manifest_digest") != manifest.digest():
        errors.append("report_manifest_digest_mismatch")
    if report.get("non_authority") is not True:
        errors.append("report_authority_flag_missing")
    manifest_by_id = {case.case_id: case for case in manifest.cases}
    report_cases = report.get("cases", ())
    seen: set[str] = set()
    for item in report_cases:
        case_id = str(item.get("case_id", ""))
        if case_id in seen or case_id not in manifest_by_id:
            errors.append(f"report_case_invalid:{case_id}")
            continue
        seen.add(case_id)
        outcome = item.get("validation_outcome")
        if outcome is not None and outcome not in _OUTCOMES:
            errors.append(f"validation_outcome_invalid:{case_id}")
        empirical = item.get("empirical_status")
        if empirical not in _EMPIRICAL:
            errors.append(f"empirical_status_invalid:{case_id}")
        elif empirical != empirical_status_for(outcome):
            errors.append(f"empirical_status_mismatch:{case_id}")
        if item.get("heuristic_status") not in _CONDITION_STATUSES or item.get("agent_status") not in _CONDITION_STATUSES:
            errors.append(f"condition_status_invalid:{case_id}")
    if seen != set(manifest_by_id):
        errors.append("report_case_set_mismatch")
    if not isinstance(report.get("selection_bias"), list) or not report["selection_bias"]:
        errors.append("selection_bias_missing")
    recall = report.get("recall_audit")
    if not isinstance(recall, dict) or not recall.get("sample_case_ids"):
        errors.append("recall_audit_missing")
    elif any(case_id not in manifest_by_id for case_id in recall["sample_case_ids"]):
        errors.append("recall_audit_case_unknown")
    tuning = set(report.get("tuning_case_ids", ()))
    holdout = {case.case_id for case in manifest.cases if case.split == "holdout"}
    if tuning.intersection(holdout):
        errors.append("report_holdout_tuning_present")
    return tuple(sorted(set(errors)))


def assemble_natural_report(
    manifest: NaturalManifest,
    source_report: dict[str, Any],
    *,
    recall_audit: dict[str, Any],
) -> dict[str, Any]:
    """Bind a recorded G30 report to the immutable G32 manifest and splits."""

    by_source = {case.source_case_id: case for case in manifest.cases}
    cases: list[dict[str, Any]] = []
    for source in source_report.get("cases", ()):
        source_id = str(source["case_id"])
        case = by_source.get(source_id)
        if case is None:
            raise NaturalCorpusError("report_source_case_unknown", source_id)
        item = dict(source)
        item["case_id"] = case.case_id
        item["source_case_id"] = source_id
        item["split"] = case.split
        item["repository_url"] = case.repository_url
        item["pinned_ref"] = case.pinned_ref
        item["candidate_selector"] = case.candidate_selector.to_dict()
        cases.append(item)
    report = {
        "schema_version": NATURAL_CORPUS_SCHEMA_VERSION,
        "run_id": "g32-natural-report-v2",
        "manifest_digest": manifest.digest(),
        "source_report_digest": _digest(source_report),
        "mode": source_report.get("mode", "recorded"),
        "model": source_report.get("model"),
        "execution": source_report.get("execution", "recorded"),
        "ground_truth": "empirical_validation",
        "cases": sorted(cases, key=lambda item: item["case_id"]),
        "metrics": dict(source_report.get("metrics", {})),
        "selection_bias": [
            "The corpus includes only public, clone-runnable markers from the vetted LangChain repository.",
            "Dependency-installable and deterministic tests are not representative of all temporal debt.",
            "One repository, one model, one recorded run; metrics are not a general quality claim.",
        ],
        "unsupported_claims": [
            "A passing disposable clone does not prove removal safe for every deployment.",
            "The report does not estimate recall outside the declared audit sample.",
        ],
        "recall_audit": recall_audit,
        "tuning_case_ids": [],
        "non_authority": True,
    }
    errors = validate_natural_report(report, manifest)
    if errors:
        raise NaturalCorpusError("report_invalid", ";".join(errors))
    return report


def report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _validate_environment(recipe: EnvironmentRecipe) -> None:
    if not recipe.environment_id or not recipe.repository_url.startswith("https://"):
        raise NaturalCorpusError("environment_identity_invalid", recipe.environment_id)
    if not _SHA_RE.fullmatch(recipe.pinned_ref):
        raise NaturalCorpusError("environment_ref_invalid", recipe.environment_id)
    if not recipe.python or not recipe.install_commands or not recipe.test_command:
        raise NaturalCorpusError("environment_recipe_incomplete", recipe.environment_id)
    _require_digest(recipe.dependency_digest, f"dependency_digest:{recipe.environment_id}")
    for key in ("timeout_seconds", "max_network_bytes", "max_packages"):
        if recipe.budgets.get(key, 0) <= 0:
            raise NaturalCorpusError("environment_budget_invalid", f"{recipe.environment_id}:{key}")


__all__ = [
    "CandidateSelector",
    "EnvironmentRecipe",
    "NaturalAudit",
    "NaturalCase",
    "NaturalCorpusError",
    "NaturalManifest",
    "NATURAL_CORPUS_SCHEMA_VERSION",
    "assemble_natural_report",
    "audit_natural_corpus",
    "derive_case_id",
    "load_environment_recipes",
    "load_evidence_records",
    "load_natural_manifest",
    "load_natural_report",
    "report_json",
    "validate_natural_manifest",
    "validate_natural_report",
]
