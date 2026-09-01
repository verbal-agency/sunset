# Sunset roadmap

Status values are `active`, `proposed`, `blocked`, and `complete`. Exactly one
goal may be active.

## Phase 1 — Deterministic foundation

| Goal | Status | Objective | Dependencies |
| --- | --- | --- | --- |
| [G01](goals/G01-deterministic-scanner.md) | complete | Build the project foundation and deterministic pytest-marker scanner | None |
| [G02](goals/G02-provenance-artifacts.md) | complete | Trace candidate provenance and persist content-addressed evidence | G01 |
| [G03](goals/G03-broader-deterministic-collectors.md) | complete | Collect dependency/version guards and compatibility shims deterministically | G02 |
| [G04](goals/G04-langgraph-investigation-memory.md) | complete | Investigate rationale with LangGraph and compact, checkpointed memory | G03 |
| [G05](goals/G05-external-assumption-verification.md) | complete | Verify external assumptions using replaceable evidence providers | G04 |
| [G06](goals/G06-approved-sandbox-validation.md) | complete | Validate candidate removal in an approved disposable sandbox | G05 |
| [G07](goals/G07-case-file-skeptical-review.md) | complete | Produce citation-verified case files with a skeptical review stage | G06 |
| [G08](goals/G08-benchmark-langsmith-evaluation.md) | complete | Benchmark quality and memory efficiency with LangSmith | G07 |
| [G08a](goals/G08a-langchain-public-corpus.md) | complete | Collect a public, pinned LangChain ecosystem evaluation corpus | G08 |
| [G09](goals/G09-end-to-end-release.md) | complete | Package a polished, reproducible end-to-end Sunset release | G08a |

## G01 — Deterministic scanner

**Purpose:** Establish a trustworthy, zero-model discovery boundary and the
stable candidate contract on which every later investigation depends.

Establish a tested Python package and CLI that discovers supported pytest
markers without network or model access. Advances OUT-01 and lays the typed
domain foundation for every later goal.

## G02 — Provenance and artifact storage

**Purpose:** Make later reasoning auditable and reusable by preserving raw
evidence outside model context with explicit source and validity metadata.

For each candidate, resolve repository identity, HEAD, blame, introduction
commit, and focused history. Store raw artifacts by content hash with source and
repository provenance. Add immutable-artifact reuse and
repository-state invalidation. Advances OUT-02 and SCN-05.

Expected completion evidence: fixture repositories demonstrate rename-aware
history where feasible, repeated retrieval reuses immutable artifacts, and a
changed HEAD invalidates only mutable repository views.

## G03 — Broader deterministic collectors

**Purpose:** Expand Sunset beyond disabled tests while preserving a
high-precision, zero-model candidate boundary for code whose compatibility
assumption may have expired.

Recognize a deliberately bounded set of static Python dependency/version guards
and compatibility shims, emit a versioned candidate contract with exact source
and Git provenance, and make unsupported dynamic forms explicit. This advances
OUT-01 across the code paths that tests alone cannot represent.

Expected completion evidence: fixture repositories demonstrate recognized
runtime and dependency-version guards plus import-fallback compatibility shims;
unrelated conditionals and dynamic forms are not fabricated as candidates.

## G04 — LangGraph investigation and efficient memory

**Purpose:** Support long-running rationale investigations that can resume,
remain within token budgets, and retain provenance without replaying full
histories into every model call.

Implement the bounded rationale-recovery graph, structured investigation ledger,
selective artifact retrieval, checkpoint/resume, per-node token accounting, and
adaptive evidence expansion. It must distinguish facts, inferences,
contradictions, unknowns, and rejected hypotheses. Advances OUT-02, OUT-03,
SCN-03, and SCN-04.

G02's blame-backed `introduction_commit` is a provenance lead, not proof of the
first semantic rationale. G04 must retain that distinction and carry shallow or
otherwise incomplete Git history forward as an explicit unknown.

