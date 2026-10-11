# G35 — Pilot readiness gap closure

**Status:** proposed (outline; not an implementation instruction)
**Dependencies:** G27 (pilot fixture and handoff), G33 (pinned-clone backend)

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
