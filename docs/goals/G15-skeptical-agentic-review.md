# G15 — Skeptical agentic review and citation-verified case files

**Status:** proposed
**Dependencies:** G14 (complete)

## Purpose

Challenge an investigator’s strongest explanation before a maintainer sees a
recommendation, so a bounded agentic trace cannot silently convert incomplete,
contradictory, or empirical-only evidence into unsafe cleanup advice.

## Objective

Add an independently budgeted skeptical-review stage that inspects the compact
investigator ledger, identifies missing/disconfirming evidence, can request only
allowlisted read-only evidence, and passes a reconciled, citation-verified
result to the existing deterministic case-file finalizer.

## Project alignment

- Advances OUT-02, OUT-05, OUT-06, and OUT-07.
- Advances SCN-01 through SCN-03 and SCN-07 through SCN-09.
- Produces the reviewable case-file input that G16 will evaluate; it does not
  publish results or apply changes.

## Architecture constraints to preserve

- The reviewer is independent inference, never an approval authority. It may
  identify objections and request bounded evidence but cannot approve G14,
  validate, edit, or create a pull request.
- G10–G14 receipts/artifacts remain facts; reviewer/investigator conclusions
  are hypotheses. The deterministic case-file finalizer must reload every
  material citation from the artifact store before rendering.
- Keep reviewer state/prompt compact and persist only structured findings,
  receipt IDs, budgets, disagreement, and trace metadata—never raw prompts,
  chain of thought, raw evidence/logs, credentials, or framework messages.

## In scope

1. Versioned skeptical finding, reviewer request, reconciliation, and
   investigator/reviewer disagreement contracts.
2. Separate recorded/live/disabled reviewer runtime configuration and bounded
   read-only tool policy composed with G12/G13 budgets.
3. Deterministic citation reload and rejection of unsupported/unknown material
   claims before the existing JSON, Markdown, and HTML case-file finalizer.
4. Agentic case-file fields for evidence map, external uncertainty, validation
   result, objections, reconciliation, residual risk, and human-only decision.
5. Fixtures for unsupported claims, contradictory evidence, omitted risks,
   reviewer failure/budget exhaustion, checkpoint resume, and raw-data safety.

## Explicit exclusions

- Hidden reasoning capture, majority-vote truth, reviewer approval/validation
  access, new evidence providers, external writes, automatic edits, pull
  requests, publication, or release-threshold evaluation.

## Deliverables

1. Reviewer/reconciliation/citation contracts and bounded graph stage.
2. Allowlisted skeptical evidence-request adapter and independent budget state.
3. Citation-verified agentic case-file bridge to the G07 finalizer.
4. Adversarial fixtures and documentation.

## Goal-level acceptance criteria

- **G15-AC01 — Independent bounded review:** Reviewer state and budgets are
  separate; it can only inspect supplied compact receipts and request declared
  read-only evidence with an explicit antecedent finding.
- **G15-AC02 — Disagreement remains visible:** Contradictory, missing, and
  omitted-risk fixtures produce structured objections/unknowns rather than a
  forced consensus or recommendation.
- **G15-AC03 — Citation-verified finalization:** Every material agentic
  case-file claim reloads a referenced raw artifact; unsupported, stale, or
  uncited claims are rejected before render.
- **G15-AC04 — Validation is not proof:** Confirmed G14 validation remains one
  cited empirical input; it never alone authorizes a removal recommendation.
- **G15-AC05 — Replay and data safety:** Reviewer checkpoints resume compatible
  work without repeating calls, invalidate on receipts/runtime/budget change,
  and exclude raw prompts, bodies, logs, credentials, and messages.
- **G15-AC06 — Compatibility and documentation:** Existing Phase 1–G14 APIs and
  rendered case files remain compatible; documentation states reviewer limits,
  citation rules, disagreement handling, and human decision boundary.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G15-AC01 | Registry/effect/budget/antecedent adversarial tests |
| G15-AC02 | Contradictory and omitted-risk fixture snapshots |
| G15-AC03 | Citation reload, missing-artifact, and unsupported-claim rejection tests |
| G15-AC04 | Confirmed-validation-only fixture with conservative output assertion |
| G15-AC05 | Interrupt/resume counters, invalidation matrix, and raw-content checkpoint scans |
| G15-AC06 | Locked full suite, focused reviewer/case-file tests, docs review, and diff check |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_agent_review.py tests/test_casefile.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G14’s approval confirms only a bounded experiment, not deletion safety. G15
  must preserve the exact validation plan/result as empirical evidence while
  asking what it did not test.
- G13 external observations can be expired, active, missing, or contradictory.
  Reviewer prompts must retain those normalized outcomes and may not summarize
  them as a single expiry fact.
- G12/G13/G14 each use immutable external store views. G15 must reuse those
  receipts without coupling its review state to framework checkpoint internals.
