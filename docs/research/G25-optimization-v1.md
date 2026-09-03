# G25 split-safe optimization

G25 runs preregistered, recorded experiments against the G24 baseline without
calling models, providers, repositories, or subprocesses. Development results
select at most one candidate; the holdout result is then appended once and
cannot change the selection.

The fixture contains four candidates:

- `g25-prompt-001` is selected from development data because it has no safety
  or unsupported-claim regression and stays within the 1,000-token budget.
- `g25-threshold-002` is rejected for an unsupported-claim and safety
  regression.
- `g25-retrieval-003` is rejected as malformed.
- `g25-tool-004` is rejected for budget exhaustion.

The selected configuration's holdout result is sealed under the G24 corpus
digest and holdout identity. This is a split-safe optimization artifact, not a
claim of production removability or universal condition accuracy.
