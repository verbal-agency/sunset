# G37 — Maintainer-independent validation benchmark

**Status:** active
**Dependencies:** G33 (complete), G34 (complete)

## Purpose

Measure whether Sunset produces reproducible, evidence-grounded investigations
when no consenting maintainer is available, while preventing historical
outcomes or automated checks from being misrepresented as human-confirmed
protected-condition labels.

## Objective

Run the existing high-level investigation and bounded validation pipeline on a
versioned set of pinned public repositories, then publish a case-level report
covering provenance, candidate coverage, evidence support, contradiction
detection, validation reproducibility, historical agreement, cost, and false
positives. Every condition judgment must be labeled `unadjudicated` or
`proxy_labeled`; no result may be labeled maintainer-confirmed or safe to
remove.

## Dependencies

- G33 provides the single-entry orchestration API and approval-boundary state.
- G34 provides real historical cases, clone recipes, outcome vocabulary, and
  the explicit warning that removal history is a weak label.
- Existing recorded traces and public-corpus fixtures are preferred over new
  model calls. A live model, new credentials, or a new external data source
  requires separate authorization.

## Project outcomes and scenarios

Advances OUT-02, OUT-04, OUT-05, OUT-06, and OUT-08; exercises SCN-01 through
SCN-03, SCN-06, SCN-07, and SCN-12. It does not satisfy the human-control or
production-safety claim in G27.

## Scope

- Freeze a benchmark manifest drawn from the existing pinned public corpus and
  G34 cases, with repository URL, exact source SHA, candidate selector, split,
  and label provenance for every case.
- Replay heuristic-only and recorded-agentic runs through the G33 entry point
  where fixtures exist; run approved disposable validation only on declared
  public clones and record its bounded scope.
- Produce per-case receipts and an aggregate report with separate sections for
  mechanical correctness, evidence quality, historical agreement, and
  unresolved obligations.
- Add negative, contradictory, malformed, unavailable-runtime, and
  unadjudicated cases to the offline replay suite.

## Explicit exclusions

- No maintainer contact, consent, outreach, or fabricated human labels.
- No claim that historical removal proves condition expiry or safe deletion.
- No target-repository mutation, pull request, cleanup, or reviewer decision.
- No tuning on holdout cases, new collector family, new language, or live model
  call unless separately authorized.

## Deliverables

- `tests/fixtures/benchmarks/g37-independent-manifest-v1.json`
- `tests/fixtures/benchmarks/g37-independent-runs-v1.json`
- `tests/fixtures/benchmarks/g37-independent-report-v1.json`
- `docs/research/G37-maintainer-independent-validation-report-v1.md`
- `tests/test_maintainer_independent_validation.py`
- Updated roadmap/backlog references that retain G27 as the human-validation
  path and state G37's evidence limits.

## Contracts and invariants

Each case receipt contains: schema version, case ID, repository URL, exact
source SHA, candidate selector, run mode, runtime identity, command argv,
network mode, timestamps, outcome, artifact IDs, label provenance, and
unresolved obligations. Label provenance is one of `human_adjudicated`,
`historical_proxy`, `unadjudicated`, or `synthetic_negative`; G37 may emit only
the last three. Validation outcomes use the existing vocabulary
`confirmed`, `still_failing`, `flaky`, `environment_error`, and
`unvalidatable`. A passing experiment proves only the declared test scope.

## Behavior matrix

| Condition | Required result |
| --- | --- |
| Exact SHA and replayable inputs | Deterministic case receipt and stable artifact IDs |
| Historical removal or retention only | `historical_proxy`; never human-confirmed expiry |
| Recorded agent response unavailable or malformed | `unadjudicated`/`inconclusive`; no guessed label |
| Contradictory evidence | Contradiction remains visible and creates an obligation |
| Moving ref, missing SHA, or scope mismatch | Fail closed before execution; no result artifact |
| Validation runtime unavailable | `environment_error` or `unvalidatable` with bounded reproduction |
| Holdout case | Reported once with frozen configuration; no tuning or threshold change |

## Authority, network, and stop rules

Only declared public repositories and disposable validation clones may be
accessed. Commands are argv-only and time-bounded. No credentials, arbitrary
paths, target checkout writes, cleanup, PRs, maintainer contact, or model calls
outside an explicitly authorized mode are allowed. Stop on a moving ref,
missing receipt field, target snapshot change, credential exposure, or any
attempt to convert a proxy label into approval.

## Acceptance criteria and evidence map

- **G37-AC01:** Every benchmark case has an exact-SHA manifest entry and a
  complete receipt; verified by manifest-integrity tests.
- **G37-AC02:** At least one heuristic-only and one recorded-agentic replay
  path execute through G33 without target mutation; verified by run fixtures and
  target-status assertions.
- **G37-AC03:** The report separates mechanical correctness, evidence quality,
  historical agreement, and unresolved obligations; verified by report-schema
  tests and the Markdown report.
- **G37-AC04:** No case or aggregate report calls a proxy/unadjudicated label
  human-confirmed or safe-to-remove; verified by negative string/policy tests.
- **G37-AC05:** Contradictory, malformed, moving-ref, unavailable-runtime, and
  holdout cases fail closed and replay byte-identically; verified by focused
  replay tests.
- **G37-AC06:** The full locked test suite and `git diff --check` pass, and the
  report records limitations that G27 still requires a consenting maintainer.

## Verification commands

```bash
uv run --locked pytest -q tests/test_maintainer_independent_validation.py
uv run --locked pytest -q
git diff --check
```

## Carried-forward risks

Historical outcomes remain biased toward visible cleanup and cannot establish
the condition's scope in downstream deployments. Recorded agent traces measure
replay behavior, not live-model quality. Small public samples can overstate
coverage. These risks must remain visible in the report and are not reasons to
upgrade a proxy result to a human judgment.