Expected completion evidence: an interrupted fixture investigation resumes;
unchanged artifacts are not fetched twice; no graph prompt contains an entire
raw history; a full-context comparison is recorded for later benchmarking.

## G05 — External assumption verification

**Purpose:** Distinguish code that is merely old from code whose causal
justification has actually expired.

Add replaceable GitHub and release-note providers that resolve explicit issue,
pull-request, and dependency-version references. Extract the assumption that
justified a marker and determine whether evidence supports `active`, `expired`,
or `unknown`. Network failures must produce an inconclusive result, not a guess.
Advances SCN-01 through SCN-03.

Expected completion evidence: recorded provider fixtures cover fixed, open,
missing, and contradictory external evidence without live-network dependence in
the default test suite.

## G06 — Approved sandbox validation

**Purpose:** Turn a probabilistic expiry hypothesis into reproducible empirical
evidence without risking the maintainer's working repository.

Introduce the human approval boundary and a disposable worktree/container
adapter. Remove only the target marker, run narrow and configured broader tests,
repeat tests to detect flakiness, and record a reproducible environment manifest.
Never mutate the source working tree. Advances OUT-04, SCN-01, SCN-02, and
SCN-07.

Expected completion evidence: approved experiments classify confirmed,
still-failing, flaky, environment-error, and inconclusive results; denied
approval performs no mutation; target Git status remains unchanged.

## G07 — Case file and skeptical review

**Purpose:** Make every recommendation conservative, challengeable, and useful
to a human reviewer instead of asking them to trust an agent narrative.

Add a separate skeptical review that searches for disconfirming evidence and a
finalizer that reloads raw evidence for every material claim. Produce Markdown
and JSON case files containing rationale, assumption status, experiment result,
confidence, residual risk, and citations. Advances OUT-02 and SCN-01 through
SCN-03.

Expected completion evidence: every report claim resolves to stored raw
evidence; deliberately unsupported claims are rejected; reports never equate
passing tests with proof of safety.

## G08 — Historical benchmark and LangSmith evaluation

**Purpose:** Prove that Sunset identifies genuine cleanup opportunities and that
its memory savings do not conceal a material loss in decision quality.

Build a versioned corpus from historical cleanup changes plus still-required
negative cases. Compare full-history and structured-memory configurations using
deterministic evaluators and calibrated semantic evaluators. Track candidate
precision, rationale recovery, classification, citation accuracy, unsupported
claims, tokens, latency, and cost. Advances OUT-03, OUT-05, and SCN-06.

Expected completion evidence: reproducible experiments run over at least 20
cases, publish per-case traces, and explicitly pass or fail the SCN-06 target.

## G09 — End-to-end release

**Purpose:** Convert the validated components into a reproducible public product
that demonstrates Sunset's thesis, safety model, and measured limitations.

Polish the CLI and a minimal investigation viewer, document privacy and safety,
record a short demonstration, and run Sunset against a meaningful open-source
repository. Publish measured limitations and contribute a cleanup only when the
evidence genuinely supports it. Advances all project outcomes and completes the
canonical scenarios end to end.

Expected completion evidence: clean-install instructions work, the demo can be
reproduced from a pinned repository revision, and public results include both
successful and inconclusive cases.

## Phase 2 — Bounded agentic investigation

Phase 2 makes the Phase 1 heuristics and evidence services usable as safe tools
inside a LangChain ecosystem agent. G10 is complete and G11 is the only fully
specified proposed goal. Later goals remain scoped outlines: when each
predecessor completes, the cycle handoff must refine only the next eligible goal
using the evidence and risks discovered so far.

Refinement protocol: the cycle that completes an active Phase 2 goal creates a
detailed specification and roadmap link for only the next eligible goal, keeps
that next goal `proposed`, and carries forward only findings routed to it. A
later user-authorized cycle may change that goal to `active`. The outlines below
are planning boundaries, not frozen acceptance criteria.

