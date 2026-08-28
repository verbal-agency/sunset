# G02 — Provenance and content-addressed artifacts

**Status:** complete
**Dependencies:** G01

## Purpose

Make later reasoning auditable and reusable by preserving exact repository
evidence outside model context, with explicit provenance and cache-validity
metadata.

## Objective

Extend each G01 candidate with a deterministic, read-only provenance collection
that identifies when and how its marker entered the repository, stores raw Git
evidence by content hash, and reuses immutable artifacts while invalidating only
repository-state-dependent views.

## Project alignment

- Advances **OUT-02 — Auditable rationale** by making raw evidence addressable.
- Establishes the storage and invalidation boundary required by OUT-03.
- Implements the repository half of **SCN-05 — Cache validity**.
- Prepares G03 without performing rationale inference or spending model tokens.

## Architecture constraints to preserve

- G01 candidate IDs and schema-v1 scan output remain backward compatible.
- Collection is deterministic, read-only with respect to the target repository,
  and uses no model or network access.
- Raw artifact identity is derived from exact bytes, never a mutable path or
  model-generated label.
- Immutable artifacts and mutable repository views have distinct identities.
- Git access and artifact persistence sit behind replaceable provider protocols.
- Missing or ambiguous history is explicit evidence, not a guessed narrative.

## In scope

- A versioned provenance manifest keyed by candidate ID and repository HEAD.
- Deterministic repository identity with an explicit local fallback when no
  canonical remote can be established without network access.
- Focused Git evidence for each candidate:
  - marker source at the scanned HEAD;
  - the blame commit already identified by G01;
  - the best-supported introduction commit;
  - rename-aware file history where Git can resolve it;
  - bounded commit metadata and patches relevant to the marker.
- A content-addressed artifact model using SHA-256 over exact stored bytes.
- A local filesystem artifact-store adapter with atomic writes, integrity
  verification, deduplication, and deterministic manifest serialization.
- Separate cache keys for immutable raw artifacts and HEAD-dependent provenance
  views.
- Reuse of existing immutable artifacts across repeated collections.
- Selective invalidation when repository HEAD changes.
- Structured errors for shallow, missing, ambiguous, or malformed Git history.
- A CLI surface for collecting provenance into an explicitly selected store.
- Fixture repositories covering multi-commit history and a file rename.
- Unit and integration tests plus documentation of the artifact boundary.

## Explicit exclusions

- LangChain, LangGraph, LangSmith, LLM, embedding, or summarization work.
- GitHub, issue, pull-request, release-note, Slack, Jira, or other network
  evidence providers.
- Claims about why a marker exists or whether its rationale has expired.
- Natural-language memory, investigation ledgers, checkpoints, or token budgets.
- Test execution, marker removal, worktrees, containers, or cleanup proposals.
- Garbage collection or eviction of stored artifacts.
- Cross-repository provenance.

## Proposed contracts

### Raw artifact

An immutable record containing artifact ID, SHA-256 digest, media type, byte
length, source kind, and exact bytes. Its identity must not include retrieval
time, filesystem location, or the current repository HEAD.

### Provenance manifest

A deterministic, versioned record containing candidate ID, repository identity,
scanned HEAD, artifact references, derivation metadata, and structured
uncertainties. Every artifact reference must resolve and pass digest
verification.

### Repository view

A derived mapping from candidate and repository state to a provenance manifest.
It may be invalidated when HEAD changes; the immutable artifacts it references
must remain reusable.

## Deliverables

1. Versioned artifact, manifest, repository-identity, and error domain models.
2. Replaceable Git-provenance and artifact-store protocols.
3. Focused, rename-aware Git history collector.
4. Local content-addressed filesystem store.
5. Provenance collection CLI and deterministic JSON output.
6. Multi-commit and rename fixture repositories.
7. Automated cache, integrity, invalidation, and side-effect tests.
8. README documentation for storage layout, trust boundaries, and limitations.

## Goal-level acceptance criteria

- **G02-AC01 — Focused provenance:** For each supported fixture candidate, the
  manifest identifies the scanned HEAD, blame commit, and best-supported
  introduction commit, with raw source and focused history artifacts.
