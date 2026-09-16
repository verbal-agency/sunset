# Finding: G27 pilot fixture records spurious introducing commits (v1)

**Discovered:** 2026-09-15, during a GitHub-direct fidelity probe of the G27
maintainer-pilot handoff.
**Severity:** High — violates a core provenance invariant ("no guessed commit";
incomplete provenance must not be presented as historical fact).
**Routed to:** [G29 — Pilot provenance correction](../goals/G29-pilot-provenance-correction.md)
(depends on [G28 — Authenticated Git evidence access](../goals/G28-authenticated-git-evidence-access.md), **complete**).
**Status:** RESOLVED (2026-09-15). Correct values captured by G28 in
`tests/fixtures/blame_evidence/openclaw-g27-blame-v1.json` and applied to the pilot
review fixture by G29, which also added the cross-file shared-commit guard
(`sunset blame-evidence verify`) and an enrichment fail-closed regression test.

## What is wrong

[`tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json`](../../tests/fixtures/public_corpus/openclaw-g27-pilot-review-v1.json)
records `introducing_commit` and `history_locator` for each of the four OpenClaw
candidates. **All four share the identical value `ad6a81d540d899ca52f8eaabb42fdd87cd893ec3`.**

Authenticated verification against `openclaw/openclaw` at the pinned head
`0965053fe6b9341776df147a6934b7485c60b5ca` shows that commit is unrelated to any
candidate:

- `ad6a81d5` (`gh api repos/openclaw/openclaw/commits/ad6a81d5…`) modifies **only**
  `src/agents/tool-search-ranking.ts` — "perf: score Tool Search queries through
  term postings (#134374)". It never touches any `ui/src/e2e/` file.

Four distinct E2E test lines cannot all be introduced by one commit that edits a
single unrelated file. The value is spurious (placeholder or mis-resolved blame),
not a real introduction point.

## Correct provenance (authenticated line-level blame at the pinned head)

Obtained via the GitHub GraphQL `blame` API as the authenticated `verbal-agency`
account — the exact capability G28 formalizes:

| Candidate ID | Location | Fixture value | True introducing commit | Date | Subject |
| --- | --- | --- | --- | --- | --- |
| `sunset-broad-v2-15be1992b07e42a78f0c0b24` | `ui/src/e2e/activity-run-inspector.e2e.test.ts:22` | `ad6a81d5` | `7ab5d99a6c3c` | 2026-08-11 | feat(ui): add durable run inspector |
| `sunset-broad-v2-a4ba4f78d9030728b801e465` | `ui/src/e2e/activity-session-feed.capture.e2e.test.ts:22` | `ad6a81d5` | `9b1c4bb3589d` | 2026-08-29 | fix(ui): theme Web Awesome popup surfaces (#132383) |
| `sunset-broad-v2-eac9359052efa9f30c01df81` | `ui/src/e2e/tool-titles.e2e.test.ts:199` | `ad6a81d5` | `3f1c84c706bf` | 2026-08-30 | fix: tool titles stop after transcript pruning (#133078) |
| `sunset-broad-v2-ccb8a75b35e18dd8955874c5` | `ui/src/e2e/activity-answer-candidates.e2e.test.ts:16` | `ad6a81d5` | `fbfad6eb4226` | 2026-07-17 | feat(codex): show answer candidates in Activity (#90610) |

Each true commit is line-accurate at the pinned head and distinct from the others.

## Reproduction

```bash
gh api graphql -f owner=openclaw -f name=openclaw \
  -F oid=0965053fe6b9341776df147a6934b7485c60b5ca \
  -f path=ui/src/e2e/activity-run-inspector.e2e.test.ts \
  -f query='query($owner:String!,$name:String!,$oid:GitObjectID!,$path:String!){
    repository(owner:$owner,name:$name){ object(oid:$oid){ ... on Commit {
      blame(path:$path){ ranges { startingLine endingLine
        commit { oid messageHeadline committedDate } } } } } } }' \
  --jq '.data.repository.object.blame.ranges[]
        | select(.startingLine <= 22 and .endingLine >= 22)
        | .commit.oid'
```

## Why it matters

- The four E2E lines (define+use, L22/L23) and validation observations were
  independently confirmed correct, so this is *narrowly* a provenance defect — but
  the case packet presents `introducing_commit` as established historical fact, and
  a reviewer weighing "when/why was this added" would be misled.
- It indicates the broad-collector provenance enrichment path either lacked
  exact-SHA blame access or emitted a placeholder without marking provenance
  `incomplete`. The contract in
  [G27](../goals/G27-maintainer-pilot-decision.md) ("Canonical contracts and legal
  states") requires a candidate that cannot establish an introduction point to be
  `incomplete`, never a guessed commit.

## Root-cause hypotheses (to confirm in G29)

1. Enrichment ran without an authenticated exact-SHA blame source and fell back to
   a single nearby/HEAD-adjacent commit (`ad6a81d5`) for every candidate.
2. A blame-batching bug reused one file's (or one default) result across all
   candidates.
3. The enrichment silently substituted a value instead of returning `incomplete`
   with an explicit obligation.

## Method note (why this was found via GitHub-direct, and the access reality)

The in-app browser could not enumerate references (code search needs login) or
script a grep (cross-origin and in-page `fetch` are sandbox-blocked), but the
**shell is fully authorized**: `gh` 2.96.0 logged in as `verbal-agency`, `git`
present, GitHub network egress working. The highest-fidelity path is therefore the
authenticated `gh`/clone route in the shell, not the browser. That access already
exists; G28 makes Sunset's provenance pipeline *use* it explicitly (host-supplied,
allowlisted, no silent credential discovery).
