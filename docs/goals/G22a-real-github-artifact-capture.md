# G22a — Real GitHub artifact capture and connectivity proof

**Status:** complete
**Dependencies:** G22 (complete), an environment authorized for bounded public
GitHub HTTPS reads

## Purpose

G22 established a safe retrieval seam, but its committed fixtures are synthetic
and the real LangChain pointers have not yet been fetched. This goal proves—or
explicitly falsifies—that Sunset can acquire the actual pinned source and patch
artifacts needed by the validation corpus. It closes the difference between
“the adapter is tested” and “the evidence workflow works on a real repository.”

## Objective

Fetch a declared set of real G21 LangChain/LangGraph pointers over bounded HTTPS,
diagnose connectivity or GitHub responses without retry storms, persist exact
public bytes as a versioned recorded fixture, and replay the fixture offline
byte-for-byte through the G22 provider. The goal must end in either a verified
real-artifact fixture or a structured blocked report naming the failed network
phase. A blocked report is an honest stop outcome, not completion, and it may
not substitute authored content for a failed fetch.

## Project alignment

- Advances OUT-02, OUT-05, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-05, SCN-08, SCN-09, and SCN-12.
- Unlocks G23's independent adjudication against inspectable, real historical
  source and patch evidence.

## Architecture constraints to preserve

- Selection is manifest-bound: the caller supplies existing G21 case IDs and
  evidence IDs. Luna cannot invent repositories, refs, paths, or URLs.
- Retrieval uses HTTPS only, full immutable SHAs, exact blob paths or commit
  patches, one request per selected pointer, explicit connect/read timeouts,
  bounded bytes, and at most one explicitly allowlisted redirect. No `git
  clone`, `git fetch`, checkout, shell, credential discovery, or arbitrary URL
  following is permitted.
- The public GitHub endpoint and any redirect destination are independently
  host-allowlisted. Redirects are recorded; a disallowed or repeated redirect
  is a structured failure, not an implicit trust expansion.
- Captured bytes are public source/patch evidence only. Do not capture tokens,
  cookies, response headers containing credentials, or unrelated repository
  files. Receipts and agent state contain metadata and artifact IDs, never raw
  bytes.
- A network failure, DNS/TLS failure, timeout, rate limit, 404, redirect
  rejection, or byte-budget exhaustion is an honest blocked/unavailable result,
  not evidence about whether a protected condition expired.

## Scope boundary

Add the real-capture command and provider hardening, capture a small declared
set of actual G21 pointers, commit the resulting fixture and digests, replay it
offline, and document the connectivity diagnosis. Do not adjudicate condition
labels, run target code, clone repositories, search GitHub broadly, add
credentials, or proceed into G23 human review.

## Execution contract

### Expected implementation surface

Extend `src/sunset/git_evidence.py` and `src/sunset/git_evidence_models.py` with
strict redirect-aware live transport and a capture result/diagnostic contract.
Extend `src/sunset/cli.py` with:

```text
sunset git-evidence capture \
  --manifest PATH \
  --selection CASE_ID:EVIDENCE_ID[,CASE_ID:EVIDENCE_ID...] \
  --output-fixture PATH \
  --store PATH \
  [--max-bytes N] [--timeout-seconds N]
```

The command must require an explicit live-network flag or equivalent approval
boundary, fetch only the declared selection, and write a fixture only after
every selected response and digest has been recorded. Add focused tests in
`tests/test_git_evidence_capture.py`, a committed fixture at
`tests/fixtures/git_evidence/g22a-langchain-real-v1.json` and
`docs/GIT-EVIDENCE.md` coverage for diagnosis and replay. If live access is
unavailable, write `docs/research/G22a-github-connectivity-blocked.md` and
leave this goal blocked instead of fabricating a fixture.

### Canonical contracts and invariants

Define `GITHUB_CAPTURE_SCHEMA_VERSION = "1"` and immutable contracts for:

- `GitCaptureSelection`: case ID, evidence ID, derived request, and expected
  pointer digest.
- `GitCaptureDiagnostic`: phase (`dns`, `connect`, `tls`, `http`, `redirect`,
  `decode`, `budget`, or `fixture_write`), stable error kind, host/status if
  available, elapsed bound, and non-authority marker.
