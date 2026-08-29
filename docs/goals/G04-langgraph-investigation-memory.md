# G04 — LangGraph investigation and efficient memory

**Status:** complete
**Dependencies:** G03

## Purpose

Turn deterministic Sunset candidates and their G02 artifacts into a resumable,
auditable investigation record without repeatedly sending raw repository history
through a model context.

## Objective

Implement a bounded LangGraph workflow that loads one existing candidate's
local-Git provenance, retrieves only needed artifacts, records structured facts
and uncertainty, checkpoints after each stage, and accounts for compact working
memory tokens. The initial workflow must end `inconclusive`; it does not verify
external assumptions or recommend removal.

## Project alignment

- Advances **OUT-02 — Auditable rationale** and **OUT-03 — Efficient
  investigation**.
- Exercises **SCN-03 — Insufficient evidence** and **SCN-04 — Safe
  interruption**.
- Establishes the memory and token baseline later evaluated by SCN-06.

## Architecture constraints to preserve

- G01/G03 candidate discovery and G02 artifacts remain the source of truth.
- Raw artifact bytes remain in the external content-addressed store; the graph
  state and any future prompt carry only IDs, bounded extracts, and structured
  ledger entries.
- The graph records facts, inferences, contradictions, unknowns, and rejected
  hypotheses as distinct kinds. A blame-backed `introduction_commit` remains a
  lead, not proof of the original rationale.
- All checkpoint and derived state is keyed by repository identity, committed
  HEAD, collector, candidate ID, and a versioned configuration fingerprint.
- Token accounting is deterministic and explicitly labelled as estimated until
  a model provider is introduced. The default per-candidate limits remain
  100,000 input and 8,000 output tokens.
- No model, network, dependency-resolution, test, worktree, target-repository
  write, external provider, or removal recommendation is allowed in G04.

## In scope

- Add LangGraph as the workflow runtime and construct an explicit bounded
  `StateGraph`.
- Versioned investigation-result, ledger, selection, token-accounting, and
  error models.
- A local-only graph that: loads candidate provenance; retrieves the source and
  blame-patch core evidence; records compact ledger facts; expands once to
  bounded focused history only when core evidence lacks a rationale cue; and
  finalizes an inconclusive result with open questions.
- Durable external-store checkpoints after each graph node and deterministic
  resume from the latest checkpoint after an intentional interruption.
- A CLI command to investigate one explicitly selected candidate and report
  JSON, including `--interrupt-after`, token budgets, and collector selection.
- Per-node compact input/output token estimates, full-context baseline metadata,
  and explicit token-budget failures.
- Fixture tests for resume, selective retrieval/reuse, no raw-history prompt
  payload, shallow-history uncertainty, stable result IDs, and target
  repository/network safety.

## Explicit exclusions

- Calling an LLM or model provider, including automatic LangSmith tracing.
- GitHub, release-note, issue, PR, dependency-resolution, or other external
  evidence; G05 owns those providers and expiry classification.
- Claiming a rationale is confirmed, a guard is obsolete, or a cleanup is safe.
- Running tests, changing the target repository, creating worktrees, or
  generating a pull request.
- Benchmarks over a historical corpus; G08 owns that measurement.

## Deliverables

1. A versioned LangGraph investigation domain contract and compact ledger.
2. Durable, HEAD-dependent checkpoint storage that reuses G02 artifacts.
3. A deterministic local-only investigation graph and CLI.
4. Fixture coverage for interruption/resume, selective retrieval, token
   accounting, uncertainty, determinism, and no-side-effect guarantees.
5. README documentation of the investigative boundary and token semantics.

## Goal-level acceptance criteria

- **G04-AC01 — Bounded graph:** A real LangGraph `StateGraph` runs the
  documented local stages, produces a structured ledger, and terminates
  `inconclusive` with no expiry or removal claim.
- **G04-AC02 — Compact structured memory:** Every ledger entry has a distinct
  claim kind and evidence IDs; graph prompt payloads omit full raw history and
  record a full-context token baseline for future comparison.
- **G04-AC03 — Checkpoint/resume:** An intentional interruption resumes from
  the latest external checkpoint without repeating completed retrieval nodes or
  losing ledger provenance.
- **G04-AC04 — Selective retrieval and invalidation:** Core source/patch
  evidence is retrieved first; focused history is retrieved once only when
  needed. Identical input reuses derived state; a changed HEAD yields a new run
  key while G02 immutable artifacts remain reusable.
- **G04-AC05 — Token budget:** Every node records estimated input/output tokens;
  configured input or output limits fail with structured errors before a model
  would be invoked.
- **G04-AC06 — Safety and uncertainty:** Tests prove no network/model calls or
  target mutation. Shallow/incomplete history and the distinction between blame
  and semantic rationale appear as explicit unknowns.
- **G04-AC07 — Documented CLI and boundary:** README and CLI document one-
  candidate investigation, checkpoint semantics, estimated tokens, and G05's
  responsibility for external verification.

## Required verification evidence

| Criterion | Evidence |
| --- | --- |
| G04-AC01 | Fixture graph result and node-stage assertions |
| G04-AC02 | Ledger/prompt inspection and baseline token assertions |
| G04-AC03 | Forced interruption followed by resume with read counters |
| G04-AC04 | Core/no-history and expanded-history fixtures plus changed-HEAD run key |
| G04-AC05 | Per-node totals and deliberately low-budget structured failure |
| G04-AC06 | Socket/model guards and before/after target Git snapshot |
| G04-AC07 | CLI JSON test and README review |

## Completion and handoff

When all criteria pass, mark G04 complete in the roadmap, preserve G05 as
proposed, and add only concrete provider-boundary findings to G05. Do not begin
G05 without a separate user instruction.

## Completion evidence

- **G04-AC01:** `tests/test_investigation.py` executes the real LangGraph
  `StateGraph` through the local provenance, core retrieval, summary, optional
  expansion, and `inconclusive` finalization stages.
- **G04-AC02:** The ledger validates one of the explicit claim kinds and every
  claim carries artifact IDs where evidence exists. The adaptive-history test
  proves the raw commit subject is absent from both result JSON and durable
  checkpoint bytes while full-context and working-memory token baselines are
  recorded.
- **G04-AC03:** The forced `retrieve_core` interruption/resume test proves the
  resumed graph retains its run ID and ledger while the counting store performs
  no additional artifact read.
- **G04-AC04:** Fixtures cover both core-only and history-expanded paths plus a
  changed committed HEAD that creates a new run ID while using G02 storage.
- **G04-AC05:** Every graph node emits estimated token usage; a one-token input
  budget returns a structured error and retains collected ledger/token evidence.
- **G04-AC06:** Read-only/socket-guard coverage and shallow-clone coverage keep
  target state unchanged and carry incomplete history into an `unknown` entry.
- **G04-AC07:** CLI coverage verifies `sunset investigate`; README documents
  checkpoints, estimated tokens, local-only scope, and G05 ownership.

## G05 handoff

G04's graph establishes the external-provider boundary: G05 should add only
replaceable recorded GitHub and release-note adapters that persist raw replies
as artifacts and write their conclusions as ledger entries. Network failures,
missing references, and conflicting evidence must remain `unknown`; they must
never make this graph recommend removal.
