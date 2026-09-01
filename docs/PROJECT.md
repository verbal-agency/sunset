# Sunset project charter

## Product thesis

Code does not merely become old; it often protects against a condition that may
no longer exist. Repositories rarely track when a temporary workaround,
disabled test, compatibility shim, or version constraint has outlived the
condition it was meant to protect against.

Sunset is a conservative, evidence-driven investigator of temporal debt. It
finds historically contingent code, forms competing hypotheses about the
protected condition, gathers evidence about whether that condition still holds,
states what remains unproven, and can validate a narrowly scoped counterfactual
experiment in an isolated environment for human review.

Sunset proposes collection. It never treats age, lack of references, model
confidence, or passing tests as sufficient proof that deletion is safe.

## Phase 1 user and scope

The initial user is a Python library maintainer reviewing disabled pytest tests.
The first complete vertical slice supports `pytest.mark.xfail`,
`pytest.mark.skip`, and `pytest.mark.skipif` in local Git repositories.

General dead-code collection, automatic merges, JavaScript/TypeScript support,
enterprise connectors, and broad technical-debt scoring are outside the first
release.

## Phase 2 product direction

Phase 1 established the deterministic, evidence, validation, and evaluation
substrate. Phase 2 turns those capabilities into allowlisted tools for a bounded
agentic investigator. The agent framework is an implementation detail, not the
product: the product is a conservative epistemic model for determining whether
the premise behind historically contingent code is still true.

The investigator may choose bounded evidence operations, form and revise
protected-condition hypotheses, identify contradictions, and conclude that the
evidence is insufficient or the condition is unvalidatable. It does not replace
deterministic collectors, raw evidence, executable validation, or human
approval. Heuristic-only operation remains supported as a safe baseline.

Phase 2 initially remains focused on the same Python-maintainer workflow. New
languages, generic dead-code detection, enterprise knowledge connectors,
automatic cleanup, and automatic pull requests remain outside the planned
agentic vertical slice.

### Temporal-condition vocabulary

Sunset treats the reason for a temporal-debt candidate as a hypothesis about a
protected condition, not as a fact recovered from Git history. A condition can
have competing hypotheses and evidence with different roles: `support`,
`contradict`, `establish`, `scope_limit`, or `missing`. Evidence is also classified by scope
(`static`, `historical`, `operational`, `external`, or `validation`) and carries
freshness and provenance. A citation can support a claim without establishing
that the claim applies to this repository's users or deployments.

Condition progress is represented separately from removal authority:
`discovered`, `condition_hypothesized`, `condition_identified`,
`condition_likely_expired`, `condition_likely_active`, `removal_testable`, and
`validated_in_scope`. `contradictory_evidence`, `insufficient_evidence`, and
`unvalidatable` are conservative terminal outcomes. `human_approved` is an
approval-boundary state, never an inference from evidence or validation.

### Claim–evidence graph semantics

Phase 2 represents each protected-condition hypothesis as a claim node linked
to evidence edges. Edges retain their role (`support`, `contradict`,
`establish`, `scope_limit`, or `missing`), source class, declared scope,
freshness, and immutable provenance IDs. `support` can make a claim plausible;
only a fresh `establish` edge whose scope matches the claim can establish it.
Contradictory edges remain visible and produce `contradictory_evidence` rather
than being ranked away. Missing or scope-insufficient evidence becomes an
explicit proof obligation. Graph inference is deterministic and
non-authoritative: it never turns model confidence, citation presence, or a
passing validation run into permission to remove code.

Context expansion is the controlled remedy for the graph's sensor bottleneck.
The investigator may request one of six named repository relations—AST parent,
callers, callees, same-commit changes, historical variant, or configuration
reference—using a candidate or symbol identity and explicit budgets. The
deterministic resolver returns structured references tied to the committed
HEAD; missing, truncated, stale, or budget-exhausted results remain explicit
unknowns. This expands observability without granting arbitrary paths, shell,
network, credentials, imports, execution, or mutation authority to a model.

Operational evidence is a separate candidate-linked provider boundary. Sunset
recognizes only configured support-policy, deployment-inventory, configuration,
contract, and runtime-telemetry sources. Recorded fixtures are the default;
live reads require an explicit host, credential identity, freshness policy,
privacy policy, and byte/request budget. Receipts retain source scope,
freshness, provenance, redaction summaries, and immutable artifact IDs, while
unavailable, stale, privacy-redacted, or conflicting data remains unknown or
contradictory rather than becoming an expiry conclusion.

