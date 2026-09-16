# G30 live loop — expanded 8-case run (v2)

**Date:** 2026-09-16
**Goal:** [G30](../goals/G30-live-agentic-escalation-evaluation.md)
**Model:** Claude Sonnet (`claude-sonnet-4-5`), one call per case; real disposable clones.
**Ground truth:** empirical — the disposable-clone outcome.
**Artifacts:** report [`tests/fixtures/benchmarks/g30-escalation-report-v2.json`](../../tests/fixtures/benchmarks/g30-escalation-report-v2.json);
recorded inputs [`g30-escalation-cases-v2.json`](../../tests/fixtures/benchmarks/g30-escalation-cases-v2.json).

A balanced set of 8 pytest-marker cases — 4 with author-set truth "expired" (test
passes without the marker), 4 "active" (still fails) — run through the full loop.

## ⚠️ Read this before the numbers

The case evidence **and** the ground truth were both authored here. The "expired"
cases' evidence contained realistic expiry signals (a dependency bumped past the
buggy version, a merged migration PR, a closed issue). So a high agent-win rate
mostly shows *the model can read expiry signals that were placed in the evidence* —
**not** that it independently discovers expiry. **These numbers are a behavioral
demonstration at N=8, not an unbiased accuracy measurement.** A real measurement
needs a natural/mined corpus where evidence and outcome are not set by the same
author. The genuinely informative cases here are the ones where evidence and truth
diverge (below).

## Result

| Case | Truth | Agent | Escalation | Clone | Empirical | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| requests-shim | expired | likely_expired | disagreement | confirmed | expired | agent right |
| py38-skip | expired | likely_expired | disagreement | confirmed | expired | agent right |
| deprecation-migrated | expired | likely_expired | disagreement | confirmed | expired | agent right |
| perf-234 | expired | likely_expired | disagreement | confirmed | expired | agent right |
| windows-lock | active | unknown | agent_uncertain | still_failing | active | resolved unknown |
| temp-migration | active | likely_expired | disagreement | still_failing | active | **agent wrong — clone caught** |
| numpy-api | active | likely_active | agreement | — | not adjudicated | agreement, no clone |
| legacy-format | active | likely_active | agreement | — | not adjudicated | agreement, no clone |

Metrics: 8 cases, escalations 6 (rate 0.75), all resolved; adjudicated
disagreements 5 — agent 4, heuristic 1; error catches 1; resolved unknowns 1.

## What this actually establishes (and what it doesn't)

**Does establish** — the mechanism behaves correctly across the full outcome space
at N=8:
- **Selective escalation, not over-escalation.** On 2 active cases the agent agreed
  with the conservative heuristic and the loop spent no clone run (numpy-api,
  legacy-format). It escalated only where it was uncertain or disagreed.
- **Abstention handled well.** With no context (windows-lock) the agent said
  `unknown`; escalation turned that into an empirical fact rather than a guess.
- **The safety net fires (temp-migration).** Evidence hinted "safe to remove after
  migration; repo on v3.4," the agent was fooled into `likely_expired`, escalated,
  and the clone returned `still_failing` — the error was caught by running the code.

**Does NOT establish** — that the agent is accurate. The 4 clean agent wins ride on
authored expiry hints (see caveat). Nothing here is a quality verdict.

## Recall gap, honestly

numpy-api and legacy-format were correctly `active` and correctly not escalated —
but if a truly *expired* case had drawn `likely_active` from both agent and
heuristic, the loop would not have escalated and would have missed it. That is the
recall gap the report declines to score (agreements are not validated by design).
A natural corpus would let us estimate it via an audit sample.
