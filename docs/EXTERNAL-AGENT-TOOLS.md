# External evidence agent tools

G13 adds one bounded external-read capability:
`sunset_resolve_external_reference`. It is deliberately separate from G10's
local read-only registry and is available only when trusted application code
creates an `ExternalEvidenceContext` beside the existing local context.

## Reference and dispatch policy

The model sees and proposes only the tool name. It never supplies a URL, host,
provider, credential, repository path, or artifact-store path. Trusted code
extracts explicit GitHub issue/pull-request and release-note references from
already-authorized local evidence, assigns stable reference IDs, and binds a
fixed host allowlist. The loop deterministically resolves an outstanding
reference ID and records the antecedent G11 reasoning invocation.

The dispatcher validates the typed reference ID, exact one-tool registry, and
declared `external_read` effect before calling the provider. It also enforces
the aggregate agent budget plus provider request, response-byte, and optional
minimum-interval policies. Unsupported references, malformed IDs, changed
effects, rate limits, missing fixtures, and provider failures are receipts with
uncertainty or structured errors—not retries or a reason to infer expiry.

## Recorded and live providers

`RecordedExternalEvidenceProvider` consumes a checked-in/local fixture and is
the default test path. It opens no socket and stores the raw fixture response as
an immutable artifact only when it supplies evidence.

`ExplicitGitHubProvider` is opt-in: the host application supplies its token and
the adapter directly. It does not read environment variables or discover
credentials. The adapter accepts only a supported GitHub issue or pull-request
reference, reads at most the configured response limit, and returns a normalized
open/closed observation. Release-note and dependency-version references are
supported by the recorded-provider contract; a host must supply a separately
configured live adapter before they can make a live request.

Provider state is not cleanup authority. A closed issue, release note, or
version match is an artifact-backed observation that may conflict with other
evidence. It never recommends a removal, runs validation, writes externally,
or crosses G14's human approval boundary.

## Replay and privacy

The G12 run identity incorporates the external context policy: provider name,
mode, host allowlist, bounded budgets, freshness key, reference grant, and a
digest of the supplied credential identity. It never contains the credential
itself. A changed provider/freshness policy rejects checkpoint reuse. An
interrupted compatible run uses its receipt ledger and does not repeat a
completed provider call.

Checkpoints retain compact normalized receipts and artifact IDs. They exclude
raw provider bodies, headers, credentials, prompt text, and framework messages.
Raw response bodies remain in the content-addressed artifact store for later
citation verification.