| Goal | Status | Objective | Dependencies |
| --- | --- | --- | --- |
| [G10](goals/G10-agent-tool-contracts.md) | complete | Expose local deterministic evidence operations as typed, scoped LangChain tools | G09 |
| [G11](goals/G11-model-runtime-structured-reasoning.md) | proposed | Add a replaceable chat-model runtime and one recorded structured reasoning step | G10 |
| G12 | proposed | Build a bounded, resumable planner–tool–observation loop over local evidence | G11 |
| G13 | proposed | Let the agent research external assumptions through recorded-first provider tools | G12 |
| G14 | proposed | Pause and resume agentic investigations across the human validation boundary | G13 |
| G15 | proposed | Add an independent skeptical reviewer and citation-verified agentic case file | G14 |
| G16 | proposed | Evaluate and package the agentic vertical slice with LangSmith and public evidence | G15 |

### G10 — Agent-ready deterministic tool contracts

**Purpose:** Turn the proven Phase 1 heuristics into a safe capability boundary
that an agent can use without bypassing provenance, budgets, or human control.

The [detailed G10 specification](goals/G10-agent-tool-contracts.md) is complete.
It introduced the safe local capability boundary without a model call or
autonomous loop.

### G11 — Replaceable model runtime and structured reasoning

**Purpose:** Introduce probabilistic interpretation behind an explicit provider
boundary without allowing a model to execute tools or become evidence.

The [detailed G11 specification](goals/G11-model-runtime-structured-reasoning.md)
is proposed. It may be activated by a later user-authorized cycle; this G10
handoff does not begin its implementation.

**Objective:** Add a LangChain chat-model adapter, recorded replay provider, and
one LangGraph reasoning node that converts compact tool receipts into a
versioned hypothesis, cited supporting or contradicting evidence, open
questions, and proposed next tool names.

**Scope:** Structured output validation; prompt and model versioning; token,
latency, and cost accounting; model-disabled, recorded, and explicitly
configured live modes; checkpoint-safe replay and structured provider failure.

**Exclusions:** Executing model-proposed tools, autonomous iteration, live
external research, validation requests, skeptical multi-agent review, or final
recommendations.

**Expected exit evidence:** Recorded responses are deterministic; malformed or
failed responses become structured `inconclusive` evidence; no prompt contains
an entire raw history; disabling the model preserves Phase 1 behavior; a second
fake `BaseChatModel` works without domain changes. Advances OUT-02, OUT-03,
OUT-06, OUT-07 and SCN-03, SCN-04, SCN-09, SCN-10.

### G12 — Bounded local-evidence agent loop

**Purpose:** Allow the investigator to choose evidence adaptively while keeping
every action allowlisted, observable, resumable, and budgeted.

**Objective:** Build a LangGraph planner–tool–observation loop that may execute
G10's local read-only tools, revise structured hypotheses, and stop for
completion, insufficient evidence, error, or budget exhaustion.

**Scope:** Iteration and tool-call budgets; deterministic tool dispatch;
duplicate-call suppression; graph interrupts and resume; terminal-reason
contracts; compact working-memory updates; model and tool invocation receipts.

**Exclusions:** Live or recorded external-provider tools, validation execution,
arbitrary shell or filesystem tools, multi-agent debate, and cleanup proposals.

**Expected exit evidence:** Different recorded evidence gaps cause different
bounded local tool paths; invalid or repeated calls are contained; interruption
does not repeat completed calls; target state remains unchanged; partial failure
preserves earlier evidence. Advances OUT-02, OUT-03, OUT-06 and SCN-03 through
SCN-05, SCN-08, SCN-09.

### G13 — Agentic external-assumption research

**Purpose:** Give the agent current causal evidence so it can distinguish old
code from code whose external justification actually expired.

**Objective:** Add typed provider tools for explicit GitHub, release-note, and
dependency-version references, allowing the bounded loop to select and compare
recorded-first external evidence while retaining contradictions and unknowns.

