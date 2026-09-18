# G30 — evidence enrichment: does richer static evidence help the agent?

**Date:** 2026-09-17
**Goal:** [G30](../goals/G30-live-agentic-escalation-evaluation.md) / [G32](../goals/G32-natural-clone-runnable-corpus.md)
**Model:** Claude Sonnet (`claude-sonnet-4-5`).
**Cases:** the same 9 real langchain-core 1.6.3 `xfail` markers as the natural report.
**Capability:** `src/sunset/evidence_enrichment.py` (test-source extraction + evidence composition).
**Data:** [`g30-enrichment-comparison-v1.json`](../../tests/fixtures/benchmarks/g30-enrichment-comparison-v1.json).

We re-ran the agent with **richer evidence** — the marker reason *plus the full test
source and the marker's blame (introducing commit + date)* — and compared it against
the thin run (reason + version only) and the empirical clone outcome.

## Result

| Case | Thin | Rich | Empirical |
| --- | --- | --- | --- |
| stream-error-cb | unknown | unknown | active |
| cache-stream | unknown | unknown | active |
| chat-tmpl-dict | likely_active | **unknown** | active |
| chain-order-v1 | unknown | unknown | active |
| sync-in-async | unknown | **likely_active** ✓ | active |
| chain-order-v2 | unknown | unknown | active |
| pydantic-v2-nested | unknown | unknown | **expired** |
| optional-param | unknown | **likely_expired** ✗ | active |
| merge-dicts-0_3 | likely_expired ✗ | **unknown** | active |

## Finding: richer static evidence did not improve discrimination

- **Abstention rate was unchanged** — 7 of 9 `unknown` under both thin and rich.
- **Definite-call accuracy was unchanged** — 1 right / 1 wrong under each; the errors
  just moved (rich fixed the merge-dicts mistake but introduced a new one on
  optional-param).
- **Neither run's agent ever identified the one genuinely expired marker**
  (pydantic-v2-nested) — it abstained on it both times. Only the clone found it.

The test source and blame tell the agent *what is asserted* and *when the marker was
added* — not whether the code under test *currently* behaves as asserted. That last
fact is the decision, and it is not present in any static text; it takes executing
the code. So enrichment reshuffled the agent's confidence without making it more
correct, and it left the actual temporal debt undetected until the clone ran.

## Why this matters

This is a genuine, slightly humbling result that **strengthens the escalation-loop
design** rather than the agent: on real markers, better static evidence does not
substitute for running the code. The agent's role is to decide *when to escalate*;
the clone remains the only reliable arbiter of whether a condition still holds. It
also cautions against a naive [G31](../goals/G31-empirical-feedback-loop.md) that
tries to teach the agent to classify better from static features — the signal it
needs may simply not be static.

## Caveats

N = 9, one model, one run. "Richer" here is test source + blame; a different
enrichment (e.g. the *current implementation* of the function under test, or
executing a lightweight probe) might carry more signal — but at that point you are
most of the way to just running the test, which the loop already does.
