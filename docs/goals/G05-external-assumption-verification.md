# G05 — External assumption verification

**Status:** proposed
**Dependencies:** G04

## Purpose

Distinguish an old local workaround from one whose external justification has
actually expired, while preserving Sunset's conservative evidence boundary.

## Objective

Add replaceable GitHub and release-note evidence providers that resolve explicit
references carried by a G04 investigation. Persist recorded raw responses as
content-addressed artifacts, connect source-backed conclusions to the ledger,
and classify only the assumption status as `active`, `expired`, or `unknown`.

## Project alignment

- Advances OUT-02 and SCN-01 through SCN-03.
- Supplies external evidence to G04's compact ledger without weakening its
  provenance or checkpoint model.

## Architecture constraints to preserve

- Provider interfaces remain explicit and replaceable; default tests use
  recorded fixtures and make no live-network request.
- Raw provider replies are stored externally and referenced by artifact ID;
  compact ledger claims retain citations and uncertainty rather than response
  bodies.
- Missing, contradictory, unauthenticated, or failed lookups yield `unknown`.
- Assumption classification is not a removal recommendation; G06 owns isolated
  validation and G07 owns final case files.

## In scope

- Provider contracts for GitHub issues/pull requests and release notes.
- Recorded response fixtures for fixed, open, missing, contradictory, and
  provider-failure cases.
- Artifact-backed ledger integration and explicit assumption-status model.
- CLI configuration that keeps live-network access opt-in and visibly reports
  unavailable credentials or provider failures as uncertainty.

## Explicit exclusions

- Running tests, changing a target repository, creating worktrees, or opening
  pull requests.
- Treating an issue state or release note as proof that removal is safe.
- General web search, enterprise connectors, model-driven citation generation,
  historical benchmarking, or automatic cleanup proposals.

## Deliverables

1. Versioned provider and assumption-status contracts.
2. Recorded GitHub/release-note providers and artifact persistence.
3. G04 ledger integration with citations and uncertainty.
4. Deterministic fixture coverage and CLI documentation.

## Goal-level acceptance criteria

- **G05-AC01:** Recorded fixtures classify explicit fixed/open/missing/
  contradictory evidence deterministically as `expired`, `active`, or
  `unknown`, with raw artifact references.
- **G05-AC02:** Provider failures and unavailable live credentials produce an
  `unknown` ledger entry and do not discard existing local evidence.
- **G05-AC03:** Repeated recorded retrieval reuses immutable artifacts; changed
  provider input or repository state invalidates only the derived view.
- **G05-AC04:** No result recommends removal or invokes a sandbox.
- **G05-AC05:** README and CLI distinguish recorded default behavior from
  explicit live-network access and explain uncertainty.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G05-AC01 | Recorded provider fixture matrix and artifact-ID assertions |
| G05-AC02 | Failure/credential tests retaining G04 ledger state |
| G05-AC03 | Artifact reuse and derived-view invalidation tests |
| G05-AC04 | Negative tests for removal/sandbox actions |
| G05-AC05 | CLI JSON and documentation review |