**Scope:** Provider-tool schemas and effect declarations; reference extraction;
recorded fixtures; opt-in live reads with credentials, rate and request budgets;
dependency-range evidence; source ranking without suppressing disagreement.

**Exclusions:** General web browsing, search without a candidate-linked lead,
enterprise connectors, external writes, validation, or treating issue closure
as proof of safe removal.

**Expected exit evidence:** Fixed, active, missing, contradictory, rate-limited,
and failed evidence paths produce cited structured outcomes; default tests and
demos are offline; live access is explicit and budgeted. Advances OUT-02,
OUT-06, OUT-07 and SCN-01 through SCN-03, SCN-08, SCN-09.

### G14 — Human-gated agentic validation

**Purpose:** Let an investigation seek empirical evidence without allowing an
agent to authorize code execution or mutate the maintainer's repository.

**Objective:** Allow the graph to produce a bounded validation request, pause at
a human decision, and on approval resume through G06's disposable validation
adapter with the result returned as a tool receipt.

**Scope:** Versioned request and decision contracts; configured command-template
selection; graph interrupts; approve and deny flows; environment/result
fingerprints; idempotent resume; target-state verification.

**Exclusions:** Agent-invented shell commands, implicit approval, target working-
tree changes, automatic cleanup, pull requests, or replacing the disposable
validation boundary.

**Expected exit evidence:** Denial executes nothing; approval runs only the
reviewed plan in a disposable clone; resume cannot duplicate an experiment;
confirmed, failing, flaky, environment-error, and inconclusive results remain
artifact-backed. Advances OUT-04, OUT-06 and SCN-01, SCN-02, SCN-07, SCN-09,
SCN-11.

### G15 — Skeptical agentic review and case files

**Purpose:** Challenge the investigator's best explanation before presenting a
cleanup recommendation to a maintainer.

**Objective:** Add an independently prompted skeptical reviewer that can inspect
the cited ledger, request bounded read-only evidence, record objections, and
hand a reconciled result to the deterministic citation-verifying finalizer.

**Scope:** Separate reviewer state and budget; disconfirming-evidence requests;
investigator/reviewer disagreement; unsupported-claim rejection; JSON,
Markdown, and HTML agentic case-file fields; human decision boundary.

**Exclusions:** Hidden chain-of-thought capture, reviewer access to validation
approval, majority-vote authority, automatic edits, or uncited narrative claims.

**Expected exit evidence:** Seeded unsupported, contradictory, and omitted-risk
claims are blocked or surfaced; every material final claim resolves to raw
evidence; passing validation alone never establishes safety. Advances OUT-02,
OUT-05, OUT-06 and SCN-01 through SCN-03, SCN-07 through SCN-09.

### G16 — Agentic evaluation and Phase 2 release

**Purpose:** Determine whether bounded agency adds trustworthy investigative
value over the deterministic baseline before presenting it as a product
capability.

**Objective:** Trace and evaluate heuristic-only and agentic configurations with
LangSmith-compatible experiments, declare release thresholds before the final
run, and package a reproducible agentic demonstration with measured limitations.

**Scope:** Versioned public evaluation cases; per-node and per-tool traces;
rationale, classification, citation, unsupported-claim, tool-use, token, cost,
latency, interruption, and approval metrics; recorded CI replay; opt-in live
evaluation; CLI/viewer release polish and pinned public demonstration.

**Exclusions:** Hiding failed thresholds, claiming fixture results prove
production precision, new collector families, enterprise connectors, automatic
cleanup, or external publication without separate human authorization.

**Expected exit evidence:** SCN-12 explicitly passes or fails predeclared
thresholds; heuristic regressions are visible; public successful, retained, and
inconclusive cases are reproducible; privacy, cost, model, and sandbox limits are
published. Advances OUT-03, OUT-05 through OUT-07 and SCN-01 through SCN-12.
