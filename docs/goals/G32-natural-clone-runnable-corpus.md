# G32 — Natural clone-runnable evaluation corpus

**Status:** complete
**Dependencies:** G30 (loop + report), G06 (disposable-clone validation), G22 + G28
(recorded/authenticated evidence), G25 (split discipline), G21 (corpus protocol)

## Purpose

Enable the first *honest* measurement of the escalation loop. Every result so far
is either a replayed fixture or a constructed demonstration whose evidence and
ground truth were set by the same author (see
[G30-live-loop-run-v2](../research/G30-live-loop-run-v2.md)). A real agent-accuracy
estimate requires cases where the **evidence is the real marker context** and the
**ground truth is the real clone outcome** — neither authored, so the two are
independent.

## Objective

Build a corpus of real `xfail`/`skip`/`skipif` markers mined from pinned public
Python repositories, each paired with (a) recorded real evidence (marker reason,
blame/provenance, linked issues) and (b) a reproducible disposable-clone validation
recipe, with fixed development/holdout splits. Then run the G30 loop over it and
publish the first agent-vs-heuristic result whose bias is characterized rather than
baked in.

## Chosen corpus: langchain-core (decided 2026-09-16)

The pilot corpus is **`langchain-ai/langchain`, package `langchain-core`
(`libs/core`)**, using its `tests/unit_tests` markers. It is pure-Python with light
deps, so clones are fast, deterministic, and cheap; its markers are real temporal
debt that can genuinely be expired or active; and it reconnects to the G08a/G21
pinned LangChain corpus. **OpenClaw is explicitly out of scope for measurement** —
its markers are heavy TS/E2E environment gates (browser, ffmpeg) that are expensive
to run, environment-sensitive (more `not_adjudicated`), and skewed toward "active";
it remains the G27 maintainer-pilot/demonstration repo only.

**Reproducible-environment recipe (pinned):** sparse-checkout `libs/core` at the
pinned commit, create a venv, `pip install -e libs/core` plus the declared `test`
dependency group, then run the marker's test with `--runxfail` (or AST marker
removal) in the disposable clone. Recorded in
[`docs/research/G30-real-case-langchain-core-v1.md`](../research/G30-real-case-langchain-core-v1.md).

**First real case captured** (pilot, N=1): `test_merge_dicts_0_3`
(`xfail "Refactors to make in 0.3"`) at langchain-core 1.6.3 — the live agent said
`likely_expired` (misled by the version signal), the clone still fails
(`likely_active`), the agent was wrong and the clone caught it. This is the first
non-author-coupled adjudicated case. Fixture:
`tests/fixtures/benchmarks/g30-real-cases-v1.json`.

**First natural report captured (2026-09-17, N=9).** All nine `xfail` markers in
`libs/core/tests/unit_tests` run through the full live loop (Sonnet + real clones).
Empirically **8 still active, 1 genuinely expired** (the pydantic-v2-nested xfail,
now supported but never removed — a real stale marker Sunset surfaced by running
the code). The agent abstained (`unknown`) on 7/9 given thin evidence (reason +
version only), escalation resolved all 7, its one confident expiry call was wrong
and the clone caught it, and it agreed-no-clone on one. Artifacts:
`tests/fixtures/benchmarks/g30-natural-{cases,report}-v1.json`, writeup
[`docs/research/G30-natural-report-v1.md`](../research/G30-natural-report-v1.md),
reproduced offline by `test_natural_report_reproduces_metrics`. Still N=9/one
model/one run — a first natural measurement, not a verdict.

**Evidence-enrichment result (2026-09-17):** feeding the agent richer static
evidence — the full test source + the marker's blame — did **not** improve
discrimination (abstention 7/9 unchanged, definite-call accuracy 1-right/1-wrong
unchanged, the one genuinely expired marker still undetected by the agent). Static
text says what is asserted, not whether the code currently behaves that way; only
the clone reveals that. This strengthens the escalation-loop design and cautions
against a G31 that tries to teach static classification. Capability lives in
`src/sunset/evidence_enrichment.py`; finding in
[`docs/research/G30-evidence-enrichment-v1.md`](../research/G30-evidence-enrichment-v1.md).

Candidate markers already located in `libs/core/tests/unit_tests` include
`test_utils.py::test_merge_dicts_0_3`, `test_function_calling.py` (two pydantic-v2
xfails), `test_cache.py` ("caching for streaming yet"), the RunnableSequence
callback-order xfails, and several `IS_GTE_3_11` / pydantic-v1/v2 `skipif` version
guards.

## Project alignment

- Advances OUT-04, OUT-05, OUT-08.
- Advances SCN-01 through SCN-03, SCN-06, SCN-12.
- Unlocks a genuine measurement for a continue/revise/stop decision, and the
  adjudicated cases that [G31](G31-empirical-feedback-loop.md) would learn from.

## Scope boundary

Pinned public repositories, read-only discovery + bounded disposable-clone
execution. A deliberately bounded candidate set with reproducible test
environments. Excludes cleanup, unbounded execution, and any claim beyond the
corpus.

