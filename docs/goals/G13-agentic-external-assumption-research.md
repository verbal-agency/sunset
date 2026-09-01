# G13 — Agentic external-assumption research

**Status:** complete
**Dependencies:** G12 (complete)

## Purpose

Give the bounded investigator current causal evidence about an explicitly
referenced external condition, so it can distinguish old local code from code
whose original justification may actually have expired.

## Objective

Add typed, recorded-first external-evidence tools for candidate-linked GitHub,
release-note, and dependency-version references. Extend the G12 loop only
through declared effects, credentials, request/rate budgets, and compact cited
observations; preserve contradictory and unavailable evidence as uncertainty.

## Project alignment

- Advances OUT-02, OUT-06, and OUT-07.
- Advances SCN-01 through SCN-03, SCN-08, and SCN-09.
- Supplies evidence needed before G14 can request a human-gated validation
  experiment; it does not execute one.

## Architecture constraints to preserve

- G10/G12 remain the authority for local state, bounded dispatch, receipts,
  checkpoint identity, raw-data boundaries, and terminal reasons. G13 adds
  provider tools; it must not create an alternate unbounded executor.
- Recorded fixtures are the default. Live reads require an explicit provider
  adapter, supplied credential, and a declared external-read effect; no model,
  environment, or tool name silently discovers credentials or contacts a host.
- A closed issue, release-note wording, or satisfying version range is evidence,
  not proof that a local cleanup is safe. Contradictions, missing references,
  stale source state, and request failures remain structured uncertainty.
- Persist compact normalized provider receipts and citation IDs only. Keep raw
  issue bodies, release documents, responses, headers, credentials, prompts,
  and framework messages outside loop state.

## In scope

1. Versioned provider-tool contracts and effect declarations for explicit
   candidate-linked references: GitHub issue/pull-request identifiers,
   release-note links, and package/version-range evidence.
2. Deterministic reference extraction from existing local receipts/provenance,
   including explicit no-reference and ambiguous-reference outcomes.
3. Recorded provider fixtures for fixed, active, missing, contradictory,
   malformed, rate-limited, and transport-failed paths; default tests must open
   no socket.
4. Opt-in live provider interfaces with supplied credentials, bounded request
   count/rate policy, response-size limits, provenance/refresh metadata, and
   stable normalized receipts.
5. G12 dispatcher/loop extension that allows only the new effect-declared
   tools, links every request to an antecedent hypothesis, compares sources
   without suppressing disagreement, and resumes without repeated compatible
   provider calls.
6. Documentation for evidence ranking, live-access opt-in, credential/redaction
   boundaries, provider cache/replay identity, and why external status is not a
   cleanup recommendation.

## Explicit exclusions

- General web crawling/search, embeddings/vector search, social or enterprise
  connectors, unbounded URL following, and references not linked to a candidate.
- External writes, issue comments, pull requests, account discovery, credential
  discovery, validation/test execution, shell commands, or repository edits.
- Automatic expiry classification, cleanup recommendation, approval, skeptical
  multi-agent review, or final case-file generation.

## Deliverables

1. Provider-independent evidence/reference/receipt/error/budget contracts.
2. Recorded-first GitHub, release-note, and dependency-range adapters behind a
   replaceable explicit live-read boundary.
3. G12-compatible external-tool registry and bounded checkpoint/resume policy.
4. Isolated fixtures and adversarial tests for source disagreement, budgets,
   redaction, replay, and no-network defaults.
5. Provider and agent-loop documentation.

## Goal-level acceptance criteria

- **G13-AC01 — Explicit, typed external tools:** Only extracted candidate-linked
  references can form a request. Each request validates schema, declared
  external-read effect, credentials, host allowlist, request/rate/byte budgets,
  and antecedent reasoning before any adapter call.
