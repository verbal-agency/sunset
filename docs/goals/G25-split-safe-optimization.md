# G25 — Split-safe optimization and ablation

**Status:** proposed
**Dependencies:** G24 (complete)

## Purpose

Improve measurable decision quality without tuning against the same evidence
used to make the product-quality claim.

> Planning boundary: this is intentionally an outline, not an executable goal.
> Cycle must replace it with a Luna-ready execution contract only after G24
> supplies measured errors, budgets, and a sealed holdout identity.

## Objective

Test predeclared, bounded changes to prompts, retrieval policy, tool policy, or
deterministic thresholds on the development split; retain a change only when it
meets declared safety and quality criteria, then measure it once on the untouched
holdout split.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, and OUT-08.
- Advances SCN-06, SCN-08 through SCN-10, and SCN-12.
- Unlocks a reproducible candidate configuration and known regressions for G26.

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

## Refinement trigger

After G24 completes, replace this outline with a Luna-ready execution contract
derived from its actual error taxonomy, baseline budgets, metrics, and sealed
holdout identity.
