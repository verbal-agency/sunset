"""Focused, read-only Git access for a committed repository snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
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
        try:
            return self.read_bytes(path).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryError(
                "source_decode_failed",
                f"source is not valid UTF-8 at byte {exc.start}",
            ) from exc

    def read_bytes(self, path: str) -> bytes:
        """Return exact bytes for a path in the immutable HEAD snapshot."""

        result = _run_git(self.root, "show", f"{self.head}:{path}")
        if result.returncode != 0:
            raise RepositoryError("git_show_failed", _git_error(result))
        return result.stdout

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

    def history_bytes(self, path: str, *, max_count: int = 25) -> bytes:
        """Return bounded, rename-aware history for one repository path."""

        result = _run_git(
            self.root,
            "log",
            "--follow",
            f"--max-count={max_count}",
            "--format=%H%x00%P%x00%an%x00%ae%x00%aI%x00%s",
            "--name-status",
            self.head,
            "--",
            path,
        )
        if result.returncode != 0:
            raise RepositoryError("git_history_failed", _git_error(result))
        return result.stdout

    def commit_patch_bytes(self, commit: str, path: str) -> bytes:
        """Return the relevant patch for a committed provenance point."""

        result = _run_git(
            self.root,
            "show",
            "--format=fuller",
            "--find-renames",
            "--patch",
            commit,
            "--",
            path,
        )
        if result.returncode != 0:
            raise RepositoryError("git_patch_failed", _git_error(result))
        return result.stdout

    def repository_identity(self) -> tuple[str, str]:
        """Return a deterministic origin identity without contacting a network."""

        remote_result = _run_git(self.root, "config", "--get", "remote.origin.url")
        if remote_result.returncode == 0:
            remote = _decode(remote_result.stdout).strip()
            if remote:
                return "origin_remote", _canonical_remote(remote)
        if remote_result.returncode not in {0, 1}:
            raise RepositoryError("git_config_failed", _git_error(remote_result))

        root_digest = hashlib.sha256(str(self.root).encode("utf-8")).hexdigest()
        return "local_path_sha256", f"sha256:{root_digest}"

    def is_shallow(self) -> bool:
        result = _run_git(self.root, "rev-parse", "--is-shallow-repository")
        if result.returncode != 0:
            raise RepositoryError("git_shallow_check_failed", _git_error(result))
        return _decode(result.stdout).strip() == "true"

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


def _canonical_remote(remote: str) -> str:
    normalized = remote.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized
