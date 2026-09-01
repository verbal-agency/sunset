# G19 — Skeptical review and temporal-debt case files

**Status:** complete
**Dependencies:** G18 (proposed)

## Purpose

Challenge a condition graph before a maintainer reviews a counterfactual change.
The case file must show what is known, what conflicts, and what remains
unproven rather than turn an agent narrative into authority.

## Objective

Add an independent, bounded review stage and citation-verified Markdown/JSON
case-file finalizer over G16–G18 claims, edges, and proof obligations.

## Project alignment

- Advances OUT-02, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-07 through SCN-09, and SCN-11.
- Unlocks G20 calibration of proof-obligation quality and unsupported-claim
  rates.

## Architecture constraints to preserve

- Review challenges claims and missing proof; it cannot approve, edit, delete,
  execute, open a pull request, or suppress contradictory evidence.
- Finalization reloads referenced raw artifacts and verifies that each material
  claim is supported, contradicted, scope-limited, or explicitly unknown.
- Citation presence is not citation support, and citation support is not proof
  of removability. Passing validation remains `validated_in_scope`.
- Reviewer/model adapters are replaceable, bounded, and non-authoritative;
  recorded replay is the default.

## Execution contract

Expected implementation surface: `src/sunset/review_models.py`,
`src/sunset/casefile_finalizer.py`, `tests/test_skeptical_review_casefiles.py`,
fixtures under `tests/fixtures/casefiles/`, and documentation in
`docs/PROJECT.md`, `docs/SAFETY.md`, and `docs/ROADMAP.md`. Equivalent modules
are allowed only when the same public contracts and test surface remain.

Define versioned contracts for `ReviewRequest`, `ReviewFinding`,
`ClaimVerification`, `CaseFile`, and `CaseFileError`. A case file must retain
candidate/hypothesis IDs, evidence and contradiction IDs, proof obligations,
review findings, scope/freshness, terminal condition state, and an explicit
non-authority marker. Raw artifact bodies remain in the artifact store.

### Deterministic behavior matrix

| Input condition | Required result |
| --- | --- |
| Claim has verified supporting evidence within scope | Include claim as supported with citations. |
| Citation exists but scope or claim support fails | Emit scope-limited/unknown finding; do not finalize as established. |
| Contradictory edges exist | Include both edges and mark the claim contradictory or unresolved. |
| Proof obligation is missing | Include it verbatim as an open obligation; no removal recommendation. |
| Referenced artifact is missing or tampered | Reject finalization with structured case-file error. |
| Reviewer/model response is malformed or budgeted out | Preserve prior graph and emit an inconclusive review result. |

### Authority and stop conditions

Stop on completed review, unresolved contradiction, missing/tampered artifact,
budget exhaustion, malformed review output, or explicit interruption. No review
path may mutate the target repository, execute validation, call external
providers outside the configured adapter, or create approval authority.

### Replay, cache, and budget rules

Review identity includes graph version, evidence IDs/digests, reviewer/prompt
version, policy, and budget ledger. Equivalent recorded review inputs reuse the
same findings; changed graph, evidence, policy, or prompt invalidates reuse.
Reviewer calls and artifact reads are bounded, duplicate-safe, and checkpointed
without raw payloads.

## In scope

1. Bounded challenge rules over G16 graph data and G18 evidence.
2. Claim/evidence verification against content-addressed artifacts.
3. Versioned Markdown/JSON case-file contracts and deterministic finalization.
4. Recorded fixtures for supported, unsupported, contradictory, missing,
   malformed, partial-failure, budget-exhausted, and tampered evidence.
5. Review trace and proof-obligation documentation.

## Explicit exclusions

- New evidence-source classes, broad browsing, automatic cleanup, edits,
  approvals, pull requests, validation changes, or release calibration.

## Deliverables

1. Review and case-file contracts with deterministic validators.
2. Recorded review fixtures and focused safety tests.
3. Citation/proof-obligation documentation.

## Goal-level acceptance criteria

- **G19-AC01 — Independent challenge:** Review findings can add support,
  contradiction, scope limits, and missing obligations without mutating the
  graph or granting approval authority.
- **G19-AC02 — Claim verification:** Every material final claim resolves to
  an artifact-backed edge whose role and scope support the rendered wording.
- **G19-AC03 — Contradiction visibility:** Contradictory evidence remains
  visible and prevents an established or removal-authority conclusion.
- **G19-AC04 — Case-file integrity:** Markdown and JSON outputs round-trip,
  preserve IDs/scope/freshness/proof obligations, and contain no raw payloads.
- **G19-AC05 — Failure containment:** Missing/tampered artifacts, malformed
  review output, interruption, and budget exhaustion produce structured
  inconclusive results while preserving prior evidence.
- **G19-AC06 — Verification:** Focused tests, locked full suite, and
  documentation/diff checks pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G19-AC01 | Bounded challenge and no-authority tests |
| G19-AC02 | Claim/citation verification matrix |
| G19-AC03 | Contradictory graph fixtures and rendered findings |
| G19-AC04 | Markdown/JSON round-trip and raw-content scans |
| G19-AC05 | Tamper, malformed, interruption, and budget fixtures |
| G19-AC06 | Focused suite, locked full suite, docs review, and diff check |

## Completion evidence

- `uv lock --check` completed successfully.
- `uv run --locked pytest -q tests/test_skeptical_review_casefiles.py` completed
  successfully: 6 tests passed.
- `uv run --locked pytest -q` completed successfully (full suite green).
- `git diff --check` completed successfully; tracked and untracked files were
  inspected with `git status --short`.
- `docs/PROJECT.md` and `docs/SAFETY.md` document independent skeptical review,
  artifact digest verification, contradiction visibility, and non-authority.

G20 remains proposed and is not started by this cycle.

Focused tests should be named `test_g19_ac01_independent_challenge` through
`test_g19_ac06_verification` (or recorded equivalent names).

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_skeptical_review_casefiles.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- Finalization must distinguish citation existence, citation support, and
  condition establishment; G20 should measure failures in each category.
- Review quality is not proof of production removability and must remain
  separate from G14 approval and validation authority.
