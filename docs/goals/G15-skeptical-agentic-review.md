# G15 — Temporal-debt epistemic model

**Status:** proposed
**Dependencies:** G14 (complete)

> The filename retains the original planning label for link stability; the
> heading and objective below are authoritative. This goal is the epistemic
> model, not a skeptical reviewer or final case-file implementation.

## Purpose

Define what Sunset is trying to know before adding more agent behavior: the
condition historically contingent code protects, the competing explanations for
that condition, and the evidence still needed before a maintainer reviews a
counterfactual removal experiment.

## Objective

Introduce versioned domain contracts and deterministic normalization for a
temporal-debt ontology, protected-condition hypotheses, evidence roles,
condition-status states, contradictions, scope/freshness, and explicit proof
obligations. Adapt existing G10–G14 receipts into this model without treating a
Git introduction, citation, external status, or passing validation as proof.

## Project alignment

- Advances OUT-02, OUT-06, OUT-07, and OUT-08.
- Advances SCN-01 through SCN-03, SCN-08, and SCN-09.
- Establishes the shared semantics required by G16 evidence graphs, G17 context
  expansion, G18 operational evidence, G19 review, and G20 calibration.

## Execution contract

This section makes G15 directly executable when the roadmap marks it `active`.
It constrains implementation choices without requiring a particular framework.

### Expected implementation surface

- Add framework-independent versioned contracts in a new temporal-epistemics
  model module, following the frozen dataclass and `to_dict`/`from_dict`
  conventions used by the existing `*_models.py` modules.
- Add deterministic normalization and state-rule logic in a separate module;
  adapters may depend on existing G10–G14 domain models but must not import
  LangChain, open a socket, execute the target repository, or invoke validation.
- Add `tests/test_temporal_epistemics.py` plus isolated fixtures under
  `tests/fixtures/` for each candidate family, competing hypotheses,
  contradiction, missing operational evidence, and validation scope limits.
- Update the project vocabulary documentation and preserve all existing public
  schemas and CLI behavior.

### Canonical contracts and invariants

The implementation must define and serialize, with one schema-version field:

| Contract | Required semantics |
| --- | --- |
| Candidate family | One of the bounded supported families; unsupported forms remain `unknown`. |
| Protected-condition hypothesis | Stable hypothesis ID, candidate ID, condition statement, confidence-independent status, and supporting evidence IDs. Multiple hypotheses must coexist. |
| Evidence statement | Evidence ID, source class, role (`support`, `contradict`, `scope_limit`, or `missing`), claim/condition reference, scope, freshness, and provenance. |
| Proof obligation | Concrete missing evidence, why it matters, scope/owner if known, and whether validation can address it. |
| Conclusion | Progress/status state, hypothesis IDs, evidence IDs, contradictions, proof obligations, and an explicit non-authority flag. |

State transitions must be deterministic and reject illegal jumps. In
particular, `validated_in_scope` cannot imply `human_approved`, and neither may
be serialized as proof that deletion is safe. Contradictory or missing decisive
evidence must terminate as `contradictory_evidence`, `insufficient_evidence`, or
`unvalidatable` rather than selecting the most confident hypothesis.

The transition rules for this goal are:

| From | Allowed next state | Rule |
| --- | --- | --- |
| `discovered` | `condition_hypothesized` or `insufficient_evidence` | A candidate may have zero or more hypotheses; no hypothesis is inferred from age alone. |
| `condition_hypothesized` | `condition_identified`, `condition_likely_expired`, `condition_likely_active`, or a conservative terminal outcome | The selected state must be justified by normalized evidence and retain alternatives. |
| `condition_identified` | `condition_likely_expired`, `condition_likely_active`, `removal_testable`, or a conservative terminal outcome | Identification is not an expiry claim. |
| `condition_likely_expired` or `condition_likely_active` | `removal_testable` or a conservative terminal outcome | Missing or contradictory decisive evidence takes precedence over a confident status. |
| `removal_testable` | `validated_in_scope` or `unvalidatable` | Validation is scope-limited and is represented only when an existing G14 receipt is present. |
| `validated_in_scope` | terminal for G15 | G15 does not authorize approval or emit a safe-removal conclusion. |

`human_approved` may be adapted from an existing receipt for compatibility, but
G15 must never create that state. A malformed receipt, illegal transition, or
unrecognized family fails closed as `insufficient_evidence` without invoking a
provider, model, repository, or validator.

### Terminal and stop conditions

Normalization stops after all supplied receipts are adapted, after a
contradiction or missing proof obligation makes further local normalization
unable to decide, or when an input violates the schema. The result must carry
the evidence and proof obligations accumulated before stopping. This goal never
opens a network connection, calls a model, executes a target repository, or
requests validation as a side effect.

### Fixture and criterion map

