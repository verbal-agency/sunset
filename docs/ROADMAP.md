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

Phase 2 treats the completed G10–G14 work as a safety substrate: bounded
evidence access, provenance, external research, replay, human-gated experiments,
and validation receipts. The product focus now shifts to the epistemic model:
what condition code protects, which evidence can support or contradict it, and
which proof obligation remains before a human reviews a counterfactual change.

G16, G17, G18, G19, and G20 are complete. This completes the Phase 2
implementation substrate, including a deterministic calibration-gate contract;
it does **not** establish that Sunset's condition inferences are empirically
accurate or optimized. Phase 3 supplies that missing validation. Only the next
eligible goal is refined or activated by a cycle; later goals remain planning
boundaries and may be adjusted when predecessor evidence changes their
assumptions.

Refinement protocol: the cycle that completes an active Phase 2 goal creates a
detailed specification and roadmap link for only the next eligible goal, keeps
that next goal `proposed`, and carries forward only findings routed to it. A
later user-authorized cycle may change that goal to `active`. The outlines below
are planning boundaries, not frozen acceptance criteria.

### Execution-readiness rules

Luna or another implementation model may execute only the single roadmap entry
marked `active`. If no entry is active, it must stop after identifying the next
eligible proposal and request authorization. A detailed active-goal
specification must include an execution contract: expected implementation
surface, canonical contracts and invariants, fixture/test locations, side-effect
boundaries, and terminal conditions. Downstream proposals intentionally omit
those details until their predecessor supplies evidence; they are not safe to
execute as-is.

| Goal | Status | Objective | Dependencies |
| --- | --- | --- | --- |
| [G10](goals/G10-agent-tool-contracts.md) | complete | Expose local deterministic evidence operations as typed, scoped LangChain tools | G09 |
| [G11](goals/G11-model-runtime-structured-reasoning.md) | complete | Add a replaceable chat-model runtime and one recorded structured reasoning step | G10 |
| [G12](goals/G12-bounded-local-evidence-loop.md) | complete | Build a bounded, resumable planner–tool–observation loop over local evidence | G11 |
| [G13](goals/G13-agentic-external-assumption-research.md) | complete | Let the agent research external assumptions through recorded-first provider tools | G12 |
| [G14](goals/G14-human-gated-agentic-validation.md) | complete | Pause and resume agentic investigations across the human validation boundary | G13 |
| [G15](goals/G15-skeptical-agentic-review.md) | complete | Define protected-condition hypotheses, proof obligations, and temporal-debt taxonomy | G14 |
| [G16](goals/G16-claim-evidence-graph.md) | complete | Build claim–evidence graphs and conservative condition-status inference | G15 |
| [G17](goals/G17-controlled-context-expansion.md) | complete | Add bounded context expansion across code, history, and configuration relations | G16 |
| [G18](goals/G18-operational-internal-evidence.md) | complete | Add recorded-first operational/internal evidence providers | G17 |
| [G19](goals/G19-skeptical-review-case-files.md) | complete | Add skeptical review and citation-verified temporal-debt case files | G18 |
| [G20](goals/G20-calibration-release.md) | complete | Calibrate and release the temporal-condition investigator | G19 |

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
is complete. It introduced a replaceable single reasoning step without tool
dispatch or an autonomous loop.

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

The [detailed G12 specification](goals/G12-bounded-local-evidence-loop.md) is
complete. It introduced deterministic planner-to-tool dispatch, compact
checkpointed state, and a no-model heuristic baseline without granting a model
new authority.

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

The [detailed G13 specification](goals/G13-agentic-external-assumption-research.md)
is complete. It added an explicitly credentialed, recorded-first external-read
tool without granting a model URLs, hosts, credentials, or cleanup authority.

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

The [detailed G14 specification](goals/G14-human-gated-agentic-validation.md)
is complete. It added a human-scoped, replay-safe approval boundary without
giving models any execution authority.

### G15 — Temporal-debt epistemic model

**Purpose:** Give Sunset a falsifiable model of what historically contingent
code protects before adding more agents, providers, or case-file prose.

**Objective:** Define a versioned taxonomy of temporal-debt candidates,
protected-condition hypotheses, condition states, evidence roles, contradictions,
scope/freshness, and explicit proof obligations.

**Scope:** Domain contracts, deterministic normalization, fixture taxonomy,
condition-state transitions, and compatibility adapters from G10–G14 receipts.

**Exclusions:** New provider integrations, broader code access, validation
execution, reviewer agents, recommendations, edits, or final case files.

