# Privacy and safety

Sunset is local-first and read-only by default. It has no telemetry. Scanning
reads committed blobs and Git metadata from the local repository; it does not
import target modules, execute target code, or upload repository content.

## Data flow and storage

The caller chooses an external `--store` directory. Raw source, patches,
provider responses, environment manifests, and test output are content-addressed
under `artifacts/sha256/`. Derived provenance and checkpoint views are stored
under `views/`. Investigation JSON and prompts retain compact claims and
artifact IDs rather than raw artifact bodies. Treat the store as sensitive when
the source repository is private, and remove it according to your own retention
policy.

The standalone HTML viewer is generated only after citation verification. It
contains claims, artifact IDs, review findings, and risks—not raw artifact
bytes. It uses no script or remote asset. Sharing a viewer can still disclose
repository paths, commit IDs, rationale text, and evidence identifiers, so
review it before publication.

## Network and external writes

Offline investigation is the default. Recorded evidence reads a local fixture.
Live GitHub lookup requires both `--evidence-mode live` and a caller-provided
`GITHUB_TOKEN`; unsupported providers and failures remain unknown. LangSmith
publication requires `--publish-langsmith` and an API key. Sunset never opens an
issue, creates a pull request, changes a target repository, or publishes a
package on its own.

## Approval and code execution

Validation does nothing without `--approve`. With approval, Sunset creates a
disposable local clone, removes only the selected marker there, and runs the
configured commands. This protects the target working tree, not the host:
pytest and broader commands execute untrusted target code with the invoking
user's host permissions. Review the repository and commands first; use a real
container or sandbox when host execution is inappropriate.

A `confirmed` clone experiment is empirical evidence only. Case files keep the
human approval boundary explicit, and Sunset never applies a cleanup. Age,
model confidence, issue state, and passing tests are insufficient proof of
safety.

## Measured limitations

The 20-case benchmark is a manually adjudicated, history-shaped regression
fixture. Its token figures are estimates, not provider billing. The 20-record
LangChain ecosystem corpus records pinned historical removals and retained code;
it is not a prevalence study or a claim of production precision. The public G09
run intentionally returns an inconclusive investigation when offline evidence
cannot resolve the assumption.
