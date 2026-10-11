"""Deterministic mining, classification, case building, and reporting for G34.

Everything here is git-only and offline once a repository is cloned: no model, no
test execution, no network. Labels derive from commit history and diff
classification alone. Clone execution and agent calls live in
``history_backtest_runner`` and are injected.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import warnings
from typing import Any, Callable, Iterable

from sunset.history_backtest_models import (
    BACKTEST_SCHEMA_VERSION,
    EVENT_CLASSES,
    MAINTAINER_EXPECTATION,
    SPLITS,
    BacktestCase,
    BacktestError,
    CaseRun,
    EvidenceItem,
    Exclusion,
    HistoricalEvent,
    MarkerRecord,
    MiningResult,
    digest,
)

SUPPORTED_MARKERS = ("xfail", "skip", "skipif")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DOC_BASENAMES = ("CHANGE", "HISTORY", "NEWS", "README", "AUTHORS", "CONTRIBUT", "LICENSE")

GitRunner = Callable[[Path, tuple[str, ...]], str]


def run_git(repo: Path, args: tuple[str, ...]) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo), *args),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise BacktestError("git_failed", result.stderr.decode("utf-8", errors="replace").strip() or "git failed")
    return result.stdout.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- paths


def is_test_path(path: str) -> bool:
    """A file that belongs to the test suite (code, conftest, or test data)."""

    pure = PurePosixPath(path)
    name = pure.name
    parts = {p.lower() for p in pure.parts[:-1]}
    if name == "conftest.py" or name.startswith("test_") or name.endswith("_test.py"):
        return True
    return bool(parts & {"tests", "test", "testing"})


def is_doc_path(path: str) -> bool:
    pure = PurePosixPath(path)
    if pure.suffix.lower() in {".md", ".rst"}:
        return True
    if pure.parts and pure.parts[0].lower() in {"docs", "doc"}:
        return True
    return pure.name.upper().startswith(_DOC_BASENAMES)


def is_test_python(path: str) -> bool:
    return path.endswith(".py") and is_test_path(path)


# ------------------------------------------------------------------ marker parsing


@dataclass(frozen=True, slots=True)
class ParsedTest:
    qualname: str
    markers: tuple[MarkerRecord, ...]
    body_digest: str
    start_line: int
    end_line: int


def _marker_kind(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    chain: list[str] = []
    while isinstance(target, ast.Attribute):
        chain.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        chain.append(target.id)
    chain.reverse()
    if len(chain) >= 2 and chain[-2] == "mark" and chain[-1] in SUPPORTED_MARKERS:
        return chain[-1]
    return None


def _reason(node: ast.expr, kind: str) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    for keyword in node.keywords:
        if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    if kind == "skip" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    if kind == "skipif" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
        return node.args[1].value
    return None


def parse_tests(source: str) -> dict[str, ParsedTest]:
    """Function-level supported markers per test. Class-level markers and
    ``pytestmark`` are intentionally not modelled (recorded as a limitation)."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # old test files carry invalid-escape SyntaxWarnings
        tree = ast.parse(source)
    found: dict[str, ParsedTest] = {}

    def visit(body: Iterable[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}::")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                markers = []
                for dec in node.decorator_list:
                    kind = _marker_kind(dec)
                    if kind:
                        markers.append(MarkerRecord(kind, ast.unparse(dec), _reason(dec, kind), dec.lineno))
                bare = type(node)(
                    name=node.name, args=node.args, body=node.body, decorator_list=[], returns=node.returns, type_comment=None
                )
                body_digest = digest(ast.dump(bare))
                qualname = f"{prefix}{node.name}"
                found[qualname] = ParsedTest(
                    qualname=qualname,
                    markers=tuple(markers),
                    body_digest=body_digest,
                    start_line=min([d.lineno for d in node.decorator_list] + [node.lineno]),
                    end_line=node.end_lineno or node.lineno,
                )

    visit(tree.body, "")
    return found


# --------------------------------------------------------------------------- mining


def _commit_date(repo: Path, sha: str, runner: GitRunner) -> str:
    return runner(repo, ("show", "-s", "--format=%cI", sha)).strip()


def _blob(repo: Path, sha: str, path: str, runner: GitRunner) -> str | None:
    try:
        return runner(repo, ("show", f"{sha}:{path}"))
    except BacktestError:
        return None


def _event_id(repository: str, event_class: str, path: str, qualname: str, as_of: str, outcome: str) -> str:
    return digest([repository, event_class, path, qualname, as_of, outcome])[:24]


def _classify_changed_files(changed: Iterable[str]) -> str:
    """``marker_only_removal`` only when every changed file is test or doc."""

    for path in changed:
        if not (is_test_path(path) or is_doc_path(path)):
            return "fix_with_removal"
    return "marker_only_removal"


def _name_status(repo: Path, parent: str, child: str, runner: GitRunner) -> list[tuple[str, str, str]]:
    """(status, old_path, new_path) for every change between two commits."""

    out = runner(repo, ("diff", "--name-status", "-M", "--no-color", parent, child))
    rows: list[tuple[str, str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        status = parts[0][0]
        if status == "R" and len(parts) >= 3:
            rows.append((status, parts[1], parts[2]))
        elif len(parts) >= 2:
            rows.append((status, parts[1], parts[1]))
    return rows


def mine_removal_events(
    repo: Path,
    repository: str,
    *,
    head: str = "HEAD",
    max_commits: int | None = None,
    runner: GitRunner = run_git,
) -> tuple[list[HistoricalEvent], list[Exclusion], int, int]:
    """Marker removals on first-parent single-parent commits that changed marker-ish lines."""

    log = runner(
        repo,
        ("log", "--format=%H %P", "-G", r"xfail|skip", head, "--", "*.py"),
    )
    commits = [line.split() for line in log.splitlines() if line.strip()]
    # git log does not diff merge commits, so none of them can appear above; count them
    # separately so the limitation is visible rather than silent.
    merge_skipped = int(runner(repo, ("rev-list", "--merges", "--count", head)).strip() or 0)
    events: list[HistoricalEvent] = []
    exclusions: list[Exclusion] = []
    scanned = 0
    for row in reversed(commits):
        if max_commits is not None and scanned >= max_commits:
            break
        child, parents = row[0], row[1:]
        if len(parents) != 1:  # root commit: nothing to compare against
            continue
        parent = parents[0]
        scanned += 1
        changes = _name_status(repo, parent, child, runner)
        touched = tuple(sorted({new for _, _, new in changes} | {old for _, old, _ in changes}))
        event_class = _classify_changed_files(touched)
        child_date = None
        parent_date = None
        for status, old, new in changes:
            if status == "D" or status == "A" or not is_test_python(old):
                continue
            old_src = _blob(repo, parent, old, runner)
            new_src = _blob(repo, child, new, runner)
            if old_src is None or new_src is None or not re.search(r"xfail|skip", old_src):
                continue
            try:
                before = parse_tests(old_src)
                after = parse_tests(new_src)
            except SyntaxError:
                exclusions.append(Exclusion("parse_error", repository, child, new, ""))
                continue
            for qualname, info in before.items():
                if not info.markers:
                    continue
                later = after.get(qualname)
                if later is None:
                    exclusions.append(Exclusion("test_missing_at_child", repository, child, new, qualname))
                    continue
                if later.markers:
                    if tuple(m.text for m in later.markers) != tuple(m.text for m in info.markers):
                        kinds_before = {m.kind for m in info.markers}
                        kinds_after = {m.kind for m in later.markers}
                        reason = "partial_marker_removal" if kinds_after < kinds_before else "marker_edited"
                        exclusions.append(Exclusion(reason, repository, child, new, qualname))
                    continue
                if later.body_digest != info.body_digest:
                    exclusions.append(Exclusion("test_modified", repository, child, new, qualname))
                    continue
                parent_date = parent_date or _commit_date(repo, parent, runner)
                child_date = child_date or _commit_date(repo, child, runner)
                events.append(
                    HistoricalEvent(
                        event_id=_event_id(repository, event_class, old, qualname, parent, child),
                        repository=repository,
                        event_class=event_class,  # type: ignore[arg-type]
                        test_path=old,
                        test_qualname=qualname,
                        markers=tuple(m.text for m in info.markers),
                        marker_kinds=tuple(m.kind for m in info.markers),
                        as_of_sha=parent,
                        as_of_date=parent_date,
                        outcome_sha=child,
                        outcome_date=child_date,
                        touched_files=touched,
                    )
                )
    return events, exclusions, scanned, merge_skipped


def _snapshot_commit(repo: Path, head: str, horizon_days: int, runner: GitRunner) -> str:
    head_date = datetime.fromisoformat(_commit_date(repo, head, runner))
    cutoff = (head_date - timedelta(days=horizon_days)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sha = runner(repo, ("rev-list", "-1", "--first-parent", f"--before={cutoff}", head)).strip()
    if not sha:
        raise BacktestError("history_too_short", "no commit exists before the retained-marker horizon")
    return sha


def _list_test_files(repo: Path, sha: str, runner: GitRunner) -> list[str]:
    return [p for p in runner(repo, ("ls-tree", "-r", "--name-only", sha)).splitlines() if is_test_python(p)]


def mine_retained_events(
    repo: Path,
    repository: str,
    *,
    head: str = "HEAD",
    horizon_days: int = 730,
    runner: GitRunner = run_git,
) -> tuple[list[HistoricalEvent], list[Exclusion], int]:
    """Markers present at the horizon snapshot and still identical at HEAD."""

    head_sha = runner(repo, ("rev-parse", head)).strip()
    snapshot = _snapshot_commit(repo, head, horizon_days, runner)
    snapshot_date = _commit_date(repo, snapshot, runner)
    head_date = _commit_date(repo, head_sha, runner)
    events: list[HistoricalEvent] = []
    exclusions: list[Exclusion] = []
    total = 0
    for path in _list_test_files(repo, snapshot, runner):
        old_src = _blob(repo, snapshot, path, runner)
        if old_src is None or not re.search(r"xfail|skip", old_src):
            continue
        try:
            before = parse_tests(old_src)
        except SyntaxError:
            exclusions.append(Exclusion("parse_error", repository, snapshot, path, ""))
            continue
        marked = {q: i for q, i in before.items() if i.markers}
        if not marked:
            continue
        new_src = _blob(repo, head_sha, path, runner)
        try:
            after = parse_tests(new_src) if new_src is not None else {}
        except SyntaxError:
            after = {}
        for qualname, info in sorted(marked.items()):
            total += 1
            later = after.get(qualname)
            if later is None:
                exclusions.append(Exclusion("test_missing_at_head", repository, head_sha, path, qualname))
                continue
            if tuple(m.text for m in later.markers) != tuple(m.text for m in info.markers):
                exclusions.append(Exclusion("marker_changed_by_head", repository, head_sha, path, qualname))
                continue
            events.append(
                HistoricalEvent(
                    event_id=_event_id(repository, "retained", path, qualname, snapshot, head_sha),
                    repository=repository,
                    event_class="retained",
                    test_path=path,
                    test_qualname=qualname,
                    markers=tuple(m.text for m in info.markers),
                    marker_kinds=tuple(m.kind for m in info.markers),
                    as_of_sha=snapshot,
                    as_of_date=snapshot_date,
                    outcome_sha=head_sha,
                    outcome_date=head_date,
                )
            )
    return events, exclusions, total


def sample_events(events: list[HistoricalEvent], limit: int | None) -> tuple[list[HistoricalEvent], list[HistoricalEvent]]:
    """Deterministic subsample in stable hash order (never random); returns (kept, dropped)."""

    if limit is None or len(events) <= limit:
        return sorted(events, key=lambda e: e.event_id), []
    ordered = sorted(events, key=lambda e: digest([e.repository, e.event_id]))
    return sorted(ordered[:limit], key=lambda e: e.event_id), sorted(ordered[limit:], key=lambda e: e.event_id)


def sample_retained(events: list[HistoricalEvent], limit: int) -> list[HistoricalEvent]:
    return sample_events(events, limit)[0]


def _as_exclusion(event: HistoricalEvent, reason: str) -> Exclusion:
    return Exclusion(reason, event.repository, event.outcome_sha, event.test_path, event.test_qualname)


def mine_repository(
    repo: Path,
    repository: str,
    *,
    head: str = "HEAD",
    horizon_days: int = 730,
    min_as_of_date: str | None = None,
    fix_limit: int | None = None,
    retained_limit: int = 20,
    runner: GitRunner = run_git,
    max_commits: int | None = None,
) -> MiningResult:
    """Mine and reconcile: every mined candidate is either an event or an exclusion."""

    head_sha = runner(repo, ("rev-parse", head)).strip()
    removals, removal_excl, scanned, merges = mine_removal_events(
        repo, repository, head=head_sha, max_commits=max_commits, runner=runner
    )
    retained, retained_excl, retained_total = mine_retained_events(
        repo, repository, head=head_sha, horizon_days=horizon_days, runner=runner
    )
    exclusions = [*removal_excl, *retained_excl]
    if min_as_of_date is not None:
        in_window = [e for e in removals if e.as_of_date[:10] >= min_as_of_date]
        exclusions += [_as_exclusion(e, "outside_eligibility_window") for e in removals if e.as_of_date[:10] < min_as_of_date]
        removals = in_window
    fixes = [e for e in removals if e.event_class == "fix_with_removal"]
    only = [e for e in removals if e.event_class == "marker_only_removal"]
    kept_fix, dropped_fix = sample_events(fixes, fix_limit)
    kept_retained, dropped_retained = sample_events(retained, retained_limit)
    exclusions += [_as_exclusion(e, "not_sampled") for e in [*dropped_fix, *dropped_retained]]
    events = tuple(sorted([*only, *kept_fix, *kept_retained], key=lambda e: (e.as_of_date, e.event_id)))
    return MiningResult(
        repository=repository,
        head_sha=head_sha,
        horizon_days=horizon_days,
        commits_scanned=scanned,
        merge_commits_skipped=merges,
        events=events,
        exclusions=tuple(sorted(exclusions, key=lambda x: (x.commit, x.test_path, x.test_qualname, x.reason))),
        retained_candidates_total=retained_total,
    )


# ----------------------------------------------------------------- evidence + leakage


def _is_ancestor(repo: Path, ancestor: str, descendant: str, runner: GitRunner) -> bool:
    try:
        runner(repo, ("merge-base", "--is-ancestor", ancestor, descendant))
    except BacktestError:
        return False
    return True


def assert_no_leakage(case: BacktestCase, repo: Path | None = None, *, runner: GitRunner = run_git) -> None:
    """Every evidence item must derive from the case's as-of commit (or an ancestor)."""

    for item in case.evidence:
        if not _SHA_RE.fullmatch(item.derived_from_sha):
            raise BacktestError("leakage_unbound", f"evidence {item.kind} lacks an exact commit")
        if item.derived_from_sha == case.as_of_sha:
            continue
        if repo is None or not _is_ancestor(repo, item.derived_from_sha, case.as_of_sha, runner):
            raise BacktestError("leakage_detected", f"evidence {item.kind} derives from a commit after the as-of commit")
    if digest([item.to_dict() for item in case.evidence]) != case.evidence_digest:
        raise BacktestError("evidence_digest_mismatch", "case evidence changed after construction")


def build_evidence(repo: Path, event: HistoricalEvent, *, runner: GitRunner = run_git) -> tuple[EvidenceItem, ...]:
    """Evidence available at the as-of commit only: marker text, test source, blame."""

    sha = event.as_of_sha
    source = _blob(repo, sha, event.test_path, runner)
    if source is None:
        raise BacktestError("evidence_unavailable", "test file missing at the as-of commit")
    info = parse_tests(source).get(event.test_qualname)
    if info is None or not info.markers:
        raise BacktestError("evidence_unavailable", "marker missing at the as-of commit")
    marker_line = min(m.line for m in info.markers)
    lines = source.splitlines()
    test_source = "\n".join(lines[info.start_line - 1 : info.end_line])[:1600]
    items = [
        EvidenceItem(
            "marker",
            sha,
            f"Test: {event.test_path}::{event.test_qualname}. Markers: " + "; ".join(m.text for m in info.markers) + ".",
        ),
        EvidenceItem("test_source", sha, "Full test source:\n" + test_source),
    ]
    try:
        blame = runner(repo, ("blame", "-L", f"{marker_line},{marker_line}", "--porcelain", sha, "--", event.test_path))
        header = blame.splitlines()[0].split()[0]
        meta = runner(repo, ("show", "-s", "--format=%cs %s", header)).strip()
        if _is_ancestor(repo, header, sha, runner):
            items.append(EvidenceItem("blame", header, f"Marker introduced by commit {header[:10]}: {meta}."))
    except BacktestError:
        pass
    items.append(
        EvidenceItem(
            "as_of",
            sha,
            f"Repository snapshot date: {event.as_of_date[:10]}. An xfail/skip marker disables a test; "
            "the reason states why. Judge whether the protected condition is still in force.",
        )
    )
    return tuple(items)


def build_case(repo: Path, event: HistoricalEvent, split: str, *, runner: GitRunner = run_git) -> BacktestCase:
    evidence = build_evidence(repo, event, runner=runner)
    case = BacktestCase(
        case_id=f"bt-{event.event_id}",
        event_id=event.event_id,
        repository=event.repository,
        event_class=event.event_class,
        split=split,  # type: ignore[arg-type]
        as_of_sha=event.as_of_sha,
        test_path=event.test_path,
        test_qualname=event.test_qualname,
        marker_kinds=event.marker_kinds,
        evidence=evidence,
        evidence_digest=digest([item.to_dict() for item in evidence]),
    )
    assert_no_leakage(case, repo, runner=runner)
    return case


# ----------------------------------------------------------------------- splits


def assign_splits(events: Iterable[HistoricalEvent], *, holdout_fraction: float = 0.4) -> dict[str, str]:
    """Per (repository, class): the latest ``holdout_fraction`` by time is holdout."""

    groups: dict[tuple[str, str], list[HistoricalEvent]] = {}
    for event in events:
        groups.setdefault((event.repository, event.event_class), []).append(event)
    assignment: dict[str, str] = {}
    for key in sorted(groups):
        ordered = sorted(groups[key], key=lambda e: (e.as_of_date, e.event_id))
        holdout_n = int(len(ordered) * holdout_fraction) if len(ordered) >= 3 else 0
        cut = len(ordered) - holdout_n
        for index, event in enumerate(ordered):
            assignment[event.event_id] = "development" if index < cut else "holdout"
    return assignment


def split_manifest(cases: Iterable[BacktestCase], *, declared_on: str) -> dict[str, Any]:
    ordered = sorted(cases, key=lambda c: c.case_id)
    body = {
        "schema_version": BACKTEST_SCHEMA_VERSION,
        "declared_on": declared_on,
        "splits": {c.case_id: c.split for c in ordered},
        "case_digests": {c.case_id: c.evidence_digest for c in ordered},
    }
    return {**body, "manifest_digest": digest(body)}


class HoldoutLedger:
    """Single-read holdout guard. A second read is a protocol violation, not a rerun."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read_once(self, manifest_digest: str, *, reader: str) -> None:
        if self.path.exists():
            prior = json.loads(self.path.read_text(encoding="utf-8"))
            raise BacktestError(
                "holdout_already_read",
                f"holdout for manifest {prior.get('manifest_digest', '?')[:12]} was already read by {prior.get('reader')}",
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"manifest_digest": manifest_digest, "reader": reader}, sort_keys=True) + "\n", encoding="utf-8"
        )


def require_manifest_before_run(manifest: dict[str, Any], cases: Iterable[BacktestCase]) -> None:
    body = {k: manifest[k] for k in ("schema_version", "declared_on", "splits", "case_digests")}
    if digest(body) != manifest.get("manifest_digest"):
        raise BacktestError("manifest_tampered", "split manifest digest does not match its contents")
    for case in cases:
        if manifest["splits"].get(case.case_id) != case.split or manifest["case_digests"].get(case.case_id) != case.evidence_digest:
            raise BacktestError("manifest_mismatch", f"case {case.case_id} differs from the declared manifest")


# ------------------------------------------------------------------------ report


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def _empirical(outcome: str | None) -> str:
    return {"confirmed": "likely_expired", "still_failing": "likely_active"}.get(outcome or "", "not_adjudicated")


def _stratum(rows: list[tuple[BacktestCase, CaseRun]]) -> dict[str, Any]:
    n = len(rows)
    adjudicated = [(c, r) for c, r in rows if _empirical(r.clone_outcome) != "not_adjudicated"]
    agent_rows = [(c, r) for c, r in rows if r.agent_status is not None]
    definite = [(c, r) for c, r in agent_rows if r.agent_status in ("likely_active", "likely_expired")]
    definite_adj = [(c, r) for c, r in definite if _empirical(r.clone_outcome) != "not_adjudicated"]
    expectation = MAINTAINER_EXPECTATION.get(rows[0][0].event_class) if rows else None
    expected = [(c, r) for c, r in agent_rows if expectation]
    out: dict[str, Any] = {
        "n": n,
        "clone_adjudicated": len(adjudicated),
        "clone_expired": sum(1 for _, r in adjudicated if _empirical(r.clone_outcome) == "likely_expired"),
        "clone_active": sum(1 for _, r in adjudicated if _empirical(r.clone_outcome) == "likely_active"),
        "clone_not_adjudicated": n - len(adjudicated),
        "heuristic_agrees_with_clone": sum(1 for _, r in adjudicated if r.heuristic_status == _empirical(r.clone_outcome)),
        "agent_runs": len(agent_rows),
        "agent_abstentions": sum(1 for _, r in agent_rows if r.agent_status not in ("likely_active", "likely_expired")),
        "agent_abstention_rate": _rate(
            sum(1 for _, r in agent_rows if r.agent_status not in ("likely_active", "likely_expired")), len(agent_rows)
        ),
        "agent_definite_calls": len(definite),
        "agent_definite_adjudicated": len(definite_adj),
        "agent_definite_correct_vs_clone": sum(1 for _, r in definite_adj if r.agent_status == _empirical(r.clone_outcome)),
        "agent_false_expire": sum(
            1 for _, r in definite_adj if r.agent_status == "likely_expired" and _empirical(r.clone_outcome) == "likely_active"
        ),
        "agent_missed_expire": sum(
            1 for _, r in definite_adj if r.agent_status == "likely_active" and _empirical(r.clone_outcome) == "likely_expired"
        ),
        "maintainer_expectation": expectation,
        "agent_matches_maintainer_expectation": (
            sum(1 for _, r in expected if r.agent_status == expectation) if expectation else None
        ),
        "lookback_lower_bounds_days": sorted(
            r.lookback_days_still_stale for _, r in rows if r.lookback_days_still_stale is not None
        ),
    }
    return out


def build_report(
    cases: Iterable[BacktestCase],
    runs: Iterable[CaseRun],
    *,
    run_id: str,
    mode: str,
    model: str | None,
    generated_on: str,
    manifest_digest: str,
    mining_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_id = {r.case_id: r for r in runs}
    paired = [(c, by_id[c.case_id]) for c in sorted(cases, key=lambda c: c.case_id) if c.case_id in by_id]
    strata: dict[str, Any] = {}
    for split in SPLITS:
        for event_class in EVENT_CLASSES:
            rows = [(c, r) for c, r in paired if c.split == split and c.event_class == event_class]
            if rows:
                strata[f"{split}/{event_class}"] = _stratum(rows)
    return {
        "schema_version": BACKTEST_SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "model": model,
        "generated_on": generated_on,
        "manifest_digest": manifest_digest,
        "ground_truth": {
            "class_labels": "git history (maintainer behavior)",
            "empirical": "disposable-clone outcome at the as-of commit",
        },
        "mining_counts": mining_counts or {},
        "strata": strata,
        "limitations": [
            "removal is weak evidence of expiry: fix_with_removal is split out because a fix often ships with the removal",
            "retained means not_removed, not active; retained markers may be stale but unremoved",
            "function-level markers only; class-level markers and pytestmark are not modelled",
            "selected repositories are not representative; easy-to-detect events are over-represented",
            "lead time is unknown unless a lookback clone check recorded a lower bound",
        ],
        "non_authority": True,
    }


__all__ = [
    "HoldoutLedger",
    "ParsedTest",
    "assert_no_leakage",
    "assign_splits",
    "build_case",
    "build_evidence",
    "build_report",
    "is_doc_path",
    "is_test_path",
    "mine_removal_events",
    "mine_repository",
    "mine_retained_events",
    "parse_tests",
    "require_manifest_before_run",
    "run_git",
    "sample_events",
    "sample_retained",
    "split_manifest",
]
