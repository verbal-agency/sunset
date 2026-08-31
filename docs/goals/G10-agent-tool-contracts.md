# G10 — Agent-ready deterministic tool contracts

**Status:** active
**Dependencies:** G09

## Purpose

Turn Sunset's proven Phase 1 heuristics into a safe capability boundary that a
LangChain ecosystem agent can use without bypassing deterministic discovery,
provenance, evidence scoping, budgets, or human control.

## Objective

Create a versioned LangChain tool registry that wraps Sunset's existing local
deterministic evidence operations in typed, effect-declared, scope-limited tool
contracts, without adding a model call or autonomous agent loop.

## Project alignment

- Advances OUT-01, OUT-02, OUT-06, and OUT-07.
- Establishes the tool boundary required by SCN-08 and SCN-09 while preserving
  SCN-03 through SCN-05 and SCN-07.
- Prepares G11 to add replaceable structured model reasoning without exposing
  arbitrary repository, filesystem, network, or execution capabilities.

## Architecture constraints to preserve

- Existing scanner, provenance, artifact-store, and domain models remain the
  source of truth. Tool wrappers adapt them; they do not reimplement heuristics.
- Tools are bound to a trusted execution context containing the target,
  committed HEAD, external store, allowed evidence IDs, and budgets. A model
  cannot supply or change repository and store paths through tool arguments.
- The G10 registry contains local read-only tools only. It performs no model
  call, live network request, target-code import, test execution, validation, or
  target-repository write.
- Raw artifact bodies remain outside persisted graph state. A bounded evidence
  excerpt may exist as a transient observation, but the checkpoint-safe receipt
  retains only its artifact ID, byte range, digest, length, and truncation
  metadata.
- Every tool declares effects and approval requirements independently of its
  prose description. Runtime policy—not a model—authorizes dispatch.
- Supported failures return structured partial receipts. They do not erase
  successful evidence or become an uncaught exception at the future agent
  boundary.
- Tool schema version, canonical inputs, repository identity and HEAD,
  execution-policy fingerprint, evidence grants, and budget-ledger state
  participate in deterministic invocation identity.

## In scope

### Bound execution context

Add a typed context constructed by trusted application code with:

- resolved target repository and committed HEAD;
- repository identity and collector family;
- external artifact-store root;
- an allowlist of evidence artifact IDs granted by prior tool receipts;
- maximum tool calls and cumulative evidence bytes;
- maximum bytes for one transient excerpt;
- network mode fixed to `offline` for all G10 tools; and
- deterministic policy and budget-ledger fingerprints used by invocation
  identity.

Tool input schemas must not contain repository paths, artifact-store paths,
commands, URLs, credentials, approval decisions, or network-mode overrides.

### Initial local tool registry

Expose exactly these capabilities through LangChain `BaseTool`-compatible
contracts:

1. **`sunset_discover_candidates`** — run the selected existing deterministic
   collector at the bound committed snapshot and return compact candidate
   records plus structured scan errors.
2. **`sunset_get_candidate_provenance`** — collect or reuse existing local Git
   provenance for one candidate ID and return its artifact references,
   introduction-provenance caveat, and uncertainties without raw artifact
   bodies.
3. **`sunset_read_evidence_excerpt`** — read a configured bounded slice from one
   artifact ID already granted to the current context. Return the slice only as
   transient observation content and a checkpoint-safe slice receipt. Reject
   ungranted IDs, unsafe ranges, and requests beyond the remaining byte budget.

The registry must be additive. Existing Python APIs and CLI commands retain
their Phase 1 behavior.

### Versioned tool contracts

Define validated input, effect, observation, and receipt schemas. Every receipt
must include:

- tool-contract schema version and tool name;
- deterministic invocation ID;
- repository identity and committed HEAD;
- terminal status: `success`, `partial`, `error`, or `budget_exhausted`;
- compact result payload and evidence artifact or slice references;
- structured errors and uncertainties;
- declared effect class and approval requirement;
- deterministic evidence-byte debit and remaining-budget values.

The persisted receipt must serialize to normalized JSON and must not contain raw
source, patch, history, provider-response, test-output, or excerpt text.
Non-deterministic invocation telemetry such as measured duration, cache-hit
observation, and framework-generated run IDs must be recorded separately from
the normalized receipt and must not participate in evidence or cache identity.

### Tool catalog and library surface

- Declare `langchain-core` as a direct, locked project dependency because G10
  imports its public tool interfaces directly.
- Provide a registry factory bound to the trusted execution context rather than
  a process-global mutable registry.
- Support normal LangChain synchronous invocation and asynchronous invocation
  with the same validated result semantics.
- Add `sunset tools --format json` to list tool names, versions, input schemas,
  effects, approval requirements, and availability without opening a target
  repository or invoking a tool.
- Document how later graphs consume transient observations while checkpointing
  only safe receipts.

## Explicit exclusions

- Any LLM, embedding, reranker, model prompt, model credential, or semantic
  inference.
- A planner, ReAct loop, autonomous tool selection, or model-generated tool
  call; these begin in G11 and G12.
- GitHub, release-note, dependency-registry, web-search, or other network tools;
  those belong to G13.
- Validation requests, shell commands, test execution, disposable clones, or
  approval decisions; those belong to G14.
- Skeptical multi-agent review, final agentic recommendations, LangSmith tracing,
  or comparative agent evaluation.
- Changing scanner recognition rules, candidate IDs, provenance semantics,
  case-file recommendations, or existing CLI output schemas.

