# G30 — first natural report (langchain-core, 9 real markers)

**Date:** 2026-09-17
**Goal:** [G30](../goals/G30-live-agentic-escalation-evaluation.md) / [G32](../goals/G32-natural-clone-runnable-corpus.md) pilot
**Model:** Claude Sonnet (`claude-sonnet-4-5`), one call per case; real disposable clones.
**Repo:** `langchain-ai/langchain`, `langchain-core` **1.6.3**, pinned `5c1f2827`.
**Artifacts:** [`g30-natural-report-v1.json`](../../tests/fixtures/benchmarks/g30-natural-report-v1.json),
recorded inputs [`g30-natural-cases-v1.json`](../../tests/fixtures/benchmarks/g30-natural-cases-v1.json).

All 9 `xfail` markers in `libs/core/tests/unit_tests`, run through the full loop:
live agent judges from static evidence (marker reason + version), disagreement or
uncertainty escalates, the real clone runs the test (`--runxfail`), the empirical
outcome adjudicates. **Nothing was author-coupled** — the maintainers wrote the
markers; the 1.6.3 behavior is the ground truth.

## Result

| Marker (reason) | Agent | Empirical (clone) | Outcome |
| --- | --- | --- | --- |
| pydantic-v2-nested — "Direct pydantic v2 models not yet supported" | unknown | **likely_expired** | escalated → **stale marker found** |
| merge-dicts-0_3 — "Refactors to make in 0.3" | likely_expired | likely_active | **agent wrong, clone caught** |
| cache-stream — "…caching for streaming yet" | unknown | likely_active | escalation resolved |
| chain-order-v1 / v2 — "Fix order of callback invocations" | unknown | likely_active | escalation resolved |
| sync-in-async — "missing functionality" | unknown | likely_active | escalation resolved |
| optional-param — "Pydantic converts str\|None to str" | unknown | likely_active | escalation resolved |
| stream-error-cb — "bug in the testing code" | unknown | likely_active | escalation resolved (not a real condition) |
| chat-tmpl-dict — "in a breaking release…" | likely_active | (not adjudicated) | agreed → no clone spent |

**Empirically: 8 of 9 markers still active; 1 genuinely expired** (pydantic-v2-nested
— now supported, marker never removed).

**Metrics:** 9 cases, 8 escalations (all resolved), 7 resolved-unknowns, 1
adjudicated disagreement (agent 0 / heuristic 1), 1 error-catch, 1 agreement (no
clone).

## What this shows — honestly

1. **On real code with thin evidence, the agent abstains rather than guesses.** It
   returned `unknown` on 7 of 9. That is the calibrated behavior we want, and it is
   the opposite of the constructed cases (where leading evidence made it
   over-confident). It also means the headline value here is **escalation +
   adjudication, not agent classification** — with only one real head-to-head.
2. **Escalation turned every "I don't know" into a tested fact** (7/7 resolved), and
   in doing so **found the one genuinely stale marker** — the pydantic-v2 xfail that
   now passes. That is Sunset working: a real piece of temporal debt surfaced by
   running the code, not by trusting a model.
3. **The agent's single confident expiry call was wrong and the clone caught it**
   (merge-dicts, fooled by the version signal) — the safety net, again, on real code.
4. **Base rate matters:** 8/9 langchain-core xfail markers are still protecting real
   failures. A tool that blithely called old markers "expired" would be wrong most
   of the time here; the conservative-heuristic-plus-empirical-check design is not.

## Caveats

- N = 9, one repo, one model, one run — a first natural measurement, not a verdict.
- **Evidence was thin** (marker reason + version only). The 7 abstentions partly
  reflect evidence starvation; richer evidence (the test body, blame via G28,
  linked-issue resolution) would likely produce more definite agent calls. Feeding
  that richer evidence is the obvious next enrichment.
- Escalation recall is still not computed (agreements are not validated by design);
  the one agreement here (chat-tmpl-dict) was in fact still active.
