# G32 — Natural clone-runnable evaluation corpus

**Status:** proposed
**Dependencies:** G30 (loop + report), G06 (disposable-clone validation), G22 + G28
(recorded/authenticated evidence), G25 (split discipline), G21 (corpus protocol)

## Purpose

Enable the first *honest* measurement of the escalation loop. Every result so far
is either a replayed fixture or a constructed demonstration whose evidence and
ground truth were set by the same author (see
[G30-live-loop-run-v2](../research/G30-live-loop-run-v2.md)). A real agent-accuracy
estimate requires cases where the **evidence is the real marker context** and the
**ground truth is the real clone outcome** — neither authored, so the two are
independent.

## Objective

Build a corpus of real `xfail`/`skip`/`skipif` markers mined from pinned public
Python repositories, each paired with (a) recorded real evidence (marker reason,
blame/provenance, linked issues) and (b) a reproducible disposable-clone validation
recipe, with fixed development/holdout splits. Then run the G30 loop over it and
publish the first agent-vs-heuristic result whose bias is characterized rather than
baked in.

## Chosen corpus: langchain-core (decided 2026-09-16)

The pilot corpus is **`langchain-ai/langchain`, package `langchain-core`
(`libs/core`)**, using its `tests/unit_tests` markers. It is pure-Python with light
deps, so clones are fast, deterministic, and cheap; its markers are real temporal
debt that can genuinely be expired or active; and it reconnects to the G08a/G21
pinned LangChain corpus. **OpenClaw is explicitly out of scope for measurement** —
its markers are heavy TS/E2E environment gates (browser, ffmpeg) that are expensive
to run, environment-sensitive (more `not_adjudicated`), and skewed toward "active";
it remains the G27 maintainer-pilot/demonstration repo only.

**Reproducible-environment recipe (pinned):** sparse-checkout `libs/core` at the
pinned commit, create a venv, `pip install -e libs/core` plus the declared `test`
dependency group, then run the marker's test with `--runxfail` (or AST marker
removal) in the disposable clone. Recorded in
[`docs/research/G30-real-case-langchain-core-v1.md`](../research/G30-real-case-langchain-core-v1.md).

**First real case captured** (pilot, N=1): `test_merge_dicts_0_3`
(`xfail "Refactors to make in 0.3"`) at langchain-core 1.6.3 — the live agent said
`likely_expired` (misled by the version signal), the clone still fails
(`likely_active`), the agent was wrong and the clone caught it. This is the first
non-author-coupled adjudicated case. Fixture:
`tests/fixtures/benchmarks/g30-real-cases-v1.json`.

**First natural report captured (2026-09-17, N=9).** All nine `xfail` markers in
`libs/core/tests/unit_tests` run through the full live loop (Sonnet + real clones).
Empirically **8 still active, 1 genuinely expired** (the pydantic-v2-nested xfail,
now supported but never removed — a real stale marker Sunset surfaced by running
the code). The agent abstained (`unknown`) on 7/9 given thin evidence (reason +
version only), escalation resolved all 7, its one confident expiry call was wrong
and the clone caught it, and it agreed-no-clone on one. Artifacts:
`tests/fixtures/benchmarks/g30-natural-{cases,report}-v1.json`, writeup
[`docs/research/G30-natural-report-v1.md`](../research/G30-natural-report-v1.md),
reproduced offline by `test_natural_report_reproduces_metrics`. Still N=9/one
model/one run — a first natural measurement, not a verdict; the obvious next
enrichment is richer evidence (test body, G28 blame, linked-issue resolution) to
reduce evidence-starved abstentions.

Candidate markers already located in `libs/core/tests/unit_tests` include
`test_utils.py::test_merge_dicts_0_3`, `test_function_calling.py` (two pydantic-v2
xfails), `test_cache.py` ("caching for streaming yet"), the RunnableSequence
callback-order xfails, and several `IS_GTE_3_11` / pydantic-v1/v2 `skipif` version
guards.

## Project alignment

- Advances OUT-04, OUT-05, OUT-08.
- Advances SCN-01 through SCN-03, SCN-06, SCN-12.
- Unlocks a genuine measurement for a continue/revise/stop decision, and the
  adjudicated cases that [G31](G31-empirical-feedback-loop.md) would learn from.

## Scope boundary

Pinned public repositories, read-only discovery + bounded disposable-clone
execution. A deliberately bounded candidate set with reproducible test
environments. Excludes cleanup, unbounded execution, and any claim beyond the
corpus.

## The hard problems (this goal must solve them, not assume them away)

1. **Reproducible environments.** Running a real marker requires the repo's
   dependencies at the pinned commit. G32 must pin dependency versions per
   candidate and record the environment, or the "empirical" result is not
   reproducible. Candidates whose environment cannot be pinned are excluded, not
   guessed.
2. **Executing third-party code safely.** G06 is explicitly *not* a security
   sandbox — running a repo's tests runs its code and installs its deps. G32 must
   either restrict to vetted repositories or add a bounded container/sandbox
   capability; unbounded execution of arbitrary repos is prohibited.
3. **Selection bias.** Clone-runnable markers (installable deps, deterministic
   tests) are a biased subset of all temporal debt. The corpus must document this
   and must not generalize beyond it.
4. **Non-conclusive outcomes.** Flaky/environment-error/inconclusive clone results
   are recorded as `not_adjudicated`, never forced into a verdict.
5. **The recall gap.** To estimate how often the loop *fails* to escalate a real
   expiry, include an audit sample of agreement cases that are also validated.

## Explicit exclusions

Author-set evidence or ground truth; unbounded dependency installation or arbitrary
third-party code execution outside a bounded/vetted boundary; cleanup or target
mutation; tuning on the holdout; treating a passing clone as removal proof;
accuracy claims beyond the clone-runnable subset.

## Outcomes and handoff

A frozen, provenance-bound, clone-runnable corpus with fixed splits, plus a G30
report over it that states an agent-vs-heuristic result with characterized
selection bias and a recall-audit estimate — the first result that is a
measurement rather than a demonstration.

## Capability unlocked for the next goal

A real evaluation substrate for G31 (empirical feedback loop) and for any
maintainer-facing quality claim.

## Note

Remains proposed until authorized. The security boundary for executing third-party
test code (problem 2) should be decided before the first candidate is run; a small
vetted-repo pilot is the natural first slice.