## Deliverables

1. Versioned tool input, effect, transient-observation, persisted-receipt, and
   execution-context models.
2. Context-bound registry with the three local read-only LangChain tools.
3. Deterministic invocation identity, evidence-scope enforcement, tool/byte
   budget accounting, and separate non-authoritative invocation telemetry.
4. JSON tool-catalog CLI and agent-tool safety documentation.
5. Positive, partial-failure, adversarial-scope, cache, sync/async, and target-
   immutability tests using isolated Git fixtures.

## Goal-level acceptance criteria

- **G10-AC01 — Typed catalog:** A context-bound registry exposes exactly the
  three specified tools as LangChain-compatible tools. Each has a versioned
  validated input schema and machine-readable effect metadata stating local
  read-only behavior, no network, no target writes, no target-code execution,
  and no approval requirement.
- **G10-AC02 — Domain parity:** Discovery and provenance tool results preserve
  the existing domain outputs, stable candidate IDs, artifact references,
  structured uncertainties, and partial errors for the same committed HEAD.
  Repeated equivalent invocations produce normalized byte-identical persisted
  receipts and deterministic invocation IDs without duplicating immutable raw
  artifacts.
- **G10-AC03 — Bound authority:** Tool-call arguments cannot select another
  repository, store, network mode, command, or credential. The target and store
  are fixed by trusted context; stores inside the target are rejected; default
  tool invocation opens no socket, imports no target module, executes no target
  code, launches no process except bounded read-only Git commands, and leaves
  tracked and untracked target state unchanged.
- **G10-AC04 — Evidence capability scope:** The excerpt tool can read only an
  artifact ID granted by a prior receipt for the bound investigation. Valid
  slices obey per-call and cumulative byte budgets and report exact byte range,
  digest, length, and truncation. Ungranted IDs, invalid ranges, cross-store
  paths, traversal attempts, and exhausted budgets return structured failures
  without disclosing bytes.
- **G10-AC05 — Checkpoint-safe receipts:** Persisted tool receipts round-trip
  through normalized JSON and a LangGraph checkpoint fixture without containing
  raw source, diff, history, or excerpt text. Transient excerpt content is
  available only in the immediate observation object and is demonstrably absent
  from the serialized receipt and checkpoint.
- **G10-AC06 — Failure and budget containment:** Parse errors, incomplete or
  shallow Git history, missing candidates, missing or corrupted artifacts,
  budget exhaustion, and supported Git failures produce `partial`, `error`, or
  `budget_exhausted` receipts while retaining successful evidence. Supported
  failures do not escape as unstructured exceptions from sync or async tool
  invocation.
- **G10-AC07 — Cache and invalidation identity:** Invocation identity and reuse
  include tool-contract version, canonical input, repository identity and HEAD,
  collector, execution-policy fingerprint, evidence grants, and budget-ledger
  state. Recreated equivalent contexts produce the same receipt; changed HEAD,
  schema version, collector, evidence scope, policy, or consumed budget cannot
  reuse an incompatible receipt or bypass a budget check.
- **G10-AC08 — Compatibility and discoverability:** Existing deterministic CLI
  tests and JSON schemas remain unchanged. `sunset tools --format json` is
  deterministic and makes no repository, network, model, or artifact-store
  access. Documentation explains tool effects, evidence scoping, transient
  versus persisted data, budgets, and why tools are not proof of safe cleanup.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G10-AC01 | Registry/catalog schema tests and effect-metadata snapshot |
| G10-AC02 | Wrapper-versus-domain parity fixtures, deterministic receipt comparison, artifact reuse counts |
| G10-AC03 | Input-schema inspection, socket/import guards, a subprocess allowlist permitting only read-only Git, repository snapshot and Git-status assertions |
| G10-AC04 | Granted-slice positives plus ungranted, traversal, range, cross-store, and byte-budget adversarial tests |
| G10-AC05 | Observation/receipt separation test and checkpoint JSON raw-content scan |
| G10-AC06 | Parse, shallow-history, missing/corrupt artifact, budget, and Git-failure fixtures through sync and async invocation |
| G10-AC07 | Same-input reuse and HEAD/schema/collector/scope/policy invalidation matrix |
| G10-AC08 | Full locked regression suite, deterministic `sunset tools` CLI snapshot, documentation review, `git diff --check` |

## Required verification commands

At minimum, the completion gate must run:

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked sunset tools --format json
git diff --check
git status --short
```

The G10 cycle must also run its focused adversarial and checkpoint tests against
isolated fixture repositories and record criterion-by-criterion evidence before
changing G10 to `complete`.

## Carried-forward findings and risks

- `langchain-core` is currently transitive through LangGraph; importing it
  directly without declaring it would make the tool boundary packaging-unsafe.
  G10 must add a compatible direct constraint and update the lockfile.
- LangChain tool APIs can evolve. Sunset's versioned domain receipts must remain
  independent of framework message objects so later adapter changes do not
  migrate evidence or case-file schemas.
- An artifact ID is a capability to potentially sensitive raw data. The bound
  evidence allowlist and byte limits are security boundaries, not prompt
  conventions.
- Promisor, partial, and shallow Git clones may need unavailable objects. Tools
  must preserve existing structured uncertainty and must not silently fetch from
  a remote in this local-only goal.
- Synchronous and asynchronous LangChain invocation may schedule work
  differently. Deterministic IDs and receipts cannot depend on task ordering,
  timestamps, or framework-generated call IDs.
