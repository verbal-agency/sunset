"""Execution seams for the G34 backtest: as-of clone check, reasoners, guards.

This module runs third-party test code, so it follows the G06/G33 posture
(``docs/SAFETY.md``): work happens only in disposable clones of an already-mined
local repository, the mined repository is never modified, commands are argv
lists (no shell), the child environment is scrubbed of credentials, and every
command is bounded by a timeout. It is host execution, not a security sandbox.
"""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any, Callable, Mapping

from sunset.history_backtest_models import BacktestCase, BacktestError, CaseRun, digest

_MARKERS = ("xfail", "skip", "skipif")
_ENV_ERROR_PATTERNS = re.compile(
    r"ModuleNotFoundError|ImportError|No module named|INTERNALERROR|no tests ran|ERROR collecting",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Execution:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


CommandRunner = Callable[[tuple[str, ...], Path, int, Mapping[str, str]], Execution]


def scrubbed_env(home: Path) -> dict[str, str]:
    """Minimal child environment: no API keys, tokens, or inherited credentials."""

    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "TMPDIR": str(home),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv")),
    }


def subprocess_runner(command: tuple[str, ...], cwd: Path, timeout: int, env: Mapping[str, str]) -> Execution:
    try:
        done = subprocess.run(
            list(command), cwd=cwd, env=dict(env), check=False, capture_output=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        return Execution(None, (exc.stdout or b"").decode("utf-8", "replace"), (exc.stderr or b"").decode("utf-8", "replace"), True)
    except OSError as exc:
        return Execution(None, "", str(exc))
    return Execution(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


@dataclass(frozen=True, slots=True)
class RepoRecipe:
    """Declared dependency recipe: only these packages are ever installed."""

    install_args: tuple[str, ...]
    test_args: tuple[str, ...] = ()
    allow_noneditable_fallback: bool = True


@dataclass(frozen=True, slots=True)
class RunnerPolicy:
    work_root: Path
    source_repos: Mapping[str, Path]  # repository name -> local mined clone
    recipes: Mapping[str, RepoRecipe]
    pythons: Mapping[str, str]  # "3.10" -> interpreter path
    python_switch_date: str = "2023-01-01"  # as-of before this uses 3.10, else 3.12
    setup_timeout: int = 900
    test_timeout: int = 300
    repeat_count: int = 2
    network_enabled: bool = False
    workers: int = 3

    def python_for(self, as_of_date: str) -> tuple[str, str]:
        key = "3.10" if as_of_date[:10] < self.python_switch_date else "3.12"
        if key not in self.pythons:
            raise BacktestError("python_missing", f"no interpreter configured for Python {key}")
        return key, self.pythons[key]


# ------------------------------------------------------------------ marker removal


def remove_markers(source: str, qualname: str) -> tuple[str, int]:
    """Delete only the supported marker decorators of one test; return (new source, removed)."""

    tree = ast.parse(source)
    parts = qualname.split("::")
    body: list[ast.stmt] = tree.body
    target: ast.AST | None = None
    for index, name in enumerate(parts):
        match = None
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                match = node
                break
        if match is None:
            raise BacktestError("test_not_found", f"{qualname} not found")
        target = match
        if index < len(parts) - 1:
            body = match.body  # type: ignore[union-attr]
    assert isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef))
    spans = []
    for dec in target.decorator_list:
        func = dec.func if isinstance(dec, ast.Call) else dec
        chain: list[str] = []
        while isinstance(func, ast.Attribute):
            chain.append(func.attr)
            func = func.value
        if isinstance(func, ast.Name):
            chain.append(func.id)
        chain.reverse()
        if len(chain) >= 2 and chain[-2] == "mark" and chain[-1] in _MARKERS:
            spans.append((dec.lineno, dec.end_lineno or dec.lineno))
    lines = source.splitlines(keepends=True)
    for start, end in sorted(spans, reverse=True):
        del lines[start - 1 : end]
    return "".join(lines), len(spans)


# --------------------------------------------------------------------- clone check


def classify_runs(results: list[str]) -> str:
    if any(r == "error" for r in results):
        return "environment_error"
    if all(r == "pass" for r in results):
        return "confirmed"
    if all(r == "fail" for r in results):
        return "still_failing"
    return "flaky"


def _single_run(execution: Execution) -> str:
    text = execution.stdout + "\n" + execution.stderr
    if execution.timed_out or execution.return_code is None:
        return "error"
    if execution.return_code == 0 and re.search(r"\b\d+ passed\b", text):
        return "pass"
    if execution.return_code == 1 and re.search(r"\b\d+ failed\b", text):
        return "error" if _ENV_ERROR_PATTERNS.search(text) else "fail"
    return "error"


