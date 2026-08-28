# G01 — Project foundation and deterministic scanner

**Status:** active
**Dependencies:** none

## Purpose

Establish a trustworthy, zero-model discovery boundary and the stable candidate
contract on which provenance, memory, investigation, validation, and evaluation
can be built without conflating static facts with model inference.

## Objective

Create an installable, tested Python package and CLI that deterministically
discovers supported pytest disablement markers in a local Git repository and
serializes them as stable candidate records, without model calls, network access,
or target-repository mutation.

## Project alignment

- Advances **OUT-01 — Deterministic discovery**.
- Establishes the candidate contract used later by OUT-02 through OUT-05.
- Advances the discovery portion of SCN-01 and SCN-02; it does not attempt to
  satisfy either scenario end to end.

## Architecture constraints to preserve

- Deterministic before probabilistic.
- Read-only by default.
- Provider boundaries remain explicit.
- Token use is zero for candidate discovery.
- Candidate identity must remain stable for the same repository state and
  logical test target.

## In scope

- Initialization of the Sunset Git repository with an appropriate `.gitignore`.
- A Python package named `sunset` with `pyproject.toml` and a reproducible `uv`
  development workflow.
- A `sunset scan <repository> --format json` CLI command.
- Recursive discovery of Python test files while respecting common repository
  exclusions and `.gitignore` where practical.
- AST-based recognition of:
  - `@pytest.mark.xfail`
  - `@pytest.mark.skip`
  - `@pytest.mark.skipif(...)`
- Static extraction of marker kind, reason when it is a literal, conditional
  expression text, file path, line number, qualified test name, repository HEAD,
  and current Git blame commit for the marker line.
- A versioned `Candidate` schema with deterministic JSON serialization and a
  stable candidate ID.
- Explicit per-file parse errors that do not abort the complete scan.
- Fixture repositories and automated unit/integration tests.
- A README describing the product boundary, supported syntax, and current
  limitations.

## Explicit exclusions

- Any LLM, embedding, LangChain, LangGraph, or LangSmith integration.
- GitHub, issue, pull-request, or release-note retrieval.
- Rationale recovery or expiry classification.
- Database or artifact-store implementation.
- Test execution, marker removal, worktrees, containers, or pull requests.
- Dynamic execution of test modules to resolve computed marker arguments.
- JavaScript/TypeScript or non-pytest frameworks.

## Deliverables

1. Installable package and CLI entry point.
2. Candidate and scan-result domain models.
3. Python AST scanner and focused Git metadata adapter.
4. Representative fixture repository covering supported and unsupported forms.
5. Automated tests and documented verification commands.
6. README with a sample JSON result and safety boundary.

## Goal-level acceptance criteria

- **G01-AC01 — Reproducible setup:** From a clean checkout, the documented `uv`
  setup and test commands complete successfully.
- **G01-AC02 — Supported discovery:** The fixture scan identifies every supported
  xfail, skip, and skipif marker exactly once with correct path, line, qualified
  name, kind, and statically available arguments.
- **G01-AC03 — Stable output:** Two scans of the same repository commit and
  configuration produce byte-identical normalized JSON and identical candidate
  IDs.
- **G01-AC04 — Graceful partial failure:** A syntactically invalid Python file is
  reported as a structured scan error while valid candidates from other files
  remain in the result.
- **G01-AC05 — Git provenance:** In a Git fixture, each candidate includes the
  repository HEAD and blame commit associated with its marker line; a non-Git
  target produces an explicit supported error rather than fabricated metadata.
- **G01-AC06 — No side effects:** Automated verification demonstrates that scan
  performs no network/model calls and leaves the target repository's status and
  tracked contents unchanged.
- **G01-AC07 — Documented boundary:** The README accurately describes supported
  syntax, exclusions, JSON schema version, deterministic behavior, and the fact
  that Sunset makes no removal recommendation in G01.

## Required verification evidence

| Criterion | Evidence |
| --- | --- |
| G01-AC01 | Clean-environment install and full test command output |
| G01-AC02 | Scanner fixture assertions and CLI integration-test output |
| G01-AC03 | Automated repeated-scan byte comparison |
| G01-AC04 | Parse-error fixture assertion |
| G01-AC05 | Git and non-Git integration-test assertions |
| G01-AC06 | Before/after Git status and content-hash assertion; network/model dependency audit |
| G01-AC07 | README review against the implemented CLI and schema |

Expected commands after scaffolding:

```bash
uv sync --all-groups
uv run pytest
uv run sunset scan tests/fixtures/pytest_repo --format json
```

## Completion and handoff

When all criteria pass:

1. Record criterion-level evidence in the cycle handoff.
2. Change G01 to `complete` in `docs/ROADMAP.md`.
3. Expand G02 into `docs/goals/G02-provenance-artifacts.md`, incorporating only
   findings routed to G02.
4. Mark G02 `proposed`; do not begin it without user authorization.
5. End the cycle report with a suggested commit message based only on G01 work.
