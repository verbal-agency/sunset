# Sunset project charter

## Product thesis

Code does not merely become old; the reasons for code expire. Repositories
rarely track when a temporary workaround, disabled test, compatibility shim, or
version constraint has outlived the condition that justified it.

Sunset is a conservative, evidence-driven garbage collector for source code. It
finds temporal-debt candidates, reconstructs their original rationale, checks
whether the underlying assumption still holds, validates a proposed cleanup in
an isolated environment, and produces a case file for human review.

Sunset proposes collection. It never treats age, lack of references, model
confidence, or passing tests as sufficient proof that deletion is safe.

## Initial user and scope

The initial user is a Python library maintainer reviewing disabled pytest tests.
The first complete vertical slice supports `pytest.mark.xfail`,
`pytest.mark.skip`, and `pytest.mark.skipif` in local Git repositories.

General dead-code collection, automatic merges, JavaScript/TypeScript support,
enterprise connectors, and broad technical-debt scoring are outside the first
release.

## Garbage-collection model

| Garbage collection concept | Sunset concept |
| --- | --- |
| Roots | Supported contracts, active behavior, users, platforms, and policies |
| Heap objects | Disabled tests, workarounds, pins, flags, and compatibility code |
| Reachability | Current callers or a still-valid external assumption |
| Mark | Evidence that the rationale remains valid |
| Sweep candidate | Rationale appears to have expired |
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

## Canonical acceptance scenarios

- **SCN-01 — Expired marker:** Given an xfail introduced for a documented
  upstream bug that is fixed in the repository's current dependency range,
  Sunset reconstructs the rationale, validates the unmarked test, and recommends
  removal with evidence and residual risks.
- **SCN-02 — Still-required marker:** Given an old xfail whose triggering
  condition remains active, Sunset records why it is retained and does not
  recommend removal.
- **SCN-03 — Insufficient evidence:** Given missing or contradictory history,
  Sunset returns `inconclusive` and identifies the evidence needed to continue.
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

## Initial quality targets

- Candidate discovery is deterministic for the same repository commit and
  configuration.
- No unsupported material claim appears in a final case file.
- Confirmed-removable recommendations require raw evidence and an isolated test
  result.
- The default complete-investigation budget is 100,000 input tokens and 8,000
  output tokens per candidate.
- The memory comparison target is defined by SCN-06.
