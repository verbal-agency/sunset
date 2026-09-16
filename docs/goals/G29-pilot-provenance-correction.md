# G29 — Pilot provenance correction and enrichment hardening

**Status:** proposed (next eligible; unblocked by G28)
**Dependencies:** G28 (authenticated exact-SHA Git evidence access, **complete**),
G27 (pilot fixture under correction, blocked)

> G28 is complete: the verified line-accurate commits are captured in
> `tests/fixtures/blame_evidence/openclaw-g27-blame-v1.json` and can be replayed
> offline via `RecordedBlameProvider` / `sunset blame-evidence fetch`. G29 applies
> those values to the pilot review fixture and hardens the enrichment path.

## Purpose

Correct the recorded provenance defect and remove its root cause so the pipeline
cannot present a guessed introduction point as historical fact again. The G27
pilot fixture records an identical, unrelated `introducing_commit`
(`ad6a81d5…`, a Tool Search perf commit) for all four OpenClaw candidates; true
line-level blame gives four distinct, line-accurate commits. Full evidence and
the correct values are in
[the finding record](../research/G27-provenance-defect-v1.md).

This matters because the charter treats a candidate that cannot establish an
introduction point as `incomplete`, never a guessed commit — and a maintainer
reviewer weighing "when/why was this added" would otherwise be misled by
confident-but-wrong provenance.

## Objective

1. Replace the four candidates' `introducing_commit`/`history_locator` in
   `tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json` with the
   G28-verified, line-accurate commits, each cited to the pinned head.
2. Root-cause the enrichment fault (see finding's three hypotheses) and change the
   broad-collector provenance path so a candidate whose introduction point cannot
   be established with authenticated exact-SHA blame is marked `incomplete` with an
   explicit obligation — never assigned a placeholder or a shared value.
3. Add a regression guard: reject a result set where multiple distinct candidate
   lines resolve to one identical `introducing_commit` unless that is
   independently verified.

## Correct values to apply (from G28-verified blame at head `0965053…`)

| Candidate ID | Location | Corrected introducing commit |
| --- | --- | --- |
| `sunset-broad-v2-15be1992b07e42a78f0c0b24` | `activity-run-inspector.e2e.test.ts:22` | `7ab5d99a6c3c` |
| `sunset-broad-v2-a4ba4f78d9030728b801e465` | `activity-session-feed.capture.e2e.test.ts:22` | `9b1c4bb3589d` |
| `sunset-broad-v2-eac9359052efa9f30c01df81` | `tool-titles.e2e.test.ts:199` | `3f1c84c706bf` |
| `sunset-broad-v2-ccb8a75b35e18dd8955874c5` | `activity-answer-candidates.e2e.test.ts:16` | `fbfad6eb4226` |

## Project alignment

- Advances OUT-02, OUT-05, OUT-08.
- Advances SCN-01 through SCN-03 (provenance an honest reviewer can trust).

## Scope boundary

Correct the four fixture records, fix and test the enrichment provenance path, and
add the duplicate-commit regression guard. Read-only against the pinned target.

## Explicit exclusions

- No removability inference, target mutation, or reviewer-decision changes; the
  four `reviewer` fields stay `pending` (that is the separate G27 human handoff).
- No change to candidate IDs (they are independent of blame results) or to the
  confirmed source lines, validation observations, or exclusions.
- No re-derivation of provenance from unauthenticated browser scraping.

## Outcomes and handoff

A corrected, line-accurate pilot fixture plus an enrichment path that fails closed
to `incomplete`. This restores the G27 packet's provenance integrity before the
single-reviewer handoff proceeds.

## Capability unlocked for the next goal

A trustworthy provenance substrate for the G27 maintainer pilot and any later
real-repository run.

## Verification direction (outline — not yet an execution contract)

Named tests for: the four corrected records matching G28 blame; the enrichment
path emitting `incomplete` (not a placeholder) when blame is unavailable; and the
regression guard rejecting an unverified shared `introducing_commit` across
distinct candidate lines.
