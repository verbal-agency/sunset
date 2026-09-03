# G26 — Broad candidate discovery

**Status:** proposed
**Dependencies:** G25 (complete)

## Purpose

Broaden what Sunset can observe before a maintainer pilot, without weakening the
provenance, uncertainty, or human-approval contracts established by the Python
marker/compatibility slice.

## Objective

Additive deterministic collectors must identify repository-level temporal
signals and at least one JavaScript/TypeScript candidate family, normalize them
into the existing language-neutral candidate/evidence contract, and measure
per-family coverage and false-positive behavior on recorded fixtures.

## Project alignment

- Advances OUT-01, OUT-02, OUT-05, OUT-06, OUT-07, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-05, SCN-06, SCN-08, SCN-09, and SCN-12.
- Unlocks a coverage-qualified candidate set for the G27 maintainer pilot.

## Scope boundary

Candidate families include repository-level version/dependency constraints,
deprecation or migration annotations, feature-flag lifecycle signals, and
environment/configuration gates, with a bounded JavaScript/TypeScript adapter.
Each collector preserves exact source locations, repository identity, committed
revision, evidence role, and unsupported dynamic forms as explicit unknowns.
Additive registry/versioning and offline benchmark fixtures are in scope.

## Explicit exclusions

- Protected-condition inference, prompt optimization, or changing G24/G25 labels.
- Broad reachability/dead-code analysis, arbitrary repository crawling,
  enterprise connectors, live provider access, cleanup, or pull requests.
- Treating a detected signal, stale flag, upstream deprecation, or passing test
  as proof that the protected condition has expired.

## Outcomes and handoff

G26 receives versioned collector contracts, representative positive/negative/
contradictory/unsupported fixtures, per-family detection and false-positive
measurements, and an explicit list of unsupported forms. G27 may use only the
families and scopes whose provenance and limitations are documented.

## Refinement trigger

After G25, refine this proposal into a Luna-ready execution contract that names
the selected signal families, module and fixture paths, schema transitions,
binary acceptance tests, and the language scope approved for the pilot.