Operational and internal evidence is a separate, candidate-linked provider
boundary. Sunset recognizes only configured support-policy, deployment-
inventory, configuration, contract, and runtime-telemetry sources. Recorded
fixtures are the default; live reads require an explicit host, credential
identity, freshness policy, privacy policy, and byte/request budget. Receipts
retain source scope, freshness, provenance, redaction summaries, and immutable
artifact IDs, while unavailable, stale, privacy-redacted, or conflicting data
remains unknown or contradictory rather than becoming an expiry conclusion.

## Garbage-collection model

| Garbage collection concept | Sunset concept |
| --- | --- |
| Roots | Supported contracts, active behavior, users, platforms, and policies |
| Heap objects | Disabled tests, workarounds, pins, flags, and compatibility code |
| Reachability | Current callers or a still-valid external assumption |
| Mark | Evidence that a protected condition still applies |
| Sweep candidate | The protected condition may no longer apply |
| Finalizer | Isolated removal experiment and tests |
| Collection | Human-approved cleanup change |

## Project outcomes

- **OUT-01 — Deterministic discovery:** Maintainers can find supported temporal-
  debt candidates without sending repository contents to a model.
- **OUT-02 — Auditable rationale:** Every material claim is connected to raw,
  immutable evidence and labeled as fact, inference, contradiction, or unknown.
- **OUT-03 — Efficient investigation:** Structured memory and selective
  retrieval materially reduce model tokens without degrading decision quality.
- **OUT-04 — Safe validation:** Potential cleanups are tested in isolation and
  never applied to the user's working tree without approval.
- **OUT-05 — Measured trustworthiness:** Historical positive and negative cases
  quantify precision, citation quality, unsupported claims, cost, and latency.
- **OUT-06 — Bounded agency:** An investigator can select allowlisted evidence
  tools, revise hypotheses, and stop within explicit iteration, token, cost, and
  side-effect budgets.
- **OUT-07 — Ecosystem portability:** Deterministic tools, model providers,
  graph persistence, and evaluation adapters integrate through replaceable
  LangChain ecosystem contracts without changing Sunset's domain objects.
- **OUT-08 — Epistemic discipline:** Every condition-status conclusion records
  its hypotheses, supporting and contradicting evidence, scope, freshness,
  missing proof obligations, and the limits of counterfactual validation.

## Canonical acceptance scenarios

- **SCN-01 — Expired marker:** Given an xfail introduced for a documented
  upstream bug that is fixed in the repository's current dependency range,
  Sunset records an upstream-condition hypothesis, distinguishes that evidence
  from local deployment/support evidence, validates the unmarked test in scope,
  and states the remaining proof obligation for a human reviewer.
- **SCN-02 — Still-required marker:** Given an old xfail whose triggering
  condition remains active, Sunset records the supporting evidence and does not
  assert that removal is safe.
- **SCN-03 — Insufficient evidence:** Given missing or contradictory history,
  Sunset returns `insufficient_evidence` or `contradictory_evidence` and
  identifies the evidence needed to continue.
- **SCN-04 — Safe interruption:** Given an investigation interrupted after
  evidence collection, Sunset resumes from a checkpoint without refetching
  unchanged artifacts or losing provenance.
- **SCN-05 — Cache validity:** Given a repository or environment change, Sunset
  reuses immutable artifacts while invalidating affected maps, summaries, and
  test results.
- **SCN-06 — Memory efficiency:** On the benchmark corpus, selective retrieval
  cuts median model input tokens by at least 50% versus full-history context,
  while classification accuracy drops by no more than five percentage points
  and citation accuracy does not decline.
- **SCN-07 — Human control:** No candidate modification, external write, or
  cleanup proposal is applied without an explicit approval boundary.
- **SCN-08 — Adaptive investigation:** Given a candidate whose core provenance
  is insufficient, the agent chooses relevant allowlisted tools, updates its
  hypotheses from their evidence, and stops with cited findings and explicit
  remaining unknowns.
- **SCN-09 — Agentic failure containment:** Given a malformed model response,
  failed tool, exhausted budget, or interrupted run, Sunset preserves successful
  evidence, records the failure, and resumes or returns `inconclusive` without
  fabricating a claim or repeating a completed side effect.
- **SCN-10 — Model portability:** Given recorded replay and two compatible
  LangChain chat-model adapters, the investigation preserves one versioned
  structured contract, provenance rules, and approval boundaries without domain
  model changes.
