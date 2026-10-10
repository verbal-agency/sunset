# G32 natural corpus report v2

**Repository:** `https://github.com/langchain-ai/langchain`
**Commit:** `5c1f28271295bb13034f4cf8964f74c117357d40`
**Package:** `langchain-core` 1.6.3
**Corpus:** 9 real `xfail` markers in `libs/core/tests/unit_tests`
**Environment:** CPython 3.12.8; `langchain-core` 1.6.3; Pydantic 2.14.0;
pytest 9.1.1; declared install `python -m pip install -e libs/core[test]`

## What was measured

The G30 recorded loop was rebound to the G32 manifest. Each case has an exact
commit, candidate selector, source-evidence digest, environment recipe, and
fixed split. The live model statuses and disposable-clone outcomes are carried
forward from the recorded G30 run; they are not labels invented for this
corpus.

- 9 cases: 6 development, 3 holdout.
- 8 escalations; all 8 resolved by disposable validation.
- 7 agent unknowns resolved by validation.
- 1 confident agent expiry claim was wrong; the clone caught it.
- 1 marker was empirically expired (`pydantic-v2-nested`); 7 escalated cases
  remained active.
- 1 agreement case (`chat-tmpl-dict`) was sampled in the recall audit. Its
  unmarked test still failed, so the agreement was correct for this case.

The recall sample is evidence about one agreement case, not a recall estimate.
The report keeps the original holdout sealed from tuning: no case, artifact, or
parameter from the three holdout cases entered the decision process.

## Limits

This is a natural, non-author-coupled corpus, but it is still one repository,
one model, one pinned revision, and a selected set of clone-runnable markers.
Installable and deterministic cases are not representative of all temporal
debt. A passing clone establishes only behavior in that tested environment; it
does not prove removal safe for every deployment or customer.

The manifest audit, environment audit, split audit, and report replay are
offline and non-authoritative. They do not clone, install, call a model, access
the network, mutate the target checkout, approve validation, or perform
cleanup.
