"""File-level orchestration for the G34 backtest CLI (mine -> cases -> run -> report)."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from sunset.history_backtest import (
    HoldoutLedger,
    assign_splits,
    build_case,
    build_report,
    mine_repository,
    require_manifest_before_run,
    split_manifest,
)
from sunset.history_backtest_models import (
    BACKTEST_SCHEMA_VERSION,
    BacktestCase,
    BacktestError,
    CaseRun,
    HistoricalEvent,
)
from sunset.history_backtest_runner import (
    CloneChecker,
    CostGuard,
    LiveAuthorization,
    RepoRecipe,
    RunnerPolicy,
    build_runs,
    guarded_reasoner,
    run_clone_checks,
)


def write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_repo_map(items: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for item in items:
        name, sep, location = item.partition("=")
        if not sep or not name or not location:
            raise BacktestError("repo_spec_invalid", "use --repo name=path")
        mapping[name] = Path(location).expanduser()
    return mapping


def mine_command(repos: Mapping[str, Path], out: str, *, min_as_of_date: str | None, fix_limit: int | None,
                 retained_limit: int, horizon_days: int) -> dict[str, Any]:
    results = [
        mine_repository(path, name, horizon_days=horizon_days, min_as_of_date=min_as_of_date,
                        fix_limit=fix_limit, retained_limit=retained_limit)
        for name, path in sorted(repos.items())
    ]
    document = {
        "schema_version": BACKTEST_SCHEMA_VERSION,
        "config": {"min_as_of_date": min_as_of_date, "fix_limit": fix_limit,
                   "retained_limit": retained_limit, "horizon_days": horizon_days},
        "repositories": [r.to_dict() for r in results],
    }
    write_json(out, document)
    return document


def cases_command(events_path: str, repos: Mapping[str, Path], cases_out: str, manifest_out: str, *,
                  declared_on: str, holdout_fraction: float = 0.4) -> dict[str, Any]:
    document = read_json(events_path)
    events = [HistoricalEvent.from_dict(e) for repo in document["repositories"] for e in repo["events"]]
    assignment = assign_splits(events, holdout_fraction=holdout_fraction)
    cases, skipped = [], []
    for event in sorted(events, key=lambda e: e.event_id):
        try:
            cases.append(build_case(repos[event.repository], event, assignment[event.event_id]))
        except BacktestError as exc:
            skipped.append({"event_id": event.event_id, "reason": exc.code})
    manifest = split_manifest(cases, declared_on=declared_on)
    dates = {e.event_id: e.as_of_date for e in events}
    write_json(cases_out, {
        "schema_version": BACKTEST_SCHEMA_VERSION,
        "cases": [c.to_dict() for c in cases],
        "as_of_dates": {c.case_id: dates[c.event_id] for c in cases},
        "case_build_skipped": skipped,
        "mining_counts": {r["repository"]: r["counts"] for r in document["repositories"]},
    })
    write_json(manifest_out, manifest)
    return manifest


def load_cases(path: str) -> tuple[list[BacktestCase], dict[str, str], dict[str, Any]]:
    document = read_json(path)
    return [BacktestCase.from_dict(c) for c in document["cases"]], document["as_of_dates"], document


def run_command(
    cases_path: str,
    manifest_path: str,
    out: str,
    *,
    policy: RunnerPolicy,
    ledger_path: str,
    splits: tuple[str, ...],
    heuristic: Callable[[str], str],
    agent_factory: Callable[[Mapping[str, BacktestCase], CostGuard], Callable[[str], str]] | None,
    authorization: LiveAuthorization | None,
    recorded_agent: Mapping[str, str] | None = None,
    skip_clone: bool = False,
) -> list[CaseRun]:
    cases, dates, _ = load_cases(cases_path)
    manifest = read_json(manifest_path)
    require_manifest_before_run(manifest, cases)  # splits must be declared before any run
    selected = [c for c in cases if c.split in splits]
    if "holdout" in splits:
        HoldoutLedger(Path(ledger_path)).read_once(manifest["manifest_digest"], reader="backtest run")
    agent = None
    if agent_factory is not None:
        guard = CostGuard(authorization)  # fails closed without explicit authorization
        agent = agent_factory({c.case_id: c for c in selected}, guard)
    elif recorded_agent is not None:
        agent = lambda cid: recorded_agent.get(cid, "unknown")  # noqa: E731
    checks = {} if skip_clone else run_clone_checks(selected, dates, CloneChecker(policy))
    runs = build_runs(selected, checks, heuristic=heuristic, agent=agent)
    write_json(out, {"schema_version": BACKTEST_SCHEMA_VERSION, "splits": list(splits),
                     "manifest_digest": manifest["manifest_digest"], "runs": [r.to_dict() for r in runs]})
    return runs


def report_command(cases_path: str, runs_paths: list[str], manifest_path: str, out: str, *, run_id: str,
                   mode: str, model: str | None, generated_on: str | None = None) -> dict[str, Any]:
    cases, _, document = load_cases(cases_path)
    manifest = read_json(manifest_path)
    runs: list[CaseRun] = []
    for path in runs_paths:
        runs += [CaseRun.from_dict(r) for r in read_json(path)["runs"]]
    report = build_report(cases, runs, run_id=run_id, mode=mode, model=model,
                          generated_on=generated_on or date.today().isoformat(),
                          manifest_digest=manifest["manifest_digest"], mining_counts=document.get("mining_counts"))
    write_json(out, report)
    return report


def recipes_from_json(path: str) -> dict[str, RepoRecipe]:
    return {name: RepoRecipe(tuple(v["install_args"]), tuple(v.get("test_args", ()))) for name, v in read_json(path).items()}
