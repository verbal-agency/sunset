# G36 — Maintainer pilot recruitment kit

**Status:** proposed (outline; not an implementation instruction)
**Dependencies:** G27 (approved Part A protocol), G33 (single-entry `pilot run`)

## Purpose

The one remaining external gate on G27 is a real, consenting maintainer, and
recruiting is slow when every step is improvised. Preparing a complete,
protocol-faithful kit lets the owner make contact with minimal effort and lets a
participant say yes or no on a concrete, bounded request.

## Objective

Produce the materials and screening needed to start a maintainer pilot under
the already-approved G27 Part A protocol: a ranked list of pre-screened target
libraries, an outreach message, a plain-language consent form and disclosure
approval step, and a per-participant run packet template that `pilot run` can
fill for at most four candidates.

## Scope boundary

- Pre-screen public Python libraries for: active maintainers, years of history,
  a meaningful number of `xfail`/`skip`/`skipif` markers, runnable test suites
  on the G33 supported runtime, and a public contact path. Record counts and the
  screening method.
- Draft the outreach message, one-page explanation of what Sunset reads and
  produces, the consent form, and the disclosure-approval step matching the Part
  A fields (≤4 candidates, read-only narrow scope, data minimization,
  retention, stop rule).
- A per-participant run-packet template and a checklist for the owner.
- Dry-run the packet on a public library as a rehearsal, with no participant
  and no contact.

## Explicit exclusions

Sunset does not contact anyone, send messages, or post publicly; the owner
sends all outreach. No fabricated participants, replies, or maintainer
decisions. No pilot on the owner's own repositories. This goal does not satisfy
G27; it only prepares the participant gate.

## Outcomes and scenarios expected to advance

OUT-04, OUT-05, OUT-08; SCN-07 (human control).

## Capability unlocked

The owner can recruit a participant with ready, consistent materials, and a
consenting maintainer can move straight to a protocol-compliant G27 run and the
Part C continue/revise/stop decision.
