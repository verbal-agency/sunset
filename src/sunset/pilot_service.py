"""One-owner orchestration for Sunset's maintainer-facing pilot path."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from sunset.artifact_store import ArtifactStore, ArtifactStoreError
from sunset.pilot_models import PilotApprovalToken, PilotCaseFile, PilotRequest, PilotResult, PilotSetupReceipt


class PilotServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    candidate_id: str
    repository_head: str
    hypothesis: str
    evidence_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvestigationSummary:
    hypothesis: str
    evidence_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    unresolved_obligations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    outcome: str
    artifact_ids: tuple[str, ...] = ()
    unresolved_obligations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PilotPreparation:
    repository_head: str
    setup_receipt: PilotSetupReceipt
    artifact_ids: tuple[str, ...] = ()


class PilotBackend(Protocol):
    """The replaceable backend behind the one-owner service."""

    def prepare(self, request: PilotRequest) -> str | PilotPreparation: ...

    def resolve(self, request: PilotRequest) -> CandidateResolution: ...

    def collect_evidence(self, request: PilotRequest, candidate: CandidateResolution) -> CandidateResolution: ...

    def investigate(self, request: PilotRequest, candidate: CandidateResolution) -> InvestigationSummary: ...

    def validate(self, request: PilotRequest, candidate: CandidateResolution) -> ValidationSummary: ...


@dataclass(frozen=True, slots=True)
class PilotConfig:
    validation_config_digest: str = "bounded-g06-v1"
    approval_ttl_seconds: int = 600

    def digest(self) -> str:
        return hashlib.sha256(self.validation_config_digest.encode("utf-8")).hexdigest()


class PilotService:
    """Own the complete pilot sequence; callers never compose internal stages."""

    def __init__(
        self,
        backend: PilotBackend,
        *,
        store: ArtifactStore,
        config: PilotConfig | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.backend = backend
        self.store = store
        self.config = config or PilotConfig()
        self.clock = clock

    def run(self, request: PilotRequest) -> PilotResult:
        run_id = self._run_id(request)
        prior = self._load(run_id)
        if prior is not None:
            return prior
        trace: list[str] = ["setup"]
        try:
            repository_head = self.backend.prepare(request)
            setup_receipt = None
            setup_artifact_ids: tuple[str, ...] = ()
            if isinstance(repository_head, PilotPreparation):
                setup = repository_head
                repository_head = setup.repository_head
                setup_receipt = setup.setup_receipt
                setup_artifact_ids = setup.artifact_ids
            candidate = self.backend.resolve(request)
            if setup_artifact_ids:
                candidate = CandidateResolution(
                    candidate.candidate_id,
                    candidate.repository_head,
                    candidate.hypothesis,
                    candidate.evidence_ids,
                    tuple(dict.fromkeys((*setup_artifact_ids, *candidate.artifact_ids))),
                )
            trace.append("resolve")
            candidate = self.backend.collect_evidence(request, candidate)
            trace.append("evidence")
            investigation = self.backend.investigate(request, candidate)
            trace.append("investigation")
        except PilotServiceError as exc:
            result = self._error_result(run_id, request, str(exc), exc.code, trace)
            return self._save(result)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            result = self._error_result(run_id, request, str(exc), "pilot_backend_error", trace)
            return self._save(result)

        if request.validation_requested:
            approval = self._approval_token(run_id, request)
            result = self._result(
                run_id=run_id,
                request=request,
                status="approval_required",
                repository_head=repository_head,
                candidate=candidate,
                investigation=investigation,
                validation_outcome=None,
                unresolved_obligations=investigation.unresolved_obligations,
                approval=approval,
                next_action="Approve disposable validation",
                trace=trace,
                setup_receipt=setup_receipt,
            )
        else:
            result = self._result(
                run_id=run_id,
                request=request,
                status="completed",
                repository_head=repository_head,
                candidate=candidate,
                investigation=investigation,
                validation_outcome=None,
                unresolved_obligations=investigation.unresolved_obligations,
                approval=None,
                next_action="Review case file",
                trace=[*trace, "casefile"],
                setup_receipt=setup_receipt,
            )
        return self._save(result)

    def approve(self, run_id: str, token: str, *, decision: str) -> PilotResult:
        prior = self._load(run_id)
        if prior is None:
            raise PilotServiceError("run_not_found", f"pilot run does not exist: {run_id}")
        if prior.status != "approval_required" or prior.approval is None:
            return prior
        if token != prior.approval.token:
            return self._save(self._with_error(
                prior,
                "approval_token_mismatch",
                "approval token does not match this run",
                keep_pending=True,
            ))
        if self.clock() >= prior.approval.expires_at:
            return self._save(self._with_error(prior, "approval_expired", "approval token has expired"))
        if decision not in {"approve", "deny"}:
            return self._save(self._with_error(
                prior,
                "approval_decision_invalid",
                "decision must be approve or deny",
                keep_pending=True,
            ))
        if decision == "deny":
            return self._save(
                self._replace(prior, status="denied", approval=None, next_action="No validation was run", trace=(*prior.stage_trace, "approval_denied"))
            )

        candidate = CandidateResolution(
            candidate_id=prior.candidate_id or "",
            repository_head=prior.repository_head,
            hypothesis=prior.hypothesis,
            evidence_ids=prior.evidence_ids,
            artifact_ids=prior.artifact_ids,
        )
        try:
            validation = self.backend.validate(prior.request, candidate)
        except PilotServiceError as exc:
            return self._save(self._with_error(prior, exc.code, exc.message, trace=(*prior.stage_trace, "validation")))
        except (OSError, KeyError, TypeError, ValueError) as exc:
            return self._save(self._with_error(prior, "validation_error", str(exc), trace=(*prior.stage_trace, "validation")))
        status = {
            "confirmed": "completed",
            "still_failing": "completed",
            "flaky": "inconclusive",
            "environment_error": "environment_error",
            "inconclusive": "inconclusive",
        }.get(validation.outcome, "unvalidatable")
        obligations = tuple(dict.fromkeys((*prior.unresolved_obligations, *validation.unresolved_obligations)))
        case_file = self._case_file(prior, validation.outcome, obligations, "Review bounded validation evidence")
        return self._save(
            self._replace(
                prior,
                status=status,
                validation_outcome=validation.outcome,
                unresolved_obligations=obligations,
                artifact_ids=tuple(dict.fromkeys((*prior.artifact_ids, *validation.artifact_ids))),
                approval=None,
                next_action="Review case file",
                case_file=case_file,
                trace=(*prior.stage_trace, "validation", "casefile"),
            )
        )

    def _run_id(self, request: PilotRequest) -> str:
        return "pilot-run-v1-" + request.digest()[:24]

    def _approval_token(self, run_id: str, request: PilotRequest) -> PilotApprovalToken:
        expires_at = float(self.clock()) + self.config.approval_ttl_seconds
        identity = f"{run_id}:{request.digest()}:{self.config.digest()}:{expires_at}"
        token = "approve-v1-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return PilotApprovalToken(token, run_id, request.digest(), self.config.digest(), expires_at)

    def _result(
        self,
        *,
        run_id: str,
        request: PilotRequest,
        status: str,
        repository_head: str,
        candidate: CandidateResolution,
        investigation: InvestigationSummary,
        validation_outcome: str | None,
        unresolved_obligations: tuple[str, ...],
        approval: PilotApprovalToken | None,
        next_action: str,
        trace: list[str],
        setup_receipt: PilotSetupReceipt | None = None,
    ) -> PilotResult:
        case_file = None if status == "approval_required" else self._case_file(request, validation_outcome, unresolved_obligations, next_action, candidate, investigation)
        return PilotResult(
            run_id=run_id,
            status=status,
            request=request,
            repository_head=repository_head,
            candidate_id=candidate.candidate_id,
            hypothesis=investigation.hypothesis,
            evidence_ids=tuple(dict.fromkeys((*candidate.evidence_ids, *investigation.evidence_ids))),
            artifact_ids=tuple(dict.fromkeys((*candidate.artifact_ids, *investigation.artifact_ids))),
            validation_outcome=validation_outcome,
            unresolved_obligations=unresolved_obligations,
            approval=approval,
            next_action=next_action,
            case_file=case_file,
            stage_trace=tuple(trace),
            setup_receipt=setup_receipt,
        )

    def _case_file(self, *args: Any) -> PilotCaseFile:
        if isinstance(args[0], PilotResult):
            prior, outcome, obligations, next_action = args[:4]
            return PilotCaseFile(prior.hypothesis, prior.evidence_ids, prior.artifact_ids, outcome, obligations, next_action)
        request, outcome, obligations, next_action, candidate, investigation = args
        return PilotCaseFile(
            investigation.hypothesis,
            tuple(dict.fromkeys((*candidate.evidence_ids, *investigation.evidence_ids))),
            tuple(dict.fromkeys((*candidate.artifact_ids, *investigation.artifact_ids))),
            outcome,
            obligations,
            next_action,
        )

    def _error_result(self, run_id: str, request: PilotRequest, message: str, code: str, trace: list[str]) -> PilotResult:
        status = "environment_error" if code in {"environment_unavailable", "dependency_setup_failed"} else "error"
        return PilotResult(run_id, status, request, "", None, "", (), (), None, (), None, "Resolve the structured error", (({"kind": code, "message": message},)), stage_trace=tuple(trace))

    def _with_error(
        self,
        prior: PilotResult,
        code: str,
        message: str,
        *,
        trace: tuple[str, ...] | None = None,
        keep_pending: bool = False,
    ) -> PilotResult:
        status = "approval_required" if keep_pending else ("environment_error" if code == "environment_error" else "error")
        return self._replace(
            prior,
            status=status,
            approval=prior.approval if keep_pending else None,
            next_action="Approve disposable validation" if keep_pending else "Review structured error",
            errors=(*prior.errors, {"kind": code, "message": message}),
            trace=trace or prior.stage_trace,
        )

    def _replace(self, prior: PilotResult, **changes: Any) -> PilotResult:
        values = prior.to_dict()
        values.update(changes)
        values["revision"] = prior.revision + 1
        if "request" not in changes:
            values["request"] = prior.request.to_dict()
        if "approval" in changes and isinstance(changes["approval"], PilotApprovalToken):
            values["approval"] = changes["approval"].to_dict()
        if "case_file" in changes and isinstance(changes["case_file"], PilotCaseFile):
            values["case_file"] = changes["case_file"].to_dict()
        if "setup_receipt" in changes and isinstance(changes["setup_receipt"], PilotSetupReceipt):
            values["setup_receipt"] = changes["setup_receipt"].to_dict()
        if "trace" in changes:
            values["stage_trace"] = list(changes["trace"])
            values.pop("trace", None)
        values.pop("schema_version", None)
        return PilotResult.from_dict(values)

    def _save(self, result: PilotResult) -> PilotResult:
        try:
            view_id = f"sunset-pilot-v1-{result.run_id}-{result.revision:04d}"
            self.store.put_view(view_id, result.to_json().encode("utf-8"))
        except ArtifactStoreError as exc:
            raise PilotServiceError("run_checkpoint_failed", exc.message) from exc
        return result

    def _load(self, run_id: str) -> PilotResult | None:
        prefix = f"sunset-pilot-v1-{run_id}-"
        candidates: list[PilotResult] = []
        for view_id in self.store.list_views(prefix=prefix):
            data = self.store.read_view(view_id)
            if data is None:
                continue
            try:
                candidates.append(PilotResult.from_dict(json.loads(data)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise PilotServiceError("run_checkpoint_invalid", str(exc)) from exc
        if not candidates:
            return None
        return max(candidates, key=lambda result: result.revision)


class RecordedPilotBackend:
    """Recorded G32 backend for deterministic product-path tests and demos."""

    def __init__(self, manifest: dict[str, Any], evidence: dict[str, Any], report: dict[str, Any], environment: dict[str, Any]) -> None:
        self.manifest = manifest
        self.evidence = {item["case_id"]: item for item in evidence["records"]}
        self.report = {item["case_id"]: item for item in report["cases"]}
        self.environment = environment

    @classmethod
    def from_paths(cls, manifest_path: str | Path, evidence_path: str | Path, report_path: str | Path, environment_path: str | Path) -> "RecordedPilotBackend":
        def load(path: str | Path) -> dict[str, Any]:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(load(manifest_path), load(evidence_path), load(report_path), load(environment_path))

    def prepare(self, request: PilotRequest) -> str:
        if request.mode != "recorded":
            raise PilotServiceError("environment_unavailable", "live pilot mode requires an explicitly configured backend")
        if request.repository_url != self.manifest["allowed_repository_urls"][0] or request.repository_ref != self.manifest["cases"][0]["pinned_ref"]:
            raise PilotServiceError("repository_not_recorded", "recorded backend has no exact repository/ref fixture")
        return request.repository_ref

    def resolve(self, request: PilotRequest) -> CandidateResolution:
        selector_path = request.candidate_path
        if not selector_path.startswith(request.scope + "/"):
            selector_path = f"{request.scope}/{selector_path}"
        matches = [case for case in self.manifest["cases"] if case["candidate_selector"]["path"] == selector_path and case["candidate_selector"]["test"] == request.candidate_test]
        if not matches:
            raise PilotServiceError("candidate_not_found", "candidate selector is not present in the pinned recorded snapshot")
        if len(matches) != 1:
            raise PilotServiceError("candidate_ambiguous", "candidate selector matched more than one recorded case")
        case = matches[0]
        record = self.evidence[case["case_id"]]
        return CandidateResolution(case["case_id"], case["pinned_ref"], record["marker_reason"], (record["record_digest"],), (f"sha256:{record['record_digest']}",))

    def collect_evidence(self, request: PilotRequest, candidate: CandidateResolution) -> CandidateResolution:
        return candidate

    def investigate(self, request: PilotRequest, candidate: CandidateResolution) -> InvestigationSummary:
        report = self.report[candidate.candidate_id]
        return InvestigationSummary(
            hypothesis=f"The marker appears to protect this condition: {candidate.hypothesis}",
            evidence_ids=candidate.evidence_ids,
            artifact_ids=candidate.artifact_ids,
            unresolved_obligations=("Production deployment and customer-support scope remain unproven.",),
        )

    def validate(self, request: PilotRequest, candidate: CandidateResolution) -> ValidationSummary:
        outcome = self.report[candidate.candidate_id].get("validation_outcome")
        if outcome is None:
            return ValidationSummary("inconclusive", unresolved_obligations=("No recorded validation outcome is available.",))
        return ValidationSummary(outcome, artifact_ids=candidate.artifact_ids)


__all__ = [
    "CandidateResolution",
    "InvestigationSummary",
    "PilotBackend",
    "PilotConfig",
    "PilotPreparation",
    "PilotService",
    "PilotServiceError",
    "RecordedPilotBackend",
    "ValidationSummary",
]
