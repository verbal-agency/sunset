# G16 — Claim–evidence graph and conservative inference

**Status:** complete
**Dependencies:** G15 (complete)

## Purpose

Make the relationship between a condition claim and its evidence auditable. A
citation or model confidence may be relevant, but it must not silently become a
condition-status conclusion when its scope does not establish that claim.

## Objective

Build a framework-independent claim–evidence–contradiction graph that consumes
G15 normalized records, preserves disagreement, and derives conservative
condition states with explicit proof obligations.

## Project alignment

- Advances OUT-02, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-08, and SCN-09.
- Unlocks G17 relation-based context expansion and G18 operational evidence
  without changing evidence semantics.

## Architecture constraints to preserve

- Evidence roles, source classes, scope, freshness, and provenance remain
  explicit; source ranking must not suppress contradictory evidence.
- A claim is established only when its declared scope and evidence rule hold.
  Upstream status cannot establish local deployment or customer compatibility.
- Inference is deterministic and non-authoritative. `insufficient_evidence`,
  `contradictory_evidence`, and `unvalidatable` remain successful outcomes.
- Existing G15 contracts and G10–G14 receipt schemas remain compatible.

## Execution contract

When activated, implement the graph in framework-independent modules following
the existing frozen-dataclass and normalized JSON conventions. The expected
surface is `src/sunset/claim_evidence_models.py`,
`src/sunset/claim_evidence_graph.py`, `tests/test_claim_evidence_graph.py`,
isolated fixtures under `tests/fixtures/claim_evidence/`, and vocabulary
updates in `docs/PROJECT.md`. Equivalent module names are allowed only when the
same contracts and test surface are preserved. The implementation must not add
providers, arbitrary context access, validation execution, model calls,
reviewer agents, or cleanup authority.

The graph must represent:

- a claim ID, candidate/hypothesis reference, statement, required scope, and
  status;
- evidence edges with role, source class, artifact/provenance IDs, scope, and
  freshness;
- contradiction edges that remain visible even when one source is ranked higher;
- proof obligations for missing or scope-insufficient evidence; and
- a non-authoritative conclusion derived only from declared deterministic rules.

### Canonical contracts and invariants

Define versioned, round-trippable contracts for `Claim`, `EvidenceEdge`,
`Contradiction`, `GraphProofObligation`, and `GraphResult`. Each claim and edge
must identify one candidate and, when applicable, one G15 hypothesis. Evidence
edges retain role, source class, artifact/provenance IDs, scope, and freshness;
contradictions retain both edge IDs. Graph results retain all hypotheses,
unknowns, contradictions, proof obligations, and a non-authority flag.

### Deterministic behavior matrix

| Input condition | Required result |
| --- | --- |
| `establish` edge with matching required scope and fresh provenance | Claim is `established` and retains the edge. |
| `support` edge without establishment scope | Claim is `supported` but remains unestablished. |
| Scope mismatch or stale edge | Claim remains `unknown`; add a scope/freshness proof obligation. |
| Support/establishment and contradiction for one claim | Preserve both edges and return `contradictory_evidence`. |
| No decisive edge | Return `insufficient_evidence` with the missing proof obligation. |
| Unknown claim/edge reference or malformed input | Reject the graph without dropping previously valid records. |

### Authority and stop conditions

Graph construction consumes supplied G15 records only. It opens no socket,
imports no target module, invokes no provider/model/validator, and performs no
repository mutation. Processing stops after all inputs are normalized, on a
schema/reference failure, or when a contradiction or missing proof obligation
prevents a deterministic conclusion; the partial graph is retained.

## In scope

1. Claim, evidence-edge, contradiction, proof-obligation, and graph-result
   contracts with schema versions and round-trip serialization.
2. Receipt-to-graph adapters for G15 normalized evidence.
3. Deterministic support, establishment, contradiction, scope, and freshness
   rules, including incompatible-evidence handling.
4. Fixtures for upstream EOL versus local support, active conditions,
   contradictory sources, missing, malformed, partial-failure,
   budget-exhausted, unsupported, and validation-scope cases.
5. Documentation of graph semantics and proof-obligation vocabulary.

## Explicit exclusions

- New evidence providers, relation-based context expansion, arbitrary file or
  system access, validation changes, reviewer agents, case-file rendering,
  recommendations, edits, pull requests, and release claims.
- Probabilistic ranking or a universal truth score that hides disagreement.

## Deliverables

1. Versioned graph domain contracts and deterministic inference rules.
2. Receipt adapters, fixture corpus, and focused tests.
3. Updated project and roadmap documentation with graph semantics.

## Goal-level acceptance criteria

- **G16-AC01 — Graph integrity:** Claims, evidence edges, contradictions, and
  proof obligations serialize deterministically and reject unknown references.
- **G16-AC02 — Scope-aware establishment:** Evidence establishes a claim only
  when source class, declared scope, freshness, and role satisfy the rule;
  otherwise the graph records a scope limit or unknown.
- **G16-AC03 — Contradiction preservation:** Incompatible support or
  establishment evidence yields `contradictory_evidence` or an explicit
  unresolved state without deleting, averaging, or hiding either source.
- **G16-AC04 — Conservative inference:** Derived states retain hypotheses and
  proof obligations; model confidence, citation presence, and passing tests do
  not create a removal-authority state.
- **G16-AC05 — Compatibility and safety:** G15 records and G10–G14 receipts
  adapt without raw-content leakage, network access, target execution, or
  provider/model/validator invocation.
- **G16-AC06 — Verification:** Focused graph tests, the locked full suite, and
  documentation/diff checks pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G16-AC01 | Graph serialization and reference-integrity tests |
| G16-AC02 | Scope/freshness matrix for upstream, local, and validation evidence |
| G16-AC03 | Contradiction fixtures with both edges retained |
| G16-AC04 | Conservative state and proof-obligation assertions |
| G16-AC05 | Receipt compatibility, raw-content, socket, and execution guards |
| G16-AC06 | Focused tests, locked full suite, documentation review, and diff check |

## Completion evidence

- `uv lock --check` completed successfully.
- `uv run --locked pytest -q` completed successfully (full suite green).
- `uv run --locked pytest -q tests/test_claim_evidence_graph.py` completed
  successfully: 6 tests passed.
- `git diff --check` completed successfully; the worktree was inspected with
  `git status --short`, including untracked graph modules and fixtures.
- `docs/PROJECT.md` documents claim–evidence graph semantics, including scope,
  freshness, contradiction preservation, proof obligations, and the
  non-authority boundary.

G17 remains proposed and is not started by this cycle.

The focused module must use named tests `test_g16_ac01_graph_integrity`,
`test_g16_ac02_scope_aware_establishment`, `test_g16_ac03_preserves_contradictions`,
`test_g16_ac04_conservative_inference`, `test_g16_ac05_receipt_and_authority_guards`,
and `test_g16_ac06_documented_verification` (or recorded equivalent names).

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_claim_evidence_graph.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G15 intentionally uses a bounded ontology; G16 must not expand candidate
  families while adding graph semantics.
- Operational/customer evidence remains a G18 concern; G16 must represent its
  absence as a proof obligation rather than inventing a provider.
