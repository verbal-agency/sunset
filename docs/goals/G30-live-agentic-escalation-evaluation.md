# G30 — Live agentic escalation loop and evaluation

**Status:** active
**Dependencies:** G06, G11, G12, G14 (complete), G24 + G25 (frozen splits and
evaluator, complete), G29 (corrected provenance, complete), plus explicit
live-model authorization for the live run.

## Grounding principle (owner steer, 2026-09-15)

Ground truth is **empirical, not asserted.** The human-approved disposable-clone
result — the tested outcome of actually removing the marker and running the code —
is the adjudicating fact for a case. Single-reviewer condition labels are treated
as "assertions that aren't tested" and are **not** the evaluation's ground truth;
they are at most a weak prior. G30 therefore *bootstraps a corpus of empirically-
adjudicated cases from validation results* rather than depending on more human
labels. **Strengthening the corpus with additional human adjudication is
explicitly NOT a prerequisite** for this goal. The headline output is the set of
empirically-adjudicated cases (especially agent-vs-heuristic disagreements), never
an aggregate accuracy claim over a handful of asserted labels.

## Purpose

Test the project's central bet, which is currently **untested** rather than
tested-and-worse (see
[agentic-evaluation-gap-v1](../research/agentic-evaluation-gap-v1.md)): that a
live model weighing evidence and choosing *when to escalate to empirical
validation* produces better-calibrated protected-condition decisions than the
deterministic heuristic. Every "agentic" number to date is a replayed authored
fixture; no live model has ever weighed evidence against this corpus, and the
full reason→escalate→run→re-weigh loop has never been exercised end-to-end.

## Progress (2026-09-15)

- **Loop core (AC01/AC02):** `src/sunset/escalation_loop.py` +
  `escalation_loop_models.py` — escalation decision, fail-closed approval gate,
  and empirical adjudication (`confirmed→likely_expired`,
  `still_failing→likely_active`, else `not_adjudicated`), with per-case
  agent/heuristic correctness and empirically-grounded aggregates. Recorded
  reasoner runs offline/deterministically.
- **Live plumbing:** `src/sunset/live_model.py` builds an injectable
  `ChatAnthropic`/`ChatOpenAI` from an explicitly named env var (optional `live`
  extra; installed). `.env` gitignored; `.env.example` added.
- **Real validator wiring + end-to-end demo (AC06):** `build_g06_validator`
  adapts the G06 disposable-clone validator; `tests/test_escalation_end_to_end.py`
  runs real clones and shows empirical adjudication both ways (agent right on an
  expired case, heuristic right on an active case), denied approval runs no clone,
  and the target repos stay unchanged.
- **Live agent reasoner + first live run:** `src/sunset/live_reasoner.py`
  (`LiveAgentReasoner`, bounded, fail-safe to `unknown`) + `live_model.load_env_file`.
  First real live reasoning executed on the four OpenClaw candidates with **both**
  Claude Sonnet and gpt-4.1 — identical statuses across models, uniformly
  conservative, and `unknown` (→ escalate) exactly where static evidence is thin.
  Recorded in [`docs/research/G30-live-reasoning-v1.md`](../research/G30-live-reasoning-v1.md).
- **End-to-end live loop (clone-runnable):** ran the full loop with a live model
  and real clones over three pytest cases — agent right where the heuristic missed
  expiry, no clone spent on agreement, and an overconfident agent error caught by
  the clone. Recorded in
  [`docs/research/G30-live-loop-run-v1.md`](../research/G30-live-loop-run-v1.md) and
  `tests/fixtures/benchmarks/g30-live-loop-run-v1.json`.
- **Report (AC03/AC05):** `src/sunset/escalation_report.py` computes empirical
  metrics (escalation rate/resolution, agent-vs-heuristic wins on adjudicated
  disagreements, error catches, resolved unknowns; recall explicitly not computed)
  and renders JSON + Markdown. The canonical report
  (`tests/fixtures/benchmarks/g30-escalation-report-v1.json`,
  [`docs/research/G30-escalation-report-v1.md`](../research/G30-escalation-report-v1.md))
  is regenerated deterministically from recorded inputs and verified offline by
  `tests/test_escalation_report.py`. 287 pass / 1 skip.
- **Remaining:** a live reasoner wired through the G11 `model_runtime` receipts
  (currently a bounded standalone classifier), and a larger clone-runnable case set
  before any aggregate quality claim.

## Objective

Compose the existing live reasoning (G11), bounded loop (G12), human-gated
validation (G14), and disposable-clone execution (G06) into one resumable
escalation loop in which the model may (a) form and revise a protected-condition
hypothesis from bounded evidence and (b) emit a validation **request** when static
evidence is insufficient or when its status diverges from the heuristic. Then
evaluate that loop against the heuristic baseline on the frozen corpus, scoring
end-to-end decision quality **including escalation appropriateness and
disagreement adjudication**, with the live-model run explicit, gated, and
recorded-first for tests.

## Project alignment

- Advances OUT-03, OUT-04, OUT-05, OUT-06, OUT-08.
- Advances SCN-06, SCN-08 through SCN-12.
- Unlocks the first empirical answer to whether agency earns its complexity, and a
  reusable live-loop harness for later pilots.

## Scope boundary

Compose existing components; add no new execution adapter and no new authority.
The loop is evaluated on the frozen G23/G24 corpus and demonstrated end-to-end on
at least one real, already-validated candidate (an OpenClaw G27 candidate). Any
tuning uses the development split only; the holdout stays sealed (G25 discipline).

## Key design constraints (from the charter)

1. **Inference and authority stay separate.** The model may *propose* a validation
   experiment; only a human approval (G14) invokes G06; only deterministic code
   executes the clone. No autonomous execution, ever.