**Expected exit evidence:** Fixtures distinguish competing hypotheses,
contradictions, missing proof obligations, progress states, and bounded
validation scope without calling any condition safe. Advances OUT-02, OUT-06,
OUT-08 and SCN-01 through SCN-03, SCN-08, SCN-09.

The [detailed G15 specification](goals/G15-skeptical-agentic-review.md) is
complete.

### G16 — Claim–evidence graph and conservative inference

**Dependencies:** G15 (complete)

**Purpose:** Make evidence relationships and condition-status conclusions
auditable instead of treating citation presence or model confidence as proof.

**Objective:** Build a claim–evidence–contradiction graph with scope, freshness,
and proof-obligation rules, then derive conservative condition states.

**Scope:** Evidence-role normalization, source ranking without suppression of
disagreement, claim support tests, and receipt-to-graph adapters.

**Exclusions:** Operational provider integrations, arbitrary context expansion,
validation changes, reviewer agents, release claims, or automatic cleanup.

**Expected exit evidence:** The same evidence can support, contradict, or fail
to establish a claim based on declared scope; incompatible evidence yields an
explicit unknown rather than consensus. Advances OUT-02, OUT-06, OUT-08 and
SCN-01 through SCN-03, SCN-08, SCN-09.

**Unlocks:** A deterministic condition-status result that downstream context
expansion and operational providers can enrich without rewriting evidence
semantics.

The [detailed G16 specification](goals/G16-claim-evidence-graph.md) is
complete.

### G17 — Controlled context expansion

**Dependencies:** G16 (complete)

**Purpose:** Avoid a compact-receipt sensor bottleneck without granting models
arbitrary repository or system access.

**Objective:** Add allowlisted, relation-based expansion for AST parents,
callers/callees, same-commit changes, historical variants, and configuration
references under explicit budgets.

**Scope boundary:** Relation-specific, read-only expansions and receipts only.
Excludes operational providers, arbitrary file/system access, and mutation.

**Advances:** OUT-02, OUT-03, OUT-06, OUT-08; SCN-04, SCN-05, SCN-08, SCN-09.

**Unlocks:** Evidence requests that can name the missing repository relation
instead of guessing from a compact receipt.

The [detailed G17 specification](goals/G17-controlled-context-expansion.md) is
complete.

### G18 — Operational/internal evidence providers

**Dependencies:** G17 (complete)

**Purpose:** Make evidence such as support policy, deployment inventory,
configuration, runtime traces, and contracts first-class because external status
often cannot establish whether a protected condition still applies.

**Objective:** Add recorded-first, replaceable operational provider contracts
with explicit privacy, scope, freshness, and access policy.

**Scope boundary:** Explicitly configured support-policy, inventory,
configuration, contract, and runtime-telemetry sources. Excludes broad
enterprise crawling and external writes.

**Advances:** OUT-02, OUT-05, OUT-06, OUT-08; SCN-01 through SCN-03,
SCN-08, SCN-09.

**Unlocks:** Internal-condition verification that can distinguish upstream
status from deployment, customer, or support reality.

The [detailed G18 specification](goals/G18-operational-internal-evidence.md) is
complete.

### G19 — Skeptical review and temporal-debt case files

**Dependencies:** G18 (complete)

**Purpose:** Challenge the condition graph and proof obligations before a human
reviews a cleanup decision.

**Objective:** Add independent bounded review and citation-verified case-file
finalization.

**Scope boundary:** Challenge claims and proof obligations using the established
graph and receipts. Excludes reviewer approval authority, new evidence-source
classes, and automatic edits.

**Advances:** OUT-02, OUT-06, OUT-08; SCN-01 through SCN-03, SCN-07 through
SCN-09, SCN-11.

**Unlocks:** Human-readable case files whose claims and missing proof are
independently auditable.

The [detailed G19 specification](goals/G19-skeptical-review-case-files.md) is
complete.

### G20 — Calibration and temporal-condition release

**Dependencies:** G19 (complete)

**Purpose:** Build reproducible calibration and release-gate mechanics without
mistaking a small fixture for proof that Sunset improves temporal-debt decisions.

**Objective:** Implement versioned comparative-evaluation, metric, threshold,
and gate contracts that a later empirically adjudicated corpus can use to
measure protected-condition quality and false-removal risk.

**Scope boundary:** Versioned benchmark cases, declared release thresholds, and
reproducible recorded evaluation. Excludes claims that benchmark performance
proves production removability or authorizes automatic cleanup.

**Advances:** OUT-03, OUT-05, OUT-06, OUT-08; SCN-01 through SCN-03,
SCN-06, SCN-08 through SCN-12.

