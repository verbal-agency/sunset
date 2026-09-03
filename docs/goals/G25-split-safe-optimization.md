# G25 — Split-safe optimization and ablation

**Status:** complete
**Dependencies:** G24 (complete)

## Purpose

Improve measurable decision quality without tuning against the same evidence
used to make the product-quality claim.

G24 has supplied measured errors, budgets, and a sealed holdout identity. This
proposal is now Luna-ready but remains proposed until the user authorizes it.

## Objective

Test predeclared, bounded changes to prompts, retrieval policy, tool policy, or
deterministic thresholds on the development split; retain a change only when it
meets declared safety and quality criteria, then measure it once on the untouched
holdout split.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, and OUT-08.
- Advances SCN-06, SCN-08 through SCN-10, and SCN-12.
- Unlocks a reproducible candidate configuration and known regressions for G26.

## Luna-ready execution contract

### Implementation surface

- `src/sunset/optimization.py` and `src/sunset/optimization_models.py`: add
  preregistration, experiment, selection, and holdout-report contracts.
- `src/sunset/cli.py`: add `sunset optimization run` with offline fixture inputs.
- `tests/fixtures/benchmarks/g25-experiments-v1.json`: recorded development
  ablations, including rejected safety regressions and budget failures.
- `tests/fixtures/benchmarks/g25-holdout-report-v1.json`: one sealed output
  generated only after development selection.
- `tests/test_optimization.py` and `docs/research/G25-optimization-v1.md`.

### Canonical contracts and invariants

Every preregistration has `experiment_id`, `corpus_digest`, `holdout_digest`,
`component`, `change_id`, `budget`, `development_case_ids`, `metrics`, and
`status`. Components are `prompt`, `retrieval`, `tool_policy`, or
`threshold`; changes are immutable once a run starts. Statuses are
`preregistered`, `evaluated_development`, `selected`, `rejected`,
`holdout_sealed`, or `inconclusive`. Selection can reference development
results only. Holdout results are append-only and cannot change selection.

G24's baseline is the control: heuristic completed-case accuracy 1.0000 on a
denominator of 4; recorded-agentic accuracy 0.6667 on a denominator of 3;
agentic median latency 30 ms, 620 input tokens, and unsupported-claim rate
0.3333. These are descriptive baselines, not universal quality thresholds.

### Deterministic behavior matrix

| Input | Required output |
| --- | --- |
| Unregistered change | reject before execution |
| Development run | metrics and safety signals recorded; may inform selection |
| Holdout run before selection | reject; no holdout observation is written |
| Selected change with safety regression or budget overrun | `rejected`; control remains eligible |
| Selected change on holdout | one `holdout_sealed` report; no retry or retuning |
| Contradictory/unknown outcomes | retained as errors; never coerced into improvement |
| Duplicate experiment or trace | deterministic rejection |

### Authority and side-effect boundaries

Runs are offline and read-only over the frozen G24 report and recorded
development fixtures. No model, network, GitHub, registry, shell, subprocess,
credential, target-repository mutation, cleanup, relabeling, or split changes.
The runner does not invent evidence or authorize a cleanup. Holdout data is
sealed after one deterministic report.

### Fixtures, replay, and budgets

Fixtures must include an improvement candidate, no-improvement candidate,
unsupported-claim regression, contradiction regression, malformed trace, and
budget exhaustion. Replaying produces byte-identical JSON and no subprocess or
network activity. The default development budget is 20 experiments and the
default per-experiment trace budget is 1,000 input tokens; overrides must be
declared in preregistration.

### Acceptance-to-evidence map

1. Contract validation and legal status transitions:
   `test_preregistration_and_status_rules`.
2. Development-only selection and safety rejection:
   `test_development_selection_is_split_safe`.
3. Single sealed holdout output and no tuning from it:
   `test_holdout_is_sealed_and_append_only`.
4. Malformed, contradictory, unsupported, duplicate, and budget outcomes:
   `test_optimization_error_taxonomy`.
5. Offline byte-stable replay: `test_optimization_replay_is_offline`.
6. Full locked suite, documentation checks, and `git diff --check`.

## Scope boundary

Implement a versioned experiment ledger, pre-registration record, ablation
runner, development-only selection rule, and final holdout report. Every
experiment records corpus/split identity, changed component, budget, metrics,
safety signals, and rejection reason.

## Explicit exclusions

- Reading holdout results to choose an optimization, retuning after a holdout
  run, corpus relabeling, or changing exclusion rules to improve a metric.
- New authority, live providers, automatic cleanup, or claims of universal
  removability.

## Outcomes and handoff

G25 receives one digest-identified candidate configuration, its development
selection evidence, the single holdout measurement, known failure classes, and
safe operating budgets. A no-improvement or safety-regression result is a valid
handoff and must not be concealed.

## Completion evidence

- `tests/test_optimization.py` passes all six focused acceptance tests.
- `tests/fixtures/benchmarks/g25-experiments-v1.json` records four
  preregistered candidates and exercises improvement, safety regression,
  malformed, and budget-exhausted outcomes.
- The offline CLI selects `g25-prompt-001`, rejects the other three candidates,
  and seals one holdout report under digest
  `ae8f4e372095e3dfb3cd73417945c4b3d3f21e486860fc52a55aec669f97c1bc`.
- Full pytest, JSON, compilation, and `git diff --check` verification pass;
  `uv lock --check` remains clean.
