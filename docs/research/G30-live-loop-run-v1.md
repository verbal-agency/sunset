# G30 live loop — end-to-end, empirically adjudicated (v1)

**Date:** 2026-09-16
**Goal:** [G30](../goals/G30-live-agentic-escalation-evaluation.md)
**Model:** Claude Sonnet (`claude-sonnet-4-5`), one call per case.
**Ground truth:** empirical — the disposable-clone validation result, not labels.
**Report artifact:** [`tests/fixtures/benchmarks/g30-live-loop-run-v1.json`](../../tests/fixtures/benchmarks/g30-live-loop-run-v1.json)

The first end-to-end run of the full loop: a **live model reasons**, disagreement or
uncertainty **escalates**, a **real disposable clone runs the code**, and the
empirical outcome **adjudicates**. Three pytest-marker cases with realistic evidence
and deliberately varied empirical ground truth (the test body decides the outcome;
it was withheld from the model).

## Result

| Case | Agent status | Escalation | Clone outcome | Empirical truth | Adjudication |
| --- | --- | --- | --- | --- | --- |
| upstream-fixed | likely_expired | disagreement | `confirmed` | likely_expired | **agent correct**, heuristic wrong |
| platform-active | likely_active | agreement (none) | — (not run) | (active) | agreed → no clone spent |
| misleading-temp | likely_expired | disagreement | `still_failing` | likely_active | **agent wrong**, heuristic correct — clone caught it |

Aggregate: 2 disagreements, both escalated and resolved; agent correct on 1,
heuristic correct on 1 — each decided by running the code.

## Why this matters

1. **Agentic value (upstream-fixed).** From the evidence that the dependency had
   moved past the buggy version, the agent inferred likely-expired — a call the
   flat "assume still active" heuristic cannot make — and the clone confirmed it.
2. **Efficiency (platform-active).** Agent and heuristic agreed the condition still
   holds, so the loop escalated nothing and spent no clone run.
3. **Safety net (misleading-temp).** The agent was misled by a "safe to remove
   after v3 migration; repo is on v3.2" hint, confidently returned likely-expired,
   and escalated. The clone ran and returned `still_failing`: the condition is
   still active. **The agent was wrong, and executing the code caught the error**
   before it could reach a human as a recommendation.

Case 3 is the concrete answer to "do we know the agent wasn't right?" — here we
know it was wrong, because we ran it. It is exactly why the disposable-clone result,
not model confidence, is the ground truth, and exactly the kind of empirically-
caught error a future feedback loop ([G31](../goals/G31-empirical-feedback-loop.md))
would learn from.

## Caveats

- Three constructed cases, one model, one run. A demonstration of the mechanism and
  its behaviors — not a measured quality verdict.
- Evidence strings were authored to span the outcome space; the empirical clone
  result, however, was not staged — it is the real result of removing the marker
  and running pytest in the clone.
- Human approval was simulated (all escalations approved) to exercise the full
  path; in production that boundary is a real human decision (G14).
