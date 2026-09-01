# G14 — Human-gated agentic validation

**Status:** complete
**Dependencies:** G13 (complete)

## Purpose

Let an investigator request empirical evidence without allowing it to authorize
code execution, mutate the maintainer's repository, or turn model confidence
into a cleanup action.

## Objective

Add a versioned validation-request and human-decision boundary to the bounded
agent loop. On explicit approval, resume through G06's existing disposable
validation adapter using only the reviewed candidate, command template, and
environment policy; on denial or expiry, execute nothing.

## Project alignment

- Advances OUT-04, OUT-06, and OUT-07.
- Advances SCN-01, SCN-02, SCN-07, SCN-09, and SCN-11.
- Supplies empirical receipts for G15 review; it does not finalize a case file
  or apply a cleanup.

## Architecture constraints to preserve

- G06 remains the sole execution/mutation authority and must retain its
  disposable-worktree, target-immutability, configured-command, and result
  contracts. G14 may request it, never replace or bypass it.
- A model may propose an allowlisted validation-plan name, but deterministic
  policy derives parameters from candidate/provenance/assumption receipts and
  presents the exact plan for a human decision. No model-supplied command,
  path, environment variable, approval token, or budget override is valid.
- Approval is explicit, scoped to one versioned plan and expiration window, and
  persisted separately from model inference. Denial, absent approval, expired
  approval, or changed plan/environment must run no validation.
- Checkpoints retain compact request/decision/result receipts and identities,
  never raw test logs, command output, credentials, framework messages, or a
  mutable target worktree path.

## In scope

1. Versioned validation-plan, approval/denial, terminal-reason, and receipt
   contracts independent of LangGraph message/checkpoint objects.
2. Deterministic plan builder from existing candidate, external-evidence, and
   G06 configuration receipts, including narrow/broader configured test choices
   and resource/timeout/flakiness policy already sanctioned by the host.
3. Agent-loop pause/interruption state that exposes a reviewable plan and
   resumes only after an explicit compatible approval decision.
4. Adapter bridge to G06's disposable validator, preserving its artifact-backed
   confirmed, still-failing, flaky, environment-error, and inconclusive result
   classifications.
5. Approval replay/idempotency, plan/environment/HEAD invalidation, target
   snapshot/status verification, and documentation.

## Explicit exclusions

- Agent-invented shell commands, test targets, clones, containers, environment
  variables, approval decisions, implicit approvals, or retries.
- Direct target-working-tree mutations, automatic marker removal, pull requests,
  external writes, cleanup recommendations, or case-file finalization.
- New external providers, general shell tools, multi-agent review, or release
  evaluation.

## Deliverables

1. Validation request/decision/receipt contracts and deterministic plan builder.
2. G12-compatible graph pause/resume node with explicit human approval adapter.
3. Narrow bridge to the existing G06 disposable validation API.
4. Isolated fixture tests for approve, deny, expiry, incompatibility, resume,
   result classes, duplicate containment, and target immutability.
5. Human-review and safety documentation.

## Goal-level acceptance criteria

- **G14-AC01 — Deterministic reviewable plan:** Given eligible local and
  external receipts, policy produces a versioned bounded validation plan whose
  candidate, command template, environment policy, budgets, and evidence links
  are all host-derived and serializable for review.
- **G14-AC02 — No approval, no execution:** Missing, denied, expired, malformed,
  or incompatible approval yields a structured paused/denied terminal result,
  invokes no G06 adapter, and leaves the target snapshot/status unchanged.
- **G14-AC03 — Scoped approved execution:** A valid approval executes only its
  exact compatible plan through G06's disposable adapter; the target repository
  remains untouched and the returned validation result is artifact-backed.
- **G14-AC04 — Replay and failure containment:** Checkpoint/resume cannot repeat
  a decision or validation run. Changed HEAD, plan, candidate, external evidence,
  validator/environment policy, approval scope/expiry, or budgets invalidate
  reuse; successful prior receipts survive later failure.
- **G14-AC05 — Result and data safety:** Confirmed, failing, flaky,
  environment-error, and inconclusive outcomes remain distinct. Checkpoints and
  prompts exclude raw logs, command output, credentials, and framework messages.
- **G14-AC06 — Compatibility and documentation:** Phase 1 through G13 contracts
  remain compatible; documentation explains the plan-review/approval boundary,
  target safety, replay policy, and why approval is not a cleanup decision.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G14-AC01 | Plan snapshots proving all fields derive from trusted receipts/configuration |
| G14-AC02 | Deny/absent/expired/adversarial approval tests with zero validator calls and target snapshot/status checks |
| G14-AC03 | Approved disposable fixture run asserting exact plan, G06 receipt, and target immutability |
| G14-AC04 | Interrupt/resume call counters and comprehensive identity invalidation matrix |
| G14-AC05 | Five validation-result fixtures and checkpoint/prompt raw-data scans |
| G14-AC06 | Locked regression suite, focused validation-agent tests, docs review, and `git diff --check` |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_agent_validation.py tests/test_validation.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G13 preserved external evidence as observations rather than expiry proof.
  G14 must require a conservative, reviewable plan even when all external
  receipts support expiry, and must never infer approval from that evidence.
- G13 model extensions use explicit allowed-tool names. G14 should add any
  request name behind the same configuration and deterministic argument resolver
  rather than broadening the model's framework-function authority.
- External-provider freshness participates in loop identity. G14 must bind the
  exact evidence receipt IDs into the approval plan so a changed external view
  cannot resume an old approval.

## Completion evidence

- **G14-AC01:** `test_plan_is_deterministic_reviewable_and_receipt_derived`
  proves the versioned plan and stable ID derive only from one provenance
  receipt, the bound HEAD, and trusted `ValidationConfig`.
- **G14-AC02:** Missing, denied, expired, wrong-plan, and changed-HEAD approval
  tests assert zero validator calls and unchanged target snapshots/status.
- **G14-AC03:** `test_approved_gate_delegates_to_g06_and_replay_does_not_repeat`
  delegates an approved plan to G06, preserves target immutability, and returns
  its artifact-backed confirmed result.
- **G14-AC04:** The same replay test proves a saved compatible result suppresses
  a second validator call; plan IDs bind candidate, receipts, HEAD, and config.
- **G14-AC05:** Parameterized tests preserve all five G06 result classes and
  scan gate views for raw-output text.
- **G14-AC06:** Existing G06/G10–G13 tests and the locked full suite pass.
  `README.md` and `docs/AGENT-VALIDATION.md` document review, approval, replay,
  target safety, and the non-cleanup-authority rule.

Verification on 2026-09-01: `uv lock --check`, focused G14/G06/G12/G13 tests,
the locked full suite, and `git diff --check` passed. The worktree remains
uncommitted pending human authorization.
