# Escalation evaluation report — g30-escalation-report-v1

- Mode: **recorded** (executed); model: **claude-sonnet-4-5**; generated 2026-09-16
- Ground truth: **empirical validation** (disposable-clone outcome), not asserted labels.

| Case | Heuristic | Agent | Escalation | Clone outcome | Empirical | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| upstream-fixed (dep bumped past buggy version) | likely_active | likely_expired | disagreement | confirmed | likely_expired | agent right |
| platform-active (windows file locking) | likely_active | likely_active | agreement | — | not_adjudicated | not adjudicated |
| misleading-temp ('safe to remove' but still fails) | likely_active | likely_expired | disagreement | still_failing | likely_active | agent wrong (clone caught) |

## Metrics (empirical)

- cases: 3; escalations: 2 (rate 0.6667)
- escalations resolved: 2 (rate 1.0)
- adjudicated disagreements: 2 — agent wins 1, heuristic wins 1
- error catches (agent wrong, clone caught): 1
- resolved unknowns: 0
- recall: agreements are not validated by design; escalation recall is not computed