@dataclass
class _EnvEntry:
    checkout: Path
    python: Path
    receipt: dict[str, Any]
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class CloneChecker:
    """Prepares one as-of environment per (repository, commit) and checks cases."""

    def __init__(self, policy: RunnerPolicy, runner: CommandRunner = subprocess_runner) -> None:
        self.policy = policy
        self.runner = runner
        self._envs: dict[tuple[str, str], _EnvEntry] = {}
        self._guard = threading.Lock()
        policy.work_root.mkdir(parents=True, exist_ok=True)
        self._home = Path(tempfile.mkdtemp(prefix="g34-home-", dir=policy.work_root))

    def _env(self) -> dict[str, str]:
        return scrubbed_env(self._home)

    def _prepare(self, case: BacktestCase, as_of_date: str) -> _EnvEntry:
        key = (case.repository, case.as_of_sha)
        with self._guard:
            entry = self._envs.get(key)
            if entry is None:
                entry = _EnvEntry(Path(), Path(), {})
                self._envs[key] = entry
                entry.lock.acquire()
                creator = True
            else:
                creator = False
        if not creator:
            with entry.lock:  # wait for the creator to finish preparing
                return entry
        try:
            self._build(entry, case, as_of_date)
        except BacktestError as exc:
            entry.error = f"{exc.code}: {exc.message}"
        finally:
            entry.lock.release()
        return entry

    def _build(self, entry: _EnvEntry, case: BacktestCase, as_of_date: str) -> None:
        policy = self.policy
        source = policy.source_repos.get(case.repository)
        recipe = policy.recipes.get(case.repository)
        if source is None or recipe is None:
            raise BacktestError("recipe_missing", f"no source clone or recipe for {case.repository}")
        py_key, python = policy.python_for(as_of_date)
        base = policy.work_root / "envs" / f"{case.repository}-{case.as_of_sha[:12]}"
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)
        checkout = base / "checkout"
        for command in (
            ("git", "clone", "--no-hardlinks", "--quiet", str(source), str(checkout)),
            ("git", "-C", str(checkout), "checkout", "--detach", "--quiet", case.as_of_sha),
        ):
            done = self.runner(command, base, policy.setup_timeout, self._env())
            if done.return_code != 0:
                raise BacktestError("checkout_failed", done.stderr.strip()[:300])
        head = self.runner(("git", "-C", str(checkout), "rev-parse", "HEAD"), base, 60, self._env()).stdout.strip()
        if head != case.as_of_sha:
            raise BacktestError("checkout_ref_mismatch", "checkout does not match the pinned as-of commit")
        if not policy.network_enabled:
            raise BacktestError("network_not_authorized", "dependency installation requires explicit network authorization")
        venv = base / "venv"
        done = self.runner(("uv", "venv", "--quiet", "--python", python, str(venv)), base, policy.setup_timeout, self._env())
        if done.return_code != 0:
            raise BacktestError("runtime_setup_failed", done.stderr.strip()[:300])
        venv_python = venv / "bin" / "python"
        install = (
            "uv", "pip", "install", "--quiet", "--python", str(venv_python),
            "--exclude-newer", as_of_date[:10] + "T23:59:59Z", *recipe.install_args,
        )
        done = self.runner(install, checkout, policy.setup_timeout, self._env())
        install_mode = "editable"
        if done.return_code != 0 and recipe.allow_noneditable_fallback and "-e" in recipe.install_args:
            # PEP 660 editable installs are unavailable in older pinned
            # repositories. Retry the same declared dependency set as a
            # regular wheel install; never broaden packages or paths.
            fallback_args = tuple("." if arg == "-e" else arg for arg in recipe.install_args)
            fallback = (
                "uv", "pip", "install", "--quiet", "--python", str(venv_python),
                "--exclude-newer", as_of_date[:10] + "T23:59:59Z", *fallback_args,
            )
            done = self.runner(fallback, checkout, policy.setup_timeout, self._env())
            install_mode = "noneditable_fallback"
        if done.return_code != 0:
            raise BacktestError("dependency_setup_failed", done.stderr.strip()[-300:])
        frozen = self.runner(("uv", "pip", "freeze", "--python", str(venv_python)), checkout, 120, self._env()).stdout
        entry.checkout = checkout
        entry.python = venv_python
        entry.receipt = {
            "python": py_key,
            "as_of_commit": case.as_of_sha,
            "exclude_newer": as_of_date[:10],
            "install_args": list(recipe.install_args),
            "install_mode": install_mode,
            "packages_digest": digest(sorted(frozen.splitlines())),
        }

    def check(self, case: BacktestCase, as_of_date: str) -> tuple[str, str | None, dict[str, Any]]:
        """Return (clone_outcome, note, receipt). Never mutates the mined repository."""

        entry = self._prepare(case, as_of_date)
        if entry.error:
            return "environment_error", entry.error[:200], entry.receipt
        recipe = self.policy.recipes[case.repository]
        with entry.lock:
            target = entry.checkout / case.test_path
            original = target.read_text(encoding="utf-8")
            try:
                edited, removed = remove_markers(original, case.test_qualname)
                if removed == 0:
                    return "environment_error", "no supported marker found at the as-of commit", entry.receipt
                target.write_text(edited, encoding="utf-8")
                node = f"{case.test_path}::{case.test_qualname}"
                command = (
                    str(entry.python), "-m", "pytest", node, "-p", "no:cacheprovider", "-q", "--no-header",
                    "-W", "ignore", *recipe.test_args,
                )
                results = []
                for _ in range(self.policy.repeat_count):
                    results.append(_single_run(self.runner(command, entry.checkout, self.policy.test_timeout, self._env())))
                outcome = classify_runs(results)
                return outcome, ",".join(results), entry.receipt
            except BacktestError as exc:
                return "environment_error", f"{exc.code}: {exc.message}"[:200], entry.receipt
            finally:
                target.write_text(original, encoding="utf-8")  # restore: the clone stays pristine