- **G02-AC02 — Rename-aware history:** A marker that predates a file rename
  retains traceable provenance when Git can follow the rename; ambiguity is
  reported explicitly when it cannot.
- **G02-AC03 — Content integrity:** Every artifact ID is derived from its exact
  bytes, every manifest reference resolves, and deliberate corruption produces
  a supported integrity error.
- **G02-AC04 — Immutable reuse:** Repeating collection for the same candidate
  and HEAD performs no duplicate artifact write and returns byte-identical
  normalized manifests.
- **G02-AC05 — Selective invalidation:** After an unrelated HEAD change, the
  repository view is recomputed while unchanged raw artifacts are reused; no
  valid immutable artifact is rewritten or discarded.
- **G02-AC06 — Provider and safety boundary:** Tests use the provider protocols
  to demonstrate zero network/model calls and no mutation of the target
  repository.
- **G02-AC07 — Graceful incomplete history:** Shallow or otherwise incomplete
  history yields structured uncertainty/errors while retaining all evidence
  that was successfully collected.
- **G02-AC08 — Documented operation:** Setup, CLI use, store selection, schema
  versions, cache semantics, and current exclusions are documented accurately.

## Required verification evidence

| Criterion | Evidence |
| --- | --- |
| G02-AC01 | Multi-commit fixture assertions for source, HEAD, blame, introduction, and focused-history artifacts |
| G02-AC02 | Rename fixture integration test and explicit ambiguity fixture |
| G02-AC03 | Digest/reference validation tests and corruption test |
| G02-AC04 | Repeated-collection byte comparison plus store write-count assertion |
| G02-AC05 | Changed-HEAD test comparing recomputed views and reused artifact IDs |
| G02-AC06 | Before/after Git status and content hashes; blocked network socket; dependency audit |
| G02-AC07 | Shallow-history fixture retaining partial evidence with structured diagnostics |
| G02-AC08 | README review against implemented CLI, schemas, and storage behavior |

Expected commands after implementation:

```bash
uv sync --all-groups
uv run pytest
uv run sunset provenance /path/to/repository --store /path/to/store --format json
```

## Completion and handoff

When all criteria pass:

1. Record criterion-level evidence in the cycle handoff.
2. Change G02 to `complete` in `docs/ROADMAP.md`.
3. Confirm G03's collector scope and route only relevant provenance findings to
   its deterministic detection work.
4. Keep G03 `proposed`; do not begin it without user authorization.
5. End the cycle report with a suggested commit message based only on G02 work.

## Completion evidence

Completed on 2026-08-28.

| Criterion | Result |
| --- | --- |
| G02-AC01 | `test_collects_rename_aware_provenance` verifies HEAD, blame, the best-supported introduction commit, source, focused-history, and patch artifacts. |
| G02-AC02 | The rename fixture starts as `test_legacy.py`, moves to `test_markers.py`, and verifies that the stored `--follow` history retains the old path. |
| G02-AC03 | `test_artifact_integrity_failure_is_detected` corrupts a stored artifact, verifies its SHA-256 failure, and receives a structured `artifact_integrity_error` on recollection. |
| G02-AC04 | `test_repeated_collection_reuses_artifacts_and_view` verifies byte-identical JSON with unchanged artifact and view write counts. |
| G02-AC05 | `test_changed_head_recomputes_view_and_reuses_immutable_artifacts` commits unrelated documentation, verifies a new view and unchanged raw-artifact writes. |
| G02-AC06 | The side-effect test blocks sockets and compares target Git status plus content hashes; the CLI and direct API reject a store inside the analyzed repository. |
| G02-AC07 | `test_shallow_history_retains_source_evidence_with_uncertainty` uses a depth-one local clone and preserves source evidence while reporting `shallow_history`. |
| G02-AC08 | README documents the CLI, external store, schemas, reuse, invalidation, identity, shallow-history behavior, and non-recommendation boundary; CLI integration tests pass. |

The next goal is [G03 — Broader deterministic collectors](G03-broader-deterministic-collectors.md),
which remains proposed and has not been started.
