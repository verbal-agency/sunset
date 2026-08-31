# G09 — End-to-end release

**Status:** complete
**Dependencies:** G08a

## Purpose

Convert Sunset's independently verified components into a reproducible public
product that demonstrates the thesis, safety model, and measured limitations
without weakening its human approval boundaries.

## Objective

Package the existing vertical slice as an installable release, add a minimal
standalone investigation viewer, document privacy and safety, and publish a
reproducible read-only demonstration against a pinned LangGraph revision.

## Project alignment

- Advances OUT-01 through OUT-05 and exercises SCN-01 through SCN-07 at the
  release boundary.
- Uses G08a's public evidence base while keeping historical outcomes distinct
  from Sunset recommendations.

## Architecture constraints to preserve

- Scanning and investigation remain read-only; the public target is pinned and
  target code is never installed, imported, or executed.
- HTML is a derived view of the citation-verified case-file contract. It embeds
  no raw artifact bytes, active script, remote assets, or unescaped claim text.
- Default demonstrations make no network, model, external-write, or validation
  request. Network access is limited to the separately documented initial clone
  of a public pinned repository.
- A completed discovery run is not called a safe cleanup. Unknown evidence is
  published as `inconclusive`, and every cleanup remains a human decision.

## In scope

- Release metadata and an isolated wheel-install smoke test.
- A version flag and standalone HTML rendering for verified case files.
- Clean-install, privacy, security, approval, and data-flow documentation.
- A short reproducible terminal demonstration.
- Saved public results from a pinned, read-only LangGraph scan and offline
  investigation, covering successful deterministic discovery and an
  inconclusive conclusion.

## Explicit exclusions

- Publishing a package, site, container, video, pull request, or cleanup change
  to an external service.
- Installing dependencies or running tests from the public target repository.
- Adding automatic cleanup, browser execution, telemetry, authentication, or a
  hosted viewer.
- Claiming historical removals establish present-day safety or production
  precision.

## Deliverables

1. Buildable wheel and source distribution with release metadata and CLI
   version reporting.
2. Escaped, script-free standalone HTML case-file viewer.
3. Release, safety/privacy, demo, and public-run documentation.
4. Machine-readable pinned public-run summary.

## Goal-level acceptance criteria

- **G09-AC01:** `uv build` produces wheel and source distributions; installing
  the wheel into an isolated environment provides `sunset --version` and a
  working committed-fixture scan without importing Sunset from the checkout.
- **G09-AC02:** `sunset casefile --format html` renders a complete standalone
  viewer from citation-verified saved results. Tests prove hostile text is
  escaped and that output contains no script, remote asset, or raw artifact
  body.
- **G09-AC03:** Release documentation states data flow, local artifact and
  checkpoint locations, live-network and validation opt-ins, host-code execution
  risk, human approval boundaries, supported scope, and measured benchmark and
  public-corpus limitations.
- **G09-AC04:** A short terminal demonstration is reproducible from committed
  fixtures using locked commands and produces both an
  `eligible_for_human_cleanup` example and an `inconclusive` example without a
  default network request or target-working-tree mutation.
- **G09-AC05:** A saved public-run summary pins the LangGraph URL and full SHA,
  records exact commands and immutable result digests, reports successful
  deterministic discovery plus an offline `inconclusive` investigation, and
  documents that target code was neither installed nor executed.
- **G09-AC06:** The locked full test suite, release-document validator, public
  result validator, and diff/whitespace checks pass; target-repository snapshots
  are unchanged by the documented workflow.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G09-AC01 | Build and isolated wheel-install smoke commands |
| G09-AC02 | HTML snapshot, escaping, no-script/no-remote-asset tests |
| G09-AC03 | Documentation contract test and manual review |
| G09-AC04 | Demo fixture test, locked command transcript, repository snapshot assertion |
| G09-AC05 | Public-run schema/digest/pinning tests and recorded LangGraph command output |
| G09-AC06 | `uv lock --check`, locked full suite, goal-specific tests, `git diff --check` |

## Completion evidence

- **G09-AC01:** `uv build --out-dir /private/tmp/sunset-g09-dist-final`
  produced the 0.1.0 wheel and source distribution. A fresh Python 3.12
  environment installed the wheel and cached locked dependencies; from
  `/private/tmp`, `sunset --version`, package-path inspection, committed-fixture
  scanning, and `release-check` all passed. The imported package path was the
  isolated environment's `site-packages`, not this checkout.
- **G09-AC02:** HTML viewer tests cover CLI rendering, hostile element and
  attribute escaping, CSP, no active script or remote asset, and exclusion of
  raw artifact bodies.
- **G09-AC03:** The documentation contract test covers local storage and
  checkpoints, privacy, live-network and publication opt-ins, validation's host
  execution risk, human control, supported scope, and benchmark/corpus limits.
- **G09-AC04:** The committed recorded demo deterministically produced both
  `eligible_for_human_cleanup` and `inconclusive`; a socket guard proves its
  default case-file workflow is offline. Both reports preserve the human
  decision boundary.
- **G09-AC05:** The full LangGraph checkout at
  `11ee185999b86bfea2d8c0e69cef9a5e37acf686` yielded 11 candidates and no scan
  errors. Offline investigation of `sunset-v1-ed51e3cc1b1b6c3bb84e5c5a`
  completed `inconclusive` with assumption status `unknown`. Saved output
  digests validate, and Git tree `10eb6105430f2551a0f49a55904f625b6877ac85`
  plus clean status matched before and after. Target code was not installed or
  executed, so no public cleanup contribution was justified.
- **G09-AC06:** `uv lock --check`, the 82-test full suite, the SCN-06 benchmark
  (60% median estimated input-token reduction, no accuracy or citation decline),
  the 20-record public corpus validator, `sunset release-check`, and
  `git diff --check` passed.

No scheduled roadmap goal follows G09. The repository is prepared for a human
release decision; package-registry publication, a hosted demo, and any cleanup
contribution remain outside this cycle's authorization.
