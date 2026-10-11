# G33 — Unified repository investigation orchestration API

**Status:** complete
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

A maintainer-facing pilot and future MCP/HTTP clients can call Sunset as one
bounded investigation capability. Low-level commands remain available for
debugging and development only.

## Completion evidence

The recorded orchestration tranche completed on 2026-10-10. The typed service and CLI transport are implemented
in `src/sunset/pilot_models.py`, `src/sunset/pilot_service.py`, and
`src/sunset/cli.py`. Recorded request, run, and case-file fixtures live under
`tests/fixtures/pilot/`; focused acceptance evidence is in
`tests/test_pilot_run.py`; and the bounded product-path findings are recorded in
`docs/research/G33-orchestration-report-v1.md`.

The original G33-AC01 through G33-AC08 criteria cover the recorded contract and
remain verified by the focused suite, the locked full suite, and
`git diff --check`. The executable extension below is now complete and supplies
the pinned-clone and environment path required by the original objective.

## G33 extension — executable bounded backend

### Purpose

Close the gap between a recorded orchestration facade and a usable maintainer
pilot. The service must execute the existing deterministic pipeline against an
exact pinned checkout in a declared disposable environment, while preserving
the recorded path, approval boundary, and non-authority contract.

### Objective

Add a replaceable execution backend behind `PilotService` that clones and pins a
repository by full SHA, selects a matching G32-style environment recipe,
creates an isolated runtime, installs only declared dependencies, resolves the
candidate, composes the existing evidence/investigation/validation components,
and returns the same resumable case-file contract through `pilot run` and
`pilot approve`.

### Scope boundary

- exact-SHA clone preparation with an explicit vetted-repository and network
  policy;
- deterministic environment-recipe selection and isolated runtime creation;
- declared argv-only dependency installation with package, byte, and time
  budgets;
- candidate discovery and evidence collection against the pinned clone;
- adapter calls into the existing G30 investigation and G06 disposable
  validator, with approval still required before validation;
- environment, clone, command, and artifact receipts attached to the existing
  `PilotResult`/case-file response; and
- recorded fixtures and an end-to-end LangChain acceptance run using the same
  frontend request shape.

### Explicit exclusions

- arbitrary shell strings, unbounded package installation, or implicit network
  access;
- mutation of the source checkout, automatic cleanup, code deletion, or pull
  requests;
- autonomous approval or validation outside G14/G06;
- multi-repository workflows, MCP/HTTP-specific orchestration, or tournament
  ranking of models; and
- changing the recorded contract or weakening any G33-AC01 through G33-AC08
  invariant.

### Execution contract

#### Expected implementation surface

- `src/sunset/pilot_runtime.py`: pinned clone preparation, environment recipe
  selection, isolated runtime provisioning, declared-command runner, and
  receipt contracts.
- `src/sunset/pilot_service.py`: inject the runtime backend without moving
  sequencing into the CLI; persist setup receipts and resume from checkpoints.
- `src/sunset/pilot_models.py`: add additive environment/setup receipt fields
  and structured setup errors without invalidating schema-1 recorded fixtures.
- `src/sunset/cli.py`: select recorded or explicitly authorized live backend;
  retain `pilot run`/`pilot approve` as the only product transport.
- `tests/test_pilot_runtime.py` and `tests/test_pilot_run_live_fixture.py`:
  exact-ref, recipe, budget, authority, checkpoint, and end-to-end tests.
- `tests/fixtures/pilot/g33-{runtime,live-run,failures}-v1.json` and the
  existing G32 environment recipe fixture.
- `docs/research/G33-executable-backend-report-v1.md`.

Equivalent modules are allowed only when these contracts, fixture boundaries,
and authority rules remain unchanged.

#### Canonical contracts and invariants

`PinnedCheckoutReceipt` contains the repository URL, requested SHA, observed
HEAD SHA, source policy ID, clone artifact ID, and target snapshot digest.
`EnvironmentReceipt` contains the selected environment ID, Python executable
identity, dependency digest, declared install argv, package budget, and
artifact ID. Setup is valid only when the observed HEAD exactly equals the
requested SHA and the recipe repository/ref identity matches. A missing recipe,
moving ref, failed install, budget exhaustion, or digest mismatch is a
structured terminal setup result; it never falls through to investigation.

The live backend may execute only declared argv vectors from the selected recipe
inside its disposable environment. It may not accept shell metacharacters,
undeclared commands, arbitrary paths, or package names outside the recipe.
`PilotResult` remains non-authoritative, and approval tokens remain bound to the
request, pinned SHA, candidate, recipe digest, validator configuration, and
run.

#### Deterministic behavior matrix

