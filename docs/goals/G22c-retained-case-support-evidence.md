# G22c — Retained-case support evidence supplement

**Status:** complete
**Dependencies:** G22b (complete) and owner-approved retained-case selection

## Purpose

Extend the declared-support evidence bundle to a retained compatibility shim so
Sunset can test whether it refuses cleanup when a protected condition remains
active in the project’s declared support scope.

## Objective

Capture and freeze packaging, published-artifact, CI, documentation-status, and
dependency-marker evidence for `lg-dataclass-version-shim` at its pinned
LangGraph head, without changing the immutable validation corpus or treating
declared support as proof about every downstream deployment.

## Scope boundary

Use the existing bounded support-evidence provider with an owner-approved
selection. Persist the selection, verified replay fixture, digest sidecar, and
documentation. Do not adjudicate labels, collect telemetry, execute LangGraph
code, or mutate the target repository.

## Acceptance criteria

1. The selection is bound to the G21 manifest digest, LangGraph repository,
   pinned head, candidate path, and exact `langgraph==1.2.11` release.
2. All five support-evidence classes are represented; documentation is an
   explicit owner-approved `not_applicable` record.
3. Bounded live capture succeeds with no diagnostics and produces a verified
   fixture whose sidecar digest matches.
4. The fixture replays offline through the recorded provider with no network or
   subprocess access.
5. Focused support-evidence tests and `git diff --check` pass.

## Completion evidence

- Selection: `tests/fixtures/support_evidence/g22c-selection-v1.json`.
- Fixture: `tests/fixtures/git_evidence/g22c-langgraph-support-v1.json`.
- Fixture digest: `0d594843ffb1a57442c8d3961764136ddf6c086427b9eb0a49a44a50d1ed03d9`.
- Capture: six declared entries (five captures and one explicit
  `not_applicable`) completed with zero diagnostics under the existing request
  and byte bounds.
- Evidence establishes declared LangGraph support for Python 3.10–3.14; it
  does not establish downstream usage or universal removability.
