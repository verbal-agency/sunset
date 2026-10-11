# G34 — Historical removal backtest

**Status:** proposed
**Dependencies:** G30 (escalation loop), G32 (natural corpus + recorded recipes),
G33 (pinned-clone executable backend), G06 (disposable-clone validation), G22 +
G28 (exact-SHA Git evidence), G25 (split discipline), live-model authorization
for the agent run only

## Purpose

Give Sunset its first measurement against **independent, real maintainer
behavior** without waiting on a recruited participant. Every result so far is
graded against either authored fixtures or Sunset's own clone runs (G30/G32), so
nothing yet shows whether Sunset would have told a maintainer something true
and early. Repository history already records what maintainers did with
markers; replaying Sunset at the commit before each action turns that history
into labels whose source is not Sunset.

## Objective

Mine pinned public Python repositories for historical marker events, run Sunset
as of the commit before each event, and report agreement with what maintainers
later did together with the **lead time** (how long a marker sat stale before a
maintainer removed it), with selection bias and label weakness characterized
rather than hidden.

## Project outcomes and scenarios advanced

- Advances OUT-05 (measured trustworthiness), OUT-08 (epistemic discipline),
  and OUT-04 (clone-validated, not asserted, outcomes).
- Advances SCN-01 (expired marker), SCN-02 (still-required marker), SCN-03
  (insufficient evidence), and SCN-12 (comparative agent evaluation).

## Scope boundary

- **Event mining (deterministic, git-only):** From each pinned repository's
  history, extract events where a supported pytest marker
  (`xfail`/`skip`/`skipif`) on an existing test was removed or kept. Each event
  records repository, ref pair, test identity, marker text, and commit metadata.
- **Event classes (the label design):**
  - `marker_only_removal`: the removal commit's diff touches only test/marker
    files and the test still exists. Strongest positive: the protected
    condition had plausibly already ceased before the maintainer noticed.
  - `fix_with_removal`: the same commit also changes non-test source. At the
    parent the condition was still active; the label is `active` at the parent,
    and the case measures whether Sunset avoids a false "expired".
  - `retained`: the marker is present at the parent and still present at a
    later fixed horizon (declared in the case set). The label is
    `not_removed`, **not** `active`; it is the weakest class and is reported
    separately.
  - Everything else (test deleted, test renamed ambiguously, marker edited
    rather than removed, mixed commits that cannot be classified) is excluded
    with a recorded reason, never forced into a class.
- **Replay as-of the parent commit:** Evidence, blame, and the G32/G33 recipe
  are computed from the pinned parent commit only. No information from the
  removal commit or later may reach the agent (leakage guard).
- **Clone check:** Each included case is also run through the G06/G33
  disposable-clone path at the parent so the maintainer-derived class can be
  compared with empirical behavior.
- **Metrics:** Class-stratified agreement for the heuristic baseline and the
  live agent, abstention rate, false-expire rate, and `marker_only_removal`
  lead time (days between the point the clone first passes and the maintainer
  removal, when recoverable; otherwise reported as unknown).
- **Splits:** Development and holdout sets fixed by repository-and-time before
  any agent run (G25 discipline). Holdout is evaluated once.

## Explicit exclusions

- No claim that a removed marker was correct to remove, or that a retained one
  is required; maintainer action is corroboration, not proof.
- No target-repository writes beyond disposable clones, no autonomous
  approval/cleanup, no auto-merge or pull requests, no arbitrary network use
  beyond the declared pinned clones and the authorized model calls.
- No new collectors, no JavaScript/TypeScript, no multi-language support, and
  no tuning of the agent on the holdout set.
- No training or fine-tuning; G31 feedback learning stays out of scope.
- No contact with maintainers.

## Execution contract

### Expected implementation surface

- `src/sunset/history_backtest_models.py`: versioned `HistoricalEvent`,
  `BacktestCase`, `BacktestRun`, and `BacktestReport` contracts.
- `src/sunset/history_backtest.py`: deterministic event mining, event
  classification, as-of replay construction, leakage guard, and report
  assembly. It reuses `natural_corpus.py`, `escalation_loop.py`,
  `pilot_service.py`, and `git_evidence.py` rather than reimplementing them.
- `src/sunset/cli.py`: `backtest mine`, `backtest run`, and `backtest report`
  subcommands that call the module; existing commands remain unchanged.
- `tests/test_history_backtest.py` and
  `tests/fixtures/backtest/g34-{events,cases,report}-v1.json`, plus small
  synthetic git repositories built in test setup for classification cases.
- `docs/research/G34-backtest-report-v1.md` and this specification.

