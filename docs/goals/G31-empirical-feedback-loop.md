# G31 — Empirical feedback loop for agent judgment (exploration)

**Status:** complete (exploration / spike)
**Dependencies:** G30 (produces empirically-adjudicated cases), G25 (split-safe
optimization discipline)

## Purpose

Explore whether and how to use G30's **empirically-adjudicated** outcomes — the
disposable-clone ground truth of who was right when the agent and heuristic
disagree — to improve the agent's *future* protected-condition judgments, without
weakening the project's epistemic, split-safety, and human-authority guarantees.

This is worth exploring precisely because the learning signal is trustworthy:
unlike systems that learn from noisy human labels ("assertions that aren't
tested"), G30 yields tested facts. The risk is not a bad signal; it is misusing a
scarce, biased one.

## Objective

An exploration goal, not a production learning system. Survey candidate feedback
mechanisms, define a leakage-safe improvement-and-measurement protocol, enumerate
the risks, and produce a bounded recommendation on whether and what to build —
optionally with one small offline prototype on the development split only.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, OUT-08.
- Advances SCN-06 and SCN-12.
- Unlocks a decision (and design) for a safe continual-improvement path, or a
  documented decision that it is not yet warranted.

## Scope boundary

Design and analysis, plus at most one small offline prototype evaluated only on the
G25 development split. No production/online learning, no change to the
human-approval boundary or the conservatism guarantees.

## Architecture constraints to preserve

1. Empirical clone outcomes are evidence about the tested scope, not removal
   authority. Feedback may change a hypothesis or escalation policy only.
2. The G25 holdout is read-only and sealed until the final measurement. No
   exemplar, calibration parameter, retrieval index, or prompt choice may be
   derived from holdout data.
3. Recorded/offline execution is the default. No model, network, subprocess,
   target-repository mutation, cleanup, or approval side effect is permitted.
4. Non-conclusive validation and asserted human labels are excluded from the
   learning signal but remain visible as exclusions and limitations.
5. The feedback mechanism is replaceable and additive. Existing G11/G12/G14/G30
   contracts and low-level CLIs remain backward compatible.

## In-scope work

- Define a versioned empirical-feedback packet that selects only development-split
  cases with `confirmed` or `still_failing` clone outcomes.
- Compare at least two bounded mechanisms from the exploration set (for example,
  adjudicated exemplars and a deterministic confidence/calibration rule).
- Specify a leakage audit that rejects holdout-derived inputs, labels, or tuning
  parameters before a prototype can run.
- Implement at most one small offline prototype behind a replaceable interface,
  and report per-case changes, escalation changes, and cost/latency deltas.
- Produce a recommendation to build, defer, or reject production feedback.

## Explicit deliverables

1. A versioned feedback schema and development-only packet under
   `tests/fixtures/benchmarks/`.
2. A leakage/eligibility audit with deterministic JSON output.
3. A comparison report covering the selected mechanisms and the no-feedback
   baseline, including exclusions and small-sample limitations.
4. If the audit passes, one offline prototype and replay fixture; otherwise an
   explicit blocked recommendation with no prototype.
5. Documentation recording the recommendation, risks, and why no production
   learning or authority was introduced.

## Goal-level acceptance criteria

- **G31-AC01 — Signal eligibility:** The feedback packet includes only
  development-split cases with empirical status `likely_active` or
  `likely_expired` derived from `confirmed` or `still_failing`; non-conclusive
  outcomes and asserted labels are rejected or recorded as excluded.
- **G31-AC02 — Leakage gate:** The audit deterministically rejects any packet,
  mechanism, or parameter containing a holdout case ID, holdout-derived artifact,
  or holdout-derived tuning value, with a named diagnostic and no prototype run.
- **G31-AC03 — Mechanism comparison:** At least two bounded mechanisms and the
  no-feedback baseline produce a versioned, per-case comparison on the
  development split; the report includes escalation, status, token/cost, and
  latency deltas or explicit unavailable values.
- **G31-AC04 — Authority preservation:** Prototype output can only alter a
  model hypothesis or escalation request; tests prove it cannot approve
  validation, mutate a target, perform cleanup, or turn a passing clone into a
  removal recommendation.
- **G31-AC05 — Replayability:** Recorded feedback input, audit, and comparison
  report reproduce byte-identically without model, network, subprocess, or target
  repository access.
- **G31-AC06 — Recommendation:** The final artifact chooses `build`, `defer`, or
  `reject`, cites the measured comparison and exclusions, and states that the
  G25 holdout remains sealed.

## Criterion-to-evidence map

| Criterion | Required evidence |
| --- | --- |
| G31-AC01 | `tests/test_feedback_loop.py::test_eligibility_excludes_non_conclusive` and the versioned development packet |
| G31-AC02 | `tests/test_feedback_loop.py::test_leakage_gate_rejects_holdout` plus audit JSON |
| G31-AC03 | `tests/test_feedback_loop.py::test_mechanism_report_compares_baselines` and comparison report fixture |
| G31-AC04 | `tests/test_feedback_loop.py::test_feedback_cannot_authorize_or_mutate` |
| G31-AC05 | `tests/test_feedback_loop.py::test_recorded_feedback_replays_byte_identically` with socket/subprocess/target guards |
| G31-AC06 | `docs/research/G31-feedback-decision-v1.md` and its cited report digest |

## Required verification commands

```bash
uv run --locked pytest -q tests/test_feedback_loop.py
uv run --locked pytest -q tests/test_feedback_loop.py tests/test_optimization.py tests/test_escalation_report.py
git diff --check
```

## Execution contract

### Expected implementation surface

- `src/sunset/feedback_models.py`: versioned eligibility, packet, mechanism,
  comparison, audit, and recommendation contracts.
- `src/sunset/feedback_loop.py`: deterministic packet audit and at most one
  injected offline mechanism prototype; no model/network/subprocess calls.
- `tests/test_feedback_loop.py`: the named acceptance and side-effect tests.
- `tests/fixtures/benchmarks/g31-feedback-{development,holdout-invalid,report}-v1.json`:
  positive, excluded, malformed, and leakage cases.
- `docs/research/G31-feedback-decision-v1.md`: recommendation and limitations.

Equivalent modules are allowed only if the same public contracts, fixture paths,
authority boundaries, and acceptance evidence remain available.

### Canonical contracts and invariants

The feedback packet schema version is `1` and includes `source_report_digest`,
`development_case_ids`, `excluded_case_ids`, `empirical_status`,
`validation_outcome`, and `mechanism_inputs`. Eligible cases must have a
development split and validation outcome `confirmed` or `still_failing`; every
other case is excluded with a reason. A recommendation is one of `build`,
`defer`, or `reject` and is non-authoritative. A packet containing a holdout ID,
holdout artifact digest, or unsealed tuning value is an invalid packet.

### Deterministic behavior matrix

| Input | Required result |
| --- | --- |
| Eligible development cases only | audit passes; comparison may run |
| `flaky`, `environment_error`, or `inconclusive` case | excluded; no inferred label |
| asserted human label without empirical outcome | excluded; diagnostic names unsupported source |
| holdout case/artifact/parameter present | audit fails; prototype does not run |
| malformed packet or unknown mechanism | structured error; no side effect |
| valid recorded replay | byte-identical audit/report |

### Authority, side effects, and stop conditions

The goal may read committed fixtures and G25/G30 report artifacts and write only
new local report artifacts. It must not access the network, credentials, target
repositories, subprocesses, model providers, validation runners, or approval
stores. Stop after the leakage audit fails, a configured development budget is
exhausted, or one prototype has completed; never silently retry a rejected or
completed experiment.

### Replay and budget rules

Packet identity includes source report digest, split, mechanism ID, and all
parameters. Replaying the same identity reuses the immutable report. Mechanisms
have explicit case, token, and output-size budgets; a budget exhaustion is a
recorded non-result, not a substituted score. Holdout access is never a cache
fallback.

## Key exploration questions

1. **Learning signal.** Only empirical adjudication (`confirmed → likely_expired`,
   `still_failing → likely_active`) is ground truth; `flaky` / `environment_error`
   / `inconclusive` and asserted reviewer labels are excluded. Confirm this is the
   sole signal.
2. **Mechanism (compare, don't assume).** Options include: a few-shot exemplar
   memory of adjudicated cases injected into the agent's context; a calibration
   layer over the agent's confidence; retrieval of similar past-adjudicated cases;
   or G25-style prompt/policy optimization. Explicitly *excluded from default
   consideration*: fine-tuning model weights.
3. **Leakage-safe measurement.** Improvement must be measured only on cases the
   agent did not learn from; the G25 holdout stays sealed. Define the protocol
   before any prototype.
4. **The scarce, biased sample.** Ground truth exists only for cases that were
   escalated *and* approved *and* conclusively validated — a biased slice. Explore
   whether learning from it generalizes or just overfits.

## Risks to characterize

- Overfitting to a handful of validated cases (tiny N).
- Distribution shift / selection bias in which cases get ground truth.
- Self-reinforcement: the agent's own outputs steering future judgments into a
  filter bubble.
- Perverse incentives: feedback making the agent over-eager to escalate (cost) or
  over-confident (skips escalation it should make).
- Any drift of model confidence toward becoming removal authority — prohibited.

## Explicit exclusions

Fine-tuning weights; learning from asserted (human) labels or from the holdout;
online self-reinforcement in production; any change that lets feedback, confidence,
or a passing validation become cleanup authority; removing the human approval gate.

## Capability unlocked for the next goal

A bounded recommendation and design for a safe empirical continual-improvement
loop — or a documented, evidence-based decision to defer it.

## Completion evidence (2026-10-10)

- **G31-AC01:** `g31-feedback-development-v1.json` contains four eligible
  development cases and one explicitly excluded inconclusive control;
  `test_eligibility_excludes_non_conclusive` passes.
- **G31-AC02:** the holdout-bearing fixture is rejected before any mechanism runs;
  `test_leakage_gate_rejects_holdout_without_running_prototype` passes.
- **G31-AC03:** the report compares no-feedback, leave-one-out exemplar, and
  calibration-guard mechanisms with per-case status, escalation, token, cost,
  and latency fields; `test_mechanism_report_compares_baselines` passes.
- **G31-AC04:** socket/subprocess guards and report inspection prove the prototype
  cannot authorize validation, mutate a target, or perform cleanup.
- **G31-AC05:** recorded comparison replay is byte-identical and the full locked
  suite passes with one pre-existing skip.
- **G31-AC06:** [`G31-feedback-decision-v1.md`](../research/G31-feedback-decision-v1.md)
  records the evidence-bounded `defer` recommendation and sealed-holdout limit.

The exploration does not change the human-gated, precision-over-recall guarantees.
