# G18 — Operational and internal evidence providers

**Status:** complete
**Dependencies:** G17 (proposed)

## Purpose

Determine whether a protected condition still exists in the environments that
matter. Upstream release status alone cannot establish deployment, customer,
support-policy, contract, or runtime reality.

## Objective

Add recorded-first, replaceable operational evidence providers with explicit
scope, freshness, privacy, and access-policy contracts that feed G16 graphs.

## Project alignment

- Advances OUT-02, OUT-05, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-08, and SCN-09.
- Unlocks G19 case files with evidence about local and customer-facing
  conditions rather than only upstream facts.

## Architecture constraints to preserve

- Provider inputs are candidate-linked and explicitly configured; no broad
  enterprise crawling or ambient credential discovery is permitted.
- Recorded fixtures are the default. Live reads require explicit provider,
  host, credential identity, request, byte, and freshness policy.
- Raw operational payloads remain content-addressed and outside prompts and
  checkpoints. Claims retain source scope, freshness, provenance, and
  disagreement.
- Provider failures, unavailable telemetry, stale inventory, and privacy
  redactions become unknowns or proof obligations, never expiry conclusions.

## Execution contract

Expected implementation surface: `src/sunset/operational_evidence_models.py`,
`src/sunset/operational_evidence.py`, `tests/test_operational_evidence.py`,
fixtures under `tests/fixtures/operational_evidence/`, and documentation in
`docs/PROJECT.md` and `docs/SAFETY.md`. Equivalent modules are allowed only if
the contracts and test surface remain unchanged.

Define versioned contracts for `OperationalSource`, `OperationalQuery`,
`OperationalEvidenceReceipt`, `PrivacyPolicy`, and `FreshnessMetadata`.
Receipts must include candidate/claim scope, source identity, recorded/live
mode, artifact IDs, freshness, redaction summary, effect metadata, errors, and
budget usage. Credentials and raw payloads must never be serialized into model
state.

### Provider catalog and behavior matrix

The initial source classes are exactly `support_policy`, `deployment_inventory`,
`configuration`, `contract`, and `runtime_telemetry`.

| Input condition | Required result |
| --- | --- |
| Recorded provider hit within freshness and scope | Evidence receipt with source/provenance metadata. |
| Recorded source missing or stale | `unknown` plus a concrete proof obligation. |
| Evidence conflicts with external or another internal source | Preserve both and return contradiction/unknown; never rank one away. |
| Privacy policy redacts decisive fields | Scope-limited evidence plus missing proof obligation. |
| Live mode disabled, credential absent, or host not allowlisted | Structured failure; no network request. |
| Live request explicitly allowed and within budget | Bounded artifact-backed receipt with live effect metadata. |

### Stop and side-effect conditions

Stop after one configured provider response, privacy rejection, freshness
failure, budget exhaustion, or structured provider error. Do not retry outside
policy, discover credentials from environment state, write to a source system,
or turn a provider status into a safe-removal recommendation.

### Replay, cache, and budget rules

Invocation identity includes provider, candidate/claim, query, repository state,
privacy policy, freshness key, mode, and budget ledger. An equivalent recorded
request reuses its receipt without a second read; changed identity or policy
invalidates reuse. Request and byte budgets are debited before live access and
exhaustion returns a structured terminal result.

## In scope

1. The five provider contracts and recorded fixture adapters.
2. Explicit opt-in live reads through replaceable provider boundaries.
3. Privacy/redaction, scope/freshness, contradiction, and budget semantics;
   fixtures cover positive, negative, stale, contradictory, malformed,
   partial-failure, budget-exhausted, and unsupported cases.
4. G16 graph adapters and proof-obligation generation.
5. Documentation of data handling and operational evidence limits.

## Explicit exclusions

- General enterprise search/crawling, unconfigured systems, external writes,
  automatic cleanup, validation changes, reviewer agents, new candidate
  collectors, and ambient credentials.

## Deliverables

1. Versioned provider/query/receipt/privacy contracts.
2. Recorded-first fixtures, optional live adapter, and safety tests.
3. Graph integration and privacy/safety documentation.

## Goal-level acceptance criteria

- **G18-AC01 — Provider boundary:** Only the five configured source classes are
  accepted; unconfigured sources and broad queries are rejected.
- **G18-AC02 — Scope and freshness:** Every receipt records source scope,
  freshness, provenance, and redaction; stale or out-of-scope evidence remains
  unknown or scope-limited.
- **G18-AC03 — Recorded-first safety:** Default and recorded modes make no
  network request and never read ambient credentials or serialize raw payloads.
- **G18-AC04 — Contradictions and gaps:** Conflicts, unavailable telemetry,
  missing inventory, and privacy redactions preserve disagreement and create
  proof obligations.
- **G18-AC05 — Live containment:** Explicit live reads enforce host,
  credential, request, byte, and wall-time policies and record effect metadata.
- **G18-AC06 — Verification:** Focused tests, locked full suite, and
  documentation/diff checks pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G18-AC01 | Provider catalog and query-scope tests |
| G18-AC02 | Freshness, scope, and redaction matrix |
| G18-AC03 | Recorded-mode socket/credential/raw-content guards |
| G18-AC04 | Contradiction and missing-proof fixtures |
| G18-AC05 | Explicit live-policy and budget tests with injected opener |
| G18-AC06 | Focused suite, locked full suite, docs review, and diff check |

## Completion evidence

- `uv lock --check` completed successfully.
- `uv run --locked pytest -q tests/test_operational_evidence.py` completed
  successfully: 6 tests passed.
- `uv run --locked pytest -q` completed successfully (full suite green).
- `git diff --check` completed successfully; tracked and untracked files were
  inspected with `git status --short`.
- `docs/PROJECT.md` and `docs/SAFETY.md` document the five-source provider
  boundary, recorded-first behavior, privacy/redaction, freshness, and live
  containment rules.

G19 remains proposed and is not started by this cycle.

Focused tests should be named `test_g18_ac01_provider_boundary` through
`test_g18_ac06_verification` (or recorded equivalent names).

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_operational_evidence.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- Operational data may be more decisive than external EOL evidence but is also
  more sensitive; privacy policy is part of the evidence contract.
- A provider receipt establishes only its configured scope and freshness, not
  universal absence of a customer or runtime condition.
