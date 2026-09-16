# G30 live reasoning — first real model evidence (v1)

**Date:** 2026-09-16
**Goal:** [G30](../goals/G30-live-agentic-escalation-evaluation.md)
**Models:** Claude Sonnet (`claude-sonnet-4-5`) and OpenAI (`gpt-4.1`), via the
`live_model` factory + `LiveAgentReasoner`.
**Cases:** the four corrected OpenClaw `ui/` candidates (G27 / G29).
**Inputs:** static evidence only (marker code, usage, provenance). The disposable-
clone validation outcomes were **deliberately withheld** so the agent reasons from
what a first pass can see; who is empirically "right" is not adjudicated here.
**Cost:** ≈ 2¢ (Sonnet) + ≈ 1¢ (gpt-4.1). One call per case, bounded output.

This is the **first time a live model has weighed evidence in Sunset.** Every prior
"agentic" number was a replayed authored fixture (see
[agentic-evaluation-gap-v1](agentic-evaluation-gap-v1.md)).

## Result

| Candidate | Conservative heuristic | Sonnet | gpt-4.1 | Human decision (G27) |
| --- | --- | --- | --- | --- |
| C1 Chromium gate | likely_active | likely_active | likely_active | retain |
| C2 proof-phase label | likely_active | unknown | unknown | investigate |
| C3 exact-HEAD | likely_active | unknown | unknown | insufficient_evidence |
| C4 capture instrumentation | likely_active | likely_active | likely_active | investigate |

Vocabulary maps roughly: retain ≈ likely_active, insufficient_evidence ≈ unknown;
"investigate" has no clean condition-status equivalent (a "worth checking" lead).

## Findings

1. **Cross-model agreement.** Sonnet and gpt-4.1 produced identical statuses on all
   four cases. The behavior below is not a single-model artifact.
2. **Uniformly conservative.** Neither model ever said `likely_expired`; there were
   zero false "safe to remove" signals (precision over recall).
3. **Discrimination the flat heuristic lacks.** The conservative heuristic
   reflexively returns `likely_active` for everything. Both models instead
   returned `unknown` on C2 and C3 — where static evidence is genuinely thin —
   while keeping `likely_active` on C1 and C4. In the full loop `unknown` is exactly
   what triggers escalation to empirical validation, so the agent "knows when it
   doesn't know." This selective escalation is the hypothesized value of the
   agentic layer, observed for the first time.
4. **Convergence with the human reviewer on the clear cases**, including C3 — the
   exact case the reviewer recorded as `insufficient_evidence`; both models
   independently returned `unknown`. Where the models differ from the human (C2,
   C4) they are *more* conservative (abstain/keep vs. the human's "investigate"),
   i.e. the safe direction.

## Caveats

- N = 4, one run per model, static evidence only. A demonstration and an
  encouraging signal — **not** a measured verdict.
- No empirical clone adjudication for these candidates (OpenClaw's TS/pnpm E2E
  clones are not cheap to run here). This compares *judgments*, not who is provably
  right. The clone-adjudication half of the loop is proven separately on runnable
  pytest cases (`tests/test_escalation_end_to_end.py`).
- Asserted human labels are a weak prior here, not ground truth (per the G30
  grounding principle). The trustworthy comparison remains empirical adjudication,
  pending a corpus of clone-runnable cases with real evidence.

## Per-case model rationale (excerpts)

- **C1 (Sonnet, likely_active):** "infrastructure accommodation … typically remains
  relevant unless there's explicit standardization of the environment."
- **C2 (Sonnet, unknown):** "I cannot definitively determine if the condition is
  still relevant."
- **C3 (Sonnet, unknown):** "doesn't demonstrate whether the reason for its
  existence … is still relevant."
- **C4 (Sonnet, likely_active):** "standard E2E test infrastructure for optional
  diagnostic capture, not a temporary workaround or compatibility shim."