The focused test module must contain named tests for G15-AC01 through G15-AC06;
each test must assert both the positive behavior and the conservative negative
case. The fixture matrix must include at least one disabled-marker case, one
compatibility-shim case, one version-guard case, and one unsupported/dynamic
case. Every normalized evidence statement must retain scope and provenance from
its source receipt.

## Architecture constraints to preserve

- A protected condition is a hypothesis, not a recovered historical fact.
  Multiple hypotheses and unresolved ambiguity must be representable.
- Evidence roles are explicit: support, contradict, establish, scope-limit, and
  missing. Citation presence alone must not establish a condition-status claim.
- Static, historical, external, operational, and validation evidence have
  distinct scope. A G14 result is `validated_in_scope`, never proof of safe
  removal or absence of an unsupported runtime/customer condition.
- The goal is deterministic and offline: no new model calls, provider requests,
  repository execution, validation execution, or arbitrary context access.

## In scope

1. A bounded temporal-debt taxonomy for the supported Phase 1 families:
   disabled pytest markers, compatibility shims, version guards, and explicit
   feature-flag-like conditional candidates where existing receipts can identify
   them.
2. Versioned protected-condition, hypothesis, claim, evidence-role,
   contradiction, scope/freshness, proof-obligation, and conclusion contracts.
3. Deterministic adapters from G10 local receipts, G13 external receipts, and
   G14 validation results into normalized evidence statements.
4. A non-automatic status vocabulary that separates investigation progress from
   removal authority: `discovered`, `condition_hypothesized`,
   `condition_identified`, `condition_likely_expired`,
   `condition_likely_active`, `removal_testable`, `validated_in_scope`, and
   `human_approved`; plus conservative terminal outcomes
   `contradictory_evidence`, `insufficient_evidence`, and `unvalidatable`.
5. Isolated fixtures that demonstrate ambiguity, contradiction, scope limits,
   missing operational evidence, and counterfactual-validation limits.
6. Documentation of the ontology and product vocabulary.

## Explicit exclusions

- New external or operational providers, arbitrary source/context expansion,
  model/reviewer calls, approval/validation changes, case-file rendering,
  recommendations, edits, pull requests, or release claims.
- Universal automated classification of arbitrary temporal debt; the taxonomy is
  deliberately bounded to current supported candidate families.

## Deliverables

1. Framework-independent epistemic domain models and deterministic adapters.
2. Fixture corpus and tests for supported candidate classes and condition states.
3. Documentation for evidence roles, scope, proof obligations, and result
   vocabulary.

## Goal-level acceptance criteria

- **G15-AC01 — Bounded ontology:** Every supported candidate maps to a declared
  temporal-debt family and protected-condition shape; unsupported forms remain
  explicit unknowns rather than fabricated categories.
- **G15-AC02 — Hypotheses and evidence roles:** The model represents multiple
  condition hypotheses plus supporting, contradicting, scope-limiting, and
  missing evidence without equating a Git commit or citation with rationale.
- **G15-AC03 — Conservative condition states:** Deterministic fixtures produce
  progress, condition-status, and conservative terminal outcomes only when their
  declared evidence rules hold; `validated_in_scope` and `human_approved` never
  imply a claim that deletion is safe.
- **G15-AC04 — Scope and proof obligations:** External EOL, source metadata,
  and validation results retain their limits; missing operational/customer/runtime
  evidence becomes a concrete proof obligation rather than a removal conclusion.
- **G15-AC05 — Compatibility and safety:** G10–G14 receipts adapt without schema
  migration or raw-content leakage, and the offline model opens no socket,
  target repository, provider, validator, or model runtime.
- **G15-AC06 — Documentation and verification:** Project framing and ontology
  documentation distinguish condition evidence from safety proof; locked full
  and focused tests pass.

## Expected verification evidence

| Criterion | Evidence |
| --- | --- |
| G15-AC01 | Positive/negative family fixture matrix |
| G15-AC02 | Multi-hypothesis and evidence-role serialization tests |
| G15-AC03 | State transition fixtures for every conservative outcome |
| G15-AC04 | EOL, support-policy-missing, and validation-scope examples |
| G15-AC05 | Receipt compatibility, socket/import/validator guards, and raw scans |
| G15-AC06 | Documentation review, focused tests, locked full suite, and diff check |

## Required verification commands

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked pytest -q tests/test_temporal_epistemics.py
git diff --check
git status --short
```

## Carried-forward findings and risks

- G13 external evidence often establishes upstream state, not deployment or
  customer compatibility. G18 must provide operational evidence contracts; G15
  must model that absence now as a proof obligation.
- G14 validation proves only behavior covered by the reviewed experiment. Its
  result must remain scope-limited even when confirmed.
- Compact receipts are safety boundaries but can become a sensor bottleneck.
  G17 must add controlled relation-based expansion only after G15 defines what
  evidence relation a hypothesis is missing.