## Architecture constraints to preserve

1. Candidate evidence and empirical outcomes remain independently recorded;
   author-set labels cannot substitute for clone results.
2. Third-party execution is limited to an explicitly vetted repository set,
   disposable clones, declared dependency installs, and configured wall/time,
   byte, and package budgets.
3. Non-conclusive, unavailable, flaky, and unsafe environments are excluded or
   marked `not_adjudicated`; they are never forced into a verdict.
4. Development and holdout partitions are fixed before agent evaluation; no
   holdout result tunes a prompt, policy, exemplar, or threshold.
5. The G30 loop, G06 validator, and G22/G28 evidence contracts remain additive
   and replaceable; no target repository is mutated.

## Deliverables

1. A versioned natural-corpus manifest with pinned repository URLs, exact refs,
   candidate selectors, split assignments, and evidence/artifact digests.
2. A reproducible per-repository environment manifest recording Python runtime,
   dependency installation inputs, package versions, and command budgets.
3. Recorded evidence and validation traces for every included candidate, plus
   explicit exclusion records for candidates that cannot be safely reproduced.
4. A G30 report over the frozen development and holdout partitions, including
   selection bias, non-conclusive counts, and a recall-audit sample.
5. A documented corpus and security audit with no cleanup or target mutation.

## Goal-level acceptance criteria

- **G32-AC01 — Provenance-bound manifest:** Every included case has an exact
  repository ref, candidate selector, source evidence digest, split, and a
  deterministic case ID; duplicate or moving refs are rejected.
- **G32-AC02 — Reproducible environments:** Every included case has a recorded
  supported runtime and dependency manifest, and the declared narrow test command
  can be replayed in a disposable clone or the case is explicitly excluded with
  a structured reason.
- **G32-AC03 — Safe execution:** The vetted-repository allowlist, disposable
  clone, package/network budgets, timeout, and target snapshot guard are enforced;
  tests prove the pinned source checkout is unchanged.
- **G32-AC04 — Honest outcomes:** Every attempted case records `confirmed`,
  `still_failing`, `flaky`, `environment_error`, or `inconclusive`; only the
  first two derive an empirical condition status.
- **G32-AC05 — Split discipline:** Development/holdout assignments are fixed
  before the G30 run, and an audit rejects holdout-derived tuning or evidence.
- **G32-AC06 — Natural evaluation:** A recorded G30 run reports per-case agent
  and heuristic statuses, escalation, clone outcome, empirical adjudication,
  unsupported claims, and selection-bias limitations, plus a declared recall
  audit over agreement cases.
- **G32-AC07 — Replayability:** Recorded corpus audit and report reproduce
  byte-identically without live model calls, network reads, or target mutation.

## Criterion-to-evidence map

| Criterion | Required evidence |
| --- | --- |
| G32-AC01 | `tests/test_natural_corpus.py::test_manifest_binds_exact_refs_and_ids` |
| G32-AC02 | `tests/test_natural_corpus.py::test_environment_recipe_is_recorded_or_excluded` and environment fixtures |
| G32-AC03 | `tests/test_natural_corpus.py::test_vetted_disposable_boundary` and target snapshot evidence |
| G32-AC04 | `tests/test_natural_corpus.py::test_non_conclusive_outcomes_are_not_labels` |
| G32-AC05 | `tests/test_natural_corpus.py::test_split_audit_rejects_holdout_tuning` |
| G32-AC06 | `tests/fixtures/benchmarks/g32-natural-report-v2.json` and `docs/research/G32-natural-report-v2.md` |
| G32-AC07 | `tests/test_natural_corpus.py::test_recorded_report_replays_byte_identically` |

## Execution contract

### Expected implementation surface

- `src/sunset/natural_corpus.py`: manifest loading, exact-ref audit, split and
  environment validation, and recorded report assembly.
- Existing `src/sunset/git_evidence.py`, `src/sunset/blame_evidence.py`,
  `src/sunset/validation.py`, and `src/sunset/escalation_report.py`: reuse these
  provider seams; do not add a second clone or evidence implementation.
- `tests/test_natural_corpus.py` and
  `tests/fixtures/benchmarks/g32-natural-{manifest,environment,report}-v2.json`.
- `docs/research/G32-natural-report-v2.md` and this goal specification.

Equivalent modules are allowed only when the exact-ref, environment, split,
side-effect, and report contracts remain unchanged.

### Canonical contracts and invariants

Manifest schema version `2` contains `case_id`, `repository_url`, `pinned_ref`,
`candidate_selector`, `split`, `evidence_digests`, `environment_id`, and
`status`. A case is runnable only when `status` is `ready`, its ref is a full
40-character SHA, its split is `development` or `holdout`, and its evidence
digests are present. Validation outcomes use the G06 five-value vocabulary;
empirical status is absent for non-conclusive outcomes. Case IDs are derived
from the pinned ref and selector, not from a mutable branch name.

### Deterministic behavior matrix

