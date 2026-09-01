# G23 — Frozen baseline evaluation

**Status:** proposed
**Dependencies:** G22 (complete)

## Purpose

Measure Sunset's actual epistemic behavior on frozen, independently adjudicated
cases before changing policies or prompts to improve a score.

> Planning boundary: this is intentionally an outline, not an executable goal.
> Cycle must replace it with a Luna-ready execution contract only after G22
> freezes the corpus and label identities.

## Objective

Execute heuristic-only and recorded-agentic baselines over the same frozen
development and holdout corpus, then publish per-case traces and aggregate
coverage, calibration, proof-obligation, unsupported-claim, safety, cost, and
latency results.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, and OUT-08.
- Advances SCN-03, SCN-06, SCN-08 through SCN-10, and SCN-12.
- Unlocks a pre-optimization baseline and measured error taxonomy for G24.

## Scope boundary

Use only recorded/offline evidence and the frozen G22 manifest. Evaluate the
same case/trace contract for both modes; report every exclusion, incomplete
run, disagreement, unsupported claim, and safety signal by case and aggregate.
Evaluation identity includes corpus, split, evaluator, prompt/model, tool, and
budget versions.

## Explicit exclusions

- Prompt, retrieval, policy, collector, or threshold optimization.
- Changes to labels, splits, source packets, or exclusions after outputs are
  known.
- Live provider access, target-repository mutation, cleanup, or release claims.

## Outcomes and handoff

G24 receives a versioned baseline report, fixed development/holdout identities,
error taxonomy, cost/latency budgets, and safety regressions. It may optimize
only against development cases and must treat the holdout report as sealed.

## Refinement trigger

After G22 completes, replace this outline with a Luna-ready execution contract
that names the actual corpus and trace schemas, test fixtures, denominator and
confidence rules, budget/stop rules, and binary acceptance criteria.
