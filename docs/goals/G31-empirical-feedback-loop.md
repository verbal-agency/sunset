# G31 — Empirical feedback loop for agent judgment (exploration)

**Status:** proposed (exploration / spike)
**Dependencies:** G30 (produces empirically-adjudicated cases), G25 (split-safe
optimization discipline)

## Purpose

Explore whether and how to use G30's **empirically-adjudicated** outcomes — the
disposable-clone ground truth of who was right when the agent and heuristic
disagree — to improve the agent's *future* protected-condition judgments, without
weakening the project's epistemic, split-safety, and human-authority guarantees.

This is worth exploring precisely because the learning signal is trustworthy:
unlike systems that learn from noisy human labels ("assertions that aren't
tested"), G30 yields tested facts. The risk is not a bad signal; it is misusing a
scarce, biased one.

## Objective

An exploration goal, not a production learning system. Survey candidate feedback
mechanisms, define a leakage-safe improvement-and-measurement protocol, enumerate
the risks, and produce a bounded recommendation on whether and what to build —
optionally with one small offline prototype on the development split only.

## Project alignment

- Advances OUT-03, OUT-05, OUT-06, OUT-08.
- Advances SCN-06 and SCN-12.
- Unlocks a decision (and design) for a safe continual-improvement path, or a
  documented decision that it is not yet warranted.

## Scope boundary

Design and analysis, plus at most one small offline prototype evaluated only on the
G25 development split. No production/online learning, no change to the
human-approval boundary or the conservatism guarantees.

## Key exploration questions

1. **Learning signal.** Only empirical adjudication (`confirmed → likely_expired`,
   `still_failing → likely_active`) is ground truth; `flaky` / `environment_error`
   / `inconclusive` and asserted reviewer labels are excluded. Confirm this is the
   sole signal.
2. **Mechanism (compare, don't assume).** Options include: a few-shot exemplar
   memory of adjudicated cases injected into the agent's context; a calibration
   layer over the agent's confidence; retrieval of similar past-adjudicated cases;
   or G25-style prompt/policy optimization. Explicitly *excluded from default
   consideration*: fine-tuning model weights.
3. **Leakage-safe measurement.** Improvement must be measured only on cases the
   agent did not learn from; the G25 holdout stays sealed. Define the protocol
   before any prototype.
4. **The scarce, biased sample.** Ground truth exists only for cases that were
   escalated *and* approved *and* conclusively validated — a biased slice. Explore
   whether learning from it generalizes or just overfits.

## Risks to characterize

- Overfitting to a handful of validated cases (tiny N).
- Distribution shift / selection bias in which cases get ground truth.
- Self-reinforcement: the agent's own outputs steering future judgments into a
  filter bubble.
- Perverse incentives: feedback making the agent over-eager to escalate (cost) or
  over-confident (skips escalation it should make).
- Any drift of model confidence toward becoming removal authority — prohibited.

## Explicit exclusions

Fine-tuning weights; learning from asserted (human) labels or from the holdout;
online self-reinforcement in production; any change that lets feedback, confidence,
or a passing validation become cleanup authority; removing the human approval gate.

## Capability unlocked for the next goal

A bounded recommendation and design for a safe empirical continual-improvement
loop — or a documented, evidence-based decision to defer it.

## Note

Remains an exploration outline until G30 has produced enough empirically-adjudicated
cases to make the exploration meaningful, and until explicitly authorized. It does
not change the human-gated, precision-over-recall guarantees.
