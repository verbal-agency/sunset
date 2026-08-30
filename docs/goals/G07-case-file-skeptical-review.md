# G07 — Case file and skeptical review

**Status:** complete
**Dependencies:** G06

## Purpose

Make Sunset’s evidence and limitations usable to a maintainer without asking
them to trust an agent narrative, a passing test, or an uncited conclusion.

## Objective

Produce versioned JSON and Markdown case files from an investigation and an
optional approved validation result. Finalize every report claim by reloading
its cited raw artifact from the content-addressed store, and run a separate,
deterministic skeptical review before selecting a conservative recommendation.

## Project alignment

- Advances OUT-02 and SCN-01 through SCN-03.
- Consumes G04/G05 rationale and external-assumption evidence plus G06
  validation, without rerunning tests, contacting providers, or mutating the
  analyzed repository.

## Architecture constraints to preserve

- A material case-file claim requires one or more resolvable content-addressed
  artifact IDs; uncited or missing-artifact claims are rejected, not rendered.
- The finalizer reads raw artifacts directly and relies on the artifact store’s
  digest verification rather than trusting an earlier summary.
- Skeptical review is a separate stage that records contradictions, unresolved
  assumption status, incomplete/failed validation, and residual risks.
- `confirmed` clone validation is empirical evidence only. It cannot by itself
  become a safety claim or an automatic cleanup action.
- Reports are read-only derived output; no provider request, target mutation,
  sandbox creation, commit, or pull request is part of this goal.

## In scope

- Versioned case-file, citation, claim, review-finding, and recommendation
  contracts.
- Artifact-ID resolver with integrity recheck and unsupported-claim rejection.
- Deterministic skeptical review and conservative recommendation policy.
- JSON and Markdown rendering plus a `sunset casefile` CLI that consumes saved
  investigation/validation JSON and the external artifact store.
- Fixture coverage for supported, retained, contradictory, unavailable, and
  deliberately uncited evidence.

## Explicit exclusions

- Model-generated narratives, web lookup, rerunning investigation/validation,
  or scoring benchmark quality.
- Editing a target repository, applying a cleanup, creating a worktree, or
  opening a pull request.
- Claiming a test pass proves deletion safe, or relying on a citation URL in
  place of a verified stored artifact.

## Deliverables

1. Case-file domain contract and citation finalizer.
2. Skeptical-review policy and conservative recommendation selection.
3. JSON/Markdown case-file CLI and documentation.
4. Deterministic adversarial fixture tests.

## Goal-level acceptance criteria

- **G07-AC01:** Every rendered material claim has at least one cited artifact
  ID that the finalizer reloads and digest-verifies; a missing or deliberately
  uncited claim is rejected with a structured error.
- **G07-AC02:** The skeptical review records evidence-backed contradiction or
  disconfirming findings and blocks cleanup eligibility when assumption status
  is active/unknown, validation is not `confirmed`, or evidence conflicts.
- **G07-AC03:** JSON and Markdown case files contain rationale, assumption
  status, validation result, recommendation, confidence boundary, residual
  risks, and citations; they never equate passing tests with proof of safety.
- **G07-AC04:** Conservative policy returns only `eligible_for_human_cleanup`,
  `retain`, or `inconclusive`; it never applies a change and emits no
  recommendation when citation finalization fails.
- **G07-AC05:** CLI consumes saved result JSON without network or target
  mutation, and README documents report limits and citation resolution.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G07-AC01 | Artifact-integrity and deliberately uncited/missing-artifact tests |
| G07-AC02 | Active, unknown, contradictory, failed-validation, and supported fixture matrix |
| G07-AC03 | JSON/Markdown snapshot assertions with citation IDs and safety wording |
| G07-AC04 | Recommendation-policy and no-mutation tests |
| G07-AC05 | CLI saved-result JSON test, socket guard, target snapshot, and README review |

## Completion evidence

- `uv lock --check` passed.
- `uv run --locked pytest -q` passed: 61 tests, including the G07 supported,
  retained, unknown, contradictory, failed-validation, uncited, missing, and
  tampered-artifact cases.
- The `casefile` CLI test loads only saved JSON plus the artifact store under a
  socket guard; its implementation has no repository, provider, validation, or
  sandbox call path.
- `git diff --check` passed before completion. The case file can only render
  after each material claim's `sha256:` artifact ID is reloaded and its raw
  bytes pass the store's digest verification.
