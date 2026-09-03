# G26 — Broad candidate discovery

**Status:** complete
**Dependencies:** G25 (complete)

## Purpose

Broaden what Sunset can observe before a maintainer pilot, without weakening the
provenance, uncertainty, or human-approval contracts established by the Python
marker/compatibility slice.

## Objective

Additive deterministic collectors must identify repository-level temporal
signals and at least one JavaScript/TypeScript candidate family, normalize them
into the existing language-neutral candidate/evidence contract, and measure
per-family coverage and false-positive behavior on recorded fixtures.

## Project alignment

- Advances OUT-01, OUT-02, OUT-05, OUT-06, OUT-07, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-05, SCN-06, SCN-08, SCN-09, and SCN-12.
- Unlocks a coverage-qualified candidate set for the G27 maintainer pilot.

## Scope boundary

Candidate families include repository-level version/dependency constraints,
deprecation or migration annotations, feature-flag lifecycle signals, and
environment/configuration gates, with a bounded JavaScript/TypeScript adapter.
Each collector preserves exact source locations, repository identity, committed
revision, evidence role, and unsupported dynamic forms as explicit unknowns.
Additive registry/versioning and offline benchmark fixtures are in scope.

## Explicit exclusions

- Protected-condition inference, prompt optimization, or changing G24/G25 labels.
- Broad reachability/dead-code analysis, arbitrary repository crawling,
  enterprise connectors, live provider access, cleanup, or pull requests.
- Treating a detected signal, stale flag, upstream deprecation, or passing test
  as proof that the protected condition has expired.

## Outcomes and handoff

G26 receives versioned collector contracts, representative positive/negative/
contradictory/unsupported fixtures, per-family detection and false-positive
measurements, and an explicit list of unsupported forms. G27 may use only the
families and scopes whose provenance and limitations are documented.

## Luna-ready execution contract

### Implementation surface

- `src/sunset/broad_collectors.py` and
  `src/sunset/broad_collectors_models.py`: deterministic repository-level
  collector and language-neutral candidate/result contracts.
- `src/sunset/git_repository.py`: reuse committed-HEAD path enumeration and
  read-only blame; do not add arbitrary filesystem access.
- `src/sunset/cli.py`: expose `sunset collect --collector broad`.
- `tests/test_broad_collectors.py`: positive, negative, dynamic, language, and
  committed-snapshot tests.
- `docs/research/G26-broad-candidate-discovery-v1.md`: measured coverage and
  unsupported-form report.

### Canonical contracts and invariants

Each candidate contains `candidate_id`, `candidate_family`, `language`, `path`,
`line`, `column`, `signal`, `subject`, `condition`, `evidence_role`,
`repository_head`, `blame_commit`, and `unsupported_dynamic`. Signal families
are `support_constraint`, `deprecation_lifecycle`, `feature_flag`, and
`environment_gate`; languages are `python`, `javascript`, `typescript`, or
`repository`. IDs are stable for the committed HEAD and source span. A
collector result is schema version `1`, sorted deterministically, and reports
parse/read/blame errors without fabricating candidates.

### Deterministic behavior matrix

| Input | Required output |
| --- | --- |
| Python/JS/TS line matching a bounded signal | One candidate with exact path/span and Git provenance |
| Known repository config containing a support constraint | `support_constraint` candidate with `scope_limit` evidence role |
| Dynamic flag/environment lookup | Candidate retained with `unsupported_dynamic=true`; no expiry inference |
| Unrelated code or unsupported syntax | No candidate; no fabricated error |
| Parse/read/blame failure | Structured error tied to path and location; scan continues |
| Untracked or working-tree-only file | Ignored because collection reads committed HEAD only |
| Repeated scan of unchanged HEAD | Byte-identical JSON and candidate IDs |

### Authority and side-effect boundaries

The collector is offline, read-only, and deterministic. It may use Git commands
already encapsulated by `GitRepository` for committed paths, source bytes, and
blame. It may not call models, network providers, registries, imports,
subprocesses outside the repository abstraction, credentials, validation,
mutation, cleanup, or pull requests.

### Fixtures and acceptance-to-evidence map

The fixture repository in `tests/test_broad_collectors.py` includes Python and
TypeScript positives, a support constraint, a dynamic unsupported form, an
unrelated untracked file, and a stable committed snapshot. Acceptance is binary:

1. Signal and language extraction: `test_discovers_repository_and_javascript_temporal_signals`.
2. Unsupported dynamic and committed-HEAD behavior:
   `test_dynamic_forms_are_explicit_and_committed_snapshot_only`.
3. Full locked suite, compilation, JSON/CLI smoke test, and `git diff --check`.

## Carried-forward limitations

These collectors identify leads and scope-limits only. They do not infer that a
condition is expired, and their regex/line-oriented coverage is intentionally
bounded. Broader AST and language-specific semantics remain future work.

## Completion evidence

- `tests/test_broad_collectors.py` passes both focused acceptance tests.
- The fixture demonstrates Python and TypeScript signals, support constraints,
  dynamic unsupported forms, exact blame, stable IDs, and committed-only reads.
- The full pytest suite, compilation, JSON/CLI smoke checks, and `git diff
  --check` pass. No live repository, network, model, or mutation authority was
  added.
