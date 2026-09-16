# Authenticated exact-SHA blame evidence (G28)

Blame evidence answers one narrow, high-fidelity question: **which commit
introduced a specific line at a specific committed head.** It exists because the
G27 pilot fixture recorded a guessed, shared `introducing_commit` for every
candidate ([finding](research/G27-provenance-defect-v1.md)); a verified line-level
blame source removes the guess.

## Design

- **Recorded-first.** `RecordedBlameProvider` replays a committed fixture and
  never opens a socket or invokes Git. This is the default for tests and demos.
- **Explicit live seam.** `GitHubBlameProvider` calls the GitHub GraphQL `blame`
  API at an exact commit `oid`. The credential is **supplied by trusted
  application code**; the provider never reads `os.environ` or any ambient
  source, never persists or serializes the token, and only ever places it in a
  per-request `Authorization` header. The host must be allowlisted
  (`api.github.com` by default).
- **Fail closed, never guess.** Any outcome other than `complete` carries
  `provenance_status: "incomplete"`. Absent credential → `unsupported`
  (`credential_absent`); missing object/line → `missing`; empty ranges →
  `incomplete`; network/parse fault → `failed`. A candidate whose line cannot be
  established is never assigned a placeholder commit.
- **Capture writes only when verified.** `capture_blame_evidence` records a
  fixture only when every request resolves `complete`, so a partial capture never
  masquerades as verified provenance. Re-capture is byte-identical.

## CLI

```bash
# Offline replay of a recorded blame line
sunset blame-evidence fetch \
  --fixture tests/fixtures/blame_evidence/openclaw-g27-blame-v1.json \
  --repository https://github.com/openclaw/openclaw \
  --commit 0965053fe6b9341776df147a6934b7485c60b5ca \
  --path ui/src/e2e/activity-run-inspector.e2e.test.ts --line 22

# Authenticated capture (bounded, explicit). The token is read ONLY from the
# env var you name; nothing is auto-discovered, and --live is required.
SUNSET_GH_TOKEN="$(gh auth token)" sunset blame-evidence capture \
  --requests requests.json \
  --output-fixture out.json \
  --live --token-env SUNSET_GH_TOKEN
```

`requests.json` is a list of `{subject_id, repository_url, commit_sha, path, line}`.

## Boundaries

Blame is read-only metadata retrieval. It runs no target code, resolves no
dependency graph, and is not a removability signal. A `complete` blame result
establishes *when a line was introduced*, not *why the protected condition
exists* or whether removal is safe. Wiring this provider into broad-collector
provenance enrichment (and correcting the G27 fixture) is G29.