| Input | Required result |
| --- | --- |
| full SHA, recorded evidence, pinned environment | case is eligible for replay |
| branch/tag ref or missing evidence digest | manifest rejected; no clone |
| missing dependency lock/runtime | case excluded with structured reason |
| vetted clone passes without marker | `confirmed` → `likely_expired` |
| vetted clone still fails without marker | `still_failing` → `likely_active` |
| flaky, timeout, unsafe, or unavailable environment | `not_adjudicated`; no inferred label |
| agreement audit sample | bounded validation may run under approval; result remains empirical |

### Authority, network, and stop conditions

Discovery and evidence are read-only. Clone execution requires an explicit
vetted-repository policy and human approval, writes only disposable temporary
directories and the external artifact store, and never writes the target
checkout. Stop after the configured case, package, byte, network, or wall-time
budget; a missing dependency or failed clone is a recorded exclusion, not a
retry loop. Live model calls are separate from recorded corpus construction.

### Replay, cache, and split rules

Manifest identity includes the exact ref, selector, environment digest, split,
and G30 configuration. Replaying the identity reuses immutable artifacts. A
changed ref or environment invalidates only affected validation results. Holdout
artifacts are readable only for the final sealed report and cannot feed tuning,
exemplar construction, or mechanism selection.

## The hard problems (this goal must solve them, not assume them away)

1. **Reproducible environments.** Running a real marker requires the repo's
   dependencies at the pinned commit. G32 must pin dependency versions per
   candidate and record the environment, or the "empirical" result is not
   reproducible. Candidates whose environment cannot be pinned are excluded, not
   guessed.
2. **Executing third-party code safely.** G06 is explicitly *not* a security
   sandbox — running a repo's tests runs its code and installs its deps. G32 must
   either restrict to vetted repositories or add a bounded container/sandbox
   capability; unbounded execution of arbitrary repos is prohibited.
3. **Selection bias.** Clone-runnable markers (installable deps, deterministic
   tests) are a biased subset of all temporal debt. The corpus must document this
   and must not generalize beyond it.
4. **Non-conclusive outcomes.** Flaky/environment-error/inconclusive clone results
   are recorded as `not_adjudicated`, never forced into a verdict.
5. **The recall gap.** To estimate how often the loop *fails* to escalate a real
   expiry, include an audit sample of agreement cases that are also validated.

## Explicit exclusions

Author-set evidence or ground truth; unbounded dependency installation or arbitrary
third-party code execution outside a bounded/vetted boundary; cleanup or target
mutation; tuning on the holdout; treating a passing clone as removal proof;
accuracy claims beyond the clone-runnable subset.

## Outcomes and handoff

A frozen, provenance-bound, clone-runnable corpus with fixed splits, plus a G30
report over it that states an agent-vs-heuristic result with characterized
selection bias and a recall-audit estimate — the first result that is a
measurement rather than a demonstration.

## Capability unlocked for the next goal

A real evaluation substrate for G31 (empirical feedback loop) and for any
maintainer-facing quality claim.

## Note

The goal is complete. The existing LangChain natural run is now a frozen
development/holdout corpus and first measurement; later work may expand the
manifest and recall-audit sample without treating the current N=9 report as a
quality verdict.

## Completion evidence (2026-10-10)

- **G32-AC01:** `g32-natural-manifest-v2.json` binds nine cases to the full
  LangChain commit SHA, derived case IDs, candidate selectors, evidence digests,
  and fixed development/holdout assignments. `test_manifest_binds_exact_refs_and_ids`
  rejects a moving ref before any clone.
- **G32-AC02:** `g32-natural-environment-v2.json` records CPython 3.12.8,
  declared package installation, package versions, dependency digest, test
  command, and budgets. `test_environment_recipe_is_recorded_or_excluded`
  passes and missing recipes are rejected.
- **G32-AC03:** The manifest allowlist and budget audit are read-only; the
  agreement-case disposable run recorded `target_unchanged: true`. The
  `test_vetted_disposable_boundary` socket/subprocess guards prove corpus audit
  and replay do not clone, network, or execute code.
- **G32-AC04:** `g32-natural-report-v2.json` records `confirmed` and
  `still_failing` outcomes as empirical statuses and preserves the unadjudicated
  agreement case. `test_non_conclusive_outcomes_are_not_labels` rejects a flaky
  result coerced into a condition label.
- **G32-AC05:** The split commitment is recorded in the manifest; holdout case
  IDs and artifacts are rejected as tuning inputs by
  `test_split_audit_rejects_holdout_tuning`. The report has no tuning inputs.
- **G32-AC06:** The report includes per-case heuristic/agent statuses,
  escalation, clone outcome, empirical status, unsupported claims, selection
  bias, and an executed one-case agreement recall audit. The audit documents
  that this is a sample, not a recall estimate.
- **G32-AC07:** `test_recorded_report_replays_byte_identically` and the locked
  suite pass without model, network, subprocess, or target-repository access;
  the manifest audit digest is
  `590647846374a91baf6f8a92c8ceccca9b0e07653ca086e67260b6fc25d39650`.

Focused verification: `.venv/bin/python -m pytest -q tests/test_natural_corpus.py`.
The full locked suite and `git diff --check` are required before commit.
