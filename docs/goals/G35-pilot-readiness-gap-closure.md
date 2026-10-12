# G35 — Pilot readiness gap closure

**Status:** proposed (outline; not an implementation instruction)
**Dependencies:** G27 planning artifacts and handoff, G33 (pinned-clone backend)

G27 need not be complete or have a participating maintainer for this goal. Its
existing fixture, exact-head candidate, and handoff are the required inputs;
the human-gated pilot remains a separate blocked path.

## Purpose

Remove known weaknesses that would undermine any pilot or backtest result before
a human sees it: an unexercised validation path that left a reviewer decision at
`insufficient_evidence`, and project documentation that may imply measured
accuracy Sunset does not yet have. Credibility of every later measurement
depends on the claims and the open gaps being honest.

## Objective

(1) Exercise the OpenClaw exact-HEAD validation path (G27 candidate 3,
`ui/src/e2e/tool-titles.e2e.test.ts:199`) in an environment where the
ffmpeg-dependent test can run, or record it as permanently unvalidatable with
the reason, and update the review fixture accordingly. (2) Audit `README.md`
and `docs/` for statements that overstate accuracy, safety, or deletion
guidance and correct them to match recorded evidence. (3) Reconcile roadmap,
backlog, and handoff-document status so no stale "blocked on X" text remains
for inputs already supplied.

## Scope boundary

- A reproducible Linux/container run recipe for the ffmpeg-dependent validation,
  recorded as an environment receipt; the resulting evidence stored as a G06
  validation artifact; the reviewer decision for candidate 3 re-offered to the
  authorized reviewer (not recorded by Sunset).
- A claims audit producing a list of each statement checked, its supporting
  artifact, and the correction made.
- Status reconciliation across `docs/ROADMAP.md`, `docs/BACKLOG.md`, and
  `docs/research/G27-maintainer-pilot-handoff-v1.md`.

## Explicit exclusions

No new analysis features, no changes to reviewer decisions without the
reviewer, no fabricated validation results, no target-repository mutation, and
no new claims. If the ffmpeg path cannot run anywhere reproducibly, that is a
valid recorded outcome.

## Outcomes and scenarios expected to advance

OUT-05, OUT-08; SCN-03 (insufficient evidence stays honest), SCN-07 (human
control).

## Capability unlocked

A pilot or backtest report can cite a pilot fixture with no known unexercised
path and documentation that does not overclaim, so a reader's trust is not
spent on avoidable errors.

## Execution contract

### Expected implementation surface

- `tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json`: append the
  candidate-3 validation receipt and preserve the prior reviewer decision.
- `tests/fixtures/pilot/g35-openclaw-validation-v1.json`: record the exact
  source SHA, test selector, runtime, command, outcome, and failure reason.
- `docs/research/G35-pilot-readiness-report-v1.md`: claims-audit table and
  validation result.
- `docs/ROADMAP.md`, `docs/BACKLOG.md`, and
  `docs/research/G27-maintainer-pilot-handoff-v1.md`: status-only corrections.
- `tests/test_pilot_readiness.py`: fixture integrity, claims-audit, and
  status-reconciliation tests.

Equivalent paths are allowed only if they preserve the same immutable receipt,
reviewer-boundary, and documentation contracts.

### Contracts and invariants

- `ValidationReceipt` has schema version, repository URL, exact source SHA,
  candidate path and selector, runtime identity, command argv, network mode,
  start/end timestamps, outcome (`confirmed`, `still_failing`, `flaky`,
  `environment_error`, or `unvalidatable`), artifact IDs, and unresolved
  obligations.
- A successful receipt proves only the declared test scope; it never changes a
  reviewer decision or grants cleanup authority.
- An unvalidatable receipt must include a stable failure code and a bounded
  reproduction command; it cannot be represented as `confirmed`.
- Existing reviewer fields remain byte-for-byte unchanged except for an
  explicitly owner-authorized re-offer marker.

### Behavior matrix

| Condition | Required result |
| --- | --- |
| Exact SHA, ffmpeg available, test passes twice | `confirmed` receipt; reviewer decision unchanged |
| Exact SHA, ffmpeg unavailable or setup fails | `unvalidatable`/`environment_error` receipt with reason and reproduction; no guessed result |
| Moving ref or missing source SHA | reject before execution; no artifact |
| Reviewer absent or not authorized | no decision update; record `reviewer_reoffer_required` |
| Claims statement lacks supporting artifact | mark `unsubstantiated` and correct or remove the statement |
| Existing blocked status has been cleared by evidence | update only the status text; do not reorder goals |

### Authority, network, and stop rules

- Only the declared OpenClaw public clone and disposable validation clone may
  be accessed. Network-enabled dependency installation requires explicit
  authorization; no credentials are copied into the child environment.
- Commands are argv-only, bounded by timeout, and run outside the target
  checkout. No target mutation, cleanup, pull request, maintainer contact, or
  reviewer decision is permitted.
- Stop immediately on a moving ref, missing receipt field, target snapshot
  change, credential exposure, or any attempt to write a reviewer decision.
- Stop with `unvalidatable` after the declared Linux/ffmpeg recipe fails twice;
  do not keep changing environments until a desired result appears.

### Fixtures, replay, and acceptance map

Record positive, unavailable-ffmpeg, malformed-receipt, moving-ref, and
reviewer-absent fixtures. Replaying the report must not clone, install, execute
third-party code, or call a model. The goal-level checks are:

- **G35-AC01:** candidate-3 validation is either reproduced at the exact SHA or
  recorded as `unvalidatable` with a stable reason and command.
- **G35-AC02:** the pilot review fixture retains the reviewer decision and
  records any re-offer as a separate pending action.
- **G35-AC03:** the claims audit lists every checked claim, artifact support,
  and correction; no unsupported accuracy/safety/deletion claim remains.
- **G35-AC04:** roadmap, backlog, and handoff statuses contain no stale blocker
  for supplied evidence, with a regression test for the corrected status.
- **G35-AC05:** malformed, moving-ref, unavailable-runtime, and reviewer-absent
  cases fail closed and replay byte-identically.

Evidence mapping: `tests/test_pilot_readiness.py` covers AC01, AC02, AC04, and
AC05; the claims-audit report covers AC03; `uv run --locked pytest -q` and
`git diff --check` are required before completion.
