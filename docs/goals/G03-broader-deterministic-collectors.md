# G03 — Broader deterministic collectors

**Status:** proposed
**Dependencies:** G02

## Purpose

Expand Sunset beyond disabled tests without pretending arbitrary old code is
garbage. Collect only high-signal, statically recognizable dependency/version
guards and compatibility shims whose justifying conditions can later be
investigated.

## Objective

Add a versioned, deterministic collector family for supported Python
dependency/version guards and import-fallback compatibility shims. It must
produce evidence-bearing candidates from a committed Git snapshot, preserve G01
candidate compatibility, and identify unsupported or dynamic forms without
executing repository code.

## Project alignment

- Broadens **OUT-01 — Deterministic discovery** beyond test markers.
- Gives G04's LangGraph investigation meaningful non-test candidates.
- Supplies G05 with explicit dependency and platform assumptions to verify.
- Advances SCN-01 and SCN-02 without drawing an expiry conclusion.

## Architecture constraints to preserve

- Candidate discovery remains deterministic, read-only, zero-model, and
  zero-network.
- G01 schema-v1 scanner output remains stable and backward compatible.
- A broader candidate uses an additive, versioned contract rather than changing
  the meaning of a test-marker candidate.
- Source facts, parsed expressions, and Git provenance are distinct from any
  later inference about rationale or safety.
- Recognition is intentionally narrow: unsupported syntax yields no invented
  semantic claim.
- New collectors reuse G02's content-addressed artifacts and provenance
  interfaces rather than creating a second evidence store.

## In scope

- A versioned candidate-family discriminator and source-location contract for
  non-test candidates.
- AST recognition of a documented, bounded set of Python runtime-version guards,
  including comparisons involving `sys.version_info`.
- AST recognition of documented static dependency-version guard forms, including
  literal package names and literal version thresholds obtained through supported
  metadata/version APIs.
- AST recognition of `ImportError`/ `ModuleNotFoundError` import fallbacks
  that select a legacy or compatibility implementation.
- Detection of explicitly structured compatibility branches when both the guard
  and protected import/code path are statically available.
- Static extraction of comparator, subject, literal threshold, protected and
  fallback source spans, import targets when present, and committed-Git
  provenance.
- CLI support for selecting the broader collector family while retaining the
  existing `sunset scan` behavior.
- Fixture repositories for recognized active and expired-looking signals,
  permanent guards, nested guards, import fallbacks, aliases, and dynamic forms.
- Tests for byte-stable output, candidate identity, exclusions, structured
  source/provenance evidence, and no side effects.
- README documentation that candidates are leads, not removal recommendations.

## Explicit exclusions

- Evaluating a version expression, importing target modules, or resolving the
  installed dependency graph.
- Inferring whether a guard is obsolete, a fallback is unused, or removal is
  safe.
- Arbitrary Boolean condition mining, natural-language TODO/FIXME collection,
  feature flags, dead-code detection, and JavaScript/TypeScript support.
- LangChain, LangGraph, LangSmith, models, embeddings, external HTTP, GitHub,
  release-note, issue, or PR retrieval.
- Test execution, worktrees, containers, edits to target repositories, and pull
  requests.

## Candidate boundaries

A recognized candidate must contain all of the following:

1. A supported static guard or import-fallback syntax shape.
2. A literal or canonical subject that identifies the guarded runtime or
   dependency.
3. A source span for the guard and its protected behavior.
4. A committed repository HEAD and blame-backed provenance, available through
   G02.

If a condition is computed, aliased beyond a documented supported form, or
cannot identify a concrete guarded behavior, Sunset records no candidate. Later
goals may use generic search as supporting evidence, but not as this collector's
truth source.

## Deliverables

1. Additive, versioned domain models for guard and shim candidates.
2. Focused AST collectors and a registry/CLI selection boundary.
3. Provenance-artifact integration through G02 interfaces.
4. Representative multi-commit fixture repositories.
5. Determinism, precision, provenance, and side-effect test coverage.
6. README and schema documentation with supported and unsupported forms.

## Goal-level acceptance criteria

- **G03-AC01 — Supported guard discovery:** Fixture scans find every documented
  static runtime/dependency-version guard exactly once, with accurate source
  spans, comparator, subject, threshold, and protected behavior.
- **G03-AC02 — Compatibility-shim discovery:** Fixture scans find supported
  `ImportError`/ `ModuleNotFoundError` fallbacks and identify both import
  alternatives without executing imports.
- **G03-AC03 — Precision boundary:** Dynamic conditions, unrecognized aliases,
  general conditionals, and permanent policy branches do not become fabricated
  compatibility candidates.
- **G03-AC04 — Stable contract:** Repeated scans of the same HEAD produce
  byte-identical JSON and stable IDs; G01 scanner output remains unchanged.
- **G03-AC05 — Provenance reuse:** Every broader candidate resolves through G02
  provenance/artifacts and repeated scans reuse immutable evidence.
- **G03-AC06 — No side effects:** Tests demonstrate no network/model calls,
  target-repository mutation, source execution, or dependency resolution.
- **G03-AC07 — Documented interpretation:** Documentation distinguishes a
  syntactic candidate from proof that the guard or shim should be removed.

## Required verification evidence

| Criterion | Evidence |
| --- | --- |
| G03-AC01 | Fixture assertions for each documented guard form and exact extracted fields |
| G03-AC02 | Fallback-import fixture assertions plus blocked-import execution test |
| G03-AC03 | Negative fixtures for aliases, dynamic values, and ordinary branches |
| G03-AC04 | Repeated-scan byte comparison and G01 regression snapshot |
| G03-AC05 | Artifact IDs and reuse assertions against the G02 store |
| G03-AC06 | Blocked socket/import hooks and before/after Git status/content hashes |
| G03-AC07 | README review against CLI, schemas, supported forms, and limitations |

## Completion and handoff

When all criteria pass:

1. Record criterion-level evidence in the cycle handoff.
2. Change G03 to `complete` in `docs/ROADMAP.md`.
3. Expand G04 with only findings relevant to structured LangGraph
   investigation memory.
4. Mark G04 `proposed`; do not begin it without user authorization.
5. End the cycle report with a suggested commit message based only on G03 work.
