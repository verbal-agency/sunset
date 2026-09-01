# G20 — Calibration and temporal-condition release

**Status:** proposed
**Dependencies:** G19 (proposed)

## Purpose

Demonstrate whether Sunset's epistemic model improves conservative temporal-debt
decisions before making release or product claims.

## Objective

Evaluate protected-condition identification, contradiction handling,
proof-obligation quality, calibration, false-removal risk, cost, and latency on
versioned historical positive and negative cases, then emit a reproducible
release-gate decision.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-06, and SCN-08 through SCN-12.
- Unlocks post-release backlog decisions and any future language or provider
  expansion without claiming benchmark performance proves removability.

## Architecture constraints to preserve

- Benchmark labels describe historical outcomes and evidence obligations, not
  universal truth about production safety.
- Heuristic-only, recorded agentic, and configured live modes are compared
  under the same versioned case and trace contracts.
- Thresholds are declared before the final comparative run; missing labels,
  unsupported cases, and inconclusive results are reported, not silently
  excluded.
- Evaluation artifacts contain identifiers and metrics, not credentials or raw
  repository/customer payloads.

## Execution contract

Expected implementation surface: `src/sunset/calibration_models.py`,
`src/sunset/calibration.py`, `tests/test_calibration_release.py`, fixtures under
`tests/fixtures/calibration/`, and release documentation in `docs/RELEASE.md`
and `docs/ROADMAP.md`. Equivalent modules are allowed only when the same
contracts and test surface remain.

Define versioned contracts for `BenchmarkCase`, `ExpectedConditionLabel`,
`EvaluationRun`, `MetricRecord`, `ReleaseThreshold`, and `ReleaseGateResult`.
Each case must identify candidate family, protected-condition label(s),
contradictions, proof obligations, evidence scope, and historical outcome.
Each metric must identify the evaluated mode, denominator, exclusions, and
uncertainty; each release result must retain thresholds, inputs, pass/fail
reasons, and a non-authority disclaimer.

### Deterministic behavior matrix

| Input condition | Required result |
| --- | --- |
| Complete versioned case and declared threshold | Reproducible metric and pass/fail result. |
| Missing or conflicting label | Exclude only with a recorded reason; mark the gate inconclusive if required coverage is unmet. |
| Unsupported or unvalidatable case | Count as a conservative outcome; never coerce to removable/active. |
| Threshold not declared before evaluation | Reject the release run. |
| Replay with unchanged cases, code, model, prompt, and evaluator versions | Byte-stable metrics and traces. |
| Changed corpus, evaluator, or threshold identity | Invalidate incompatible cached results and rerun. |

### Authority and stop conditions

Stop after all cases are evaluated, a required label/threshold is invalid, a
budget is exhausted, or a replay identity is incompatible. Evaluation opens no
new provider or mutation path, authorizes no cleanup, and may only publish a
release-gate artifact with explicit limitations.

### Replay, cache, and budget rules

Evaluation identity includes corpus digest, case labels, evaluator/mode,
threshold version, code/model/prompt versions, and budget ledger. Equivalent
cases and configurations reuse immutable metric artifacts; changed identity
invalidates cached results. Duplicate case IDs are rejected, and token,
request, and wall-time budgets produce a structured incomplete gate result.

## In scope

1. Versioned historical benchmark cases with positive, negative, contradictory,
   insufficient, unvalidatable, malformed, partial-failure, budget-exhausted,
   and unsupported outcomes.
2. Baseline comparisons for heuristic-only and agentic modes.
3. Metrics for condition identification, calibration, proof obligations,
   unsupported claims, citations, tool use, tokens, latency, cost, and false
   removal risk.
4. Predeclared thresholds, deterministic replay, and release-gate artifacts.
5. Documentation of measured limitations.

## Explicit exclusions

- New collectors/providers, production telemetry, automatic cleanup, pull
  requests, benchmark label invention, or claims that evaluation proves a
  deletion safe.

## Deliverables

1. Versioned benchmark, metric, threshold, and release-gate contracts.
2. Reproducible corpus, evaluator, fixtures, and focused tests.
3. Public release evidence and limitations documentation.

## Goal-level acceptance criteria

- **G20-AC01 — Case integrity:** Benchmark cases and labels serialize
  deterministically and preserve scope, contradictions, and proof obligations.
- **G20-AC02 — Comparable evaluation:** Heuristic-only and agentic runs use
  the same case/trace contracts and report denominators and exclusions.
- **G20-AC03 — Calibration and risk metrics:** The evaluator reports declared
  condition, contradiction, proof-obligation, citation, unsupported-claim,
  cost/latency, and false-removal-risk metrics.
- **G20-AC04 — Threshold gate:** Thresholds are immutable inputs declared before
  evaluation; missing coverage or invalid labels fail/inconclusive the gate.
- **G20-AC05 — Replay and privacy:** Compatible replay is stable; incompatible
  identities invalidate caches; artifacts contain no credentials or raw payloads.
- **G20-AC06 — Verification:** Focused tests, locked full suite, and
  documentation/diff checks pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G20-AC01 | Case/label serialization and scope-integrity tests |
| G20-AC02 | Cross-mode evaluator parity fixtures |
| G20-AC03 | Metric snapshots and denominator audits |
| G20-AC04 | Predeclared-threshold and invalid-label tests |
| G20-AC05 | Replay/invalidation and raw-content/privacy guards |
| G20-AC06 | Focused suite, locked full suite, docs review, and diff check |

Focused tests should be named `test_g20_ac01_case_integrity` through
`test_g20_ac06_verification` (or recorded equivalent names).

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_calibration_release.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- Benchmark performance must not be presented as proof that a production
  condition is absent; release language must preserve this limitation.
- G19 case-file quality and G18 operational evidence coverage determine which
  calibration metrics are meaningful; missing coverage is itself reported.