**Unlocks:** Deterministic gate mechanics and explicit limits for the Phase 3
empirical release decision.

The [detailed G20 specification](goals/G20-calibration-release.md) is complete.

## Phase 3 — Empirical validation and optimization

Phase 3 tests the product thesis: whether Sunset can infer a historically
contingent code path's protected condition, state what evidence is missing, and
produce better-calibrated handoffs than deterministic baselines. It does not
treat G20's calibration mechanics or historical outcomes as proof that a
condition label is true. The phase requires provenance-bound evaluation cases,
human adjudication with explicit reviewer-count limits, frozen comparison runs,
split-safe optimization, and an explicitly limited maintainer pilot. A later
second-review pass may strengthen, but is not required for the initial
single-reviewer validation.

G22 is complete as an implementation seam. G22a completed real pinned GitHub
artifact capture and offline replay. G22b completed a five-class
declared-support bundle before adjudication while leaving actual deployment
usage as a separate proof obligation. G23 now uses one owner-authorized human
reviewer and records its corpus as single-reviewer provisional; a second review
is a later strengthening step. G24 is complete with an offline baseline report
and six non-authoritative cross-repository reference fixtures. G25 is complete
with a split-safe optimization report; G26 is the only next eligible proposal
and owns the required breadth expansion. G27 remains the pilot planning
boundary.

The current marker/compatibility slice is intentionally a baseline, not the
product's coverage boundary. Before a maintainer pilot, Sunset must broaden
candidate discovery across repository-level temporal signals and at least one
additional language family while preserving the same provenance and uncertainty
contracts.

| Goal | Status | Objective | Dependencies |
| --- | --- | --- | --- |
| [G21](goals/G21-validation-corpus-protocol.md) | complete | Establish a provenance-bound validation-corpus protocol and offline audit | G20 |
| [G22](goals/G22-pinned-git-evidence-ingestion.md) | complete | Retrieve pinned Git source and patches as replayable evidence | G21 |
| [G22a](goals/G22a-real-github-artifact-capture.md) | complete | Prove real pinned GitHub artifact capture or document blocked connectivity | G22 + authorized network |
| [G22b](goals/G22b-current-support-evidence.md) | complete | Capture a declared-support evidence bundle without mutating G21 | G22a + owner-approved selections |
| [G22c](goals/G22c-retained-case-support-evidence.md) | complete | Capture declared-support evidence for a retained LangGraph compatibility shim | G22b + owner-approved retained-case selection |
| [G23](goals/G23-independent-adjudication.md) | complete | Capture single-reviewer provisional protected-condition labels and proof obligations | G22b/G22c + one owner-authorized human reviewer |
| [G24](goals/G24-frozen-baseline-evaluation.md) | complete | Compare frozen heuristic and agentic traces on G23 cases plus pinned cross-repository lifecycle references | G23 |
| [G25](goals/G25-split-safe-optimization.md) | complete | Optimize declared bounded components on development data and measure regressions on holdout data | G24 |
| [G26](goals/G26-broad-candidate-discovery.md) | proposed | Broaden repository-level temporal signals and add a bounded JavaScript/TypeScript adapter | G25 |
| [G27](goals/G27-maintainer-pilot-decision.md) | proposed | Run a limited maintainer pilot and publish an evidence-bounded product decision | G25 + G26 + pilot authorization |

### G21 — Validation corpus protocol and provenance audit

**Dependencies:** G20 (complete)

**Purpose:** Establish trustworthy evaluation inputs before measuring or
optimizing an epistemic system whose labels cannot safely be inferred from code
age or historical removals alone.

**Objective:** Define and enforce a versioned, provenance-bound corpus packet
and offline audit that separates a pinned historical outcome from an
unadjudicated protected-condition label, records required evidence and
exclusions, and fixes development/holdout partitions before later evaluation.

**Scope boundary:** Local schema, manifest, audit, CLI, fixtures, and
documentation only. Excludes model evaluation, label adjudication, live
collection, optimization, and any claim about Sunset quality.

**Advances:** OUT-02, OUT-05, OUT-08; SCN-01 through SCN-03 and SCN-12.

**Unlocks:** A replayable, leakage-controlled input contract that G22 and
G22a can use without conflating provenance with ground truth.

The [detailed G21 specification](goals/G21-validation-corpus-protocol.md) is
complete. G22 completed the evidence-ingestion prerequisite for adjudication.

### G22 — Pinned Git evidence ingestion

**Dependencies:** G21 (complete)

**Purpose:** Make corpus pointers inspectable by retrieving pinned source and
diff artifacts instead of asking reviewers to trust commit subjects.