Equivalent modules are allowed only when this specification records the
substitution and preserves the same contracts, fixtures, and authority
boundaries.

### Repository selection (recorded during the cycle)

Choose up to three public repositories before mining and record them here with
the substitution note. Required properties: pure Python, installable on the G33
supported runtime, at least five years of history, a test suite that runs within
a declared time budget, and at least thirty qualifying events across the set. If
fewer than twenty qualifying events exist, stop and report inconclusive
(see stop conditions).

### Canonical contracts and invariants

- Every event and case carries the exact parent SHA, child SHA, and class;
  mining is deterministic and byte-identical on rerun.
- Every case's evidence is bound to the parent SHA; a test proves no artifact
  referenced by a case was produced from a later commit.
- Excluded events appear in the output with a reason; the included/excluded
  counts reconcile to the mined total.
- Class labels derive only from git history and diff classification, never from
  agent or clone output.
- Report numbers are reproducible offline from the recorded cases and runs, and
  every aggregate states N, class, and split.

### Authority, network, and stop conditions

- Network is limited to the declared public clones. Model calls require the
  existing live-model authorization and a declared cost cap; without it the run
  is `recorded` replay or heuristic-only.
- Clone execution of third-party test code follows G06/G33 isolation and the
  safety posture in `docs/SAFETY.md`; G06 is not a security sandbox, so cases
  that cannot be vetted are excluded and recorded.
- Stop and report an honest inconclusive result if: fewer than twenty included
  events, clone/environment failure above a declared threshold, any leakage
  guard failure, or the cost cap is reached. Never backfill with authored cases.

### Replay and cache rules

Mined events, case sets, and runs are content-addressed and frozen after the
split declaration. The holdout split is read once; a second read is a recorded
protocol violation, not a silent rerun.

## Goal-level acceptance criteria

- **G34-AC01 — Deterministic mining:** `backtest mine` over the pinned repos
  produces a byte-identical event set on rerun, with included and excluded
  counts reconciling to the mined total.
- **G34-AC02 — Honest classification:** Synthetic-repository tests classify
  `marker_only_removal`, `fix_with_removal`, `retained`, and each exclusion
  reason correctly, and ambiguous events are excluded rather than forced.
- **G34-AC03 — No leakage:** Tests prove evidence, blame, and recipes for a
  case derive only from the parent SHA, and a deliberately leaky fixture is
  rejected.
- **G34-AC04 — Pre-declared splits:** Development/holdout assignment is fixed
  and recorded before any agent run; a second holdout read fails.
- **G34-AC05 — Stratified measurement:** The report gives per-class,
  per-split agreement, abstention rate, false-expire rate, and lead time for
  the baseline and the agent, each with N and unknowns stated.
- **G34-AC06 — Bias and weakness stated:** The report records selection bias,
  the weakness of the `retained` label, one-repository-family limits, and makes
  no accuracy claim beyond the measured sample.
- **G34-AC07 — Authority and cost:** Tests prove no target writes, no
  undeclared network use, and that a live run without authorization or past the
  cost cap fails closed.
- **G34-AC08 — Replayability:** The report reproduces offline from the recorded
  cases and runs; focused tests, the locked suite, and diff checks pass.

## Criterion-to-evidence map

| Criterion | Required evidence |
| --- | --- |
| G34-AC01 | `tests/test_history_backtest.py::test_mining_is_deterministic_and_reconciles` |
| G34-AC02 | `test_event_classification_and_exclusions` on synthetic git repositories |
| G34-AC03 | `test_case_evidence_is_parent_bound` and `test_leaky_case_is_rejected` |
| G34-AC04 | `test_splits_fixed_before_run_and_holdout_single_read` |
| G34-AC05 | `test_report_is_stratified_with_n_and_unknowns` and the recorded report |
| G34-AC06 | Report section review plus `test_report_states_bias_and_label_limits` |
| G34-AC07 | `test_backtest_authority_and_cost_guards` |
| G34-AC08 | `test_backtest_report_reproduces_offline`, locked suite, diff check |

## Required verification commands

```bash
.venv/bin/python -m pytest -q tests/test_history_backtest.py
uv run --locked pytest -q
git diff --check
```

## Capability unlocked

A measured, maintainer-independent answer to "would Sunset have said something
true, and how early?", which feeds the G27 continue/revise/stop decision and
shows whether a larger natural corpus (or a maintainer pilot) is worth the cost.

## Carried-forward risks

- Maintainer removal is weak evidence of expiry (a fix often ships in the same
  commit, hence the class split); retained markers may be stale but unremoved.
- Easy-to-detect events are over-represented; results will not generalize to
  all libraries.
- Third-party test execution cost and flakiness may shrink the included set.
