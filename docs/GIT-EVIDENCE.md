# Pinned Git evidence

Sunset can retrieve the source blob or commit patch referenced by an existing
validation-corpus `EvidencePointer`. This is an evidence-ingestion capability,
not a rationale or removability decision.

## Recorded-first workflow

Use a committed fixture for reproducible runs:

```bash
sunset git-evidence fetch \
  --manifest tests/fixtures/validation_corpus/langchain-validation-v1.json \
  --case-id CASE_ID \
  --evidence-id EVIDENCE_ID \
  --store /tmp/sunset-evidence \
  --fixture tests/fixtures/git_evidence/g22-recorded.json
```

The pointer supplies the repository, full commit SHA, and path. A commit
pointer resolves to a pinned `.patch`; a blob pointer resolves to the exact
path at that SHA. The fixture provider performs no socket, Git, subprocess, or
model operation. Missing, malformed, contradictory, and over-budget records
remain structured uncertainty or errors.

## Explicit live boundary

`--live` is an opt-in read-only public GitHub GET. The URL is derived by the
provider, restricted to GitHub's allowlisted hosts, limited to one request and
64 KiB by default, and bounded by a ten-second timeout. No ambient credentials
are discovered and no links are followed. A transport error, 404, rate limit,
or oversized response never becomes a condition conclusion.

For real corpus acquisition, use the G22a capture command with an explicit
selection and live flag. It performs one request per pointer and writes the
fixture atomically only when every selected response is available:

```bash
sunset git-evidence capture \
  --manifest tests/fixtures/validation_corpus/langchain-validation-v1.json \
  --selection lc-python39-removeprefix-shim:history,lc-stream-error-xfail:history \
  --output-fixture tests/fixtures/git_evidence/g22a-langchain-real-v1.json \
  --store /tmp/sunset-g22a-capture --live --max-bytes 262144
```

DNS, TLS, timeout, HTTP, redirect, decode, and budget failures are reported by
phase. They leave the capture unverified and must be recorded as a blocked
outcome rather than replaced with authored fixture content.

The repository includes a real replay fixture captured from three pinned
LangChain pointers at
`tests/fixtures/git_evidence/g22a-langchain-real-v1.json`; its SHA-256 is
recorded alongside it in `g22a-langchain-real-v1.sha256`. The fixture is the
offline handoff to later adjudication, not a claim that any protected condition
has expired.

## Declared-support evidence bundle

G22b extends the same recorded-first boundary to an owner-approved bundle of
package metadata, published artifact metadata, CI/version matrices, dependency
markers, and any explicitly declared support documentation. It accepts only
declared HTTPS locators on the GitHub and PyPI host allowlists; it does not
search repositories or infer deployment usage. A support-documentation class
may be explicitly `not_applicable` when no authoritative policy source exists.

The captured LangChain bundle is replayable at
`tests/fixtures/git_evidence/g22b-langchain-support-v1.json`, with its digest
in `g22b-langchain-support-v1.sha256`. It contains pinned GitHub artifacts and
`langchain-core==1.6.1` PyPI metadata for the two Python compatibility-shim
cases. The bundle records declared support only; customer or deployment usage
remains a separate operational evidence obligation.

Capture it with an explicit live authorization and byte budget:

```bash
sunset support-evidence capture \
  --manifest tests/fixtures/validation_corpus/langchain-validation-v1.json \
  --supplement tests/fixtures/support_evidence/g22b-selection-v1.json \
  --output-fixture tests/fixtures/git_evidence/g22b-langchain-support-v1.json \
  --store /tmp/sunset-g22b-support --live --max-bytes 1200000
```

G22c extends the bundle to the retained LangGraph case
`lg-dataclass-version-shim`. Its owner-approved selection and verified fixture
are `tests/fixtures/support_evidence/g22c-selection-v1.json` and
`tests/fixtures/git_evidence/g22c-langgraph-support-v1.json`, respectively;
the fixture digest is recorded in `g22c-langgraph-support-v1.sha256`. The
bundle captures `langgraph==1.2.11` metadata, Python 3.10–3.14 CI coverage, and
dependency markers. This establishes that Python 3.10 remains in the declared
support scope; it is evidence for adjudication, not a removal recommendation.

## Receipts and artifacts

Available bytes are written to the configured content-addressed artifact store
and represented to callers by a SHA-256 digest, artifact ID, locator, byte
length, provider identity, and freshness key. Receipt JSON does not contain raw
source, patch bytes, credentials, or a cleanup recommendation. Cached receipts
are reused only when the pointer, provider policy, fixture digest, freshness
key, and byte budget match; the artifact is integrity-checked before reuse.

## Non-authority boundary

Retrieved source and patches answer only “what was recorded at this pinned
location?” They do not establish that a protected condition has expired,
validate a removal, or authorize a mutation. Adjudication must compare this
evidence with operational/internal evidence, counter-evidence, and an explicit
proof obligation in a later goal.
