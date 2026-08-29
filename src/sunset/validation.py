"""Approval-gated validation in a disposable local clone of a Git snapshot."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Callable, Literal

from sunset.artifact_store import ArtifactStore
from sunset.git_repository import GitRepository
from sunset.models import Candidate
from sunset.scanner import scan_repository
from sunset.validation_models import (
    CommandExecution,
    CommandRun,
    EnvironmentManifest,
    ValidationError,
    ValidationResult,
)


CommandRunner = Callable[[tuple[str, ...], Path, int], CommandExecution]


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    repeat_count: int = 2
    broader_commands: tuple[tuple[str, ...], ...] = ()
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if self.repeat_count < 1:
            raise ValueError("repeat_count must be at least one")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be at least one")
        if any(not command for command in self.broader_commands):
            raise ValueError("broader commands must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "repeat_count": self.repeat_count,
            "broader_commands": [list(command) for command in self.broader_commands],
            "timeout_seconds": self.timeout_seconds,
        }


def validate_candidate(
    target: str | Path,
    *,
    store_path: str | Path,
    candidate_id: str,
    approved: bool = False,
    collector: Literal["pytest", "compatibility"] = "pytest",
    config: ValidationConfig | None = None,
    artifact_store: ArtifactStore | None = None,
    command_runner: CommandRunner | None = None,
) -> ValidationResult:
    """Validate one marker only after explicit approval, never in *target*."""

    config = config or ValidationConfig()
    repository = GitRepository.open(target)
    if not approved:
        return _result(
            approved=False,
            candidate_id=candidate_id,
            collector=collector,
            repository_head=repository.head,
            status="approval_required",
            errors=(ValidationError("approval_required", "Pass explicit approval before Sunset creates a disposable clone or runs tests."),),
        )
    if collector != "pytest":
        return _result(
            approved=True,
            candidate_id=candidate_id,
            collector=collector,
            repository_head=repository.head,
            status="inconclusive",
            errors=(ValidationError("unsupported_collector", "G06 validates only pytest-marker candidates."),),
        )
    store = artifact_store or ArtifactStore(store_path)
    if store.root != Path(store_path).expanduser().resolve():
        raise ValueError("injected artifact store does not match store_path")
    if _inside_repository(store.root, repository.root):
        return _result(
            approved=True,
            candidate_id=candidate_id,
            collector=collector,
            repository_head=repository.head,
            status="inconclusive",
            errors=(ValidationError("artifact_store_inside_repository", "validation artifacts must be stored outside the analyzed repository."),),
        )
    candidate = next(
        (item for item in scan_repository(target).candidates if item.candidate_id == candidate_id),
        None,
    )
    if candidate is None:
        return _result(
            approved=True,
            candidate_id=candidate_id,
            collector=collector,
            repository_head=repository.head,
            status="inconclusive",
            errors=(ValidationError("candidate_not_found", "candidate was not available in the committed repository snapshot."),),
        )
    run_id = _run_id(repository, candidate, config)
    environment = _record_environment(store, run_id, repository.head, candidate, config)
    runner = command_runner or _run_command
    with tempfile.TemporaryDirectory(prefix="sunset-validation-") as temporary:
        sandbox = Path(temporary) / "repository"
        clone_error = _create_clone(repository.root, repository.head, sandbox)
        if clone_error is not None:
            return _result(
                approved=True,
                candidate_id=candidate_id,
                collector=collector,
                repository_head=repository.head,
                environment=environment,
                status="inconclusive",
                errors=(clone_error,),
            )
        transform_error = _remove_marker(sandbox, candidate)
        if transform_error is not None:
            return _result(
                approved=True,
                candidate_id=candidate_id,
                collector=collector,
                repository_head=repository.head,
                environment=environment,
                status="inconclusive",
                errors=(transform_error,),
            )
        runs = _run_tests(sandbox, candidate, config, runner, store, run_id)
    return _result(
        approved=True,
        candidate_id=candidate_id,
        collector=collector,
        repository_head=repository.head,
        environment=environment,
        runs=runs,
        status=_classify(runs),
    )


def _result(
    *,
    approved: bool,
    candidate_id: str,
    collector: str,
    repository_head: str,
    status: str,
    environment: EnvironmentManifest | None = None,
    errors: tuple[ValidationError, ...] = (),
    runs: tuple[CommandRun, ...] = (),
) -> ValidationResult:
    return ValidationResult(
        approved=approved,
        candidate_id=candidate_id,
        collector=collector,
        environment=environment,
        errors=errors,
        repository_head=repository_head,
        runs=runs,
        status=status,  # type: ignore[arg-type]
    )


def _inside_repository(path: Path, repository_root: Path) -> bool:
    try:
        path.relative_to(repository_root)
    except ValueError:
        return False
    return True


def _run_id(repository: GitRepository, candidate: Candidate, config: ValidationConfig) -> str:
    identity_kind, identity_value = repository.repository_identity()
    value = json.dumps(
        {
            "repository_identity": [identity_kind, identity_value],
            "head": repository.head,
            "candidate_id": candidate.candidate_id,
            "config": config.to_dict(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _record_environment(
    store: ArtifactStore,
    run_id: str,
    head: str,
    candidate: Candidate,
    config: ValidationConfig,
) -> EnvironmentManifest:
    packages = sorted(
        f"{distribution.metadata['Name']}=={distribution.version}"
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    )
    value = {
        "schema_version": "1",
        "run_id": run_id,
        "candidate_id": candidate.candidate_id,
        "repository_head": head,
        "config": config.to_dict(),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "platform": platform.platform(),
        "packages": packages,
    }
    data = _json_bytes(value)
    fingerprint = hashlib.sha256(data).hexdigest()
    artifact = store.put(
        data,
        media_type="application/json",
        source_kind="sandbox_environment_manifest",
        source_locator=f"validation:{run_id}:environment",
    )
    return EnvironmentManifest(artifact=artifact, fingerprint=fingerprint)


def _create_clone(source: Path, head: str, sandbox: Path) -> ValidationError | None:
    clone = subprocess.run(
        ["git", "clone", "--no-hardlinks", "--quiet", str(source), str(sandbox)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if clone.returncode != 0:
        return ValidationError("sandbox_clone_failed", _message(clone.stderr, "unable to create disposable clone"))
    checkout = subprocess.run(
        ["git", "-C", str(sandbox), "checkout", "--detach", "--quiet", head],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if checkout.returncode != 0:
        return ValidationError("sandbox_checkout_failed", _message(checkout.stderr, "unable to pin disposable clone to candidate HEAD"))
    return None


def _remove_marker(sandbox: Path, candidate: Candidate) -> ValidationError | None:
    path = (sandbox / candidate.path).resolve()
    try:
        path.relative_to(sandbox.resolve())
    except ValueError:
        return ValidationError("candidate_path_unsafe", "candidate path escapes the disposable clone.")
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationError("sandbox_source_read_failed", str(exc))
    try:
        tree = ast.parse(source, filename=candidate.path)
    except SyntaxError as exc:
        return ValidationError("sandbox_source_parse_failed", exc.msg)
    decorator = _find_decorator(tree, source, candidate)
    if decorator is None or decorator.end_lineno is None:
        return ValidationError("marker_span_not_found", "selected marker decorator was not found at its committed AST span.")
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: decorator.lineno - 1])
    end = sum(len(line) for line in lines[: decorator.end_lineno])
    path.write_text(source[:start] + source[end:], encoding="utf-8")
    return None


def _find_decorator(tree: ast.AST, source: str, candidate: Candidate) -> ast.expr | None:
    for node in ast.walk(tree):
        decorators = getattr(node, "decorator_list", None)
        if not isinstance(decorators, list):
            continue
        for decorator in decorators:
            if not isinstance(decorator, ast.expr) or decorator.lineno != candidate.line:
                continue
            source_line = source.splitlines()[decorator.lineno - 1]
            if source_line.find("@") != candidate.column:
                continue
            call = decorator if isinstance(decorator, ast.Call) else None
            target = call.func if call is not None else decorator
            if _attribute_chain(target) == ("pytest", "mark", candidate.marker_kind):
                return decorator
    return None


def _attribute_chain(node: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    else:
        return ()
    return tuple(reversed(parts))


def _run_tests(
    sandbox: Path,
    candidate: Candidate,
    config: ValidationConfig,
    runner: CommandRunner,
    store: ArtifactStore,
    run_id: str,
) -> tuple[CommandRun, ...]:
    target = "::".join((candidate.path, *candidate.qualified_name.split(".")))
    narrow = (sys.executable, "-m", "pytest", "-q", target)
    scheduled: list[tuple[Literal["narrow", "broader"], int, tuple[str, ...]]] = [
        ("narrow", attempt, narrow) for attempt in range(1, config.repeat_count + 1)
    ]
    scheduled.extend(("broader", attempt, command) for attempt, command in enumerate(config.broader_commands, 1))
    runs: list[CommandRun] = []
    for phase, attempt, command in scheduled:
        execution = runner(command, sandbox, config.timeout_seconds)
        output = _record_output(store, run_id, phase, attempt, command, execution)
        runs.append(
            CommandRun(
                command=command,
                phase=phase,
                attempt=attempt,
                return_code=execution.return_code,
                output=output,
                timed_out=execution.timed_out,
            )
        )
        if execution.timed_out or execution.return_code not in {0, 1}:
            break
    return tuple(runs)


def _run_command(command: tuple[str, ...], cwd: Path, timeout_seconds: int) -> CommandExecution:
    try:
        result = subprocess.run(
            command,
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


def _record_output(
    store: ArtifactStore,
    run_id: str,
    phase: str,
    attempt: int,
    command: tuple[str, ...],
    execution: CommandExecution,
):
    data = _json_bytes(
        {
            "command": list(command),
            "return_code": execution.return_code,
            "stdout": execution.stdout.decode("utf-8", errors="replace"),
            "stderr": execution.stderr.decode("utf-8", errors="replace"),
            "timed_out": execution.timed_out,
        }
    )
    return store.put(
        data,
        media_type="application/json",
        source_kind="sandbox_test_output",
        source_locator=f"validation:{run_id}:{phase}:{attempt}",
    )


def _classify(runs: tuple[CommandRun, ...]) -> str:
    if not runs:
        return "inconclusive"
    if any(run.timed_out or run.return_code not in {0, 1} for run in runs):
        return "environment_error"
    codes = {run.return_code for run in runs}
    if codes == {0}:
        return "confirmed"
    if codes == {1}:
        return "still_failing"
    return "flaky"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _message(value: bytes, fallback: str) -> str:
    message = value.decode("utf-8", errors="replace").strip()
    return message or fallback
