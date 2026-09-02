# G22b — Declared-support evidence bundle

**Status:** complete
**Dependencies:** G22a (complete), owner-approved supplement selections

## Purpose

G22a supplies real historical patches and one current source file, but the
first adjudication case still lacks current package-support evidence. A single
TOML file would be too narrow: support is represented across packaging,
published artifacts, CI, documentation, and dependency markers. This goal adds
that evidence bundle without mutating the immutable G21 corpus or treating a
historical cleanup as a current support-policy fact.

## Objective

Capture a declared-support evidence bundle for selected G21 cases at their
existing pinned heads and corresponding published release, persist it as a
separate manifest-bound supplement, and replay it offline through G22. The
bundle covers repository packaging metadata, published artifact metadata, CI
version matrices, support documentation/release notes, and dependency/version
markers. It distinguishes declared project support from actual deployment
usage and remains non-authoritative.

## Project alignment

- Advances OUT-02, OUT-05, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-05, SCN-08, and SCN-09.
- Unlocks G23 review packets with current declared-support evidence.

## Architecture constraints to preserve

- G21 remains immutable. Supplement entries reference an existing `case_id`
  and `pinned_head` but do not rewrite its historical outcome, split, or
  requirements.
- The owner supplies a finite supplement manifest containing an exact source
  kind, GitHub or public-registry locator, full SHA where applicable, relative
  path, release identity where applicable, evidence class, and evidence ID.
  Luna may not discover arbitrary files or invent URLs.
- Capture uses the bounded G22 HTTPS provider only: one request per entry,
  allowlisted GitHub or public-registry hosts/redirects, explicit timeout,
  byte budget, no clone/fetch, credentials, subprocesses, model calls, or
  target-repository mutation. The initial registry host allowlist is
  `pypi.org` and `files.pythonhosted.org`; GitHub hosts follow G22's existing
  allowlist.
- Missing or contradictory support evidence remains unknown/blocked. It does
  not establish that Python versions are unsupported or that removal is safe.

## Scope boundary

Implement a versioned supplement manifest and capture/replay path, capture a
five-class declared-support bundle for `lc-python39-removeprefix-shim` (and the
paired `lc-python310-aiter-shim` case when applicable), and document the
distinction between declared support and actual usage. Do not adjudicate
condition labels, collect customer telemetry, or begin G23 review.

## Execution contract

### Expected implementation surface

Add `src/sunset/support_evidence_models.py` and
`src/sunset/support_evidence.py` with a `SUPPORT_EVIDENCE_SCHEMA_VERSION`,
immutable `SupportEvidenceSupplement`, `SupportEvidenceEntry`, and validation
errors. Extend the capture CLI/provider to accept a supplement manifest
alongside the immutable G21 manifest and allow only explicitly allowlisted
GitHub and public package-registry hosts. Add
`tests/test_support_evidence.py`, a committed selection under
`tests/fixtures/support_evidence/`, the resulting replay fixture under
`tests/fixtures/git_evidence/`, and update `docs/GIT-EVIDENCE.md`.

### Canonical contracts and invariants

`SupportEvidenceEntry` requires `case_id`, `evidence_id`, `evidence_class`,
`status`, and a nonempty source description. `status` is `capture` or
`not_applicable`. A `capture` entry additionally requires `source_kind`,
`locator`, and the fields required by that source: `source_kind` is
`public_git` or `public_registry`; Git entries require `commit_sha` and a safe
relative `path`; registry entries require an exact published release identity
and a registry URL for that release. `evidence_class` is one of
`packaging_metadata`, `published_artifact`, `ci_support`,
`support_documentation`, or `dependency_marker`. The case ID and SHA must
match the referenced G21 case; hosts must be allowlisted; and paths must be
relative and traversal-free. A `not_applicable` entry requires an
owner-supplied `reason`, has no locator, and is excluded from network capture.

