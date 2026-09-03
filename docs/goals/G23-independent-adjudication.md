# G23 — Single-reviewer adjudication and evidence quality

**Status:** complete
**Dependencies:** G22b (complete), an owner-supplied review protocol, and one
recorded human reviewer authority decision

## Purpose

Turn provenance-bound case packets into explicitly scoped, provisional
evaluation labels without allowing the system under test to create its own
ground truth. A second reviewer is a later strengthening step, not a
precondition for this goal.

## Objective

Record one owner-authorized human protected-condition and proof-obligation
assessment per eligible case, preserve abstention and unresolved obligations,
and freeze a single-reviewer provisional manifest for later offline evaluation.

## Project alignment

- Advances OUT-02, OUT-05, and OUT-08.
- Advances SCN-01 through SCN-03 and SCN-12.
- Unlocks a single-reviewer provisional development/holdout corpus for
  exploratory evaluation. It must not be described as independent ground
  truth until a later second-review pass.

## Scope boundary

Create reviewer packets and import/validation contracts that bind each decision
to G21/G22a/G22b/G22c evidence IDs, a protocol version, and a reviewer identity
pseudonym. Preserve the individual decision, abstention, unresolved proof
obligations, validation scope, and the fact that the manifest is
single-reviewer. Freeze the corpus digest and split before downstream goals
read it. A later reviewer may append a decision but may not rewrite this
record.

## Explicit exclusions

- Model-authored, majority-by-model, or historical-outcome-derived labels.
- Running baseline evaluations, optimization, live provider access, cleanup, or
  target-repository mutation.
- Claiming inter-reviewer agreement, general downstream safety, or universal
  removability.
- Removing abstaining or unresolved cases to increase apparent coverage.

## Authority and stop condition

The owner designates one human reviewer and supplies a protocol version and
reviewer-authority record. Luna may prepare packets, inspect implementations,
run bounded validation, and import/validate the supplied decision, but may not
choose the label, fabricate reviewer identity, or infer a second review. If the
protocol, authority record, or decision is unavailable, Cycle must mark the
goal blocked with the missing-input list.

## Resolved input gate

The owner supplied `sunset-g23-single-reviewer-v1`, designated
`owner-reviewer`, and approved a five-case review set with explicit
`not_adjudicated_in_this_pass` exclusions for the remaining corpus cases.

## Luna-ready execution contract

### Implementation surface

- `src/sunset/adjudication_models.py`: versioned authority, decision, and
  frozen-manifest contracts.
- `src/sunset/adjudication.py`: deterministic validation, evidence binding,
  coverage checks, and digest freezing.
- `src/sunset/cli.py`: `sunset adjudication freeze` entry point.
- `tests/fixtures/adjudication/`: authority, five decisions, and frozen
  manifest fixtures.
- `tests/test_adjudication.py`: focused acceptance and illegal-state tests.

The importer is offline and read-only. It accepts only the G21 corpus plus
recorded G22/G22a/G22b/G22c evidence fixtures; it never calls a model, network,
subprocess, or target repository.

For every eligible case, the reviewer supplies exactly one decision containing:

- `case_id`, `protocol_version`, pseudonymous `reviewer_id`, and the bound
  evidence IDs;
- a protected-condition hypothesis and status (`identified`, `active`,
  `likely_expired`, `unknown`, or `contradictory`);
- an evidence sufficiency decision and explicit proof obligations;
- the validation scope and any abstention or exclusion reason.

The importer rejects unknown case/evidence IDs, duplicate decisions, missing
proof obligations for non-terminal statuses, malformed enum values, and labels
derived from historical outcomes. It records `review_mode: single_reviewer`
and `second_review_status: not_available` in the frozen manifest.

## Acceptance criteria

1. The owner-supplied protocol and reviewer-authority record identify the single
   authorized human reviewer and the decision schema above.
2. Every imported decision is bound to the eligible case and immutable G21,
   G22a, G22b, or G22c evidence IDs; no model-authored or historical-outcome-derived
   label is accepted.
3. The validator preserves each condition status, abstention, contradiction,
   and exclusion with reasons and rejects malformed or duplicate records.
4. The frozen manifest includes its digest, corpus split identities, coverage
   limits, `single_reviewer` mode, unavailable second-review status, and each
   case's proof obligations.
5. Focused importer/fixture tests, the locked full suite, `uv lock --check`,
   documentation checks, and `git diff --check` pass.

## Outcomes and handoff

The goal succeeds with a frozen manifest that separates single-reviewer
condition-status decisions, abstentions, contradictions, and exclusions with
reasons. G23
receives the manifest digest, coverage limits, split identities, reviewer mode,
and per-case proof obligations; downstream goals must not silently upgrade its
labels to independent ground truth.

## Completion evidence

- Authority: `tests/fixtures/adjudication/g23-authority-v1.json`.
- Decisions and explicit exclusions: `tests/fixtures/adjudication/g23-decisions-v1.json`.
- Frozen manifest: `tests/fixtures/adjudication/g23-frozen-manifest-v1.json`.
- Focused verification: `tests/test_adjudication.py` (8 passed), including
  duplicate, unknown-evidence, cross-case, missing-obligation, historical-field,
  incomplete-coverage, contradiction, and exclusion checks.
- The manifest contains five owner-reviewed cases and fifteen explicit
  exclusions, with development/holdout split identities and
  `single_reviewer`/`not_available` metadata.

## Single-reviewer limitation

This goal deliberately does not measure agreement or claim independent ground
truth. A later goal may collect a second human review and append it as a new,
provenance-bound record. Until then, G24 must report all evaluation results as
conditioned on this single-reviewer provisional corpus.
