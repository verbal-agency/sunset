# G27 — Maintainer pilot and product decision

**Status:** proposed
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

The maintainer pilot uses the G25 configuration and these G26 collectors within
existing read-only investigation and human-gated validation boundaries. Define
participant consent, candidate count, data minimization/redaction, success and
harm measures, retention, and an incident stop rule before the first maintainer
run. Publish aggregate and per-case evidence only with participant-approved
disclosure.

## Explicit exclusions

- Automatic cleanup, changing a target repository, broad telemetry collection,
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
may not write the target, execute target code, access credentials, or make live
network requests. Model calls, external providers, and sandbox validation remain
disabled unless separately authorized by the maintainer-pilot protocol.

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