**Objective:** Add a replaceable, recorded-first Git evidence provider with an
explicit bounded live GitHub seam, artifact-backed receipts, replay identity,
and a CLI for manifest-bound source/patch retrieval.

**Scope boundary:** Pointer-derived blob/patch retrieval, fixture/live adapter,
content-addressed persistence, CLI, and tests. Excludes adjudication labels,
model behavior, general web search, clones, execution, and mutation.

**Advances:** OUT-02, OUT-05, OUT-06, OUT-08; SCN-01 through SCN-05,
SCN-08, and SCN-09.

**Unlocks:** Inspectable evidence packets for G23's human adjudication.

The [detailed G22 specification](goals/G22-pinned-git-evidence-ingestion.md) is
complete. Its recorded-first provider and explicit live seam are now available
to the real-capture proof in G22a.

### G22a — Real GitHub artifact capture and connectivity proof

**Dependencies:** G22 (complete) and an environment authorized for bounded
public GitHub HTTPS reads

**Purpose:** Prove that the evidence workflow can acquire the actual pinned
LangChain/LangGraph source and patch artifacts, or distinguish a network
access failure from missing repository evidence.

**Objective:** Fetch a declared set of real G21 pointers, persist exact bytes
and digests as a versioned recorded fixture, and replay them offline through
G22. If access fails, produce a phase-specific blocked report rather than
fabricating source content.

**Scope boundary:** Bounded HTTPS capture, redirect/timeout diagnostics,
fixture generation, offline replay, and documentation. Excludes cloning,
general GitHub search, credentials, adjudication, execution, and mutation.

**Advances:** OUT-02, OUT-05, OUT-06, OUT-08; SCN-01 through SCN-05, SCN-08,
SCN-09, and SCN-12.

**Unlocks:** Real inspectable evidence for G23's human adjudication.

The [detailed G22a specification](goals/G22a-real-github-artifact-capture.md)
is complete. Its real fixture and connectivity report are available to G23.

### G22b — Declared-support evidence bundle

**Dependencies:** G22a (complete) and owner-approved supplement selections

**Purpose:** Capture a declared-support evidence bundle for adjudication
without mutating the immutable G21 corpus or conflating declared support with
actual deployment usage.

**Objective:** Add a manifest-bound supplement, capture exact evidence from
repository packaging, published artifacts, CI matrices, support documentation,
and dependency/version markers, and replay it offline through G22.

**Scope boundary:** Finite GitHub and public-registry pointers across the five
support-evidence classes, bounded capture, diagnostics, fixture generation, and
replay. Excludes broad search, telemetry, adjudication, execution, and
mutation.

**Advances:** OUT-02, OUT-05, OUT-08; SCN-01 through SCN-03, SCN-05, SCN-08,
and SCN-09.

**Unlocks:** A current declared-support evidence bundle for G23, while leaving
actual deployment usage as a separate proof obligation.

The [detailed G22b specification](goals/G22b-current-support-evidence.md) is
complete. Its owner-approved selection, real capture fixture, and offline
replay evidence are available to G23.

### G22c — Retained-case support evidence supplement

**Dependencies:** G22b (complete) and owner-approved retained-case selection

**Purpose:** Extend the declared-support bundle to a retained compatibility
shim so Sunset can test refusal to remove code whose protected condition remains
active in the declared support scope.

**Objective:** Capture and freeze the five support-evidence classes for
`lg-dataclass-version-shim` at its pinned LangGraph head and exact published
release, without changing the validation corpus or claiming downstream safety.

**Unlocks:** G23 review of a retained holdout case with current declared-support
evidence.

The [G22c specification](goals/G22c-retained-case-support-evidence.md) and
verified fixture are complete.

### G23 — Single-reviewer adjudication and evidence quality

**Dependencies:** G22b/G22c (complete), an owner-supplied review protocol, and one
recorded human reviewer authority decision

**Purpose:** Turn provenance-bound case packets into explicitly scoped,
single-reviewer provisional evaluation labels without allowing the system under
test to create its own ground truth.

**Objective:** Record one owner-authorized human protected-condition and
proof-obligation assessment per eligible case, preserve abstention and
unresolved obligations, and freeze a single-reviewer provisional manifest.

**Scope boundary:** Review packets, label/import contracts, disagreement
records, and provenance checks. Excludes automatic label generation, model
optimization, live provider access, cleanup, and rewriting historical evidence.

**Advances:** OUT-02, OUT-05, OUT-08; SCN-01 through SCN-03 and SCN-12.

**Unlocks:** A single-reviewer provisional development/holdout corpus for
exploratory G24 evaluation; it cannot be called independent ground truth.

