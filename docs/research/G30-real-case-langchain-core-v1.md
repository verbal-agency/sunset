# G30 — first natural clone-runnable case (langchain-core)

**Date:** 2026-09-16
**Goal:** [G30](../goals/G30-live-agentic-escalation-evaluation.md) / pilot for [G32](../goals/G32-natural-clone-runnable-corpus.md)
**Fixture:** [`tests/fixtures/benchmarks/g30-real-cases-v1.json`](../../tests/fixtures/benchmarks/g30-real-cases-v1.json)

The first case where **nothing was authored to produce the result**: a real
LangChain marker, a real live-model judgment, and a real disposable-clone outcome.

## The case

- **Repo:** `langchain-ai/langchain`, package `langchain-core`, pinned at
  `5c1f28271295bb13034f4cf8964f74c117357d40` (version **1.6.3**).
- **Marker:** `libs/core/tests/unit_tests/utils/test_utils.py::test_merge_dicts_0_3`
  — `@pytest.mark.xfail(reason="Refactors to make in 0.3")`.
- **What it protects:** the test asserts `merge_dicts` raises `ValueError("Unable to
  merge")` on conflicting `type` keys.

## What happened

1. **Live agent (Claude Sonnet), static evidence only →** `likely_expired`. It was
   misled by the obvious version signal: "0.3 was long ago, the repo is on 1.6.3,
   the refactor must have landed."
2. **Conservative heuristic →** `likely_active`.
3. **Disagreement → escalate → run the code.** In a disposable venv with
   langchain-core 1.6.3 + its test group installed:
   `pytest ...::test_merge_dicts_0_3 --runxfail` → **2 failed.** `merge_dicts` still
   returns `{'type': 'foobar'}` instead of raising. Empirical status: **`likely_active`.**
4. **Adjudication:** agent **wrong**, heuristic **right**, and the clone caught the
   agent's error.

## Why it matters

- **Non-author-coupled.** The maintainers wrote the marker; `merge_dicts`'s actual
  1.6.3 behavior is the ground truth; the run just observed it. Unlike the
  constructed cases, this is a genuine data point.
- **A real misleading temporal signal in the wild.** The version number strongly
  implies expiry, and the agent (a strong model) fell for it. A maintainer skimming
  "0.3 refactors, we're on 1.6.3" could make the same mistake.
- **Concrete harm avoided.** Acting on `likely_expired` would have un-skipped a test
  that genuinely still fails — a real regression prevented by executing the code
  rather than trusting the model's confidence.

This is exactly the value the escalation loop exists to deliver, now shown on real
code: **the model's judgment is a hypothesis; the clone is the arbiter.**

## Caveat

N = 1. One real case is a data point, not a measurement. It is, however, the first
honest one, and it already demonstrates the safety net firing on real code. Scaling
this into an actual measurement is [G32](../goals/G32-natural-clone-runnable-corpus.md).

## Reproduce

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/langchain-ai/langchain lc
cd lc && git sparse-checkout set libs/core && git checkout 5c1f28271295bb13034f4cf8964f74c117357d40
python -m venv .venv && .venv/bin/pip install -e libs/core \
  freezegun pytest-mock syrupy pytest-asyncio grandalf responses pytest-socket \
  pytest-xdist blockbuster numpy langchain-tests pytest-benchmark pytest-codspeed
.venv/bin/python -m pytest \
  libs/core/tests/unit_tests/utils/test_utils.py::test_merge_dicts_0_3 --runxfail -q
```
