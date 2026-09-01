# G17 — Controlled context expansion

**Status:** proposed
**Dependencies:** G16 (proposed)

## Purpose

Prevent compact receipts from becoming a sensor bottleneck while preserving
the distinction between model reasoning and repository authority.

## Objective

Expose a bounded, relation-based context-expansion capability that returns
deterministic receipts for the missing repository relation a G16 claim or G15
hypothesis requires.

## Project alignment

- Advances OUT-02, OUT-03, OUT-06, and OUT-08.
- Advances SCN-04, SCN-05, SCN-08, and SCN-09.
- Unlocks G18 operational evidence by making local configuration and ownership
  references discoverable without arbitrary model access.

## Architecture constraints to preserve

- Expansion is allowlisted, read-only, repository-state-bound, and receipt-only.
- Models request a named relation and budget; deterministic infrastructure
  resolves it and may return unknown or scope-limited evidence.
- No arbitrary paths, shell commands, network requests, credentials, target
  imports, execution, mutation, or cleanup authority.
- Existing G10–G16 contracts remain compatible; raw source remains outside
  persisted checkpoints.

## Execution contract

Expected implementation surface: `src/sunset/context_expansion_models.py`,
`src/sunset/context_expansion.py`, `tests/test_context_expansion.py`,
fixtures under `tests/fixtures/context_expansion/`, and documentation updates
to `docs/AGENT-TOOLS.md` and `docs/PROJECT.md`. Equivalent modules are allowed
only if the same public contracts and test surface remain.

Define versioned contracts for `RelationKind`, `ContextExpansionRequest`,
`ContextExpansionReceipt`, and `ContextExpansionObservation`. A request must
contain candidate or symbol identity, one relation kind, repository HEAD, and
per-call/cumulative budgets. A receipt must contain invocation identity,
relation, result artifact IDs or structured references, truncation, scope,
errors, and remaining budget; it must not contain raw source in checkpoint data.

### Relation catalog

The initial allowlist is exactly: `ast_parent`, `callers`, `callees`,
`same_commit_changes`, `historical_variant`, and `configuration_reference`.
Unknown relations, arbitrary path selectors, and cross-repository references
are rejected before repository access.

### Deterministic behavior matrix

| Input condition | Required result |
| --- | --- |
| Allowlisted relation and valid bound identity | Read-only receipt with structured result and provenance. |
| Relation cannot be resolved at the bound HEAD | `unknown` result with a proof obligation; no fabricated relation. |
| Invalid relation, path, identity, or grant | Rejected structured error with no bytes disclosed. |
| Per-call or cumulative budget exhausted | `budget_exhausted`; no additional read. |
| Duplicate compatible request | Reused receipt with no repeated read. |
| HEAD, policy, schema, or grant changed | Checkpoint/cache invalidation; incompatible reuse rejected. |

### Stop and side-effect conditions

Stop after one relation result, budget exhaustion, invalid input, repository
identity/HEAD mismatch, or a deterministic read error. Do not loop, retry, open
network connections, import target code, execute commands, or mutate the target.

## In scope

1. The six relation kinds and their typed request/receipt contracts.
2. Read-only adapters over existing Git/AST/configuration infrastructure.
3. Per-call and aggregate byte/tool budgets, duplicate suppression, and
   checkpoint/cache identity.
4. Recorded fixtures for resolved, missing, contradictory, malformed, and
   budget-exhausted relations.
5. Documentation of relation scope and transient versus persisted content.

## Explicit exclusions

- Operational or enterprise providers, arbitrary filesystem access, network
  browsing, validation execution, model changes, reviewer agents, cleanup,
  edits, pull requests, and new candidate families.

## Deliverables

1. Versioned relation contracts and deterministic expansion adapters.
2. Fixture corpus and focused safety/replay tests.
3. Updated tool and project documentation.

## Goal-level acceptance criteria

- **G17-AC01 — Allowlisted relations:** Exactly the six catalogued relations
  are accepted; unknown relations and arbitrary selectors are rejected.
- **G17-AC02 — Scoped receipts:** Successful results retain HEAD, relation,
  provenance, scope, truncation, and artifact references without raw checkpoint
  content.
- **G17-AC03 — Bounded behavior:** Byte, call, and wall-time policies produce
  deterministic success, unknown, error, or budget-exhausted outcomes.
- **G17-AC04 — Replay safety:** Compatible duplicate requests reuse receipts;
  changed HEAD, policy, grant, or schema invalidates incompatible state.
- **G17-AC05 — Authority safety:** No network, target import/execution, target
  mutation, arbitrary shell, or unapproved repository access occurs.
- **G17-AC06 — Verification:** Focused tests, locked full suite, and
  documentation/diff checks pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G17-AC01 | Relation catalog and adversarial selector tests |
| G17-AC02 | Receipt/checkpoint raw-content and provenance tests |
| G17-AC03 | Budget, missing-relation, and structured-error matrix |
| G17-AC04 | Duplicate/replay and invalidation tests |
| G17-AC05 | Socket/import/process/target-state guards |
| G17-AC06 | Focused suite, locked full suite, docs review, and diff check |

Focused tests should be named `test_g17_ac01_allowlisted_relations` through
`test_g17_ac06_verification` (or recorded equivalent names).

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_context_expansion.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- Compact receipts must remain immediate-only even when relation expansion
  reads sensitive source; G16 graph edges receive IDs and scope, not raw text.
- A missing relation is useful evidence of an open proof obligation, not a
  license to widen the allowlist during implementation.
