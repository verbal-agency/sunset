# G08 — Benchmark and LangSmith evaluation

**Status:** complete
**Dependencies:** G07

## Purpose

Measure whether Sunset's compact evidence memory saves material context without
quietly weakening its conservative decisions, citations, or human-review
boundary.

## Objective

Create a versioned, reproducible benchmark corpus of at least 20 manually
adjudicated history-shaped cases. Evaluate compact-memory case-file decisions
against their expected outcome and full-context token baseline, then export the
same local result in a LangSmith-compatible experiment shape. Publication to
LangSmith is explicit and never part of the default run.

## Project alignment

- Advances OUT-03, OUT-05, and SCN-06.
- Builds on G07's citation-verified case files; it does not make a cleanup
  decision or alter an analyzed repository.

## Architecture constraints to preserve

- Corpus inputs, expected outcomes, evaluator rules, and aggregate report are
  versioned and deterministic; the default benchmark makes no network request.
- Cases are transparent, manually adjudicated regression fixtures with
  committed Git-like histories. They are not represented as a prevalence study
  or as independently verified production incidents.
- The compact-memory measurement uses Sunset's recorded `TokenBaseline` and
  per-node usage. It must call out that the current model-free workflow measures
  estimated context, not provider-billed tokens.
- Quality scoring is deterministic: recommendation/classification match,
  citation resolvability, unsupported-claim rate, and invariant preservation.
  Any optional semantic/human score remains separately labeled.
- LangSmith integration is an adapter: a local export is default; an upload
  requires a caller-supplied API key and an explicit publish flag. No corpus
  source or raw artifact is published implicitly.

## In scope

- Versioned corpus and contracts for cases, expected outcomes, and results.
- At least 20 balanced expired, active, unknown, and contradictory cases.
- Deterministic evaluator plus median token reduction, accuracy, citation,
  unsupported-claim, latency, and cost-availability metrics.
- `sunset benchmark` CLI for local JSON/Markdown report and a LangSmith
  experiment-export document; optional explicit upload adapter with recorded
  request tests.
- Documentation describing corpus limits, SCN-06 threshold, and how to
  interpret a pass or failure.

## Explicit exclusions

- Claiming synthetic or manually adjudicated fixtures prove production
  precision, semantic quality, or provider cost.
- Re-running target tests, providers, or Git collection during a default
  benchmark; all inputs are saved cases and artifact-store data.
- Automatic model judging, hidden network calls, or publishing raw source,
  artifact bytes, credentials, or private repositories.

## Deliverables

1. Versioned benchmark corpus, models, and deterministic evaluator.
2. Local JSON/Markdown benchmark CLI and LangSmith-compatible export.
3. Explicit optional LangSmith upload adapter with no default external write.
4. Twenty-case fixture matrix, threshold report, and usage documentation.

## Goal-level acceptance criteria

- **G08-AC01:** A committed versioned corpus contains at least 20 adjudicated
  cases covering expired, active, unknown, and contradictory evidence; every
  case identifies expected recommendation and token baseline.
- **G08-AC02:** A deterministic local evaluator reports per-case and aggregate
  recommendation accuracy, citation accuracy, unsupported-claim rate, median
  input-token reduction, latency, and cost availability without a network call.
- **G08-AC03:** The report explicitly passes or fails SCN-06 using a 50% median
  reduction, no more than five percentage points classification decline, and no
  citation-accuracy decline; unavailable semantic/cost data is labelled, never
  fabricated.
- **G08-AC04:** JSON and Markdown reports preserve corpus/version/provenance,
  per-case expected-versus-observed results, limitation text, and threshold
  verdict; no recommendation or source content is silently changed.
- **G08-AC05:** `sunset benchmark` defaults to saved inputs and no external
  write. LangSmith export is structured and deterministic; upload requires an
  explicit flag and credential and is covered with a fake-client test.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G08-AC01 | Corpus-schema test and 20-case category/count assertion |
| G08-AC02 | Deterministic metric fixture test plus socket guard |
| G08-AC03 | Passing and threshold-failing comparison fixtures |
| G08-AC04 | JSON/Markdown assertions and immutable input snapshot |
| G08-AC05 | CLI local/export tests and explicit fake LangSmith upload test |

## Completion evidence

- `uv lock --check` passed and `uv run --locked pytest -q` passed: 66 tests.
- `uv run --locked sunset benchmark --corpus tests/fixtures/benchmarks/corpus-v1.json --format markdown`
  produced a 20-case SCN-06 pass: 60% median estimated input-token reduction,
  0.0 classification-accuracy drop, 1.0 citation accuracy in both modes, and
  0.0 unsupported-claim rate.
- The deterministic corpus and evaluator tests cover all four categories, a
  threshold failure, local socket guard, JSON/Markdown output, data-only
  LangSmith export, explicit credential rejection, and fake-client publication.
- The corpus is intentionally labeled as manually adjudicated history-shaped
  regression data. Cost and semantic values are correctly reported as
  unavailable; no provider-billed or production-quality claim is made.
