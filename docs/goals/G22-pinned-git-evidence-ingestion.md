# G22 — Pinned Git evidence ingestion

**Status:** complete
**Dependencies:** G21 (complete)

## Purpose

Make a corpus pointer inspectable without asking a reviewer or agent to trust a
commit subject. Historical provenance is useful only when the pinned source and
diff can be retrieved, preserved, and replayed as evidence.

## Objective

Add a replaceable, read-only Git evidence provider that resolves an allowlisted
G21 `EvidencePointer` into a content-addressed source blob or commit patch.
Recorded fixtures are the default; live GitHub reads are explicit, pinned,
bounded, cacheable, and failure-safe. The provider must return compact metadata
and an artifact ID, never raw bytes in agent state.

## Project alignment

- Advances OUT-02, OUT-05, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-04, SCN-05, SCN-08, and SCN-09.
- Unlocks G22a's real-artifact capture prerequisite for G23 adjudication of
  protected-condition hypotheses and
  proof obligations.

## Architecture constraints to preserve

- The caller supplies an existing G21 pointer; the model cannot invent a URL,
  host, repository, commit, path, credential, or artifact-store location.
- Only immutable full Git SHAs and safe relative paths are accepted. No branch,
  tag, “latest,” arbitrary URL following, or repository checkout is allowed.
- Recorded mode opens no socket. Live mode is opt-in, host-allowlisted,
  response-limited, timeout-bounded, and uses an injected opener/credential
  boundary. A failure remains `missing`, `failed`, or `budget_exhausted`.
- Raw source and patch bytes are content-addressed artifacts. Receipts retain
  locator, commit, path, byte length, digest, freshness, and artifact ID only.
- Evidence retrieval does not infer a condition, authorize validation, mutate a
  target repository, or produce a cleanup recommendation.

## Scope boundary

Implement the provider contracts, recorded fixture adapter, explicit live
adapter, artifact persistence, CLI fetch path, tests, and documentation. Do not
add adjudication labels, model behavior, general web search, repository clones,
test execution, or target-repository mutation.

## Execution contract

### Expected implementation surface

Create `src/sunset/git_evidence_models.py` and
`src/sunset/git_evidence.py`; extend `src/sunset/cli.py` with
`sunset git-evidence fetch --manifest PATH --case-id ID --evidence-id ID
--store PATH [--fixture PATH | --live] [--kind blob|patch] [--max-bytes N]`;
add `tests/test_git_evidence.py`; add recorded fixtures under
`tests/fixtures/git_evidence/`; and create `docs/GIT-EVIDENCE.md`.
Equivalent modules are allowed only when these public contracts, CLI behavior,
fixture location, and focused tests remain available.

### Canonical contracts and invariants

Define `GIT_EVIDENCE_SCHEMA_VERSION = "1"` and immutable contracts for
`GitEvidenceRequest`, `GitEvidenceResponse`, `GitEvidenceReceipt`, and
`GitEvidenceError`.

`GitEvidenceRequest` is derived only from an existing G21 `EvidencePointer` and
has `evidence_id`, `repository_url`, `commit_sha`, `path` (for `blob`),
`kind` (`blob` or `patch`), and a positive `max_bytes`. A commit pointer maps to
the pinned commit patch; a blob pointer maps to the exact pinned path. The
request identity includes schema, repository, SHA, path, kind, provider policy,
and byte budget.

`GitEvidenceResponse` has outcome `available`, `missing`, `failed`,
`budget_exhausted`, or `unsupported`; summary; canonical source locator; byte
length; and optional raw bytes that are immediately persisted and excluded from
the receipt. `GitEvidenceReceipt` has request identity, outcome, artifact ID (if
available), SHA-256 digest, byte length, provider/mode, freshness key, and
non-authority marker.

Reject non-GitHub repository hosts, URLs not matching the pointer's repository,
abbreviated SHAs, unsafe/absolute/parent-traversing paths, unsupported pointer
roles, branch/tag refs, malformed fixtures, nonpositive byte budgets, and
responses that exceed the remaining byte budget. A live provider must not read
ambient credentials; any credential identity is supplied by the host and is
represented only by a digest in request identity.

### Deterministic behavior matrix

| Input/evidence condition | Required observable result |
| --- | --- |
| Recorded blob fixture matches pointer, SHA, and path | Persist exact bytes and return `available` receipt with artifact digest. |
| Recorded patch fixture matches pinned commit | Persist exact patch and return `available` receipt whose locator remains pinned. |
| No matching recorded response | Return `missing` with no artifact and no network attempt. |
| Malformed pointer, unsupported host/kind, or unsafe path | Return stable validation error before provider invocation. |
| Provider response exceeds `max_bytes` | Return `budget_exhausted`/`failed` with no partial artifact. |
| Transport, timeout, 404, rate limit, or malformed live response | Return `failed` or `missing` with structured error; never infer expiry. |
| Same request and unchanged fixture/provider policy replay | Reuse byte-identical artifact and receipt identity; do not refetch. |
| Changed SHA, path, kind, fixture digest, freshness, or policy | Reject incompatible reuse and create a distinct request identity. |

### Authority, side effects, and stop conditions