- **SCN-11 — Approval-seeking validation:** Given an agent that has enough
  evidence to request an experiment, Sunset presents a bounded validation plan
  and pauses; denial executes nothing, while approval resumes only the existing
  disposable validation path.
- **SCN-12 — Comparative agent evaluation:** On a versioned public benchmark,
  heuristic-only and agentic modes are compared for protected-condition
  hypotheses, condition-status calibration, proof-obligation quality, citations,
  unsupported claims, tool use, tokens, latency, and cost, and the release gate
  explicitly passes or fails declared thresholds.

## Architecture constraints

1. **Deterministic before probabilistic.** ASTs, Git, dependency graphs, exact
   identifiers, and test results precede semantic or model-based inference.
2. **Read-only by default.** Scans and investigations cannot modify the target
   repository. Experiments use disposable worktrees or containers.
3. **Raw evidence is external to prompts.** Full diffs, issues, source, release
   notes, and logs live in a content-addressed artifact store.
4. **Working memory is compact and structured.** Prompts receive a ledger of
   facts, hypotheses, evidence IDs, open questions, and the current task—not the
   entire transcript.
5. **Compress early, verify late.** Summaries guide retrieval; final claims are
   rechecked against raw evidence.
6. **Memory is versioned.** Repository knowledge is keyed by repository state;
   test results include code, environment, and dependency hashes.
7. **Model output is not authority.** Confidence cannot replace provenance,
   executable validation, or human review.
8. **Provider boundaries remain explicit.** Git hosting, model, sandbox, and
   persistence adapters must be replaceable without changing domain objects.
9. **Token use is a product metric.** Each investigation records input/output
   tokens by node and enforces configurable budgets.
10. **Precision outranks recall.** Missing some garbage is preferable to a
    confident unsafe deletion recommendation.
11. **Agency is tool-mediated.** Models can request only registered tools with
    validated inputs, declared effects, scoped evidence access, and structured
    results.
12. **Agency is bounded and replayable.** Every run limits iterations, tool
    calls, tokens, cost, and wall time; prompt, model, tool, and state schema
    versions participate in checkpoint and cache identity.
13. **Deterministic mode remains first-class.** Scanning, saved-evidence
    workflows, and heuristic-only investigation do not require model credentials
    or silently acquire network access.
14. **Inference and authority remain separate.** A model may propose evidence
    retrieval or validation, but only deterministic code executes tools and only
    an explicit human decision crosses an approval boundary.
15. **Agent traces are evidence maps, not hidden authority.** Tool calls,
    structured model outputs, budgets, errors, and citations are observable and
   evaluable without treating chain-of-thought or confidence as proof.
16. **Protected conditions are hypotheses.** Git history can locate an
    introduction, but cannot establish a single original rationale. Sunset must
    represent alternative protected-condition hypotheses and preserve ambiguity.
17. **Evidence has scope.** Static, historical, operational/internal, external,
    and counterfactual-validation evidence answer different questions. A citation
    may support, contradict, or fail to establish a claim; no evidence type is a
    universal substitute for another.
18. **Insufficient evidence is useful.** `insufficient_evidence`,
    `contradictory_evidence`, and `unvalidatable` are successful conservative
    outcomes, not errors to hide with a recommendation.

## Initial quality targets

- Candidate discovery is deterministic for the same repository commit and
  configuration.
- No unsupported material claim appears in a final case file.
- A passing isolated test can only support `validated_in_scope`; it cannot by
  itself establish a removal recommendation.
- The default complete-investigation budget is 100,000 input tokens and 8,000
  output tokens per candidate.
- The memory comparison target is defined by SCN-06.

## Phase 2 quality targets

- Existing deterministic CLI and domain contracts remain backward compatible
  unless a goal explicitly defines and tests a migration.
- Model-disabled and recorded-replay modes make no live model or network request.
- Every model-derived material claim cites an evidence artifact with an explicit
  support, contradiction, or scope-limiting role; unsupported or malformed
  claims are rejected before case-file finalization.
- Each agentic run records model, prompt, tool, graph-state, and budget versions
  plus tool calls, token use, latency, cost availability, and terminal reason.
- Model, tool, or budget failure yields structured partial evidence and an
  `inconclusive` outcome rather than a guessed recommendation.
- Phase 2 release thresholds are declared before the final comparative run; no
  agentic quality claim is made solely from fixtures or model confidence.
