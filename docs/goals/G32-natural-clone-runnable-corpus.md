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