The provider may read the local G21 manifest, recorded fixture, and configured
artifact store. Recorded mode may write only the content-addressed artifact and
receipt view. Live mode may perform only the one explicit HTTP GET for the
derived GitHub blob or patch URL. It may not clone, checkout, import, execute,
call a model, follow links, write GitHub, modify a target repository, or approve
validation. Stop after one response, a validation error, a timeout, or byte
budget exhaustion; no unbounded retry loop is permitted.

### Replay, cache, and budget rules

`max_bytes` must be positive and defaults to 64 KiB. Live reads use a 10-second
timeout and one request per invocation. The request identity includes provider
name, mode, host allowlist, credential-identity digest (never the secret),
freshness key, and all pointer fields. Existing artifact bytes are verified by
SHA-256 before reuse. A changed identity cannot reuse an old receipt or artifact
as if it were current evidence.

### Required fixture matrix

The focused suite must use committed offline fixtures for positive blob and
patch responses, retained/missing evidence, contradictory source and patch
artifacts, malformed fixture records, unsupported hosts/paths, partial transport
failure, byte-budget exhaustion, and replay/invalidation. Socket and subprocess
guards must prove recorded mode is offline.

## In scope

1. Pointer-derived, pinned blob/patch request and receipt contracts.
2. Recorded-first fixture provider and content-addressed artifact persistence.
3. Explicit, injected-opener live GitHub adapter with strict bounds.
4. CLI fetch path, cache identity, failure handling, and documentation.

## Explicit exclusions

- General GitHub browsing/search, issue/PR inference, branch/tag resolution, or
  arbitrary URL fetches.
- Repository cloning/checkouts, imports, test execution, model calls,
  adjudication labels, optimization, cleanup, or approval.
- Treating a retrieved source/diff or historical removal as proof that a
  protected condition is absent or removal is safe.

## Deliverables

1. Versioned Git evidence contracts and replaceable recorded/live providers.
2. Artifact-backed source and patch receipts with replay/invalidation rules.
3. Offline adversarial tests and an explicit live-provider seam.
4. CLI and documentation sufficient for a reviewer to inspect G21 cases offline.

## Goal-level acceptance criteria

- **G22-AC01 — Pointer-bound requests:** Only a valid G21 pointer can produce a
  request; host, SHA, path, kind, and budget validation rejects illegal inputs
  before provider invocation.
- **G22-AC02 — Recorded evidence:** Matching blob and patch fixtures persist
  exact bytes as immutable artifacts and return compact receipts; missing,
  contradictory, malformed, and unsupported fixtures remain structured
  uncertainty/errors.
- **G22-AC03 — Explicit live boundary:** Injected-opener live tests prove one
  pinned, bounded request with no ambient credential discovery, link following,
  or mutation path.
- **G22-AC04 — Replay and budgets:** Compatible replay is byte-stable and does
  not refetch; changed pointer/policy/freshness identity invalidates reuse;
  oversized, timeout, rate-limit, and partial failures retain no unsafe partial
  artifact.
- **G22-AC05 — CLI and privacy:** The CLI fetches a manifest-bound pointer,
  emits a receipt/artifact ID, and never prints raw bytes, credentials, or
  writes outside the configured store/output.
- **G22-AC06 — Verification and documentation:** Focused and locked full suites,
  lock/diff checks, and `docs/GIT-EVIDENCE.md` pass and document the
  non-authority boundary.

## Criterion-to-verification map

| Criterion | Required named evidence |
| --- | --- |
| G22-AC01 | `test_g22_ac01_pointer_bound_requests` plus malformed/host/path/SHA/budget fixtures |
| G22-AC02 | `test_g22_ac02_recorded_evidence` plus blob/patch/missing/contradictory fixtures |
| G22-AC03 | `test_g22_ac03_explicit_live_boundary` with injected opener and credential guard |
| G22-AC04 | `test_g22_ac04_replay_and_budgets` with cache, invalidation, timeout, and size cases |
| G22-AC05 | `test_g22_ac05_cli_and_privacy` against the committed manifest and isolated store |
| G22-AC06 | `test_g22_ac06_verification`, lock/full suite, docs review, and `git diff --check` |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q tests/test_git_evidence.py
uv run --locked pytest -q
git diff --check
git status --short
```

## Risks and carried-forward findings

- G13's existing live provider handles only issue/PR state; this goal adds the
  missing pinned source/patch path without broadening external search.
- A GitHub 404, rate limit, network outage, or stale source must remain an
  explicit unavailable result. It cannot be converted into a condition label.
- Retrieved source and patches may contain hostile or sensitive text. Keep raw
  bytes in the artifact store and expose only IDs/metadata to the agent and
  reviewer workflow.

## Completion evidence

- `tests/test_git_evidence.py`: 7 focused tests pass, covering all six goal
  criteria, including offline socket guards, contradictory source/patch
  artifacts, malformed and partial failures, cache invalidation, and CLI
  privacy.
- `.venv/bin/python -m pytest -q`: full suite passes (194 collected tests).
- `uv lock --check`, `git diff --check`, JSON fixture validation, and Python
  compilation pass.
- CLI replay against the committed G21 manifest returns a compact `missing`
  receipt when no matching recorded response exists; it emits no raw bytes.
- Live GitHub retrieval is verified only through the injected-opener boundary;
  no real network fetch is required for completion and no target repository was
  changed.
