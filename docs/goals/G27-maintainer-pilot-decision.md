# G27 — Maintainer pilot and product decision

**Status:** active
**Dependencies:** G25 (complete), G26 (complete), and explicit pilot authorization

## Purpose

Test whether the validated workflow is useful and appropriately conservative in
real maintainer review, where operational evidence and missing context matter
most.

## Objective

Make G26 usable at real-repository scale, run a declared read-only technical
pilot against a pinned public repository, then run a consented maintainer pilot
against a small qualified candidate set and publish an evidence-bounded
continue, revise, or stop decision.

## Project alignment

- Advances OUT-04, OUT-05, OUT-06, and OUT-08.
- Advances SCN-01 through SCN-03 and SCN-07 through SCN-12.
- Unlocks a product decision based on empirical results and maintainer feedback
  rather than architecture claims alone.

## Scope boundary

The technical pilot may scan a pinned public checkout without contacting or
mutating the target owner. It must use a two-phase collector contract:
deterministic discovery emits stable signals without Git-history subprocesses,
and a separate bounded enrichment step adds provenance only for selected
candidates. Enrichment batches blame by file, caches by repository head and
path (the immutable HEAD pins the blob identity), groups history and patch retrieval, and reports shallow or
unavailable history explicitly. The feature-flag detector must not classify a
bare UI capability method such as `.isEnabled()` as a lifecycle flag. The run
must record its ref, commit, scope, configuration digest, candidate counts,
false-positive exclusions, provenance completeness, errors, and runtime.

### Declared OpenClaw candidate bundle

The technical pilot is pinned to OpenClaw `v2026.8.2` at
`0965053fe6b9341776df147a6934b7485c60b5ca`, scoped to `ui/`. The initial bundle
contains four candidates selected to exercise distinct epistemic outcomes:

| Candidate ID | Location | Protected-condition hypothesis | Pilot role |
| --- | --- | --- | --- |
| `sunset-broad-v2-15be1992b07e42a78f0c0b24` | `ui/src/e2e/activity-run-inspector.e2e.test.ts:22` | Chromium may be unavailable in the execution environment, so this lane is intentionally skipped. | Active/retained control; verify with and without Chromium and inspect CI setup. |
| `sunset-broad-v2-a4ba4f78d9030728b801e465` | `ui/src/e2e/activity-session-feed.capture.e2e.test.ts:22` | A proof-phase label may be temporary instrumentation whose absence should not change test behavior. | Low-risk removal hypothesis; inspect all references and compare artifact output with the variable unset. |
| `sunset-broad-v2-eac9359052efa9f30c01df81` | `ui/src/e2e/tool-titles.e2e.test.ts:199` | An exact-head value may be needed to make visual-test metrics reproducible, or may be unused metadata. | Unknown/reproducibility case; search consumers and verify metrics behavior. |
| `sunset-broad-v2-ccb8a75b35e18dd8955874c5` | `ui/src/e2e/activity-answer-candidates.e2e.test.ts:16` | Screenshot/video capture is optional instrumentation shared across many E2E tests. | Repeated-condition case; test deduplication and scope reasoning, not immediate cleanup. |

The bundle deliberately excludes the two remaining feature-family matches:
`patternFlags` in `ui/src/lib/browser-redact.ts:14` is a regular-expression
flag, and `dangerousConfigFlags` in `ui/src/pages/plugins/consent-dialog.ts:148`
is configuration safety metadata. Neither is a product feature-lifecycle
candidate. Their exclusion is recorded as a detector-quality finding for this
goal, not as a removal conclusion.

### Authorized disposable-clone validation (2026-09-03)

The owner authorized bounded execution in a fresh clone at
`/private/tmp/openclaw-g27-validation`. Node 24.15.0, pnpm 12.1.0, and the
installed Google Chrome binary were used; the pinned checkout remained clean.
The activity-run-inspector lane passed with Chromium (10/10) and skipped
cleanly when Chromium was unavailable and the allow-missing gate was enabled
(10 skipped). The session-feed capture lane passed with and without its proof
phase value (1/1 each). The answer-candidates lane passed with and without
capture enabled (1/1 each). The tool-titles lane passed 5/6 tests; its
240-row video test was unavailable because Playwright ffmpeg is unsupported on
macOS 13 arm64. These are validation observations, not removability proof; the
per-command record is in the pilot fixture.

## Goal-level acceptance criteria

- **G27-AC01 — Technical run manifest:** A metadata-only report records the
  pinned OpenClaw ref/head, `ui/` scope, collector schema/configuration, deferred
  and enriched counts, runtime, errors, and target-mutated=`false`.
- **G27-AC02 — Deferred/enriched behavior:** Deferred discovery performs no Git
  history calls; selected enrichment produces complete provenance for the four
  declared candidates, leaves non-selected candidates deferred, and replays
  byte-identically from the cache.
- **G27-AC03 — Candidate review packet:** Each declared candidate has a source
  locator, introducing commit, protected-condition hypothesis, pilot role,
  evidence scope, and at least one explicit proof obligation. Reviewer status
  remains `pending` until the authorized reviewer records a decision.
- **G27-AC04 — False-positive exclusions:** The packet records both excluded
  feature-family matches and their exclusion reasons; neither is presented as a
  lifecycle candidate.
