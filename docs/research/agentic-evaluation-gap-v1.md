# Finding: the agentic thesis is untested, not tested-and-worse (v1)

**Discovered:** 2026-09-15, while re-examining the G24 baseline in response to the
question "do we know the agent wasn't right?"
**Severity:** High (strategic) — the project's central bet is unmeasured, and the
one number that looked like a measurement is not one.
**Routed to:** [G30 — Live agentic escalation loop and evaluation](../goals/G30-live-agentic-escalation-evaluation.md).

## What the evidence actually shows

The G24 baseline reports heuristic condition accuracy 1.0000 (4 cases) vs.
recorded-agentic 0.6667 (3 cases), which reads as "the agent is worse." Inspecting
the fixtures shows that framing is wrong:

- `src/sunset/baseline_evaluation.py` performs **no classification** at evaluation
  time. It only `load_recorded_traces(...)` and scores them against labels. No
  model call, no rule engine, no reasoning.
- Both `heuristic` and `agentic_recorded` traces in
  `tests/fixtures/benchmarks/g24-recorded-traces-v1.json` are **pre-authored JSON
  records**. The `condition_status`, `unsupported_claims`, `citation_accuracy`,
  `input_tokens`, and `latency_ms` are all baked in.
- The G24 report states the fixture was built to "exercise unknown, contradictory,
  malformed, interrupted, budget-exhausted, and unsupported-claim outcomes." So the
  single divergent agentic case (`lc-stream-cache-xfail`: `contradictory` + one
  unsupported claim + citation 0.75) is a **deliberately scripted failure trace**,
  authored to test that the evaluator counts failures — not a live model fumbling
  evidence.

A live-model seam exists (`src/sunset/model_runtime.py`, `mode="live"` with an
injected `BaseChatModel`) but has **never been run against this corpus**.

## Conclusion

There is no measurement anywhere of a live agent weighing evidence and classifying.
The agentic thesis — that a model weighing evidence and choosing when to escalate
to empirical validation beats a static heuristic — is **untested**, not tested and
found wanting. The G24 accuracy gap is a property of fixture authorship.

Additionally, the full intended loop (model reasons → judges evidence
insufficient → requests a disposable-clone validation → re-weighs with the
empirical result) exists only as separate parts (G11 live reasoning, G12 loop,
G14 human-gated validation, G06 clone execution) and has never been exercised
end-to-end on real candidates.

## Why it matters

The current comparison scores the agent only on static hypothesis accuracy — its
weakest terrain, where a deterministic heuristic is naturally tidy — and gives it
zero credit for its hypothesized edge: knowing when to stop reasoning and run the
code. On disagreement cases especially, "I can't tell statically, so validate" may
be the correct behavior the metric records as a miss. G30 is designed to test this
directly, using the human-approved disposable-clone result to adjudicate
agent-vs-heuristic disagreements in scope.
