# G27 maintainer-pilot handoff (v1, draft)

**Status:** draft for owner/reviewer completion
**Prepared:** 2026-09-15
**Active goal:** [G27 — Maintainer pilot and product decision](../goals/G27-maintainer-pilot-decision.md)
**Run under review:** `openclaw-v2026.8.2-ui-g27-pilot-v1`
(OpenClaw `v2026.8.2`, head `0965053fe6b9341776df147a6934b7485c60b5ca`, scope `ui/`)

This document is the human-facing bridge between the completed technical pilot and
G27's remaining acceptance criteria. It carries **no cleanup authority**. Nothing
here proves a protected condition is absent; every "decision" field is a scoped
review judgment, not a removal instruction. The technical evidence it summarizes is
frozen in
[`tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json`](../../tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json)
and the run manifest
[`openclaw-g27-ui-run-v2.json`](../../tests/fixtures/public_corpus/openclaw-g27-ui-run-v2.json).

Two things are still required to satisfy G27:

- **Part A** — a declared maintainer-pilot protocol (spec lines 109–114). *Owner completes the bracketed fields before the first maintainer run.*
- **Part B** — a single-reviewer decision worksheet (AC03, AC06). *One authorized reviewer records a decision per candidate.*

When both are complete, Part C's continue/revise/stop template becomes the G27
outcome artifact.

---

## Part A — Maintainer-pilot protocol (owner to complete)

The technical pilot needed no protocol because it was read-only against a pinned
public checkout. A **maintainer pilot involves a consenting person and their
judgment about their own repository**, so the following must be fixed *before* the
first maintainer run. Leaving any field as `[TBD]` blocks the run.

| Protocol element | Declared value |
| --- | --- |
| Participant(s) and consent record | `[TBD — named maintainer(s); how consent is captured and where stored]` |
| Candidate count per participant | `[TBD — small, e.g. ≤ the 4 declared OpenClaw candidates; no full-inventory dump]` |
| Repository scope | `[TBD — pinned ref + path scope, mirroring the read-only technical pilot's discipline]` |
| Data minimization / redaction | `[TBD — what leaves the participant's environment; default: only candidate locators, hypotheses, and decisions, never raw source or secrets]` |
| Success measures | `[TBD — e.g. reviewer finds the proof-obligations actionable; hypotheses judged fair; no over-confident "safe to remove" framing]` |
| Harm measures | `[TBD — e.g. any candidate a reviewer flags as misleading, any pressure toward unsafe removal, any privacy leak]` |
| Retention | `[TBD — how long per-case notes are kept; deletion trigger]` |
| Incident stop rule | `[TBD — concrete threshold that halts new runs, per spec "Authority and stop condition"]` |
| Disclosure | `[TBD — aggregate + per-case evidence published only with participant-approved disclosure]` |

**Guardrails carried from the goal spec (non-negotiable, do not edit):**

- Read-only investigation and human-gated validation only. No automatic cleanup,
  no target-repository writes, no unbounded target-code execution.
- The complete raw candidate inventory is never sent to a model before
  deterministic filtering/deduplication.
- Maintainer approval, a passing test, or a small pilot is **not** proof that a
  protected condition is absent anywhere.
- Any privacy incident, unapproved side-effect request, or crossed harm threshold
  stops new pilot runs while preserving already-authorized evidence.

---

## Part B — Single-reviewer decision worksheet (reviewer to complete)

One owner-authorized reviewer. No second reviewer or consensus is implied
(`second_review_required: false`). For each candidate, choose exactly one decision
and record rationale tied to the proof obligations.

**Allowed decisions:** `retain` · `investigate` · `insufficient_evidence`
(a decision is **never** `remove`).

The "validation observed" column summarizes the already-recorded disposable-clone
experiments — empirical, in-scope observations only, not removability proof.

### Candidate 1 — active/retained control (Chromium gate)

- **ID:** `sunset-broad-v2-15be1992b07e42a78f0c0b24`
- **Location:** `ui/src/e2e/activity-run-inspector.e2e.test.ts:22`
- **Signal:** `const allowMissingChromium = process.env.OPENCLAW_UI_E2E_ALLOW_MISSING_CHROMIUM === "1";`
- **Hypothesis:** Playwright Chromium may be unavailable in some environments, so this E2E lane is intentionally skipped there.
- **Proof obligations:** (1) identify which environments set the variable; (2) run with Chromium available and unavailable without touching the target; (3) do not remove unless supported environments and skip semantics are documented.
- **Validation observed:** passed 10/10 with Chromium; cleanly skipped 10/10 when Chromium unavailable and the allow-missing gate enabled. Reads as an active, working gate.
- **Reviewer decision:** `[ retain | investigate | insufficient_evidence ]`
- **Rationale / residual obligation:** `[TBD]`

### Candidate 2 — low-risk removal hypothesis (proof-phase label)