2. **Recorded-first.** Default and CI runs replay recorded model responses and make
   no live model or network call. The live run is a separate, explicitly enabled,
   separately authorized step (mirrors the G22a live-capture pattern) and, if not
   executed, is reported as `not_executed` — never fabricated.
3. **Labels remain limited.** G23 single-reviewer provisional labels are the only
   ground truth; every result carries that limitation. The disposable-clone result
   is in-scope empirical evidence, not proof of removability.
4. **Split-safe.** No holdout-driven tuning; holdout may be read once for the
   final report.

## Escalation and disagreement semantics

- **Escalation trigger:** the loop escalates (emits a validation request) when the
  model reports insufficient static evidence, an `unknown`/`contradictory` status,
  or a status that diverges from the heuristic for the same case.
- **Disagreement adjudication:** when the live agent's condition status diverges
  from the heuristic, the human-approved disposable-clone validation result is
  recorded per case as the in-scope adjudicator of the divergence — directly
  answering "was the agent right?" for that case, within validation scope.
- **Escalation appropriateness:** a declared, versioned rule classifies each case
  as escalation-warranted or not (from its evidence sufficiency and open proof
  obligations); the report records per-case escalated/warranted flags and aggregate
  escalation precision/recall.

## Goal-level acceptance criteria

- **G30-AC01 — Composed gated loop:** A loop exists where the model can emit a
  validation request and only a valid human approval invokes G06; absent/denied/
  expired/wrong-plan approval runs nothing. Verified by unit tests.
- **G30-AC02 — Recorded determinism:** In recorded mode the loop runs with no live
  model or network call and replays byte-identically. Verified by tests.
- **G30-AC03 — Escalation metric:** The evaluation report records, per case, the
  escalation decision, approval decision, validation outcome class, and an
  escalation-appropriateness flag from a declared versioned rule, plus aggregate
  escalation precision/recall alongside condition accuracy, unsupported-claim rate,
  and citation accuracy.
- **G30-AC04 — Disagreement adjudication:** For every case where the agent status
  diverges from the heuristic, the report records the escalation and, when
  approved and run, the disposable-clone adjudication result; unrun divergences are
  marked `not_adjudicated`, never guessed.
- **G30-AC05 — Paired comparison:** A paired agent-vs-heuristic report over the
  frozen development split (and a single sealed holdout read) is produced; a live
  run is gated and reported as `executed` or `not_executed`.
- **G30-AC06 — End-to-end demonstration:** At least one real candidate (an OpenClaw
  G27 candidate) is carried through reason → escalate → human-approve → clone-run →
  re-weigh, recorded as a trace, with the pinned target checkout unchanged.
- **G30-AC07 — Side-effect boundary:** No autonomous execution, target mutation,
  holdout tuning, or fabricated live result; recorded default makes no model or
  network call; live model/network only under explicit enablement.

## Criterion-to-evidence map

| Criterion | Evidence |
| --- | --- |
| G30-AC01 | `tests/test_escalation_loop.py` (approval gating) |
| G30-AC02 | recorded-mode replay test + byte-identical assertion |
| G30-AC03 | escalation metric in the evaluation report + test |
| G30-AC04 | per-case disagreement/adjudication fields in the report fixture |
| G30-AC05 | paired report fixture under `tests/fixtures/benchmarks/` |
| G30-AC06 | recorded end-to-end trace fixture for one OpenClaw candidate |
| G30-AC07 | boundary tests (no-live-call default, no-mutation, gated live) |

## Explicit exclusions

Autonomous code execution, automatic cleanup, target-repository writes,
holdout-driven tuning, treating a passing validation as removal proof, general
availability claims, and any live-model run without explicit authorization.

## Authority and side effects

Recorded mode is the default and is fully offline. The live run requires an
explicitly injected `BaseChatModel` plus host authorization; it makes bounded
model calls only. Validation execution remains G14-gated and G06-disposable; the
analyzed/target repository is never modified.

## Execution contract

### Expected implementation surface

- `src/sunset/escalation_loop.py`: compose `model_runtime` (G11), `agent_loop`
  (G12), `agent_validation` (G14), and `validation` (G06) into one resumable loop
  with a typed escalation decision and recorded-first replay.
- `src/sunset/baseline_evaluation.py` (or a new `escalation_evaluation.py`): add
  the escalation-appropriateness and disagreement-adjudication metrics to the
  report without breaking the G24 report schema (additive, versioned).
- `tests/test_escalation_loop.py`, an escalation evaluation test, recorded loop
  fixtures, and a paired report fixture under `tests/fixtures/benchmarks/`.
- This specification and `docs/ROADMAP.md`.

### Canonical contracts and legal states

The loop's terminal states are the existing conservative outcomes plus an explicit
`escalation_requested` / `escalation_denied` / `validated_in_scope` /
`not_adjudicated`. A divergence with no approved run is `not_adjudicated`, never a
resolved status. A live result is `executed`; its absence is `not_executed`.

### Behavior matrix

| Input/evidence condition | Required result |
| --- | --- |
| recorded mode, no credential | full loop, no model/network call, byte-identical replay |
| sufficient static evidence, agent agrees with heuristic | no escalation; recorded status |
| insufficient evidence or agent/heuristic divergence | escalation request emitted |
| escalation approved by human | G06 disposable-clone run; result recorded and re-weighed |
| escalation denied/absent/expired | no run; `escalation_denied`/`not_adjudicated` |
| live mode without injected model | structured error; no fabricated trace |

### Verification evidence

Named tests for approval gating, recorded determinism/replay, the escalation
metric, disagreement adjudication, the no-live-call default, and the gated live
path, plus a saved paired report and one end-to-end recorded trace. A passing loop
is evidence of behavior only; it is never a removability conclusion.
