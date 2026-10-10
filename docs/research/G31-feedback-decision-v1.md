# G31 empirical feedback decision v1

**Date:** 2026-10-10
**Input:** `tests/fixtures/benchmarks/g31-feedback-development-v1.json`
**Report:** `tests/fixtures/benchmarks/g31-feedback-report-v1.json`
**Source report digest:** `4b12698934f358ab40b945b4f812b204d8888b444cfe480b2a89c077142867fb`

## Decision

**Defer production feedback.** The offline prototype is useful as a measurement
and leakage-control seam, but four eligible development cases are not enough to
justify an online or production learning mechanism.

## What was compared

The packet contains four eligible LangChain cases from the G30 natural report and
one explicitly excluded inconclusive control. The comparison is development-only
and uses empirical outcomes from `confirmed` and `still_failing` validation runs.

| Mechanism | Definite accuracy | Escalation rate | Interpretation |
| --- | ---: | ---: | --- |
| no-feedback baseline | 0.00 | 0.75 | Mostly abstains; one definite claim is wrong |
| leave-one-out exemplar memory | 0.50 | 0.25 | Correctly resolves the two same-family stream cases, but misclassifies the pydantic pair |
| calibration guard | 0.00 | 0.75 | Reduces one definite claim to `unknown` but does not improve measured accuracy |

Token, cost, and latency measurements are carried through unchanged; this
prototype performs no model calls and has zero feedback overhead. The exemplar
mechanism never uses the case being classified, and the leakage audit rejects
holdout IDs, holdout artifacts, and holdout-bearing mechanism parameters before
any mechanism runs.

## Limitations and authority boundary

The packet is a selected, small, clone-runnable development subset. It does not
estimate general accuracy, recall, or production value. Non-conclusive outcomes
and asserted human labels are excluded rather than converted into labels. No
feedback output approves validation, mutates a repository, performs cleanup, or
establishes removability.

The G25 holdout remains sealed. A future build decision requires a preregistered
mechanism, a larger independent development set, and a separate holdout read.
