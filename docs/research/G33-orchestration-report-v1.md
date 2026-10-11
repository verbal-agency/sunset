# G33 orchestration report v1

**Run date:** 2026-10-10  
**Mode:** recorded, deterministic, no live network  
**Canonical case:** LangChain at commit `5c1f28271295bb13034f4cf8964f74c117357d40`,
`test_convert_to_openai_function_nested_v2`

## Result

G33 adds one product-facing `pilot run` path. The caller supplies a typed
repository/candidate request once. The service owns setup, candidate lookup,
evidence collection, bounded investigation, approval state, validation resume,
artifact references, and case-file output. The existing low-level commands are
still available for debugging, but a frontend does not compose them.

The recorded canonical request returns `approval_required` with a stable run ID,
a token bound to the request and validation configuration, the inferred
hypothesis, evidence/artifact IDs, and the next action `Approve disposable
validation`. Denial produces no validation call. Approval resumes the same run
and returns a terminal case file with a recorded `confirmed` outcome and an
explicit unresolved production-scope obligation.

## Safety and replay evidence

- Moving refs, unsupported live mode, malformed selectors, and missing recorded
  candidates fail closed before investigation or validation.
- Approval tokens are scoped to one run, request digest, validation digest, and
  expiry. A mismatched token is recorded without consuming the pending approval
  or invoking validation.
- Each run state is stored as an immutable revision. Resuming a run reads the
  highest compatible revision; the original evidence IDs are retained and
  completed stages are not repeated.
- Recorded tests patch socket and subprocess entry points and prove the product
  path uses neither. The service has no target-repository mutation or cleanup
  authority.
- Replaying a recorded request returns byte-identical JSON. Approval transitions
  add immutable revisions rather than overwriting evidence or state.

## Deliberate boundary

The original report covered the recorded tranche. The G33 extension now supplies
the explicit live backend described here: declared runtime recipes, network
authorization, dependency budgets, and the existing disposable validator. The
returned case file remains evidence for human review, never an authorization to
remove code.

## Verification

```text
.venv/bin/python -m pytest -q tests/test_pilot_run.py
uv run --locked pytest -q
git diff --check
```