`SupportEvidenceSupplement` contains the G21 manifest digest, entry IDs,
captured artifact digests, source locators, byte lengths, freshness/policy
identity, and `non_authority=true`. It may add evidence pointers but cannot
change G21 case labels or splits. Raw bytes live only in content-addressed
artifacts and replay fixtures.

### Required selections

The initial supplement must include owner-approved entries for
`lc-python39-removeprefix-shim` at head
`e92c8a08bf382121cc1e95f7e75ddc8cb9c01ab0` in all five evidence classes:

1. repository packaging metadata;
2. published artifact metadata for the corresponding release;
3. CI/test Python-version matrix;
4. support documentation or release notes; and
5. dependency/version markers relevant to the compatibility workaround.

Repository entries may be drawn from the pinned GitHub head; published
artifact entries must identify the exact package release and its metadata
endpoint. The corresponding release need not equal the repository head, but
the supplement must record both identities and their freshness scopes. The
allowlisted public registry is limited to `pypi.org` and
`files.pythonhosted.org`; no arbitrary web search is permitted.

Include the paired `lc-python310-aiter-shim` entries when they use the same
support contract. Every path or registry URL must be explicitly declared in the
supplement manifest; no repository-wide discovery is permitted. If a class is
genuinely not applicable, the manifest must contain a `not_applicable` record
with an owner-supplied reason; it may not be silently omitted.

The owner-approved initial selection is recorded at
`tests/fixtures/support_evidence/g22b-selection-v1.json`. It uses the exact
paths and `langchain-core==1.6.1` release identity recorded there. Live capture
may begin only through the bounded G22 provider and must still verify that each
declared locator is available; availability does not turn the bundle into
ground truth.

### Deterministic behavior matrix

| Condition | Required result |
| --- | --- |
| Capture entry matches an existing case, repository, SHA, and safe path | Capture exact bytes and digest as a supplement artifact. |
| `not_applicable` entry has an owner-supplied reason | Record the class as explicitly not applicable without a network request. |
| Entry is a published artifact with an exact release identity and allowlisted registry URL | Capture the registry metadata and bind it to the corresponding case/head without treating it as repository-HEAD evidence. |
| Entry case/SHA/repository mismatch or duplicate ID | Reject before network access. |
| Current metadata returns 200 within budget | Record the declared-support evidence class with locator, digest, freshness scope, and non-authority marker. |
| 404, timeout, DNS/TLS failure, rate limit, redirect rejection, or oversized response | Structured unavailable/blocked diagnostic; no support conclusion. |
| All selected entries succeed | Write supplement fixture atomically and make it replayable offline. |
| Any entry fails | Do not write a verified supplement; preserve diagnostics and leave G22b incomplete/blocked. |
| Offline replay | No socket, Git, subprocess, model, or target-repository access; digests and manifest binding match. |

### Authority, side effects, and stop conditions

Only the owner-approved supplement manifest, G21 manifest, configured artifact
store, output fixture, and optional diagnostic report are writable/readable.
Live mode performs only the declared HTTPS GETs. Stop after one response per
entry, a validation error, timeout, or budget exhaustion. Never infer actual
deployment usage from package metadata.

### Required fixture and test matrix

Cover valid and invalid supplement entries, case/SHA/path mismatch, duplicate
IDs, each of the five evidence classes, explicit `not_applicable` records,
real successful GitHub and registry capture, 404/timeout/redirect/rate-limit/
budget failures, atomic writes, digest and manifest invalidation, and offline
replay with socket/subprocess guards.

## Explicit exclusions

- Editing the G21 corpus, changing historical outcomes/splits, broad GitHub or
  registry search, clone/fetch, customer telemetry, private repositories, or
  credentials.
- Condition adjudication, removal recommendations, validation execution,
  cleanup, or treating declared support as proof about every deployment.

## Goal-level acceptance criteria

- **G22b-AC01 — Supplement binding:** Every entry is owner-declared and bound to
  an existing G21 case and pinned head; illegal identities fail before network.