def run_clone_checks(
    cases: list[BacktestCase], dates: Mapping[str, str], checker: CloneChecker
) -> dict[str, tuple[str, str | None, dict[str, Any]]]:
    """Run checks grouped by environment; groups run in parallel, cases within one are sequential."""

    groups: dict[tuple[str, str], list[BacktestCase]] = {}
    for case in cases:
        groups.setdefault((case.repository, case.as_of_sha), []).append(case)

    def run_group(group: list[BacktestCase]) -> list[tuple[str, tuple[str, str | None, dict[str, Any]]]]:
        return [(c.case_id, checker.check(c, dates[c.case_id])) for c in group]

    out: dict[str, tuple[str, str | None, dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=checker.policy.workers) as pool:
        for rows in pool.map(run_group, [groups[k] for k in sorted(groups)]):
            out.update(rows)
    return out


# ------------------------------------------------------------------ reasoner guards


@dataclass(frozen=True, slots=True)
class LiveAuthorization:
    """Explicit, caller-supplied permission for model calls, with a hard cap."""

    model: str
    max_calls: int
    granted_by: str


class CostGuard:
    def __init__(self, authorization: LiveAuthorization | None) -> None:
        if authorization is None:
            raise BacktestError("live_not_authorized", "a live agent run requires an explicit LiveAuthorization")
        if authorization.max_calls <= 0:
            raise BacktestError("cost_cap_invalid", "max_calls must be positive")
        self.authorization = authorization
        self.calls = 0
        self._lock = threading.Lock()

    def charge(self) -> None:
        with self._lock:
            if self.calls >= self.authorization.max_calls:
                raise BacktestError("cost_cap_reached", "the declared model-call cap was reached")
            self.calls += 1


def guarded_reasoner(inner: Callable[[str], str], guard: CostGuard) -> Callable[[str], str]:
    def reason(case_id: str) -> str:
        guard.charge()
        return inner(case_id)

    return reason


def build_runs(
    cases: list[BacktestCase],
    checks: Mapping[str, tuple[str, str | None, dict[str, Any]]],
    *,
    heuristic: Callable[[str], str],
    agent: Callable[[str], str] | None,
) -> list[CaseRun]:
    runs = []
    for case in sorted(cases, key=lambda c: c.case_id):
        outcome, note, receipt = checks.get(case.case_id, (None, "not_checked", {}))  # type: ignore[assignment]
        runs.append(
            CaseRun(
                case_id=case.case_id,
                heuristic_status=heuristic(case.case_id),
                agent_status=agent(case.case_id) if agent else None,
                clone_outcome=outcome,
                clone_note=note,
                extras={"environment": receipt},
            )
        )
    return runs


__all__ = [
    "CloneChecker",
    "CommandRunner",
    "CostGuard",
    "Execution",
    "LiveAuthorization",
    "RepoRecipe",
    "RunnerPolicy",
    "build_runs",
    "classify_runs",
    "guarded_reasoner",
    "remove_markers",
    "run_clone_checks",
    "scrubbed_env",
    "subprocess_runner",
]
