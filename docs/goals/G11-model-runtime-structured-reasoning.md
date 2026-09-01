# G11 — Replaceable model runtime and structured reasoning

**Status:** proposed
**Dependencies:** G10 (complete)

## Purpose

Introduce probabilistic interpretation behind an explicit provider boundary so
Sunset can form evidence-linked hypotheses while ensuring that a model cannot
execute tools, become evidence, or weaken deterministic authority controls.

## Objective

Add a replaceable LangChain chat-model runtime, deterministic recorded replay,
and one LangGraph reasoning node that converts compact G10 tool observations
into a versioned structured hypothesis with cited support and contradiction,
open questions, and proposed G10 tool names without executing any proposal.

## Project alignment

- Advances OUT-02, OUT-03, OUT-06, and OUT-07.
- Establishes the model-portability and failure-containment boundary required
  by SCN-03, SCN-04, SCN-09, and SCN-10.
- Prepares G12 to add bounded deterministic dispatch around model proposals;
  G11 itself remains a single non-agentic reasoning step.

## Architecture constraints to preserve

- G10 receipts, artifact references, effect declarations, evidence grants, and
  budgets remain authoritative. Model output is a labeled inference and never
  raw evidence, tool authorization, validation approval, or a recommendation.
- The runtime depends on LangChain's public chat-model contract through an
  injected provider. Provider-specific framework messages do not enter Sunset's
  domain schemas or persisted reasoning result.
- Default and CI behavior is model-disabled or recorded replay. Live invocation
  requires explicit configuration and an injected model; it is never selected
  by credentials merely being present.
- Prompts use compact checkpoint-safe receipts and, when explicitly supplied to
  the immediate node, only G10-bounded transient observations. Full source,
  patches, histories, provider bodies, and transcripts remain outside graph
  state and checkpoints.
- Deterministic code validates structured output, citation scope, proposed tool
  names, budgets, and checkpoint identity. A malformed response or provider
  failure yields structured `inconclusive`, never a guessed claim.
- Prompt, model, output-schema, receipt, configuration, and budget versions
  participate in replay/checkpoint identity. Measured latency and unavailable
  provider cost remain explicit telemetry, not evidence or deterministic IDs.

## In scope

### Versioned reasoning contract

Define a framework-independent structured result containing:

- schema, prompt, and model-runtime versions;
- provider/model identity and deterministic reasoning invocation ID;
- terminal status: `success`, `inconclusive`, `disabled`, `error`, or
  `budget_exhausted`;
- one bounded rationale/assumption hypothesis labeled as model-derived;
- structured supporting, contradicting, and unknown claims whose citations are
  restricted to evidence IDs present in the supplied G10 receipts;
- open questions and proposed next tool names restricted to G10's catalog;
- structured validation/provider errors; and
- input/output token accounting, cost value or explicit unavailability, and
  checkpoint-safe budget remaining values.

No free-form chain of thought is requested or persisted. Concise hypothesis and
claim summaries are product outputs and must be citation-validated.

### Replaceable model runtime

Provide one trusted runtime factory with three explicit modes:

1. `disabled` — returns a structured disabled/inconclusive result without
   constructing or invoking a model;
2. `recorded` — replays versioned local response fixtures through the same
   structured validation path as a live response; and
3. `live` — invokes only an explicitly injected LangChain `BaseChatModel` under
   configured token/cost/time budgets.

Demonstrate portability with two behaviorally different fake `BaseChatModel`
implementations. Provider adapters may translate messages and usage metadata,
but Sunset's reasoning and evidence contracts must not change.

### Single LangGraph reasoning node

Add one node or one-node graph that assembles a bounded prompt, invokes the
runtime once, validates the result, and checkpoints only safe structured state.
It may emit proposed G10 tool names for later dispatch, but it cannot access a
tool registry, execute a proposal, retry autonomously, or iterate.

Checkpoint/resume must reuse an already completed compatible recorded/model
result and must not duplicate a live model call. Incompatible prompt, model,
schema, receipt, configuration, or budget identity must not reuse a result.

### Accounting and observability

Record provider-reported token usage when available and label deterministic
estimates separately when it is not. Enforce configured input/output limits
before accepting a reasoning result. Record latency and cost availability in
separate invocation telemetry so timing does not destabilize normalized replay
or checkpoint artifacts.

## Explicit exclusions

- Executing a model-proposed tool, choosing tools in a loop, duplicate-call
  suppression, autonomous retries, or multi-step planning; these belong to G12.
- New local collector capabilities, external-provider research, live web/GitHub
  tools, embeddings, vector stores, rerankers, or general retrieval.
- Validation requests, shell commands, target-code execution, disposable
  clones, approval decisions, file edits, cleanup recommendations, or pull
  requests.
- Skeptical multi-agent review, debate, case-file finalization, comparative
  LangSmith evaluation, or release claims.
