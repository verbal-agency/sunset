# G27 — Maintainer pilot and product decision

**Status:** proposed
**Dependencies:** G25 (complete), G26 (complete), and explicit pilot authorization

## Purpose

Test whether the validated workflow is useful and appropriately conservative in
real maintainer review, where operational evidence and missing context matter
most.

## Objective

Run a consented, read-only pilot against a small declared set of candidates from
the G26 coverage-qualified collector set, record review outcomes and failures,
and publish an evidence-bounded continue, revise, or stop decision.

## Project alignment

- Advances OUT-04, OUT-05, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03 and SCN-07 through SCN-12.
- Unlocks a product decision based on empirical results and maintainer feedback
  rather than architecture claims alone.

## Scope boundary

Use the G25 configuration and G26 collectors within existing read-only
investigation and human-gated validation boundaries. Define participant
consent, candidate count, data minimization/redaction, success and harm
measures, retention, and an incident stop rule before the first pilot run.
Publish aggregate and per-case evidence only with participant-approved
disclosure.

## Explicit exclusions

- Automatic cleanup, changing a target repository, broad telemetry collection,
  general-availability claims, or any use of pilot data beyond consent.
- Treating maintainer approval, a passing test, or a small pilot as proof that a
  protected condition is absent everywhere.

## Authority and stop condition

The goal requires explicit pilot authorization and maintainer participation.
Without those inputs, Cycle must stop as blocked. Any privacy incident,
unapproved side-effect request, or configured harm threshold stops new pilot
runs while preserving the evidence already authorized for retention.

## Outcomes and handoff

The final artifact reports the declared pilot protocol, configuration digest,
coverage, maintainer outcomes, failures, unresolved proof obligations, and a
bounded continue/revise/stop recommendation. It is not a cleanup authorization.

## Refinement trigger

After G26 completes and a pilot owner supplies authorization, replace this
outline with a Luna-ready execution contract containing the approved candidate
list, privacy rules, stop thresholds, fixtures/simulation tests, and binary
acceptance criteria.
