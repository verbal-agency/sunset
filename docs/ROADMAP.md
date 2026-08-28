# Sunset roadmap

Status values are `active`, `proposed`, `blocked`, and `complete`. Exactly one
goal may be active.

| Goal | Status | Objective | Dependencies |
| --- | --- | --- | --- |
| [G01](goals/G01-deterministic-scanner.md) | complete | Build the project foundation and deterministic pytest-marker scanner | None |
| [G02](goals/G02-provenance-artifacts.md) | proposed | Trace candidate provenance and persist content-addressed evidence | G01 |
| [G03](goals/G03-broader-deterministic-collectors.md) | proposed | Collect dependency/version guards and compatibility shims deterministically | G02 |
| G04 | proposed | Investigate rationale with LangGraph and compact, checkpointed memory | G03 |
| G05 | proposed | Verify external assumptions using replaceable evidence providers | G04 |
| G06 | proposed | Validate candidate removal in an approved disposable sandbox | G05 |
| G07 | proposed | Produce citation-verified case files with a skeptical review stage | G06 |
| G08 | proposed | Benchmark quality and memory efficiency with LangSmith | G07 |
| G09 | proposed | Package and publish a polished end-to-end Sunset release | G08 |

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
commit, and focused history. Store raw artifacts by content hash with source,
retrieval time, and repository provenance. Add immutable-artifact reuse and
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