- **ID:** `sunset-broad-v2-a4ba4f78d9030728b801e465`
- **Location:** `ui/src/e2e/activity-session-feed.capture.e2e.test.ts:22`
- **Signal:** `const proofPhase = process.env.OPENCLAW_MENU_THEME_PROOF_PHASE;`
- **Hypothesis:** A proof-phase label may be temporary screenshot instrumentation; when unset, behavior should be unchanged apart from the artifact filename.
- **Proof obligations:** (1) confirm all references and whether any artifact consumer depends on the phase suffix; (2) run with the variable unset and compare behavior + artifact paths; (3) treat unchanged behavior as validation-in-scope only.
- **Validation observed:** passed 1/1 both with and without the value; the value changes only the captured artifact's filename. Assertions unaffected.
- **Reviewer decision:** `[ retain | investigate | insufficient_evidence ]`
- **Rationale / residual obligation:** `[TBD]`

### Candidate 3 — unknown / reproducibility case (exact-HEAD)

- **ID:** `sunset-broad-v2-eac9359052efa9f30c01df81`
- **Location:** `ui/src/e2e/tool-titles.e2e.test.ts:199`
- **Signal:** `exactHead: process.env.OPENCLAW_TOOL_TITLES_EXACT_HEAD?.trim() ?? null,`
- **Hypothesis:** An exact-HEAD value may make visual-test metrics reproducible, or may be unused diagnostic metadata.
- **Proof obligations:** (1) find consumers / upload paths relying on the exact-head field; (2) compare metrics output unset vs. set to the pinned head; (3) preserve the field if it is reproducibility or audit provenance.
- **Validation observed:** **incomplete** — 5/6 passed; the 240-row video-producing test could not run (Playwright ffmpeg unsupported on mac13-arm64), so no `metrics.json` was produced and the exact-head path was **not** exercised. Reproducibility question remains open.
- **Reviewer decision:** `[ retain | investigate | insufficient_evidence ]`
- **Rationale / residual obligation:** `[TBD — note the unresolved ffmpeg-blocked validation]`

### Candidate 4 — repeated-condition case (capture instrumentation)

- **ID:** `sunset-broad-v2-ccb8a75b35e18dd8955874c5`
- **Location:** `ui/src/e2e/activity-answer-candidates.e2e.test.ts:16`
- **Signal:** `const captureUiProof = process.env.OPENCLAW_CAPTURE_UI_PROOF === "1";`
- **Hypothesis:** Screenshot/video capture is optional instrumentation shared across many E2E tests; may be needed for visual proof or debugging.
- **Proof obligations:** (1) group all references and identify the workflow that consumes captured artifacts; (2) verify unsetting changes only optional artifacts, not assertions; (3) do not generalize one file's result to the shared condition without scope evidence.
- **Validation observed:** passed 1/1 with capture enabled; optional screenshots emitted. One file only — the shared-condition scope is untested.
- **Reviewer decision:** `[ retain | investigate | insufficient_evidence ]`
- **Rationale / residual obligation:** `[TBD]`

### Excluded feature-family matches (detector-quality findings, not candidates)

Recorded so the reviewer can confirm the detector correctly declined them; neither
is a lifecycle candidate. No decision required.

- `patternFlags` at `ui/src/lib/browser-redact.ts:14` — regular-expression flags.
- `dangerousConfigFlags` at `ui/src/pages/plugins/consent-dialog.ts:148` — configuration safety metadata.

---

## Part C — Continue / revise / stop decision (owner, after Parts A & B)

The G27 outcome artifact. Fill only after the maintainer pilot has run under the
Part A protocol and the reviewer has completed Part B.

- **Configuration digest / run identity:** `openclaw-v2026.8.2-ui-g27-pilot-v1` (+ any maintainer-run identity)
- **Coverage:** `[TBD — candidates reviewed, environments checked, obligations closed vs. open]`
- **Maintainer outcomes:** `[TBD — per-case decisions + reviewer sentiment on hypothesis fairness and proof-obligation usefulness]`
- **Failures / unavailable evidence:** `[TBD — e.g. ffmpeg-blocked exact-HEAD validation; any environment gaps]`
- **Unresolved proof obligations:** `[TBD]`
- **Recommendation (choose one):** `[ continue | revise | stop ]`
- **Bounded justification:** `[TBD — explicitly not a cleanup authorization]`

---

## Completion mapping to G27 acceptance criteria

| Criterion | Satisfied by |
| --- | --- |
| G27-AC03 (reviewer status leaves `pending`) | Part B decisions recorded back into the pilot-review fixture |
| G27-AC06 (single-reviewer handoff) | Part B, with `review_protocol.reviewer_count = 1` unchanged |
| Spec lines 109–114 (pilot protocol) | Part A fully declared before the first maintainer run |
| Outcomes/handoff (spec lines 133–137) | Part C completed after the run |

Recording Part B decisions means updating the four `reviewer` objects in
`openclaw-g27-pilot-review-v1.json` from `{"status": "pending", ...}` to the
chosen decision and notes, and flipping `review_protocol.reviewer_status` to
`complete`. That fixture edit should be a separate, reviewed change once a real
reviewer decision exists — this draft does not pre-fill it.
