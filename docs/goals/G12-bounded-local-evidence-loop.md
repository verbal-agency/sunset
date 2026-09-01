# G12 — Bounded local-evidence agent loop

**Status:** proposed
**Dependencies:** G11 (complete)

## Purpose

Allow an investigator to adaptively request relevant local evidence while
keeping every action allowlisted, observable, replayable, and constrained by
deterministic policy rather than model intent.

## Objective

Build a bounded LangGraph planner–tool–observation loop that consumes G11's
structured hypotheses, deterministically dispatches only G10 local read-only
tools, updates compact state, and stops with a versioned terminal reason without
executing arbitrary actions or external research.

## Project alignment

- Advances OUT-02, OUT-03, OUT-06, and OUT-07.
- Establishes the adaptive-investigation path for SCN-03 through SCN-05,
  SCN-08, and SCN-09.
- Prepares G13 to add separately effect-declared external evidence tools; G12
  remains local, offline, and read-only.

## Architecture constraints to preserve

- G10's context, tool schemas, effect declarations, evidence grants, artifacts,
  budgets, receipts, and authority boundary remain the sole dispatch authority.
  A model may propose a catalog name and validated arguments but cannot supply a
  repository/store path, call a tool directly, or bypass policy.
- G11's result is model-derived inference. It can guide the next local evidence
  request but is neither a fact nor authorization to continue indefinitely.
- The loop stores only compact receipts, hypotheses, selected evidence IDs,
  state/budget versions, terminal reason, and structured errors. Raw excerpts
  are immediate-only observations and must not enter checkpoints or long-term
  graph state.
- Deterministic dispatch owns all tool calls and makes duplicate completed calls
  idempotent. Any side-effect classification other than G10 local read-only is
  rejected before invocation.
- The default remains offline, target-code-free, and non-mutating. No external
  evidence, validation, shell, target import, or approval boundary belongs in
  this goal.

## In scope

### Graph and state contract

Define versioned investigation state and result contracts for one local-evidence
run: run identity, repository identity/HEAD, tool/context policy identity,
reasoning invocation IDs, completed-call ledger, compact receipt/hypothesis
history, iteration and budget state, terminal reason, and structured errors.

The graph may execute this bounded cycle: assemble compact context; obtain or
replay one G11 reasoning result; validate one model-proposed G10 tool request;
dispatch deterministically; incorporate the safe receipt; and either continue
or stop. It must not expose graph state as a tool argument or accept arbitrary
LangChain tool calls.

### Deterministic planner-to-tool dispatch

Create a policy dispatcher that accepts only a G11 proposed G10 tool name and
validated arguments. It checks the bound registry catalog, declared effect,
current call/byte budget, evidence grant scope, and completed-call ledger before
calling the existing `BaseTool` wrapper. Unsupported names, malformed arguments,
wrong effect metadata, direct invocation attempts, and duplicate completed
requests produce structured graph observations without executing a tool.

G12 may choose an initial deterministic discovery action when no receipt exists;
subsequent actions must be traceable to a reasoning result or an explicit
deterministic stop policy.

### Bounded execution and checkpoint/resume

Add configurable maximum iterations, wall time, and aggregate G10 tool/budget
limits. Define terminal reasons at least for `completed`, `insufficient_evidence`,
`tool_error`, `model_error`, `tool_budget_exhausted`, `iteration_budget_exhausted`,
`wall_time_exhausted`, and `interrupted`.

Persist checkpoints after a completed reasoning or tool observation. Resume a
compatible run without repeating a completed tool or model call; invalidate when
repository HEAD, tool/context policy, model/prompt/output identity, input
receipts, evidence scope, or budget ledger changes. Preserve successful receipts
when a later call fails.

### Observability and deterministic baseline

Emit a compact trace of state transitions, reasoning IDs, tool receipts,
duplicate suppression, budgets, terminal reason, and telemetry references. Add
an explicit heuristic-only mode that never constructs a model runtime and can
stop after deterministic discovery/provenance according to policy.

## Explicit exclusions

- G13 external-provider, GitHub, release-note, dependency-registry, web-search,
  embedding, vector, or enterprise tools.
- Validation requests, test execution, shell commands, disposable clones,
  approval decisions, code edits, cleanup recommendations, pull requests, or
  target-repository writes.
- Open-ended ReAct behavior, arbitrary tool/function calling, automatic retries
  outside configured policy, or a model-selected budget/effect override.
- Multi-agent skepticism, case-file finalization, LangSmith tracing/evaluation,
  public release claims, or external publication.
- Persisting raw model prompts/responses, hidden chain of thought, raw excerpts,
  source, patches, history, credentials, or framework tool messages.

