# G33 — Unified repository investigation orchestration API

**Status:** proposed  
**Dependencies:** G30 (bounded agentic escalation loop), G32 (natural
clone-runnable corpus), with G06/G22/G28/G29 inherited through those goals

## Purpose

Make Sunset usable as a product rather than a bag of internal commands. A
frontend should submit one repository/candidate investigation request and receive
one resumable case-file result; it must not know or compose the
`scan → provenance → investigate → validate → casefile` plumbing.

## Objective

Add a canonical typed orchestration service, exposed through at least one
supported transport (the first transport should be the CLI `pilot/run` surface),
that owns pinned checkout, supported-runtime selection, isolated dependency setup,
candidate resolution, evidence collection, bounded investigation, approval
issuance, disposable validation, artifact storage, and case-file finalization.
MCP or HTTP adapters may be thin projections of the same service; they must not
reimplement the workflow.

## Project outcomes and scenarios advanced

- Advances OUT-02, OUT-03, OUT-04, OUT-06, OUT-07, and OUT-08.
- Advances SCN-01, SCN-03, SCN-04, SCN-05, SCN-07, SCN-09, and SCN-11.
- Provides the single-entry product path needed for a maintainer-facing pilot.

## Scope boundary

The goal covers:

- a versioned request/response contract for repository URL and ref, scope,
  candidate locator, recorded/live mode, and validation intent;
- a run-state machine with resumable `approval_required`, `running`,
  `completed`, `inconclusive`, and failure states;
- deterministic candidate lookup with explicit ambiguity and not-found errors;
- supported-runtime selection and dependency installation into an isolated,
  recorded environment;
- approval tokens bound to the pinned repository, candidate, configuration, and
  run;
- artifact storage and one case-file response containing status, hypothesis,
  evidence IDs, artifact IDs, validation outcome, unresolved obligations, and
  next action; and
- one end-to-end path for the G32 LangChain pydantic-v2-nested case without
  frontend command composition.

## Explicit exclusions

- Removing or weakening the existing low-level commands.
- Autonomous approval, cleanup, or target-repository mutation.
- Arbitrary shell or filesystem access.
- Unbounded dependency installation or hidden live-network use.
- Multi-repository investigations.
- A frontend-specific orchestration graph or duplicated MCP/HTTP workflow.

Runtime setup may install only declared dependencies inside an isolated,
recorded environment and must fail closed when the environment cannot be
reproduced.

## Execution contract

### Expected implementation surface

- `src/sunset/pilot_models.py`: versioned request, run-state, approval-token,
  case-file, and structured-error contracts.
- `src/sunset/pilot_service.py`: one orchestration service that composes the
  existing scanner, evidence, G30 loop, G14 approval boundary, G06 validator,
  artifact store, and case-file finalizer. It is the only owner of workflow
  sequencing.
- `src/sunset/cli.py`: a `pilot run` entry point and an approval/resume entry
  point that call the service; existing low-level commands remain unchanged.
- `tests/test_pilot_run.py` and
  `tests/fixtures/pilot/g33-{requests,runs,casefiles}-v1.json`: recorded
  success, approval, denial, ambiguity, failure, replay, and authority cases.
- `docs/research/G33-orchestration-report-v1.md` and this specification.

Equivalent modules are allowed only when they preserve the same typed
contracts, one-owner sequencing, fixture coverage, and authority boundaries.

### Canonical contracts and invariants

`PilotRequest` schema `1` contains a repository URL, full 40-character ref,
scope, candidate path/test selector, mode (`recorded` or explicitly configured
`live`), and validation intent. `PilotRun` has one immutable `run_id`, a legal
state transition (`created → running → approval_required → running → terminal`),
repository identity, candidate identity, artifact IDs, and terminal status.
Approval tokens are schema-versioned, single-purpose, bound to run ID, pinned
repository, candidate, validation configuration, and expiry; they cannot
authorize a different run. A case file is non-authoritative and must retain
hypothesis, evidence IDs, validation outcome, unresolved obligations, and the
next action. Unknown or ambiguous candidates never resolve by guess.

### Deterministic behavior matrix

| Input | Required result |
| --- | --- |
| Full ref, unique candidate, recorded mode | One resumable run with recorded evidence and a case-file result. |
| Branch/tag ref or malformed request | Structured rejection; no clone, install, model, or validation call. |
| Candidate not found or ambiguous within scope | Structured `candidate_not_found` or `candidate_ambiguous`; no investigation. |
| Validation requested before approval | `approval_required` with a bound token; no disposable clone. |
| Denied or expired token | Structured denial; no validation or mutation. |
| Valid token | Resume the same run and invoke only the existing disposable validator. |
| Runtime/dependency setup unavailable | `environment_error` or `unvalidatable`; no hidden retry or fallback install. |
| Interrupted/replayed compatible run | Resume or reuse completed artifacts without repeating side effects. |