- **G27-AC05 — Side-effect boundary:** The collector and packet creation make
  no model calls, live provider requests, target-repository writes, or cleanup
  changes. Any separately authorized validation runs execute only in a fresh
  disposable clone, record their commands/outcomes, and leave the pinned target
  checkout unchanged.
- **G27-AC06 — Single-reviewer handoff:** The packet is ready for one authorized
  reviewer to classify each candidate as `retain`, `investigate`, or
  `insufficient_evidence`; no second reviewer or consensus is implied.

### Criterion-to-evidence map

| Criterion | Evidence |
| --- | --- |
| G27-AC01 | `tests/fixtures/public_corpus/openclaw-g27-ui-run-v2.json` and regenerated CLI reports |
| G27-AC02 | `tests/test_broad_collectors.py`, `tests/test_git_repository.py`, and deferred/selected/complete OpenClaw reports |
| G27-AC03 | `tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json` |
| G27-AC04 | Pilot review fixture `exclusions` records both non-lifecycle matches |
| G27-AC05 | Read-only command logs, unchanged target checkout snapshot, and no model/provider artifacts |
| G27-AC06 | Pilot review fixture `review_protocol` and pending per-case reviewer fields |

The maintainer pilot uses the G25 configuration and these G26 collectors within
existing read-only investigation and human-gated validation boundaries. Define
participant consent, candidate count, data minimization/redaction, success and
harm measures, retention, and an incident stop rule before the first maintainer
run. Publish aggregate and per-case evidence only with participant-approved
disclosure.

## Explicit exclusions

- Automatic cleanup, changing a target repository, unbounded target-code
  execution, broad telemetry collection,
  general-availability claims, or any use of pilot data beyond consent.
- Treating maintainer approval, a passing test, or a small pilot as proof that a
  protected condition is absent everywhere.
- Sending the complete raw candidate inventory to a model before deterministic
  filtering or deduplication.

## Authority and stop condition

The goal requires explicit pilot authorization and maintainer participation.
Without those inputs, Cycle must stop as blocked. Any privacy incident,
unapproved side-effect request, or configured harm threshold stops new pilot
runs while preserving the evidence already authorized for retention.

## Outcomes and handoff

The final artifact reports the declared pilot protocol, configuration digest,
coverage, maintainer outcomes, failures, unresolved proof obligations, and a
bounded continue/revise/stop recommendation. It is not a cleanup authorization.

## Execution contract

### Expected implementation surface

- `src/sunset/broad_collectors.py`: separate discovery from provenance
  enrichment, semantic feature-flag filtering, and deterministic deduplication.
- `src/sunset/git_repository.py`: file-level porcelain blame and bounded
  provenance cache primitives.
- `src/sunset/broad_collectors_models.py`: additive provenance status and
  schema-versioned deferred/enriched result representation.
- `src/sunset/cli.py`: explicit deferred collection and selected-candidate
  enrichment commands or equivalent flags.
- `tests/test_broad_collectors.py`, `tests/test_git_repository.py`, and a
  focused real-run report fixture under `tests/fixtures/public_corpus/`.
- This goal specification and `docs/ROADMAP.md` for protocol and evidence
  requirements.

### Canonical contracts and legal states

Discovery candidates retain `candidate_id`, family, language, path, line,
column, signal, subject/condition, evidence role, repository head, and
`unsupported_dynamic`. Provenance is one of `deferred`, `complete`, or
`incomplete`; a candidate with `incomplete` provenance cannot be treated as a
historical fact. Candidate IDs are independent of blame results. Duplicate
signals for the same repository head, path, line, column, family, and
condition are illegal and must be rejected deterministically.

### Behavior matrix

| Input/evidence condition | Required result |
| --- | --- |
| valid committed source, deferred mode | candidates with no Git-history subprocesses and `deferred` provenance |
| selected candidates, full history | one blame lookup per unique file and `complete` provenance |
| repeated enrichment, unchanged head/blob | cache hit with byte-identical result |
| shallow or missing history | `incomplete` provenance plus explicit error/obligation |
| `.isEnabled()` UI method | no `feature_flag` candidate |
| explicit feature-flag name or environment gate | candidate with extracted subject and stable ID |
| malformed source or failed Git operation | structured error; no guessed commit |

### Authority and side effects

The technical pilot is read-only and limited to a detached/pinned checkout.
Collectors may read committed blobs and invoke bounded local Git commands; they
may not write the target, access credentials, or make live network requests.
Target-code execution and disposable-clone validation are separate capabilities:
they remain disabled unless explicitly authorized by the maintainer-pilot
protocol, must use a fresh clone, and must record environment, command, outcome,
and any unavailable dependency. Cleanup changes remain prohibited.

### Verification evidence

Acceptance requires named unit tests for deferred mode, per-file blame caching,
cache invalidation, shallow-history handling, semantic false-positive
filtering, and deterministic replay, plus a saved OpenClaw run manifest/report
containing the pinned ref/head, scope, counts, errors, provenance status, and
runtime. A passing scan is evidence of pipeline behavior only; it is not a
removability conclusion.

## Refinement trigger

After the technical pilot satisfies its acceptance criteria and a pilot owner
supplies authorization, freeze the approved candidate list, privacy rules, stop
thresholds, fixtures/simulation tests, and maintainer-review protocol before
any agentic or validation run.