## Deliverables

1. Versioned local-agent run, state, terminal-reason, call-ledger, and trace
   contracts independent of LangGraph checkpoint/message internals.
2. Deterministic G10 registry dispatcher with effect, schema, duplicate, grant,
   and budget enforcement.
3. Bounded LangGraph planner–tool–observation graph with checkpoint/resume and
   model-enabled recorded/live plus heuristic-only configurations.
4. Isolated fixture tests for adaptive evidence paths, interruption/resume,
   duplicate suppression, failures, target immutability, and state safety.
5. Documentation of loop policy, terminal reasons, replay identity, raw-data
   boundaries, model authority limits, and the heuristic-only baseline.

## Goal-level acceptance criteria

- **G12-AC01 — Allowlisted dispatch:** The loop exposes no model-callable
  capability beyond G10's exact registry. A deterministic dispatcher validates
  model-proposed name and arguments against the registry, rejects unknown or
  malformed requests, and verifies the local-read-only effect before any call.
- **G12-AC02 — Adaptive local evidence:** Recorded hypotheses with different
  evidence gaps deterministically lead to different valid bounded local paths
  (for example discovery → provenance or provenance → granted excerpt). Every
  completed action has a G10 receipt and every non-initial action links to its
  antecedent reasoning result.
- **G12-AC03 — Bounded terminal behavior:** Iteration, wall-time, tool-call, and
  evidence-byte limits produce the defined terminal reasons. The graph cannot
  loop indefinitely, silently retry, or expand a G10 tool's authority.
- **G12-AC04 — Checkpoint/replay safety:** Compatible interruption/resume does
  not repeat completed model or tool calls. Changed HEAD, context policy,
  receipt/model/prompt/schema identity, grant scope, or budget ledger cannot
  reuse an incompatible checkpoint.
- **G12-AC05 — Duplicate and partial-failure containment:** Identical completed
  requests are suppressed or reused deterministically. Invalid model proposals,
  tool errors, malformed output, and exhausted budgets preserve earlier
  receipts/hypotheses and terminate or continue only through explicit policy.
- **G12-AC06 — Data and authority safety:** Checkpoints/traces exclude raw
  excerpts, raw source/history/patches, raw prompts/responses, credentials, and
  framework tool messages. Default/recorded/heuristic-only modes open no socket;
  no target module is imported or executed, and the target snapshot/status is
  unchanged.
- **G12-AC07 — Heuristic baseline and portability:** A model-disabled
  heuristic-only run completes its configured local path without model
  construction. Recorded replay and two injected `BaseChatModel` adapters use
  the same run/trace contracts without changing G10 or G11 domain schemas.
- **G12-AC08 — Compatibility and documentation:** Existing Phase 1, G10, and
  G11 APIs and CLI schemas remain compatible. Documentation covers dispatch
  policy, budgets, terminal reasons, replay/checkpoints, heuristic-only mode,
  and why an agent trace is not a cleanup authority.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G12-AC01 | Registry/effect/schema adversarial dispatcher tests and no-direct-call guard |
| G12-AC02 | Recorded fixture graph paths with exact receipt/reasoning antecedent trace assertions |
| G12-AC03 | Iteration, clock, tool-call, and byte-budget boundary fixtures with terminal reason snapshots |
| G12-AC04 | Interrupted graph call counters plus comprehensive identity invalidation matrix |
| G12-AC05 | Duplicate, malformed proposal/output, tool failure, and partial-receipt preservation tests |
| G12-AC06 | Socket/import/process guards, raw-content checkpoint scans, target snapshot/status assertions |
| G12-AC07 | Heuristic-only no-model guard and two-fake-model contract parity tests |
| G12-AC08 | Locked regression suite, compatibility snapshots, documentation review, `git diff --check` |

## Required verification commands

At minimum, the completion gate must run:

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_agent_loop.py tests/test_agent_dispatch.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G10's tools already account for evidence/call budgets. G12 must avoid a
  competing ledger: its aggregate budget state should compose G10 receipts and
  reject a request before dispatch when either boundary is exhausted.
- G11 graph caching is identity-safe for a single invocation but does not decide
  an action. G12 must explicitly link a reasoning proposal to each dispatch and
  preserve that link over checkpoint/resume.
- LangChain/Graph may represent tool calls and messages differently across
  versions. Keep framework adapters narrow and persist Sunset call/trace models,
  not framework objects.
- A bounded local excerpt can still contain sensitive repository data. G12 must
  keep it immediate-only even while using it to update compact model reasoning.
- Recorded paths demonstrate containment and replay, not autonomous quality or
  real-world tool-selection precision. G16 remains responsible for comparative
  evaluation and release thresholds.
