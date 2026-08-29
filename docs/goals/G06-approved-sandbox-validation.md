# G06 — Approved sandbox validation

**Status:** complete
**Dependencies:** G05

## Purpose

Turn an evidence-backed expiry hypothesis into reproducible empirical evidence
without risking a maintainer's working repository or treating passing tests as
proof of safe deletion.

## Objective

Add an explicit approval-gated validator that creates a disposable local clone
at the selected committed `HEAD`, removes only the selected supported pytest
marker there, repeats a narrow test command and optional configured broader
commands, and records raw outputs plus a reproducible environment manifest.

## Project alignment

- Advances OUT-04 and SCN-01, SCN-02, and SCN-07.
- Consumes G04/G05 candidate provenance but does not replace their
  `inconclusive` investigation result or create a final recommendation.

## Architecture constraints to preserve

- No sandbox is created and no test command runs until an explicit approval
  flag is supplied.
- The analyzed repository is read-only: clone source objects but never create a
  worktree, edit files, or alter Git metadata in the target repository.
- Only the AST span for the selected `pytest.mark.xfail`, `skip`, or `skipif`
  decorator may be removed in the disposable clone.
- Test commands run without a shell, in the disposable clone, with bounded
  timeout and raw output stored as content-addressed artifacts outside it.
- A passing experiment is empirical evidence only. It is never phrased as a
  removal recommendation; G07 owns final case files and skeptical review.

## In scope

- Versioned validation result, run, environment-manifest, and error contracts.
- Approval-gated disposable local-clone adapter.
- Marker-only edit and repeated narrow pytest execution.
- Optional configured broader commands, run after the narrow repetitions.
- Artifact-backed stdout/stderr and deterministic fixture coverage for every
  result class.
- CLI and README documentation.

## Explicit exclusions

- Editing the analyzed repository, automatic commits, pull requests, or a
  recommendation that a candidate be removed.
- Containers, networked test setup, dependency installation, or model calls.
- Validating compatibility-collector candidates; their edits need a different
  semantic transformation and remain out of scope for this goal.
- Retry policy based on model confidence, broad project test discovery, or
  flakiness quarantine management.

## Deliverables

1. Approval and sandbox-validation contracts plus a `sunset validate` CLI.
2. Disposable local clone adapter, marker-only transform, and safe command
   runner.
3. Artifact-backed test outputs and environment manifest.
4. Isolated Git-fixture tests and user documentation.

## Goal-level acceptance criteria

- **G06-AC01:** Without approval, validation returns `approval_required`,
  creates no sandbox, runs no command, and leaves the target repository
  byte-for-byte and Git-status unchanged.
- **G06-AC02:** With approval, validation uses a disposable clone pinned to the
  candidate `HEAD`, removes exactly one selected supported pytest decorator,
  and leaves the target repository unchanged.
- **G06-AC03:** Repeated narrow runs plus optional broader commands classify
  results as `confirmed`, `still_failing`, `flaky`, `environment_error`, or
  `inconclusive`, with raw output artifact references.
- **G06-AC04:** Every approved result records a versioned environment manifest
  tied to candidate ID, source `HEAD`, command configuration, and environment
  fingerprint; any transform or command setup failure remains structured.
- **G06-AC05:** CLI and README require explicit approval, describe the
  disposable-clone boundary, and state that no validation result is a removal
  recommendation.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G06-AC01 | Denied-approval fixture with command spy, target snapshot, and Git-status assertions |
| G06-AC02 | Approved fixture compares clone-only decorator removal and target snapshot/status |
| G06-AC03 | Passing, failing, alternating, command-error, and setup-failure fixture matrix |
| G06-AC04 | Manifest/artifact integrity and structured-error assertions |
| G06-AC05 | CLI JSON test and README review |

## Completion evidence

| Criterion | Verified evidence |
| --- | --- |
| G06-AC01 | `test_denied_approval_creates_no_sandbox_runs_no_command_and_preserves_target` asserts `approval_required`, no store, no clone, no command, and unchanged target hashes/status. |
| G06-AC02 | `test_approved_validation_removes_only_clone_marker_and_records_manifest_and_outputs` proves clone-only removal of the selected `xfail` while a second `skip` decorator and the target repository remain intact. |
| G06-AC03 | `tests/test_validation.py` covers actual passing and failing pytest experiments, injected flaky and command-error outcomes, optional broader commands, raw-output artifacts, and structured transform failure. |
| G06-AC04 | The approved-validation test resolves the manifest artifact and checks candidate ID, committed HEAD, and run configuration; setup failure retains that manifest with a structured error. |
| G06-AC05 | CLI tests cover denied and approved JSON output; README documents `--approve`, clone boundaries, result classes, and the absence of a removal recommendation. |

Final verification: `uv lock --check`, `git diff --check`, and
`uv run --locked pytest -q` (52 passed) all passed. A direct recorded fixture
run of `sunset validate ... --approve` produced `confirmed`, two identical raw
test-output artifact IDs, and a content-addressed environment manifest while
the analyzed checkout remained unmodified.