The [G23 execution contract](goals/G23-independent-adjudication.md) and frozen
single-reviewer manifest are complete. A later second-review pass may append
independent decisions without rewriting the provisional manifest.

### G24 — Frozen baseline evaluation

**Dependencies:** G23 (complete)

**Purpose:** Measure the system's actual epistemic behavior on a frozen,
explicitly labelled corpus before changing policies or prompts. If G23 has only
single-reviewer labels, all results must carry that limitation; independent
adjudication is a later strengthening path.

**Objective:** Execute heuristic-only and recorded-agentic baselines over the
same frozen development and holdout corpus, validate pinned cross-repository
lifecycle references as non-authoritative criterion fixtures, then publish per-case traces,
coverage, calibration, unsupported-claim, proof-obligation, safety, cost, and
latency results.

**Scope boundary:** Offline/replay evaluation and error taxonomy only. Excludes
prompt or heuristic changes, live providers, cleanup, and changing labels or
partitions after outputs are known.

**Advances:** OUT-03, OUT-05, OUT-06, OUT-08; SCN-03, SCN-06, SCN-08 through
SCN-10, and SCN-12.

**Unlocks:** A pre-optimization baseline and documented failure modes for G25.

The [G24 execution contract](goals/G24-frozen-baseline-evaluation.md) is
complete. Its report shows heuristic accuracy 1.0000 on four completed included
cases and recorded-agentic accuracy 0.6667 on three, with explicit interrupted,
malformed, contradictory, unsupported, and excluded outcomes. G25 is now the
next proposed goal and must tune only against development data.

### G25 — Split-safe optimization and ablation

**Dependencies:** G24 (complete)

**Purpose:** Improve measurable decision quality without tuning against the
same evidence used to make the product-quality claim.

**Objective:** Test predeclared, bounded changes on development data; retain a
change only under declared safety and quality criteria, then measure it once on
the untouched holdout split.

**Scope boundary:** Versioned ablations, experiment ledger, split-safe selection,
and final holdout report. Excludes holdout-driven tuning, relabeling, new
authority, cleanup, and universal removability claims.

**Advances:** OUT-03, OUT-05, OUT-06, OUT-08; SCN-06 and SCN-08 through SCN-10,
and SCN-12.

**Unlocks:** A reproducible candidate configuration and known regressions for
G26.

The [G25 execution contract](goals/G25-split-safe-optimization.md) is complete.
Its offline runner selected one development candidate, rejected safety,
malformed, and budget regressions, and sealed one holdout measurement without
using it for selection. G26 is now the next proposed goal.

### G26 — Broad candidate discovery

**Dependencies:** G25 (complete)

**Purpose:** Broaden candidate observability before a maintainer pilot without
weakening provenance or uncertainty boundaries.

**Objective:** Add repository-level version/dependency, deprecation/migration,
feature-flag, and environment/configuration signals plus a bounded
JavaScript/TypeScript adapter, all using the existing candidate/evidence
contract.

**Scope boundary:** Additive deterministic collectors, registry/versioning,
offline fixtures, and per-family coverage/false-positive measurement.

**Exclusions:** Inference or optimization changes, arbitrary crawling,
enterprise connectors, live access, cleanup, and removability claims.

**Unlocks:** A coverage-qualified candidate set for the G27 pilot.

The [G26 outline](goals/G26-broad-candidate-discovery.md) is proposed and will
be refined into a Luna-ready execution contract after G25 supplies its final
configuration and measured regressions.

### G27 — Maintainer pilot and product decision

**Dependencies:** G25 and G26 (complete), plus explicit pilot authorization

**Purpose:** Test whether the validated workflow is useful and appropriately
conservative in real maintainer review, where operational evidence and missing
context matter most.

**Objective:** Run a consented, read-only pilot against a small declared set of
maintainer-selected candidates, record review outcomes and failures, and publish
an evidence-bounded continue, revise, or stop decision.

**Scope boundary:** Read-only investigations and human-reviewed validation
requests under the existing approval boundary. Excludes automatic cleanup,
changes to target repositories, broad telemetry collection, and general
availability claims.

**Advances:** OUT-04, OUT-05, OUT-06, OUT-08; SCN-01 through SCN-03, SCN-07
through SCN-12.

**Unlocks:** A product decision based on empirical results and maintainer
feedback rather than architecture claims alone.

The [G27 outline](goals/G27-maintainer-pilot-decision.md) will be refined only
after G25 and G26 supply the pilot configuration, coverage limits, risk limits,
and measurable success/failure criteria.
