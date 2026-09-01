# Sunset local agent tools

G10 adapts Sunset's Phase 1 heuristics to LangChain's `BaseTool` interface. It
does not add a model, planner, ReAct loop, or autonomous behavior. The existing
scanner, compatibility collector, provenance collector, artifact store, and
domain models remain authoritative; the wrappers enforce capability scope and
return checkpoint-safe receipts.

## Catalog

Run the context-free catalog command:

```bash
uv run --locked sunset tools --format json
```

The catalog exposes exactly:

| Tool | Validated model input | Capability |
| --- | --- | --- |
| `sunset_discover_candidates` | none | Run the context-selected deterministic collector at the bound HEAD |
| `sunset_get_candidate_provenance` | `candidate_id` | Collect or reuse local Git evidence and grant its artifact IDs |
| `sunset_read_evidence_excerpt` | granted `artifact_id`, byte `offset`, optional `length` | Return a byte-bounded transient evidence slice |

Repository paths, store paths, URLs, network modes, credentials, commands, and
approval choices are absent from all model-facing schemas. Every tool declares
the same machine-readable effect: `local_read_only`, no network, no target
writes, no target-code execution, and no approval requirement.

## Trusted setup

Application code binds authority before constructing the registry:

```python
from sunset.agent_tools import ToolExecutionContext, create_tool_registry

context = ToolExecutionContext.create(
    "/path/to/repository",
    store_path="/path/outside/repository/sunset-store",
    collector="pytest",
    max_tool_calls=12,
    max_evidence_bytes=65_536,
    max_excerpt_bytes=8_192,
)
registry = create_tool_registry(context)
tools = registry.tools
```

The context pins repository identity and committed HEAD, operates in offline
mode, rejects a store inside the target repository, and owns the evidence-grant
and budget ledgers. Both `tool.invoke({...})` and `await tool.ainvoke({...})`
return the same validated observation shape. Supported validation, Git,
artifact, and budget failures are structured receipts instead of exceptions at
the tool boundary.

## Receipts, evidence, and checkpoints

Every invocation returns an observation with a normalized `receipt`. The
receipt records contract version, tool, deterministic invocation ID,
repository identity and HEAD, status, compact result, evidence references,
structured failures and uncertainties, declared effects, and deterministic
budget debit/remaining values.

Invocation identity includes canonical input, contract version, repository
identity and HEAD, collector, execution-policy fingerprint, current evidence
grants, and pre-call budget-ledger state. Equivalent recreated contexts can
reuse byte-identical discovery/provenance receipts and immutable artifacts;
changing any identity input prevents incompatible reuse. Measured duration and
observed cache reuse live only in `context.telemetry`, outside receipt identity.

Raw source, patches, history, and evidence excerpts do not belong in graph
state. The excerpt tool returns text in the immediate observation's
`transient_content`, while its receipt retains only the artifact ID, requested
range outcome, digest, byte length, total length, and truncation flag. A graph
node may reason over that immediate observation, but it must checkpoint only
`observation["receipt"]`.

Artifact IDs are capabilities. The excerpt tool accepts only IDs granted by a
prior provenance receipt in the same bound context, verifies content integrity,
and enforces per-call and cumulative byte limits. Invalid IDs, traversal-like
strings, ungranted or cross-store IDs, unsafe ranges, missing/corrupt artifacts,
and exhausted budgets disclose no bytes.

## Interpretation boundary

Candidate discovery, provenance, and a readable excerpt are evidence leads—not
proof that rationale expired or cleanup is safe. G10 performs no semantic
inference and makes no recommendation. Later goals may place a replaceable
model runtime and a bounded loop above this registry, but deterministic policy
continues to authorize tools and human approval continues to guard validation
and cleanup.
