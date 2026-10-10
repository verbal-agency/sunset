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
