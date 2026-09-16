# G28 — Authenticated exact-SHA Git evidence access

**Status:** complete (2026-09-15)
**Dependencies:** G22 (recorded-first Git evidence provider, complete), G27
(pilot surfaced the need) + explicit host authorization to use a credential

## Completion evidence

- `src/sunset/blame_evidence.py` + `src/sunset/blame_evidence_models.py`:
  `RecordedBlameProvider` (offline default), `GitHubBlameProvider` (explicit
  host-supplied token, allowlisted `api.github.com`, no env discovery, no token
  persistence, fail-closed to `incomplete`), `capture_blame_evidence` (writes a
  fixture only when every request resolves `complete`), `fetch_blame_evidence`.
- Live capture as the authenticated `verbal-agency` account produced
  `tests/fixtures/blame_evidence/openclaw-g27-blame-v1.json` — four distinct,
  line-accurate commits (`7ab5d99a`, `9b1c4bb3`, `3f1c84c7`, `fbfad6eb`).
- `sunset blame-evidence {fetch,capture}` CLI (`--token-env` names the credential
  var explicitly; `--live` required for capture).
- 20 named tests (`tests/test_blame_evidence.py`, `tests/test_cli.py`): recorded
  replay resolves a known line; missing line → `incomplete`; live resolve via
  injected opener; per-line range selection; object-not-found → `missing`;
  GraphQL error → `failed`; credential-absent → `unsupported` with a guard that
  `os.environ` is not read; non-allowlisted host → `unsupported`; byte-identical
  re-capture; partial capture writes no fixture; token never serialized. Full
  suite: 251 passed.
- `docs/BLAME-EVIDENCE.md` documents the capability and boundaries.

## Purpose

Give Sunset a first-class, host-authorized, exact-SHA provenance path so
real-repository blame and reference evidence is *verified line-level Git data*
rather than a guess. The G27 pilot proved the gap: provenance enrichment recorded
a spurious, shared `introducing_commit` for all four candidates
([finding](../research/G27-provenance-defect-v1.md)) because it had no reliable
authenticated blame source at the pinned head. The credential and network already
exist in the operator's shell; this goal makes the pipeline *use* them under the
charter's explicit-provider rules instead of silently guessing.

## Objective

Add an authenticated, exact-SHA Git evidence adapter (authenticated `gh`/GraphQL
blame and/or a bounded shallow clone) behind the existing G22 recordable provider
seam, so that provenance enrichment can obtain line-accurate blame and bounded
reference results at a pinned commit, or return `incomplete` with an explicit
obligation when access is unavailable.

## Project alignment

- Advances OUT-02 (auditable rationale), OUT-05 (measured trustworthiness),
  OUT-07 (replaceable provider contracts), OUT-08 (epistemic discipline).
- Advances SCN-01 through SCN-05, SCN-08, SCN-09.
- Unlocks G29's provenance correction and any future real-repository pilot that
  must cite line-accurate history.

## Scope boundary

- The credential is **host-supplied and explicitly authorized**; the adapter
  never discovers an ambient credential, never widens scope beyond an allowlisted
  host/owner, and records which identity was used.
- Evidence is fetched at an exact pinned commit (`oid`), never at moving `main`.
- Results are content-addressed as recorded fixtures through the existing G22
  path so downstream runs replay offline and byte-identically.
- Read-only: blame, commit metadata, and bounded reference/tree reads only. No
  writes, no clone-and-execute, no target-code execution.
- Line-level blame is authoritative; reference enumeration is explicitly bounded
  (a declared file/path set or an authenticated search budget), and anything not
  covered is reported as an explicit unknown, not silently "none".

## Explicit exclusions

- Storing, printing, or transmitting the credential value; embedding tokens in
  fixtures or artifacts.
- Unauthenticated in-browser code search or scraping as a provenance source
  (proven low-fidelity in the G27 probe).
- Any cleanup, target mutation, or removability inference.
- Broad crawling of a repository beyond the declared candidate/reference budget.

## Outcomes and scenarios advanced

Provides the verified-provenance capability behind OUT-02/OUT-08 and the
provider-portability guarantee of OUT-07, so SCN-01–SCN-03 evidence about "when
and why was this introduced" rests on line-accurate blame rather than a guess.

## Capability unlocked for the next goal

G29 can recompute and verify correct line-level introducing commits for the four
OpenClaw candidates and harden the enrichment path to emit `incomplete` rather
than a placeholder.

## Verification direction (outline — not yet an execution contract)

Named tests for: authenticated blame resolving a known line to a known commit at a
pinned `oid`; `incomplete` returned when the credential/host is absent; recorded
replay producing byte-identical results offline; and a guard proving no credential
value appears in any persisted artifact.
