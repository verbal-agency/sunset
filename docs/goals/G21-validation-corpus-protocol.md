# G21 — Validation corpus protocol and provenance audit

**Status:** complete
**Dependencies:** G20 (complete)

## Purpose

Establish trustworthy evaluation inputs before measuring or optimizing an
epistemic system whose labels cannot safely be inferred from code age, a commit
message, or a historical cleanup alone.

## Objective

Define and enforce a versioned, provenance-bound validation-corpus packet and
offline audit. The packet must distinguish a pinned historical outcome from an
unadjudicated protected-condition label, record the evidence needed for later
adjudication, make exclusions explicit, and fix development/holdout partitions
before any evaluation or optimization run.

## Project alignment

- Advances OUT-02, OUT-05, and OUT-08.
- Advances SCN-01 through SCN-03 and SCN-12.
- Unlocks G22a's real-artifact capture and G23's independent adjudication
  without conflating source provenance,
  historical outcome, and protected-condition ground truth.

## Architecture constraints to preserve

- Historical removal or retention is an observed outcome, not evidence that a
  protected condition was absent, present, or safely removable.
- The corpus is local, recorded, and read-only by default. Loading, auditing,
  and tests must make no network request, model call, subprocess, repository
  checkout, target-code import, or target-repository mutation.
- Raw source payloads, credentials, customer data, and model outputs are not
  stored in the corpus manifest or audit output. References use immutable IDs,
  pinned commits, and public URLs only.
- The split is part of corpus identity. Holdout cases cannot contain an
  optimization result, a selected configuration, or an evaluation prediction.
- `unprepared`, `excluded`, and later `unadjudicated` states are legitimate
  outcomes. The audit must never promote them to eligible labels.

## Scope boundary

Implement only the local corpus packet, audit, CLI, fixtures, and documentation
needed to prepare later independent adjudication. This goal neither decides a
protected condition nor runs Sunset against a case. It is deliberately a
protocol-and-provenance goal, not an evaluation or optimization goal.

## Execution contract

### Expected implementation surface

Create `src/sunset/validation_corpus_models.py` and
`src/sunset/validation_corpus.py`; extend `src/sunset/cli.py` with
`sunset validation-corpus audit --manifest PATH [--output PATH] [--max-cases N]`;
add
`tests/test_validation_corpus.py`; add fixtures under
`tests/fixtures/validation_corpus/`; and create `docs/VALIDATION.md`.
Update `docs/ROADMAP.md`, `docs/RELEASE.md`, and `docs/SAFETY.md` only as needed
to link the protocol and its non-authority limitation. Equivalent modules are
permitted only if they retain these public imports, CLI behavior, fixture path,
and focused-test coverage.

### Canonical contracts and invariants

Define `VALIDATION_CORPUS_SCHEMA_VERSION = "1"` and versioned, immutable
contracts for `EvidencePointer`, `EvidenceRequirement`, `ValidationCase`,
`ValidationCorpus`, `CorpusAudit`, and `ValidationCorpusError`.

`EvidencePointer` has a unique `evidence_id`, a `source_kind` of
`public_git` or `recorded_artifact`, a role of `historical_outcome`,
`introduction_context`, `condition_evidence`, `counter_evidence`, or
`validation_scope`, a pinned full Git SHA when the source is Git, and a URL or
artifact ID. It contains no raw payload field.

`EvidenceRequirement` has a stable `requirement_id`, one of
`introduction_context`, `condition_status`, `counter_evidence`, or
`validation_scope`, and a nonempty proof obligation. It may reference zero or
more `EvidencePointer` IDs; zero references means the requirement remains
missing, not satisfied.

`ValidationCase` has a unique `case_id`, `source_case_id`, candidate family,
repository identity, pinned HEAD, candidate path, historical outcome
(`removed`, `retained`, or `unknown`), split (`development`, `holdout`, or
`excluded`), packet state (`unprepared`, `ready_for_adjudication`, or
`excluded`), evidence pointers, evidence requirements, and an optional
nonempty exclusion reason. It has no condition-state label, model prediction,
selected configuration, raw payload, credential, or cleanup authority field.

`ValidationCorpus` has an ID, schema version, source-manifest identity, and
cases. `CorpusAudit` has the deterministic corpus digest, counts by split,
historical outcome, and packet state; missing requirement IDs; excluded cases
and reasons; processed and unprocessed IDs; a `gate_ready` boolean; and an
explicit non-authority disclaimer.

