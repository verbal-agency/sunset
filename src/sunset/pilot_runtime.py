"""Bounded executable backend for the unified pilot workflow.

The backend owns only disposable clones and declared environments.  It never
mutates the requested source checkout and never invokes a shell string.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Callable
from urllib.parse import urlparse
from pathlib import PurePosixPath

from sunset.artifact_store import ArtifactStore
from sunset.investigation import InvestigationConfig, investigate_candidate
from sunset.natural_corpus import EnvironmentRecipe, load_environment_recipes
from sunset.pilot_models import PilotRequest, PilotSetupReceipt
from sunset.pilot_service import (
    CandidateResolution,
    InvestigationSummary,
    PilotPreparation,
    PilotServiceError,
    ValidationSummary,
)
from sunset.provenance import collect_provenance
from sunset.scanner import scan_repository
from sunset.validation import ValidationConfig, validate_candidate
from sunset.validation_models import CommandExecution


CommandRunner = Callable[[tuple[str, ...], Path, int], CommandExecution]


class PilotRuntimeError(PilotServiceError):
    """A structured setup, authority, or execution failure."""


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    allowed_hosts: tuple[str, ...] = ("github.com",)
    network_enabled: bool = False
    source_checkout: Path | None = None
    python_executable: str | None = None
    setup_timeout_seconds: int = 120
    max_output_bytes: int = 2_000_000
    install_dependencies: bool = True

    def __post_init__(self) -> None:
        if self.setup_timeout_seconds < 1:
            raise ValueError("setup_timeout_seconds must be positive")
        if self.max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")


class LivePilotBackend:
    """Execute one approved pilot through a pinned, disposable checkout."""

    def __init__(
        self,
        *,
        environment_path: str | Path,
        store: ArtifactStore,
        policy: RuntimePolicy | None = None,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.store = store
        self.policy = policy or RuntimePolicy()
        self.command_runner = command_runner or _run_command
        self.recipes = load_environment_recipes(environment_path)
        self.checkout_path: Path | None = None
        self.runtime_python: str | None = None
        self.recipe: EnvironmentRecipe | None = None
        self.preparation: PilotPreparation | None = None

    def prepare(self, request: PilotRequest) -> PilotPreparation:
        if request.mode != "live":
            raise PilotRuntimeError("environment_unavailable", "live backend requires mode=live")
        recipe = self._select_recipe(request)
        self.recipe = recipe
        run_key = request.digest()[:24]
        run_root = self.store.root / "pilot-runs" / run_key
        checkout = run_root / "repository"
        setup_view = self.store.read_view(f"sunset-pilot-runtime-v1-{run_key}")
        if setup_view is not None and checkout.exists():
            preparation = self._load_cached_preparation(setup_view, checkout, request)
            self.checkout_path = checkout
            self.runtime_python = preparation.setup_receipt.environment["runtime_python"]
            self.preparation = preparation
            return preparation

        run_root.mkdir(parents=True, exist_ok=True)
        if checkout.exists():
            shutil.rmtree(checkout)
        self._clone(request, checkout)
        observed_head = self._git_output(("git", "-C", str(checkout), "rev-parse", "HEAD"), run_root).strip()
        if observed_head != request.repository_ref:
            raise PilotRuntimeError("checkout_ref_mismatch", "disposable checkout HEAD does not match requested SHA")
        snapshot_digest = self._git_output(
            ("git", "-C", str(checkout), "rev-parse", f"{observed_head}^{{tree}}"), run_root
        ).strip()
        checkout_receipt = {
            "repository_url": request.repository_url,
            "requested_ref": request.repository_ref,
            "observed_head": observed_head,
            "policy_id": "g33-v1",
            "snapshot_digest": snapshot_digest,
        }

        runtime_python = self._prepare_environment(recipe, checkout, run_root)
        self.runtime_python = runtime_python
        environment_receipt = {
            "environment_id": recipe.environment_id,
            "python": recipe.python,
            "runtime_python": runtime_python,
            "dependency_digest": recipe.dependency_digest,
            "install_commands": [list(command) for command in recipe.install_commands],
            "budgets": dict(sorted(recipe.budgets.items())),
            "platform": platform.platform(),
        }
        checkout_artifact = self._put_receipt(
            checkout_receipt,
            "pilot_checkout_receipt",
            f"pilot:{run_key}:checkout",
        )
        environment_artifact = self._put_receipt(
            environment_receipt,
            "pilot_environment_receipt",
            f"pilot:{run_key}:environment",
        )
        setup = PilotSetupReceipt(checkout_receipt, environment_receipt)
        preparation = PilotPreparation(
            repository_head=observed_head,
            setup_receipt=setup,
            artifact_ids=(checkout_artifact, environment_artifact),
        )
        self.store.put_view(
            f"sunset-pilot-runtime-v1-{run_key}",
            json.dumps(
                {"checkout_dir": str(checkout), "preparation": setup.to_dict(), "artifact_ids": list(preparation.artifact_ids)},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8"),
        )
        self.checkout_path = checkout
        self.preparation = preparation
        return preparation

    def resolve(self, request: PilotRequest) -> CandidateResolution:
        self._ensure_prepared(request)
        checkout = self._require_checkout()
        target = checkout / request.scope
        scan = scan_repository(target)
        selector_path = request.candidate_path
        if not selector_path.startswith(request.scope + "/"):
            selector_path = f"{request.scope}/{selector_path}"
        matches = [
            candidate
            for candidate in scan.candidates
            if candidate.path == selector_path and candidate.qualified_name == request.candidate_test
        ]
        if not matches:
            raise PilotRuntimeError("candidate_not_found", "candidate selector is not present in the pinned checkout")
        if len(matches) != 1:
            raise PilotRuntimeError("candidate_ambiguous", "candidate selector matched more than one candidate")
        candidate = matches[0]
        return CandidateResolution(
            candidate_id=candidate.candidate_id,
            repository_head=candidate.repository_head,
            hypothesis=candidate.reason or "The marker protects an unknown temporary condition.",
            evidence_ids=(),
            artifact_ids=self.preparation.artifact_ids if self.preparation else (),
        )

    def collect_evidence(self, request: PilotRequest, candidate: CandidateResolution) -> CandidateResolution:
        self._ensure_prepared(request)
        checkout = self._require_checkout()
        provenance = collect_provenance(
            checkout / request.scope,
            store_path=self.store.root,
            artifact_store=self.store,
        )
        entry = next((item for item in provenance.candidates if item.candidate_id == candidate.candidate_id), None)
        if entry is None:
            raise PilotRuntimeError("provenance_unavailable", "candidate provenance was not available in the pinned checkout")
        return CandidateResolution(
            candidate.candidate_id,
            candidate.repository_head,
            candidate.hypothesis,
            tuple(artifact.artifact_id for artifact in entry.artifacts),
            tuple(dict.fromkeys((*candidate.artifact_ids, *(artifact.artifact_id for artifact in entry.artifacts)))),
        )

    def investigate(self, request: PilotRequest, candidate: CandidateResolution) -> InvestigationSummary:
        self._ensure_prepared(request)
        checkout = self._require_checkout()
        result = investigate_candidate(
            checkout / request.scope,
            store_path=self.store.root,
            candidate_id=candidate.candidate_id,
            config=InvestigationConfig(evidence_mode="offline"),
            artifact_store=self.store,
        )
        unresolved = tuple(dict.fromkeys((*result.open_questions, *(error.message for error in result.errors))))
        selected = tuple(item.artifact_id for item in result.selected_evidence)
        return InvestigationSummary(
            hypothesis=candidate.hypothesis,
            evidence_ids=tuple(dict.fromkeys((*candidate.evidence_ids, *selected))),
            artifact_ids=tuple(dict.fromkeys((*candidate.artifact_ids, *selected))),
            unresolved_obligations=unresolved or ("Operational deployment and customer scope remain unproven.",),
        )

    def validate(self, request: PilotRequest, candidate: CandidateResolution) -> ValidationSummary:
        self._ensure_prepared(request)
        checkout = self._require_checkout()
        recipe = self.recipe
        if recipe is None:
            raise PilotRuntimeError("environment_unavailable", "no environment recipe is bound to this run")
        result = validate_candidate(
            checkout,
            store_path=self.store.root,
            candidate_id=candidate.candidate_id,
            approved=True,
            collector="pytest",
            config=ValidationConfig(
                repeat_count=2,
                timeout_seconds=int(recipe.budgets.get("timeout_seconds", 120)),
                python_executable=self.runtime_python,
            ),
            artifact_store=self.store,
        )
        artifact_ids = list(candidate.artifact_ids)
        if result.environment is not None:
            artifact_ids.append(result.environment.artifact.artifact_id)
        for run in result.runs:
            artifact_ids.append(run.output.artifact_id)
        return ValidationSummary(
            outcome=result.status,
            artifact_ids=tuple(dict.fromkeys(artifact_ids)),
            unresolved_obligations=tuple(error.message for error in result.errors),
        )

    def _select_recipe(self, request: PilotRequest) -> EnvironmentRecipe:
        matches = [
            recipe
            for recipe in self.recipes.values()
            if recipe.repository_url == request.repository_url and recipe.pinned_ref == request.repository_ref
        ]
        if len(matches) != 1:
            code = "environment_recipe_missing" if not matches else "environment_recipe_ambiguous"
            raise PilotRuntimeError(code, "no unique environment recipe matches repository and pinned ref")
        return matches[0]

    def _clone(self, request: PilotRequest, destination: Path) -> None:
        parsed = urlparse(request.repository_url)
        if parsed.scheme != "https":
            raise PilotRuntimeError("repository_url_invalid", "repository URL must use HTTPS")
        if self.policy.source_checkout is not None:
            source = self.policy.source_checkout.expanduser().resolve()
            if not source.is_dir():
                raise PilotRuntimeError("source_checkout_missing", "configured source checkout does not exist")
            command = ("git", "clone", "--no-hardlinks", "--quiet", str(source), str(destination))
        else:
            if not self.policy.network_enabled:
                raise PilotRuntimeError("network_not_authorized", "live clone requires explicit network authorization")
            if parsed.hostname not in self.policy.allowed_hosts:
                raise PilotRuntimeError("repository_host_denied", "repository host is outside the configured allowlist")
            command = ("git", "clone", "--no-hardlinks", "--quiet", request.repository_url, str(destination))
        execution = self.command_runner(command, self.store.root, self.policy.setup_timeout_seconds)
        if execution.return_code != 0:
            raise PilotRuntimeError("clone_failed", execution.stderr.decode("utf-8", errors="replace") or "git clone failed")
        checkout = self.command_runner(
            ("git", "-C", str(destination), "checkout", "--detach", "--quiet", request.repository_ref),
            self.store.root,
            self.policy.setup_timeout_seconds,
        )
        if checkout.return_code != 0:
            raise PilotRuntimeError("checkout_failed", checkout.stderr.decode("utf-8", errors="replace") or "git checkout failed")

    def _prepare_environment(self, recipe: EnvironmentRecipe, checkout: Path, run_root: Path) -> str:
        runtime_python = self.policy.python_executable
        if runtime_python is None:
            venv = run_root / "venv"
            execution = self.command_runner(
                (sys.executable, "-m", "venv", str(venv)),
                checkout,
                self.policy.setup_timeout_seconds,
            )
            if execution.return_code != 0:
                raise PilotRuntimeError("runtime_setup_failed", "unable to create isolated Python runtime")
            runtime_python = str(venv / "bin" / "python")
        if not Path(runtime_python).exists():
            raise PilotRuntimeError("runtime_missing", "selected Python runtime does not exist")
        if not self.policy.install_dependencies:
            return runtime_python
        if not self.policy.network_enabled:
            raise PilotRuntimeError(
                "network_not_authorized",
                "declared dependency installation requires explicit network authorization",
            )
        for command in recipe.install_commands:
            self._validate_declared_command(command, checkout)
            rewritten = (runtime_python, *command[1:])
            execution = self.command_runner(rewritten, checkout, self.policy.setup_timeout_seconds)
            if execution.return_code != 0:
                raise PilotRuntimeError("dependency_setup_failed", "declared dependency installation failed")
            if len(execution.stdout) + len(execution.stderr) > self.policy.max_output_bytes:
                raise PilotRuntimeError("setup_output_budget_exhausted", "setup command output exceeded its budget")
        return runtime_python

    def _validate_declared_command(self, command: tuple[str, ...], checkout: Path) -> None:
        if not command or command[0] != "python" or any(any(char in part for char in ";&|><$`") for part in command):
            raise PilotRuntimeError("undeclared_command", "environment recipes may contain only argv Python commands")
        if len(command) < 4 or command[1:3] != ("-m", "pip") or command[3] != "install":
            raise PilotRuntimeError("undeclared_command", "only python -m pip install commands are permitted")
        if "-e" in command:
            index = command.index("-e")
            if index + 1 >= len(command):
                raise PilotRuntimeError("undeclared_command", "editable install is missing its path")
            location = command[index + 1].split("[", 1)[0]
            pure = PurePosixPath(location)
            resolved = (checkout / pure).resolve()
            try:
                resolved.relative_to(checkout.resolve())
            except ValueError as exc:
                raise PilotRuntimeError("undeclared_command", "editable install path escapes the pinned checkout") from exc

    def _git_output(self, command: tuple[str, ...], cwd: Path) -> str:
        execution = self.command_runner(command, cwd, self.policy.setup_timeout_seconds)
        if execution.return_code != 0:
            raise PilotRuntimeError("git_command_failed", execution.stderr.decode("utf-8", errors="replace"))
        return execution.stdout.decode("utf-8", errors="replace")

    def _put_receipt(self, value: dict[str, object], source_kind: str, locator: str) -> str:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self.store.put(data, media_type="application/json", source_kind=source_kind, source_locator=locator).artifact_id

    def _load_cached_preparation(self, data: bytes, checkout: Path, request: PilotRequest) -> PilotPreparation:
        value = json.loads(data)
        setup = value["preparation"]
        observed = setup["checkout"]["observed_head"]
        if observed != request.repository_ref:
            raise PilotRuntimeError("checkout_ref_mismatch", "cached checkout does not match requested SHA")
        return PilotPreparation(
            repository_head=observed,
            setup_receipt=PilotSetupReceipt(dict(setup["checkout"]), dict(setup["environment"])),
            artifact_ids=tuple(value["artifact_ids"]),
        )

    def _require_checkout(self) -> Path:
        if self.checkout_path is None or self.preparation is None:
            raise PilotRuntimeError("setup_required", "pilot setup must complete before this stage")
        return self.checkout_path

    def _ensure_prepared(self, request: PilotRequest) -> None:
        if self.preparation is None:
            self.prepare(request)


def _run_command(command: tuple[str, ...], cwd: Path, timeout_seconds: int) -> CommandExecution:
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandExecution(None, exc.stderr or b"", exc.stdout or b"", timed_out=True)
    except OSError as exc:
        return CommandExecution(None, str(exc).encode("utf-8"), b"")
    return CommandExecution(result.returncode, result.stderr, result.stdout)


__all__ = ["LivePilotBackend", "PilotRuntimeError", "RuntimePolicy"]
