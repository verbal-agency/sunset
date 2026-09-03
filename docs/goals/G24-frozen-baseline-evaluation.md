# G24 — Frozen baseline evaluation

**Status:** complete
**Dependencies:** G23 (complete)

## Purpose

Measure Sunset's actual epistemic behavior on a frozen, explicitly labelled
corpus before changing policies or prompts to improve a score. The current G23
manifest is single-reviewer provisional; results must carry that limitation
until a later independent review pass exists.

## Objective

Execute heuristic-only and recorded-agentic baselines over the same frozen
development and holdout corpus, then publish per-case traces and aggregate
coverage, calibration, proof-obligation, unsupported-claim, safety, cost, and
latency results.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, and OUT-08.
- Advances SCN-03, SCN-06, SCN-08 through SCN-10, and SCN-12.
- Unlocks a pre-optimization baseline and measured error taxonomy for G25.

## Scope boundary

Use only recorded/offline evidence and the frozen G23 manifest. Evaluate the
same case/trace contract for both modes; report every exclusion, incomplete
run, disagreement, unsupported claim, and safety signal by case and aggregate.
Evaluation identity includes corpus, split, evaluator, prompt/model, tool, and
budget versions.

## Luna-ready execution contract

### Implementation surface

- `src/sunset/benchmark.py` and `src/sunset/calibration.py`: reuse existing
  deterministic metric and release-gate primitives where their contracts fit.
- `src/sunset/baseline_evaluation.py`: add the offline heuristic/recorded-agentic
  runner and versioned trace normalization.
- `src/sunset/baseline_evaluation_models.py`: add the trace, case result, and
  report contracts below.
- `src/sunset/cli.py`: add `sunset baseline-evaluation run` with manifest and
  recorded-trace inputs only.
- `tests/fixtures/adjudication/g23-frozen-manifest-v1.json`: immutable input.
- `tests/fixtures/benchmarks/g24-reference-cases-v1.json`: six pinned public
  repository references used to exercise lifecycle, support-window,
  operational-state, and quarantine criteria. These references are
  `reference_only`, not adjudicated labels or evaluation denominators.
- `tests/fixtures/benchmarks/g24-recorded-traces-v1.json`: paired recorded
  heuristic and agentic traces, including conservative failures.
- `tests/test_baseline_evaluation.py`: focused contract, metric, and offline
  safety tests.
- `docs/research/G24-baseline-v1.md` and
  `tests/fixtures/benchmarks/g24-baseline-report-v1.json`: committed outputs.

Equivalent module names are allowed only if they preserve these contracts and
are recorded in the completion report.

### Canonical contracts and invariants

The frozen G23 manifest is read-only. Each evaluated case produces exactly one
`heuristic` and one `agentic_recorded` result with:

`case_id`, `split`, `condition_status`, `observed_status`,
`proof_obligations`, `evidence_ids`, `citation_accuracy`, `unsupported_claims`,
`tool_calls`, `input_tokens`, `latency_ms`, `trace_id`, `run_status`, and an
optional `error_kind`.

`run_status` is one of `completed`, `inconclusive`, `budget_exhausted`,
`malformed_trace`, or `excluded`. A result with `run_status != completed` cannot
be counted as a correct classification. Every evidence ID must exist in the
G23 manifest or its recorded evidence fixtures; unknown IDs are rejected.
Historical outcomes are never treated as condition labels. G23's
`single_reviewer` limitation is copied into every report and cannot be omitted.

Reference cases use `reference_id`, repository, exact `commit_sha`, path,
source URL, `reference_class`, and a list of criteria exercised. A reference
may supply a criterion example or counterexample, but cannot supply a G23
condition label or change an evaluation denominator.

### Deterministic behavior matrix

| Input condition | Required result |
| --- | --- |
| Valid paired traces for an included development/holdout case | One normalized result per mode; metrics include the case in its declared split. |
| Excluded G23 case | `excluded` result with the manifest exclusion reason; no accuracy denominator contribution. |
| Unknown or cross-case evidence ID | Reject the trace with `evidence_not_found` or `evidence_case_mismatch`; preserve the error in the report. |
| Malformed trace or missing required field | `malformed_trace`; do not infer status or proof obligations. |
| Tool failure, budget exhaustion, or interruption | `inconclusive`/`budget_exhausted`; preserve successful prior trace entries and do not retry completed calls. |
| Contradictory or unknown adjudication status | Include in coverage and calibration/error taxonomy, never coerce to expired or active. |
| Reference-only case | Validate its pinned source identity and criterion mapping; retain it outside scored condition accuracy. |
| Holdout result requested before report finalization | Compute it once from the frozen manifest and record the sealed report identity; no tuning inputs are accepted. |

### Authority and side-effect boundaries

The runner is offline and read-only. It may read the frozen manifest, recorded
traces, and local report paths. It may not call models, GitHub, registries,
shell commands, subprocesses, target repositories, credentials, mutation, or
cleanup. The evaluator computes metrics; it does not alter labels, splits,
evidence, prompts, heuristics, or traces. A recorded agentic trace is evidence
of a prior run, not authority to execute its tool calls again.

### Fixtures, budgets, and replay

The trace fixture must include at least one completed, unknown, contradictory,
malformed, excluded, partial-failure, budget-exhausted, and unsupported case
outcome. Replaying the same fixture twice must produce byte-identical report
JSON and no network or subprocess activity. The report records corpus digest,
manifest digest, split identities, evaluator schema version, trace fixture
digest, and metric denominators. No checkpoint may contain raw evidence bytes.

### Acceptance-to-evidence map

1. Paired normalized outputs and per-case traces: `test_g24_pairs_and_trace_schema`
   plus `g24-baseline-report-v1.json`.
2. Reference corpus pinning, criterion mapping, and non-authority handling:
   `test_g24_reference_cases_are_pinned_and_unscored`.
3. Frozen-manifest binding and single-reviewer limitation:
   `test_g24_manifest_binding_and_limitation`.
4. Conservative status, contradiction, exclusion, malformed, and budget
   handling: `test_g24_conservative_outcomes`.
5. Offline replay, deterministic report digest, and no subprocess/network:
   `test_g24_replay_is_offline_and_byte_stable`.
6. Full locked suite, `uv lock --check`, documentation checks, and
   `git diff --check`.

## Explicit exclusions

- Prompt, retrieval, policy, collector, or threshold optimization.
- Changes to labels, splits, source packets, or exclusions after outputs are
  known.
- Live provider access, target-repository mutation, cleanup, or release claims.

## Outcomes and handoff

G24 receives a versioned baseline report, fixed development/holdout identities,
error taxonomy, cost/latency budgets, and safety regressions. It may optimize
only against development cases and must treat the holdout report as sealed.

## Carried-forward limitations

The five-case, single-reviewer corpus is exploratory and not independent ground
truth. G24 must report per-family coverage and denominators, retain the fifteen
explicit exclusions, and avoid any production-removability claim. Optimization
and prompt/heuristic changes belong only to G25.

## Completion evidence

- `tests/test_baseline_evaluation.py` passes all six focused acceptance tests.
- `tests/fixtures/benchmarks/g24-baseline-report-v1.json` is generated by the
  offline CLI and binds the frozen corpus, manifest, and evaluation digests.
- The report contains 40 paired mode results, 15 explicit exclusions per mode,
  and six pinned `reference_only` cases outside scored denominators.
- Full pytest, locked dependency, JSON, compilation, and diff checks are the
  required final verification before handoff.