Packet state is immutable within a G21 manifest: it has no runtime transition.
`unprepared` is legal only when one or more of the four required requirement
categories is absent; `ready_for_adjudication` is legal only when all four are
present, regardless of whether a requirement still has zero evidence pointers;
`excluded` is legal only with a nonempty exclusion reason. G21 never emits
`adjudicated`, `eligible`, or a condition-status terminal state.

Reject duplicate case, source-case, evidence, or requirement IDs; unsupported
schema/enums; abbreviated or unpinned Git identity; a missing candidate path;
an `excluded` case without a reason; an exclusion reason on a non-excluded
case; dangling evidence references; and a holdout case containing a prohibited
evaluation/optimization field. A case missing a required requirement category
is valid only as `unprepared`; a requirement with no evidence pointers remains
an explicit proof obligation. Neither state is gate ready. `gate_ready` is
always false in G21 because G23 has not independently adjudicated any
protected-condition labels.

### Deterministic behavior matrix

| Input or evidence condition | Required observable result |
| --- | --- |
| Valid pinned source case with all four requirement categories | `ready_for_adjudication`; audit lists any requirement with zero evidence pointers. |
| Valid pinned case with missing condition-status or counter-evidence | Preserve the case as `unprepared` and list the missing proof obligation; do not infer a label. |
| Two cases or pointers share an ID | Reject the manifest with a stable duplicate-ID error code. |
| Pinned historical removal has no condition label | Report `historical_outcome=removed`, `gate_ready=false`; never treat removal as expiry. |
| Excluded case has a recorded reason | Count and report it separately from eligible/adjudication-ready coverage. |
| Excluded case lacks a reason, or a required source field is malformed | Reject the manifest with a stable validation error code. |
| Audit reaches its declared `max_cases` budget | Return a deterministic incomplete audit with processed and unprocessed IDs; do not claim coverage or readiness. |
| Same corpus and audit-policy identity replay | Produce byte-stable JSON and the same digest. |
| Corpus, schema, or audit-policy identity changes | Produce a different digest and do not reuse the incompatible report. |

### Authority, side effects, and stop conditions

The module and CLI may read the supplied local JSON manifest and write an audit
only to an explicit output path. They may not access the network, credentials,
model providers, shells, Git commands, target repositories, target code,
validation adapters, or mutation/approval paths. The CLI stops after a valid
complete audit, a validation error, or the caller's `max_cases` budget. It
returns a structured incomplete audit for budget exhaustion and a nonzero error
for malformed input; it never silently falls back to live collection.

### Replay, cache, and budget rules

Audit identity is a SHA-256 digest of canonical corpus JSON plus schema and
audit-policy versions. A caller may reuse an existing audit only when that
identity matches exactly. Duplicate audit requests with the same explicit
output destination may overwrite only byte-identical content; otherwise they
must fail rather than replace a result from a different identity. `max_cases`
must be a positive integer; the audit orders cases by `case_id` before applying
the budget. No model, token, request, or external-operation budget exists in
this goal because those operations are prohibited.

### Required fixture matrix

The focused suite must use committed offline fixtures for all of the following:

| Fixture condition | Required assertion |
| --- | --- |
| Positive historical removal and retained cases | Both preserve their distinct outcomes without becoming a condition label. |
| Negative/missing-evidence case | It remains `unprepared` with a named proof obligation. |
| Contradictory-evidence case | Both condition and counter-evidence pointers remain visible; the audit makes no resolution. |
| Malformed and duplicate records | Stable validation error codes are returned. |
| Partial/budget-exhausted audit | Processed and unprocessed case IDs are exact and the report is incomplete. |
| Unsupported schema or evidence source | The loader rejects it without fallback or network access. |
| Replay and identity change | Matching input is byte-stable; changed corpus or policy identity is not reused. |

## In scope

1. A local, versioned validation-corpus packet schema and strict loader.
2. A 20-case starter packet derived one-to-one from the committed G08a public
   corpus records, preserving each source identity and historical outcome.
3. Fixed development/holdout/excluded partitions and required-evidence packet
   metadata for each starter case.
