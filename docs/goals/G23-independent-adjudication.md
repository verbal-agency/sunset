# G23 — Independent adjudication and evidence quality

**Status:** blocked
**Dependencies:** G22b (complete) and recorded human review input

## Purpose

Turn provenance-bound case packets into defensible evaluation labels without
allowing the system under test to create its own ground truth.

> Planning boundary: this is intentionally an outline, not an executable goal.
> Cycle must replace it with a Luna-ready execution contract after G22b and
> the stated human-review input are available.

## Objective

Record two independent protected-condition and proof-obligation assessments per
eligible case, preserve disagreement and abstention, and freeze an adjudicated
evaluation manifest for later offline evaluation.

## Project alignment

- Advances OUT-02, OUT-05, and OUT-08.
- Advances SCN-01 through SCN-03 and SCN-12.
- Unlocks an independently adjudicated development/holdout corpus for G24.

## Scope boundary

Create reviewer packets and import/validation contracts that bind each decision
to G21 evidence IDs, a protocol version, reviewer identity pseudonym, and an
adjudication outcome. Preserve individual decisions, agreement/disagreement,
abstention, and unresolved proof obligations. Freeze the accepted corpus digest
and split before G24 reads it.

## Explicit exclusions

- Model-authored, majority-by-model, or historical-outcome-derived labels.
- Running baseline evaluations, optimization, live collection, cleanup, or
  target-repository mutation.
- Removing contradictory or abstaining reviews to increase apparent coverage.

## Authority and stop condition

This goal needs supplied, recorded decisions from two independent human
reviewers under an agreed review protocol. Luna may implement packet/import
mechanics and validate supplied records, but may not fabricate reviewers or
labels. If the decisions or review authority are unavailable, Cycle must mark
the goal blocked with the missing-input list.

## Outcomes and handoff

The goal succeeds only with a frozen manifest that separates adjudicated,
disagreed, abstained, and excluded cases with reasons. G23 receives the manifest
digest, coverage limits, split identities, and per-case proof obligations; it
must not change any of them.

## Refinement trigger

After G22b completes, incorporate its concrete evidence packet schema, audit output, and
the owner-supplied review protocol into a Luna-ready execution contract with
binary criteria and recorded-review fixtures.

## Blocker

Activation is blocked because the repository contains no owner-supplied review
protocol, reviewer-authority record, or two independent recorded decisions for
the eligible cases. It also awaits the declared-support evidence bundle from
G22b.
Unblock only when those inputs are provided as immutable,
reviewer-pseudonymized artifacts bound to G22a/G22b evidence IDs. Luna may then
refine this outline into the required execution contract; it must not create
stand-in labels or treat historical outcomes as adjudication.
