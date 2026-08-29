from __future__ import annotations

from pathlib import Path
import socket

from sunset.compatibility import scan_compatibility_repository
from sunset.git_repository import GitRepository
from sunset.provenance import collect_compatibility_provenance

from conftest import repository_snapshot, run_git


def test_collects_documented_guards_and_import_fallbacks(
    compatibility_repository: Path,
) -> None:
    result = scan_compatibility_repository(compatibility_repository)

    assert result.errors == ()
    assert result.repository_head == run_git(compatibility_repository, "rev-parse", "HEAD")
    assert [candidate.candidate_kind for candidate in result.candidates] == [
        "runtime_version_guard",
        "dependency_version_guard",
        "dependency_version_guard",
        "import_fallback",
        "import_fallback",
        "runtime_version_guard",
    ]
    runtime, packaged, direct, import_error, module_not_found, inner_nested = result.candidates
    assert (runtime.comparator, runtime.subject, runtime.threshold) == ("<", "runtime:python", "3.11")
    assert runtime.condition == "sys.version_info < (3, 11)"
    assert runtime.protected_imports == ("legacy_runtime.Parser",)
    assert runtime.fallback_imports == ("modern_runtime.Parser",)
    assert runtime.guard_span.start_line == 6
    assert runtime.protected_span.start_line == 7
    assert runtime.fallback_span is not None and runtime.fallback_span.start_line == 9
    assert (packaged.comparator, packaged.subject, packaged.threshold) == ("<", "dependency:upstream-lib", "2.4")
    assert (direct.comparator, direct.subject, direct.threshold) == (">=", "dependency:direct-lib", "5.0")
    assert import_error.condition == "ImportError"
    assert import_error.protected_imports == ("modern_api.Widget",)
    assert import_error.fallback_imports == ("legacy_api.Widget",)
    assert module_not_found.condition == "ModuleNotFoundError"
    assert all(candidate.candidate_id.startswith("sunset-compat-v1-") for candidate in result.candidates)
    assert all(len(candidate.blame_commit) == 40 for candidate in result.candidates)
    assert inner_nested.line > runtime.line


def test_excludes_dynamic_alias_general_and_policy_forms(compatibility_repository: Path) -> None:
    result = scan_compatibility_repository(compatibility_repository)
    conditions = {candidate.condition for candidate in result.candidates}

    assert "sys.version_info < minimum" not in conditions
    assert 'distribution_version("aliased-lib") < "1.0"' not in conditions
    assert 'sys.platform == "win32"' not in conditions
    assert "sys.version_info < (3, 8)" not in conditions


def test_compatibility_scan_is_stable_and_reads_committed_sources_only(
    compatibility_repository: Path,
) -> None:
    first = scan_compatibility_repository(compatibility_repository)
    (compatibility_repository / "src" / "untracked.py").write_text(
        "import sys\nif sys.version_info < (3, 1):\n from x import Y\nelse:\n from z import Y\n",
        encoding="utf-8",
    )
    second = scan_compatibility_repository(compatibility_repository)

    assert first.to_json().encode("utf-8") == second.to_json().encode("utf-8")
    assert [candidate.candidate_id for candidate in first.candidates] == [
        candidate.candidate_id for candidate in second.candidates
    ]
    assert GitRepository.open(compatibility_repository).list_python_files() == ("src/compatibility.py",)


def test_compatibility_provenance_reuses_g02_artifacts(
    compatibility_repository: Path,
    tmp_path: Path,
) -> None:
    from sunset.artifact_store import ArtifactStore

    store = ArtifactStore(tmp_path / "store")
    first = collect_compatibility_provenance(
        compatibility_repository, store_path=store.root, artifact_store=store
    )
    writes = (store.artifact_write_count, store.view_write_count)
    second = collect_compatibility_provenance(
        compatibility_repository, store_path=store.root, artifact_store=store
    )

    assert first.errors == ()
    assert len(first.candidates) == 6
    assert first.to_json().encode("utf-8") == second.to_json().encode("utf-8")
    assert (store.artifact_write_count, store.view_write_count) == writes
    assert all(entry.artifacts for entry in first.candidates)


def test_compatibility_collection_does_not_execute_or_mutate_or_use_network(
    compatibility_repository: Path,
    monkeypatch,
) -> None:
    status_before = run_git(compatibility_repository, "status", "--porcelain=v1", "--untracked-files=all")
    contents_before = repository_snapshot(compatibility_repository)

    def forbid_network(*args, **kwargs):
        raise AssertionError("collector attempted to create a network socket")

    monkeypatch.setattr(socket, "socket", forbid_network)
    result = scan_compatibility_repository(compatibility_repository)

    assert len(result.candidates) == 6
    assert status_before == run_git(compatibility_repository, "status", "--porcelain=v1", "--untracked-files=all")
    assert contents_before == repository_snapshot(compatibility_repository)
