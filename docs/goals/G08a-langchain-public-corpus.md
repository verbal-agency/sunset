# G08a — Public LangChain historical corpus

**Status:** active
**Dependencies:** G08

## Purpose

Replace Sunset's self-authored benchmark fixture with public, reproducible
evidence from the ecosystem whose developer workflow Sunset aims to understand.

## Objective

Collect and version a minimum 20-case corpus from public `langchain-ai`
repositories: 12 cases from `langchain`, four from `langgraph`, and four from
`langsmith-sdk`. Every record must pin a repository URL, immutable commit SHA,
path, case type, and observed historical outcome. Collection is read-only.

## Project alignment

- Strengthens OUT-03, OUT-05, and SCN-06 with independently inspectable source
  history.
- Provides the evidence base required before G09 can make a credible public
  demonstration claim.

## Architecture constraints to preserve

- Public Git history is an input, not authority: a removal commit establishes a
  historical outcome, not that all similar markers are removable.
- Every corpus record retains exact source provenance and a collection timestamp;
  summaries never substitute for the pinned commit.
- The collector never checks out, imports, installs, or runs target code. It
  does not open issues, write to GitHub, or upload to LangSmith.
- Retained cases must identify a currently present marker or compatibility shim
  at a pinned HEAD; they are not inferred merely because an old addition commit
  exists.

## In scope

- Read-only public Git collection and a versioned corpus manifest.
- Removal and retained-marker cases with exact paths and commit identifiers.
- Per-case raw patch/source references suitable for later artifact ingestion.
- Corpus validation for count, repository allocation, source immutability, and
  required outcome categories.

## Explicit exclusions

- Executing any collected repository's test suite or installing its dependencies.
- Claiming semantic correctness, test-pass status, or production precision.
- Publishing to LangSmith, creating GitHub issues/PRs, or changing any target.

## Goal-level acceptance criteria

- **G08a-AC01:** The committed manifest has at least 20 unique records: 12
  `langchain`, four `langgraph`, and four `langsmith-sdk`; every record has URL,
  full SHA, path, source commit, and collection mode `public_git_read_only`.
- **G08a-AC02:** At least eight records are historical marker/shim removals and
  at least eight are retained current markers or shims. Each record identifies which
  evidence establishes its observed outcome.
- **G08a-AC03:** A deterministic validator rejects duplicate IDs, abbreviated
  SHAs, missing paths, unpinned repository URLs, or an invalid distribution.
- **G08a-AC04:** Collection tests use recorded Git metadata only, never execute
  target code or make a default network request; README explains the corpus’s
  historical—not predictive—meaning.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G08a-AC01 | Manifest schema/count/distribution test |
| G08a-AC02 | Removal and retained evidence-reference assertions |
| G08a-AC03 | Adversarial malformed-manifest tests |
| G08a-AC04 | Socket/subprocess guard and documentation review |
