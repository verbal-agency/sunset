# Sunset structured model runtime

G11 adds one bounded LangChain reasoning invocation. It is not an agent: it
cannot construct a G10 registry, invoke a tool, select an iteration, request
validation, or make a cleanup recommendation. It adapts provider output into a
framework-independent Sunset contract and labels every accepted hypothesis as
model-derived inference.

## Explicit modes

Trusted application code constructs `ModelRuntime` with one mode:

```python
from sunset.model_runtime import ModelRuntime, ModelRuntimeConfig

# Safe baseline: no model construction or call.
disabled = ModelRuntime(ModelRuntimeConfig(mode="disabled"))

# Deterministic local fixture replay for tests and demos.
recorded = ModelRuntime(
    ModelRuntimeConfig(mode="recorded", recorded_fixture_path="responses.json")
)

# Live access is explicit and requires an injected public LangChain adapter.
live = ModelRuntime(
    ModelRuntimeConfig(mode="live", model_identity="provider:model-v1"),
    model=my_base_chat_model,
)
```

Disabled and recorded modes open no socket and do not construct a live model.
Live mode is never inferred from an environment variable or the presence of a
credential; the caller must select it and inject a `BaseChatModel`. Sunset does
not store model credentials.

## Input and output boundary

`ReasoningRequest` contains only G10's checkpoint-safe `ToolReceipt` objects
and a bounded task. `TransientEvidence` is optional immediate-only input for an
artifact ID granted by those receipts. Its text must fit the G10-sized boundary.

Prompt assembly includes compact receipt fields and selected artifact metadata;
it omits artifact-store locations, raw source, patches, histories, provider
responses, unrelated environment data, and previous transcripts. Prompt text is
ephemeral. The persisted `ReasoningResult` contains no prompt, raw model
response, LangChain message, or transient text.

The accepted structured response has an `active`, `expired`, or `unknown`
assumption hypothesis; supporting, contradicting, or unknown claims; citations;
open questions; and optional names from G10's fixed tool catalog. Citation IDs
must appear in supplied receipt evidence, and proposed names must be catalog
members. Unsupported citations, tools, fields, enums, or oversized text produce
structured `inconclusive` output rather than a fabricated interpretation.

An `expired` hypothesis is not proof that code is safe to remove. It remains an
input for a later bounded loop, deterministic evidence checks, disposable
validation, skeptical review, and a human decision.

## Budgets, telemetry, and replay

`ModelRuntimeConfig` includes input/output token budgets, an optional provider
cost limit, and an optional timeout. Provider-reported usage is retained when
complete; otherwise Sunset records a separate deterministic estimate. Provider
cost may be unavailable and is represented as `null`, never guessed from text
or latency.

Normalized reasoning identity includes runtime, prompt, output-schema, model or
fixture, receipt, task, transient-content digest, and budget configuration.
`ReasoningGraph` uses that identity to reuse a completed compatible result. A
changed receipt, prompt/model/schema version, fixture, transient digest, mode,
or budget cannot reuse it.

Latency, framework run IDs, and graph cache observations live in runtime/graph
telemetry and are intentionally outside normalized results and cache identity.
The graph persists only its safe request/result state to the external artifact
store; it keeps transient evidence in memory only for the immediate node call.

## Recorded fixtures

Recorded mode reads local JSON shaped like:

```json
{
  "schema_version": "1",
  "response": {
    "assumption_status": "unknown",
    "summary": "More evidence is needed.",
    "claims": [],
    "open_questions": ["What external condition applies?"],
    "proposed_tools": ["sunset_read_evidence_excerpt"]
  },
  "usage": {"input_tokens": 42, "output_tokens": 18}
}
```

The fixture is replayed through exactly the same output validation used for a
live adapter. A malformed/missing fixture, provider exception, timeout,
cancellation, invalid response, budget exhaustion, or corrupt checkpoint
becomes a structured result that retains the original safe receipt IDs.
