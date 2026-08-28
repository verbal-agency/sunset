"""Focused, read-only Git access for a committed repository snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import subprocess


EXCLUDED_PATH_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "vendor",
        "venv",
    }
)


class RepositoryError(RuntimeError):
    """A supported repository failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class GitRepository:
    """A repository root, optional target prefix, and immutable HEAD snapshot."""

    root: Path
    target_prefix: str
    head: str

    @classmethod
    def open(cls, target: str | Path) -> GitRepository:
        requested = Path(target).expanduser()
        if not requested.exists() or not requested.is_dir():
            raise RepositoryError(
                "target_not_directory",
                "target must be an existing directory",
            )

        requested = requested.resolve()
        root_result = _run_git(requested, "rev-parse", "--show-toplevel")
        if root_result.returncode != 0:
            raise RepositoryError(
                "not_git_repository",
                "target is not inside a Git repository",
            )

        root = Path(_decode(root_result.stdout).strip()).resolve()
        try:
            prefix_path = requested.relative_to(root)
        except ValueError as exc:
            raise RepositoryError(
                "invalid_repository_root",
                "Git returned a repository root outside the requested target",
            ) from exc

        head_result = _run_git(root, "rev-parse", "--verify", "HEAD")
        if head_result.returncode != 0:
            raise RepositoryError(
                "missing_head",
                "repository does not have a committed HEAD",
            )

        target_prefix = "" if prefix_path == Path(".") else prefix_path.as_posix()
        return cls(root=root, target_prefix=target_prefix, head=_decode(head_result.stdout).strip())

    def list_test_files(self) -> tuple[str, ...]:
        result = _run_git(
            self.root,
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            self.head,
        )
        if result.returncode != 0:
            raise RepositoryError("git_ls_tree_failed", _git_error(result))

        paths = _decode(result.stdout).split("\0")
        selected = [
            path
            for path in paths
            if path and self._inside_target(path) and _is_test_file(path)
        ]
        return tuple(sorted(selected))

    def read_text(self, path: str) -> str:
        result = _run_git(self.root, "show", f"{self.head}:{path}")
        if result.returncode != 0:
            raise RepositoryError("git_show_failed", _git_error(result))
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryError(
                "source_decode_failed",
                f"source is not valid UTF-8 at byte {exc.start}",
            ) from exc

    def blame_commit(self, path: str, line: int) -> str:
        result = _run_git(
            self.root,
            "blame",
            "--line-porcelain",
            "-L",
            f"{line},{line}",
            self.head,
            "--",
            path,
        )
        if result.returncode != 0:
            raise RepositoryError("git_blame_failed", _git_error(result))

        first_line = _decode(result.stdout).splitlines()[0]
        commit = first_line.split(" ", 1)[0].lstrip("^")
        if not commit:
            raise RepositoryError("git_blame_failed", "Git blame returned no commit")
        return commit

    def _inside_target(self, path: str) -> bool:
        if not self.target_prefix:
            return True
        return path == self.target_prefix or path.startswith(f"{self.target_prefix}/")


def _is_test_file(path: str) -> bool:
    pure_path = PurePosixPath(path)
    if EXCLUDED_PATH_PARTS.intersection(pure_path.parts):
        return False
    name = pure_path.name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise RepositoryError("git_unavailable", f"unable to execute Git: {exc}") from exc


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _git_error(result: subprocess.CompletedProcess[bytes]) -> str:
    message = _decode(result.stderr).strip()
    return message or f"Git exited with status {result.returncode}"