| Input | Required result |
| --- | --- |
| Allowed URL + full SHA + matching recipe | Clone, verify HEAD, record setup receipts, then continue to candidate resolution. |
| Branch/tag/missing object/wrong observed HEAD | `environment_error`; no install, model, investigation, or validation. |
| Missing or mismatched recipe | `environment_error` with recipe error; no fallback runtime or dependency guess. |
| Declared install succeeds within budgets | Record environment receipt and continue once. |
| Install command, package, byte, or time budget fails | Structured setup failure; preserve clone/evidence artifacts and do not retry implicitly. |
| Candidate absent or ambiguous in pinned clone | `candidate_not_found`/`candidate_ambiguous`; no investigation or validation. |
| Investigation requests validation before approval | `approval_required`; no disposable validation clone. |
| Valid approval | Resume the same run and invoke G06 only in a disposable clone. |
| Replay of compatible live run | Reuse setup/evidence artifacts; do not reclone, reinstall, or repeat completed stages. |

#### Authority, network, and stop conditions

The host must explicitly authorize the repository host, credential identity (if
needed), network budget, and vetted-repository policy. The source checkout is
read-only. Network is permitted only for the pinned clone and declared package
installation; model calls use the existing G30 provider budgets. Stop on any
identity, recipe, budget, checkpoint, approval, or validator error, preserve
successful artifacts, and return the structured reason. Cleanup is limited to
disposable runtime directories owned by the backend and is never applied to the
target repository.

#### Replay and cache rules

The live run identity includes repository URL/SHA, candidate selector,
environment recipe and dependency digests, provider/model identity, validator
configuration, and budget ledger. Setup receipts are immutable. A changed SHA,
recipe, provider, budget, or approval token creates a new run identity; it may
not reuse incompatible setup or evidence. Recorded mode remains byte-identical
and offline.

### Extension acceptance criteria

- **G33-AC09 — Exact pinned setup:** An authorized live backend clones the
  requested repository, verifies the exact SHA, records a checkout receipt, and
  fails closed on branches, missing objects, or mismatched HEADs.
- **G33-AC10 — Reproducible environment:** The backend selects the matching G32
  recipe, creates an isolated runtime, executes only declared argv installs
  within budgets, records an environment receipt, and fails closed on missing or
  failed setup.
- **G33-AC11 — Real stage composition:** One `pilot run` request drives the
  pinned clone through deterministic discovery, provenance/evidence,
  investigation, approval, G06 validation, and case-file finalization without
  frontend phase commands.
- **G33-AC12 — Approval and target safety:** Approval is required before
  validation; approved validation runs only in a disposable clone; source
  checkout snapshots and working trees are unchanged for approve, deny, expiry,
  mismatch, and failure paths.
- **G33-AC13 — Failure and resume safety:** Setup, install, model, validator,
  interruption, and budget failures preserve completed artifacts, return typed
  reasons, and do not repeat completed clone/install/evidence stages on replay.
- **G33-AC14 — Authority and network boundary:** Tests prove only configured
  hosts, declared commands, credentials, budgets, and disposable paths are
  reachable; arbitrary shell, undeclared installs, hidden network, cleanup of
  the target, and autonomous approval are rejected.

### Extension criterion-to-evidence map

| Criterion | Required evidence |
| --- | --- |
| G33-AC09 | `tests/test_pilot_runtime.py::test_exact_sha_checkout_and_fail_closed_refs` |
| G33-AC10 | `test_recipe_selection_and_isolated_install_receipt` plus runtime fixture |
| G33-AC11 | `tests/test_pilot_run_live_fixture.py::test_single_request_drives_real_pipeline` |
| G33-AC12 | `test_approval_required_before_disposable_validation` and target snapshot fixture |
| G33-AC13 | `test_setup_failure_checkpoint_and_replay` plus failure fixture |
| G33-AC14 | `test_declared_command_and_network_authority` |

### Extension verification commands

```bash
.venv/bin/python -m pytest -q tests/test_pilot_runtime.py tests/test_pilot_run_live_fixture.py
uv run --locked pytest -q
git diff --check
```

## Extension completion evidence

G33-AC09 through G33-AC14 completed on 2026-10-10. The executable backend is
implemented in `src/sunset/pilot_runtime.py`, wired through `pilot run` and
`pilot approve`, and covered by `tests/test_pilot_runtime.py` and
`tests/test_pilot_run_live_fixture.py`. The canonical LangChain run is recorded
in `docs/research/G33-executable-backend-report-v1.md`: it verified the exact
commit, selected `langchain-core-py312-v1`, collected provenance, paused for
approval, resumed from a separate process, and returned `completed` with a
`confirmed` disposable validation outcome.

All extension acceptance criteria have named test or run evidence. The focused
runtime, live-pipeline, and recorded-pipeline tests pass; the locked full suite
passes; and `git diff --check` passes. No source checkout was mutated, and the
agent tournament remains explicitly outside G33.

## Promotion requirements satisfied

G30 supplied the stable escalation result contract and G32 supplied the
reproducible recorded runtime/dependency recipe. The implementation preserved
the Luna-ready execution contract, transport, fixtures, approval store,
authority/network/side-effect boundaries, terminal/stop conditions, binary
acceptance criteria, and criterion-to-evidence map.
