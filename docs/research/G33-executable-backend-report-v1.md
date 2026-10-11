# G33 executable backend report v1

**Run date:** 2026-10-10  
**Mode:** live transport with explicit GitHub/network authorization  
**Repository:** `https://github.com/langchain-ai/langchain`  
**Pinned commit:** `5c1f28271295bb13034f4cf8964f74c117357d40`  
**Candidate:** `libs/core/tests/unit_tests/utils/test_function_calling.py::test_convert_to_openai_function_nested_v2`

## End-to-end result

The canonical `pilot run` request cloned the repository, checked out and
verified the exact SHA, selected the G32 `langchain-core-py312-v1` recipe,
installed the declared editable dependency set in the configured isolated
runtime, resolved the candidate, collected Git evidence, ran the bounded
investigation, and returned `approval_required` without running validation.

The separate `pilot approve` request resumed the same run from its immutable
checkpoint and ran G06 validation in a disposable clone. It returned:

```text
status: completed
validation_outcome: confirmed
repository_head: 5c1f28271295bb13034f4cf8964f74c117357d40
stage_trace: setup → resolve → evidence → investigation → validation → casefile
```

The result included checkout and environment receipts, immutable evidence and
test-output artifact IDs, the hypothesis `Direct pydantic v2 models not yet
supported`, and the unresolved obligation that production deployment and
customer scope remain unproven. The case file stayed explicitly
non-authoritative.

## Boundary evidence

- The source checkout was never edited. Validation removed the marker only in a
  second disposable clone.
- Approval was required before the validator ran; the pre-approval result had
  no validation outcome or case file.
- The live backend rejected a local partial clone with missing Git objects and
  rejected dependency installation when network authorization was absent.
  These are structured fail-closed outcomes, not hidden retries.
- Setup receipts exclude ephemeral filesystem paths from their stable payloads;
  compatible resume reuses the cached checkout and environment receipt.
- Install commands are argv-only, must be `python -m pip install`, and editable
  paths must remain inside the pinned checkout. Shell metacharacters and
  undeclared paths are rejected.

## Verification

```text
.venv/bin/python -m pytest -q tests/test_pilot_runtime.py tests/test_pilot_run_live_fixture.py
.venv/bin/python -m pytest -q tests/test_pilot_run.py
uv run --locked pytest -q
git diff --check
```

This run demonstrates bounded execution of one natural case. It does not prove
that the hypothesis is true for every deployment, and it does not evaluate an
agent tournament.