### Authority, network, and stop conditions

The service may read the pinned repository, declared evidence providers, and
recorded fixtures. It may create only disposable clones and isolated declared
environments outside the target checkout. It must not mutate the target,
approve itself, perform cleanup, open arbitrary shell/filesystem access, or
install undeclared dependencies. Live network and model calls require explicit
configuration and their existing provider budgets. Stop on malformed input,
unknown candidate, failed setup, invalid approval, exhausted budget, terminal
validator result, or incompatible checkpoint; preserve prior artifacts and
return the structured reason.

### Replay and cache rules

Run identity includes request, repository ref, candidate selector, mode,
configuration, tool/prompt/model identities, and budget ledger. Compatible
recorded replay reuses immutable artifacts. A changed ref, selector, provider
identity, environment recipe, approval token, or budget invalidates only the
affected run state. The frontend never invokes an internal phase command.

## Goal-level acceptance criteria

- **G33-AC01 — Single entry point:** `pilot run` accepts the canonical request
  and returns one versioned run/result object; tests prove no frontend command
  composition is required.
- **G33-AC02 — Deterministic setup:** The service pins the ref, selects a
  supported recipe, records the environment, resolves a unique candidate, and
  fails closed on moving refs, missing recipes, not-found, or ambiguity.
- **G33-AC03 — Workflow ownership:** Recorded execution invokes scan, evidence,
  investigation, approval, validation, and case-file stages in one service;
  tests prove low-level CLI behavior remains compatible.
- **G33-AC04 — Approval boundary:** Validation requests pause with a bound
  approval token; denial, expiry, mismatch, or replay cannot run validation or
  mutate the target; approval resumes the same run.
- **G33-AC05 — Case-file completeness:** Terminal results include status,
  hypothesis, evidence/artifact IDs, validation outcome, unresolved obligations,
  and next action, with non-authority explicitly true.
- **G33-AC06 — Failure and resume safety:** Malformed model/tool responses,
  setup errors, interruption, exhausted budgets, and incompatible checkpoints
  preserve successful artifacts and return structured terminal reasons without
  repeating completed side effects.
- **G33-AC07 — Authority and privacy:** Tests prove no target mutation,
  arbitrary shell/filesystem access, undeclared install, hidden network use, or
  autonomous cleanup/approval.
- **G33-AC08 — Replayability:** Recorded requests, approval transitions, and
  case files reproduce byte-identically; focused tests, the locked suite, and
  documentation/diff checks pass.

## Criterion-to-evidence map

| Criterion | Required evidence |
| --- | --- |
| G33-AC01 | `tests/test_pilot_run.py::test_pilot_run_is_single_entry_point` |
| G33-AC02 | `test_pinned_setup_and_candidate_resolution` plus malformed/ref fixtures |
| G33-AC03 | `test_service_owns_stage_sequence` and low-level CLI compatibility tests |
| G33-AC04 | `test_approval_token_binds_resume_and_denial_is_side_effect_free` |
| G33-AC05 | `test_terminal_casefile_contains_required_fields` |
| G33-AC06 | `test_failure_checkpoint_and_resume_preserve_artifacts` |
| G33-AC07 | `test_pilot_authority_guards` with socket/subprocess/target snapshot guards |
| G33-AC08 | `test_recorded_pilot_replays_byte_identically`, locked suite, and report |

## Required verification commands

```bash
.venv/bin/python -m pytest -q tests/test_pilot_run.py
uv run --locked pytest -q
git diff --check
```

## Expected product contract

An invocation equivalent to:

```json
{
  "repository": {
    "url": "https://github.com/langchain-ai/langchain",
    "ref": "5c1f28271295bb13034f4cf8964f74c117357d40"
  },
  "scope": "libs/core/tests/unit_tests",
  "candidate": {
    "path": "utils/test_function_calling.py",
    "test": "test_convert_to_openai_function_nested_v2"
  },
  "mode": "recorded",
  "validation": {"requested": true}
}
```

must yield one run identifier and a structured result. Before validation approval,
the result is `approval_required` with an approval token and next action
`Approve disposable validation`. Approval resumes the same run and never asks
the frontend to invoke another internal command. Terminal results distinguish
completed, inconclusive, contradictory, environment-error, and unvalidatable
outcomes.

## Capability unlocked

Once promoted and completed, a maintainer-facing pilot and future MCP/HTTP
clients can call Sunset as one bounded investigation capability. Low-level
commands remain available for debugging and development only.

## Promotion requirements

This proposal must not be activated until G30 supplies a stable escalation
result contract and G32 demonstrates a reproducible runtime/dependency recipe.
Promotion requires a Luna-ready execution contract naming the service modules,
transport, fixtures, approval store, authority/network/side-effect boundaries,
and terminal/stop conditions, plus binary acceptance criteria and a
criterion-to-evidence map.