- Persisting raw prompts that contain transient evidence, raw model provider
  responses, full transcripts, hidden chain of thought, or model credentials.

## Deliverables

1. Versioned reasoning input, output, failure, budget, and telemetry models.
2. Explicit disabled, recorded-replay, and injected-live model runtime factory.
3. One checkpoint-safe LangGraph reasoning node with prompt/output validation.
4. Recorded fixtures plus two fake `BaseChatModel` portability adapters.
5. Documentation for modes, evidence/citation rules, budgets, privacy, and the
   boundary between a reasoning proposal and deterministic tool authority.

## Goal-level acceptance criteria

- **G11-AC01 — Replaceable provider boundary:** One runtime factory supports
  explicit disabled, recorded, and injected-live modes. Two fake
  `BaseChatModel` implementations produce the same Sunset reasoning contract
  without changes to G10 or other domain models; provider message objects do
  not appear in persisted output.
- **G11-AC02 — Validated structured reasoning:** A successful recorded response
  yields the versioned hypothesis, labeled claim classes, scoped citations,
  open questions, and only catalog-valid proposed G10 tool names. Unknown
  citation IDs, unknown tools, extra fields, invalid enums, and oversized text
  are rejected into structured `inconclusive` or `error` results.
- **G11-AC03 — Evidence and prompt safety:** Prompt construction accepts compact
  G10 receipts and only explicitly supplied bounded transient content. Tests
  prove it excludes whole raw source/history/patch artifacts, artifact-store
  paths, credentials, unrelated environment data, and prior transcript text;
  persisted state contains neither transient content nor raw provider response.
- **G11-AC04 — Explicit modes and authority separation:** Disabled and recorded
  modes open no socket and invoke no live model. Live mode cannot run without
  explicit selection and an injected model. Proposed tools are data only: the
  node has no registry/dispatch capability and target/store state is unchanged.
- **G11-AC05 — Budget and telemetry containment:** Input/output token limits are
  enforced with provider usage distinguished from estimates; cost is a value or
  explicitly unavailable. Budget exhaustion returns structured partial state.
  Latency, cache observation, and framework run IDs remain outside normalized
  reasoning identity and evidence.
- **G11-AC06 — Replay and checkpoint identity:** Recorded fixtures replay
  byte-identically. An interrupted/reinvoked compatible one-node graph reuses a
  completed result without another model call, while changed prompt version,
  model identity, output schema, input receipts, mode/configuration, or budget
  state cannot reuse an incompatible checkpoint.
- **G11-AC07 — Failure containment:** Malformed JSON/structured output, provider
  exceptions, timeout/cancellation, missing recorded fixtures, absent usage
  metadata, and checkpoint decode errors return structured `inconclusive`,
  `error`, or `budget_exhausted` results without losing valid input receipts or
  escaping as unstructured sync/async node failures.
- **G11-AC08 — Compatibility and documentation:** Existing deterministic APIs,
  CLIs, G10 tool schemas, and heuristic-only workflows remain byte-compatible
  and credential-free. Documentation explains modes, prompt data flow,
  citation validation, accounting limitations, checkpoint contents, and why a
  model hypothesis is neither evidence nor a cleanup recommendation.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G11-AC01 | Runtime-factory mode tests and two-fake-`BaseChatModel` contract parity |
| G11-AC02 | Valid recorded fixture plus schema, citation, tool-name, enum, extra-field, and size adversarial tests |
| G11-AC03 | Prompt snapshot/size assertions, raw-content sentinels, checkpoint scan, environment/credential guards |
| G11-AC04 | Socket/model-call guards, explicit-live construction failures, no-dispatch test, target/store snapshots |
| G11-AC05 | Provider/estimated token fixtures, input/output exhaustion, cost-unavailable, normalized telemetry separation |
| G11-AC06 | Byte-identical replay, model call counter across checkpoint resume, identity invalidation matrix |
| G11-AC07 | Recorded malformed/missing cases and throwing/timeout fake models through sync and async graph paths |
| G11-AC08 | Full locked regression suite, public-contract snapshots, documentation review, `git diff --check` |

## Required verification commands

At minimum, the completion gate must run:

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_model_runtime.py tests/test_reasoning_graph.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G10 deliberately separates normalized receipts from non-deterministic
  telemetry and transient excerpts. G11 must preserve that split rather than
  serializing a convenient LangChain message or full observation into state.
- G10 invocation identity is independent of framework run IDs. G11 needs its
  own prompt/model/output-schema identity layered above receipt IDs; it must not
  alter G10 cache keys.
- `langchain-core` 1.6.1 is the current locked interface but may evolve. Keep
  provider translation narrow and test the public `BaseChatModel` contract
  instead of persisting framework internals.
- Provider token and cost metadata is not uniformly available. Missing values
  must be explicit and may not be fabricated from latency or text length.
- Recorded fixtures can prove determinism and containment, not live-model
  quality. Comparative quality claims and release thresholds remain G16 work.