- `GitCaptureReport`: manifest digest, selection IDs, per-pointer receipts or
  diagnostics, fixture digest (if written), request count, redirect count,
  byte totals, and `status` (`verified`, `partial`, or `blocked`).

The recorded fixture must preserve for every captured pointer: case/evidence ID,
repository URL, full commit SHA, exact path or patch kind, canonical source
locator, final allowlisted locator if redirected, byte length, SHA-256 digest,
and exact bytes (UTF-8 text or base64 for non-UTF-8). Fixture identity includes
the source-manifest digest, selection, provider policy, timeout, byte budget,
and captured artifact digests. A fixture is never considered verified solely
because its JSON is well formed.

### Required real selection

Use at least these existing G21 pointers unless the manifest has changed, in
which case record the replacement IDs and rationale in the report:

1. `lc-python39-removeprefix-shim:history` — real commit patch
   `9ac8882a2c405e1f1a75957e81782538e4894c8b`.
2. `lc-python310-aiter-shim:history` — the same real commit patch, providing a
   second case-bound receipt for the shared historical change.
3. `lc-stream-error-xfail:history` — a pinned blob at the real LangChain head,
   exercising raw source retrieval and a retained case.

The capture must confirm that each response's repository, SHA, kind, path,
final URL, byte length, and digest agree with the manifest-derived request. A
404 or missing pointer is recorded as unavailable and causes `blocked` unless
the owner explicitly changes the selection with a recorded reason.

### Deterministic behavior matrix

| Condition | Required result |
| --- | --- |
| Real pinned blob or patch returns within bounds | Store exact bytes, digest, locator, and receipt; include in fixture. |
| GitHub returns one allowlisted redirect | Follow exactly once, record both locators, then capture or return a bounded failure. |
| Redirect host is not allowlisted or loops | `blocked`/`failed` diagnostic; no artifact from the response. |
| DNS, TCP, TLS, timeout, 404, 403/429, or 5xx | Stable phase/error diagnostic with no expiry inference and no retry loop. |
| Response exceeds budget or is non-decodable | `budget`/`decode` diagnostic; no partial fixture entry or artifact. |
| All selected pointers succeed and digests match | Write one fixture atomically and report `verified`. |
| Any selected pointer fails | Do not write a `verified` fixture; report `partial` or `blocked` and preserve successful receipts only in the diagnostic report. |
| Replaying the committed fixture | No socket, Git, subprocess, or model call; byte-identical artifacts and receipts. |

### Authority, side effects, and stop conditions

The capture command may read the committed G21 manifest, make the explicitly
approved HTTPS requests, and write only the configured artifact store, output
fixture, and diagnostic report. It may not modify a target repository or GitHub,
read ambient credentials, follow arbitrary links, or execute repository code.
Stop after the declared selection, the first terminal failure for a pointer, a
timeout, or byte exhaustion. There is no automatic retry or background job.

### Required fixture and test matrix

The focused suite must cover: real-selection derivation from the committed
manifest; successful blob and patch capture through fake HTTP responses;
allowlisted and rejected redirects; DNS/TLS/timeout/404/rate-limit/5xx
diagnostics; byte-budget and malformed-byte failures; atomic fixture writes;
digest and manifest invalidation; duplicate-selection rejection; and offline
replay with socket/subprocess guards. A live smoke command must be runnable by
Luna in an authorized network environment, but CI remains replay-only.

## Explicit exclusions

- Git clone/fetch, repository checkout, broad GitHub search, issue/PR browsing,
  or arbitrary URL retrieval.
- Ambient or persisted credentials, private-repository access, write APIs,
  model calls, condition adjudication, validation execution, or cleanup.
- Treating a successful HTTP response, historical removal, or captured patch as
  proof that a protected condition is absent or code is removable.

## Goal-level acceptance criteria

- **G22a-AC01 — Real selection:** The capture command accepts only the named
  G21 selections and derives exact pinned requests; duplicates, changed SHAs,
  path mismatches, and invented URLs fail before network access.