4. Deterministic offline audit, JSON output, CLI, fixture coverage, and
   documentation of what the audit does and does not establish.

## Explicit exclusions

- Protected-condition label creation, adjudication, or automatic resolution.
- Running Sunset's heuristic or agentic investigator, collecting live Git data,
  browsing, fetching artifacts, or calling a model.
- Performance, calibration, or removal-safety claims.
- Any target-repository execution, validation, mutation, cleanup proposal, or
  approval action.
- Replacing G20's evaluator or changing its thresholds.

## Deliverables

1. Versioned corpus, evidence-pointer, requirement, and audit contracts.
2. A committed 20-case starter validation packet and adversarial fixtures.
3. Offline audit CLI and deterministic JSON report.
4. Validation-protocol documentation that explains label limits, split rules,
   and the handoff to independent adjudication.

## Goal-level acceptance criteria

- **G21-AC01 — Schema integrity:** The loader accepts the committed starter
  packet and rejects every illegal state named in the contract with stable
  error codes.
- **G21-AC02 — Provenance and non-inference:** The starter packet preserves all
  20 G08a source identities and historical outcomes, contains required evidence
  categories, and cannot serialize a protected-condition label or model output.
- **G21-AC03 — Split and exclusion control:** Every case has exactly one valid
  split; excluded cases have explicit reasons; holdout records reject leakage
  fields; and packet state never makes a G21 case gate-ready.
- **G21-AC04 — Deterministic audit:** The CLI and library emit a byte-stable
  audit with digest, counts, missing requirements, exclusions, and incomplete
  budget behavior.
- **G21-AC05 — Offline safety and replay:** Socket, subprocess, model, and
  target-repository guards prove default loading/auditing are local-only;
  compatible replay is stable and changed identity invalidates reuse.
- **G21-AC06 — Verification and documentation:** The focused suite, locked full
  suite, docs review, and diff checks pass, and `docs/VALIDATION.md` states that
  the packet is not independently adjudicated ground truth.

## Criterion-to-verification map

| Criterion | Required named evidence |
| --- | --- |
| G21-AC01 | `test_g21_ac01_schema_integrity` plus malformed, duplicate, and illegal-state fixtures |
| G21-AC02 | `test_g21_ac02_provenance_and_non_inference` against the 20-case starter packet |
| G21-AC03 | `test_g21_ac03_split_and_exclusion_control` including holdout-leakage and exclusion-reason cases |
| G21-AC04 | `test_g21_ac04_deterministic_audit` including complete and `max_cases`-limited reports |
| G21-AC05 | `test_g21_ac05_offline_safety_and_replay` with socket/subprocess/model guards and identity invalidation |
| G21-AC06 | `test_g21_ac06_verification`, `uv lock --check`, locked full suite, documentation review, and `git diff --check` |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q tests/test_validation_corpus.py
uv run --locked pytest -q
git diff --check
git status --short
```

## Risks and carried-forward findings

- The current G08a corpus demonstrates pinned historical outcomes, not the
  condition labels needed for efficacy claims. G23 owns independent human
  assessment; it must not treat G21 packet preparation as adjudication.
- A 20-case starter packet supports protocol testing, not a statistically
  persuasive product conclusion. G22 and G23 must report coverage and any
  representativeness limits before an empirical claim.
- If source evidence becomes unavailable or contradicts the packet, retain the
  case with an explicit missing/contradictory requirement or exclude it with a
  reason; do not repair it with an inferred label.

## Completion evidence

- `uv lock --check` completed successfully.
- `uv run --locked pytest -q tests/test_validation_corpus.py` completed
  successfully: 6 tests passed.
- `uv run --locked pytest -q` completed successfully: full suite green.
- `.venv/bin/python -m sunset validation-corpus audit --manifest
  tests/fixtures/validation_corpus/langchain-validation-v1.json` completed
  successfully: 20 cases audited, 14 development, 6 holdout, 60 missing proof
  obligations, and `gate_ready=false`.
- `git diff --check` completed successfully.
- The committed 20-case packet audits as 14 development and 6 holdout cases,
  with `gate_ready=false` and missing condition-status proof obligations.

All six goal criteria are satisfied by the named tests and artifacts above.
G22 subsequently completed the pinned Git evidence-ingestion seam. G22a is now
the next proposed goal; G23 follows it and requires recorded independent human
review input before activation.