- **G22b-AC02 — Support bundle:** Every required evidence class for the
  selected case is captured from its declared GitHub or public-registry source
  into a digest-verified replay fixture, or a genuinely unavailable class is
  represented by an owner-approved `not_applicable`/blocked diagnostic; no
  synthetic substitute or silent omission is accepted.
- **G22b-AC03 — Bounded transport:** Capture uses only explicit allowlisted
  HTTPS requests with timeout, byte, redirect, and request-count bounds.
- **G22b-AC04 — Failure honesty:** Missing/contradictory/partial/over-budget
  evidence remains structured unavailable state and never becomes a support or
  removability conclusion.
- **G22b-AC05 — Offline replay:** The supplement replays byte-for-byte through
  G22 without network and preserves manifest, pointer, and artifact digests.
- **G22b-AC06 — Documentation and verification:** Focused tests, locked full
  suite, lock/diff checks, and support-vs-usage documentation pass; G23 remains
  blocked until its independent reviews are supplied.

## Criterion-to-verification map

| Criterion | Required named evidence |
| --- | --- |
| G22b-AC01 | `test_supplement_binding_and_rejection` |
| G22b-AC02 | `test_real_support_bundle_capture_or_blocked_report`, live capture report, and committed fixture/digest |
| G22b-AC03 | `test_support_transport_bounds` |
| G22b-AC04 | `test_support_failure_diagnostics` |
| G22b-AC05 | `test_support_fixture_replays_offline` |
| G22b-AC06 | `test_supplement_binding_and_rejection`, locked full suite, `uv lock --check`, `git diff --check` |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q tests/test_support_evidence.py tests/test_git_evidence.py
uv run --locked pytest -q
uv run --locked sunset support-evidence capture --manifest tests/fixtures/validation_corpus/langchain-validation-v1.json --supplement tests/fixtures/support_evidence/g22b-selection-v1.json --output-fixture tests/fixtures/git_evidence/g22b-langchain-support-v1.json --store /tmp/sunset-g22b-support --live --max-bytes 1200000
git diff --check
git status --short
```

## Risks and carried-forward findings

- Package metadata establishes declared support only; actual users may still
  require older runtimes. G23 must retain actual-usage as a separate proof
  obligation.
- If the exact metadata or CI path is absent at the pinned head, record the
  404/path mismatch and leave this goal blocked rather than broadening search.

## Completion evidence

- The owner-approved selection was validated against the immutable G21 corpus;
  all ten capture entries use the pinned head and the two support-documentation
  classes are explicit `not_applicable` records.
- Live capture succeeded with 10 bounded HTTPS requests, a 1,200,000-byte
  per-entry budget, and no diagnostics. It captured 10 responses totaling
  2,302,806 bytes (five unique payloads after content-addressed deduplication)
  and produced the
  replay fixture digest recorded in
  `tests/fixtures/git_evidence/g22b-langchain-support-v1.sha256`.
- The fixture replays offline through `RecordedSupportEvidenceProvider`; the
  focused support-evidence suite and locked full suite pass.

| Criterion | Evidence | Result |
| --- | --- | --- |
| G22b-AC01 | `test_supplement_binding_and_rejection`; selection bound to G21 digest `5b379fe7…` and pinned head `e92c8a…` | pass |
| G22b-AC02 | Authorized live capture returned `status=verified`; 10 available captures plus 2 explicit `not_applicable` records; fixture sidecar matches `49009157…` | pass |
| G22b-AC03 | `test_support_transport_bounds`; live run used one bounded request per capture entry, allowlisted hosts, 10-second timeout, and 1,200,000-byte limit | pass |
| G22b-AC04 | `test_support_failure_diagnostics`; 404 and over-budget responses remain structured failures and suppress fixture publication | pass |
| G22b-AC05 | `test_support_fixture_replays_offline`; socket guard and digest checks pass | pass |
| G22b-AC06 | Focused suite (13 passed), locked full suite (green), `uv lock --check`, documentation review, and `git diff --check` | pass |