- **G22a-AC02 — Real artifact proof:** In an authorized network environment,
  the required LangChain/LangGraph selection produces a digest-verified
  recorded fixture containing exact bytes. If access fails, a committed
  phase-specific blocked report is required for diagnosis, but AC02 remains
  unmet and Cycle must mark G22a blocked. No synthetic body can satisfy this
  criterion.
- **G22a-AC03 — Bounded transport:** Tests and the live smoke prove HTTPS-only
  requests, explicit timeouts, one request per pointer, at most one
  allowlisted redirect, no ambient credentials, and no clone/fetch path.
- **G22a-AC04 — Failure honesty:** DNS/TLS/HTTP/redirect/decode/budget/partial
  failures remain structured unavailable outcomes, retain no unsafe partial
  fixture, and never become condition or removability claims.
- **G22a-AC05 — Offline replay:** The committed real fixture, when available,
  replays through G22 without network and reproduces every artifact digest,
  receipt, selection identity, and manifest binding byte-for-byte.
- **G22a-AC06 — Documentation and verification:** Focused tests, locked full
  suite, lock/diff checks, capture report or blocked report, and updated
  `docs/GIT-EVIDENCE.md` pass; G23 remains proposed and is not started.

## Criterion-to-verification map

| Criterion | Required named evidence |
| --- | --- |
| G22a-AC01 | `test_capture_selection_is_manifest_bound` and duplicate/path/SHA rejection fixtures |
| G22a-AC02 | `test_capture_real_fixture_or_blocked_report` plus committed fixture/report and digest manifest |
| G22a-AC03 | `test_redirect_allowlist_and_bounds` plus authorized live-smoke diagnostic |
| G22a-AC04 | `test_capture_failure_diagnostics` covering transport, HTTP, partial, malformed, and budget cases |
| G22a-AC05 | `test_real_fixture_replays_offline` with socket/subprocess guards |
| G22a-AC06 | `test_capture_contract`, focused/full suites, `uv lock --check`, `git diff --check`, documentation review |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q tests/test_git_evidence_capture.py tests/test_git_evidence.py
uv run --locked pytest -q
uv run --locked sunset git-evidence capture --manifest tests/fixtures/validation_corpus/langchain-validation-v1.json --selection lc-python39-removeprefix-shim:history,lc-python310-aiter-shim:history,lc-stream-error-xfail:history --output-fixture tests/fixtures/git_evidence/g22a-langchain-real-v1.json --store /tmp/sunset-g22a-capture --live --max-bytes 262144
git diff --check
git status --short
```

The live command is the only network-dependent check. If it cannot complete in
the authorized environment, write the blocked report, mark G22a blocked, and
stop; do not rerun indefinitely or claim AC02 completion.

## Risks and carried-forward findings

- GitHub may redirect commit patches to a separate host, rate-limit anonymous
  requests, or be unreachable from the execution environment. The diagnostic
  must distinguish these cases so “network unavailable” is not confused with
  “evidence missing.”
- Public source and patches may contain sensitive text despite public
  visibility. Capture only the selected paths/patches and expose IDs/digests to
  later agent state.
- A verified artifact proves historical content at a pinned location only. G23
  still requires independent human condition adjudication and operational
  evidence.

## Completion evidence

- The bounded live capture fetched all three declared G21 pointers from public
  GitHub with `--max-bytes 262144` and `--timeout-seconds 10`: two pinned
  commit patches (7,719 bytes each) and one pinned LangChain blob (67,167
  bytes). The report status was `verified`, with three requests and zero
  diagnostics.
- The committed fixture is
  `tests/fixtures/git_evidence/g22a-langchain-real-v1.json` (82,605 captured
  bytes) with manifest digest
  `5b379fe73ef3530a515b7d4aca5e557fd23d26acfbd56785b206cf85a4c4eeb7` and
  fixture digest
  `153e250fb2e6115cf3806c7b88f3276911afd09cb23c3a705371ecebc2947d06`.
  The digest is duplicated in the adjacent `.sha256` file.
- `tests/test_git_evidence_capture.py` and `tests/test_git_evidence.py` pass;
  the committed fixture replays through the recorded provider with socket
  guards and matching artifact digests.
- The full suite passes (201 collected tests), `uv lock --check`, JSON
  validation, Python compilation, and `git diff --check` pass. No target
  repository was cloned or modified.