- **G13-AC02 — Recorded-first causal evidence:** Recorded fixtures deterministically
  represent fixed, active, missing, contradictory, malformed, rate-limited, and
  failed provider outcomes as cited receipts with facts, uncertainty, and source
  provenance; default/recorded execution opens no socket.
- **G13-AC03 — Conservative comparison:** The loop retains disagreement and
  unknowns across local provenance, issue/PR state, release notes, and dependency
  range evidence. It never translates issue closure or a version comparison into
  proof that marker removal is safe.
- **G13-AC04 — Bounded, replay-safe live access:** Supplied-credential live calls
  are opt-in, host-scoped, response-limited, and budgeted. Checkpoint replay
  reuses compatible receipts but invalidates on reference, provider policy,
  credential-identity, response freshness, request/budget, or local HEAD change.
- **G13-AC05 — Data and compatibility safety:** Persisted state excludes raw
  provider bodies/headers/credentials and framework messages. Existing Phase 1,
  G10–G12 APIs and offline behavior remain compatible.
- **G13-AC06 — Documentation and verification:** Documentation states the
  evidence-ranking and non-authority rules; locked full and focused suites pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G13-AC01 | Adversarial schema/effect/host/credential/budget tests before fake adapter invocation |
| G13-AC02 | Offline fixture matrix, socket guards, and byte-identical normalized receipt snapshots |
| G13-AC03 | Contradictory evidence graph fixtures asserting cited uncertainty and no safety conclusion |
| G13-AC04 | Live fake-adapter request counters plus cache/replay invalidation matrix |
| G13-AC05 | Raw/secret checkpoint scans and Phase 1–G12 regression suite |
| G13-AC06 | Documentation review, `uv lock --check`, focused tests, full locked suite, and `git diff --check` |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_external_agent_tools.py tests/test_external_agent_loop.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G12 showed that G11 supplies tool names only. Preserve deterministic argument
  resolution for local actions; if G13 needs reference parameters, add a
  separately versioned structured proposal/normalization contract rather than
  smuggling raw provider URLs through a prompt.
- G12 checkpoint identity now includes initial/current evidence grants and G10
  budget state. Provider receipt freshness and request budgets must participate
  in the same compatibility boundary without invalidating immutable local
  receipts unnecessarily.
- Raw external bodies can be sensitive and may contain hostile text. Normalized
  provider claims and citations must remain compact, while raw evidence stays in
  the artifact store and never becomes agent memory by default.

## Completion evidence

- **G13-AC01:** `tests/test_external_agent_tools.py` verifies that only
  extracted reference IDs enter the typed external registry. Schema, effect,
  host allowlist, rate/request/response limits, and reasoning antecedents are
  checked before the provider is invoked.
- **G13-AC02:** Recorded GitHub and release-note fixtures cover expired, active,
  missing, failed, malformed, and rate-limited outcomes. Socket guards prove
  recorded execution is offline; supporting responses are immutable artifacts.
- **G13-AC03:** Existing and new external-evidence tests retain contradictory
  active/expired evidence as `unknown`. The new tool records provider outcome
  only and contains no removal recommendation.
- **G13-AC04:** `ExplicitGitHubProvider` accepts only an injected credential,
  supported GitHub host/reference, and bounded response read. G13 loop tests
  verify provider-policy/freshness invalidation and compatible interruption
  resume without a second provider call.
- **G13-AC05:** `test_recorded_external_tool_runs_inside_bounded_g12_loop`
  scans the run and checkpoint views for a seeded raw provider body. Existing
  G10–G12 and full locked regressions remain compatible.
- **G13-AC06:** `README.md` and `docs/EXTERNAL-AGENT-TOOLS.md` document the
  recorded-first policy, live opt-in, credential and raw-data boundaries,
  replay identity, and non-authority rule.

Verification on 2026-09-01: `uv lock --check`, the focused external/G10/G11/G12
suite, the locked full suite, and `git diff --check` passed. The worktree remains
uncommitted pending human authorization.
