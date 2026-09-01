# Bounded local-evidence loop

G12 joins the existing G10 local tools and G11 structured reasoning step into
a small, resumable LangGraph loop. It is a library contract, not a CLI agent or
a cleanup recommender.

## Authority and dispatch

`LocalEvidenceAgentLoop` receives a pre-bound `ToolExecutionContext`. Its sole
dispatcher holds exactly that context's G10 registry and invokes only a typed
`BaseTool` wrapper after checking:

- the requested name is in the exact G10 registry;
- Pydantic accepts the complete arguments;
- the tool still declares the `local_read_only` effect; and
- the completed-call ledger and both loop/G10 budgets permit the request.

G11 intentionally returns proposed tool *names*, not untrusted repository or
store arguments. G12 therefore derives any missing arguments deterministically
from receipts and evidence grants already authorized by the context: it can
choose the first stable discovery candidate for provenance, or an unconsumed
granted artifact for a bounded excerpt. A future model contract may provide
arguments only through the same `ToolRequest` validation boundary.

Every non-initial call records the reasoning invocation that anteceded it. The
one allowed initial action is deterministic discovery when the receipt ledger is
empty. Unknown names, malformed arguments, changed effect metadata, and missing
reasoning antecedents become structured dispatch observations without a call.

## Modes, limits, and terminal reasons

`AgentLoopConfig(mode="heuristic")` creates no model runtime. It performs the
fixed local discovery/provenance path and is the offline baseline. `recorded`
and `live` require an injected G11 `ModelRuntime` of the matching mode; live
still has no provider selection or credential discovery.

The loop limits graph transitions, wall time, aggregate tool calls, aggregate
excerpt bytes, and the underlying G10 call/byte budgets. It finishes with one
of these versioned terminal reasons:

- `completed` or `insufficient_evidence`
- `tool_error`, `model_error`, or `tool_budget_exhausted`
- `iteration_budget_exhausted`, `wall_time_exhausted`, or `interrupted`

There are no automatic retries. Partial G10 receipts remain in the ledger; a
later structured failure cannot erase them or fabricate a conclusion.

## Checkpoints and data boundary

After each reasoning or tool transition, the loop writes an immutable state
view in the existing external artifact store. The state contains receipt IDs
and compact receipts, structured G11 results, call records, budget counters,
trace references, and terminal reason. It does not contain framework messages,
raw prompts or responses, raw source/history/patches, credentials, or an
excerpt's transient bytes.

Resume accepts a prior `run_id` only when repository identity/HEAD, context
policy, initial/current evidence grants, loop/model/prompt/output identity, and
current G10 budget ledger are compatible. A compatible interrupted run resumes its pending action without
repeating its completed model or tool observation. A changed identity raises an
explicit incompatibility error rather than using stale state.

An agent trace records control flow and evidence receipts; it is not evidence
that code is safe to remove. External research, validation, edits, approval,
and cleanup recommendations remain outside G12.
