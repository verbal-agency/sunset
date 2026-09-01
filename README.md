# Sunset

Sunset is a conservative, evidence-driven garbage collector for source code.
It finds code whose original rationale may have expired, gathers evidence, and
eventually validates cleanup proposals for human review.

The 0.1.0 alpha release deterministically discovers pytest skip and
expected-failure markers plus a deliberately narrow family of Python
compatibility guards in a committed Git snapshot. It then records local Git
provenance as immutable artifacts, assembles one candidate's bounded
investigation ledger, and can classify explicitly cited external assumptions
from recorded evidence. With explicit approval, it can validate one marker
removal in a disposable local clone. It can also turn saved investigation and
validation results into a citation-verified case file that keeps skeptical
evidence and limitations beside a conservative, human-only recommendation. It
does not decide that any candidate is obsolete and does not modify the analyzed
repository.

Release setup, privacy and host-execution boundaries, a short deterministic
demo, and a pinned LangGraph run are documented in
[`docs/RELEASE.md`](docs/RELEASE.md), [`docs/SAFETY.md`](docs/SAFETY.md),
[`docs/DEMO.md`](docs/DEMO.md), and [`docs/PUBLIC-RUN.md`](docs/PUBLIC-RUN.md).

## Quick start

Sunset supports Python 3.10 or newer and requires Git and
[`uv`](https://docs.astral.sh/uv/). This repository pins Python 3.12 for its
development environment so the verification toolchain is reproducible.

```bash
uv sync --all-groups
uv run --locked sunset --version
uv run sunset scan /path/to/repository --format json
uv run sunset collect /path/to/repository --collector compatibility --format json
uv run sunset provenance /path/to/repository --store /path/outside/repository --format json
uv run sunset provenance /path/to/repository --collector compatibility --store /path/outside/repository --format json
uv run sunset investigate /path/to/repository --candidate-id CANDIDATE_ID --store /path/outside/repository --format json
uv run sunset investigate /path/to/repository --candidate-id CANDIDATE_ID --store /path/outside/repository --evidence-mode recorded --recorded-evidence /path/to/responses.json --format json
uv run sunset validate /path/to/repository --candidate-id CANDIDATE_ID --store /path/outside/repository --approve --format json
uv run sunset investigate /path/to/repository --candidate-id CANDIDATE_ID --store /path/outside/repository --format json > investigation.json
uv run sunset validate /path/to/repository --candidate-id CANDIDATE_ID --store /path/outside/repository --approve --format json > validation.json
uv run sunset casefile --investigation-result investigation.json --validation-result validation.json --store /path/outside/repository --format markdown
uv run sunset casefile --investigation-result investigation.json --validation-result validation.json --store /path/outside/repository --format html > casefile.html
uv run sunset benchmark --corpus tests/fixtures/benchmarks/corpus-v1.json --format markdown
uv run sunset benchmark --corpus tests/fixtures/benchmarks/corpus-v1.json --langsmith-export sunset-experiment.json
uv run sunset corpus --manifest tests/fixtures/public_corpus/langchain-ecosystem-v1.json
uv run sunset release-check --manifest docs/releases/G09-public-run.json
uv run sunset tools --format json
```

Commands return `0` for a complete result, `1` when useful output is
available with one or more structured errors, and `2` for a repository-level
error such as a missing Git repository, missing committed HEAD, or an artifact
store placed inside the analyzed repository.

The `casefile` command is a read-only finalizer. It loads prior JSON rather
than rerunning investigation or validation, makes no provider request, and does
not open the target repository. Before rendering, it reloads every cited
`sha256:<digest>` raw artifact from the configured store and verifies its digest.
An uncited or unavailable material claim produces a structured error instead of
a report. A `confirmed` validation run remains empirical evidence only: it is
not proof that removal is safe and does not apply a change.
The HTML format is a standalone, script-free viewer with no remote assets or raw
artifact bodies; it still may contain sensitive paths and rationale text.

## Benchmarking memory and quality

G08 evaluates a committed 20-case, manually adjudicated regression corpus. It
compares a recorded full-context baseline with the compact-memory result,
measuring recommendation accuracy, citation accuracy, unsupported claims,
estimated input-token reduction, latency, and availability of cost or semantic
metrics. It evaluates SCN-06 directly: compact memory needs at least 50% median
input-token reduction, no more than a five-point classification-accuracy drop,
and no citation-accuracy decline.

The default command reads only saved benchmark data and makes no network
request. `--langsmith-export` writes a data-only experiment document. Sending
that document to LangSmith requires both `--publish-langsmith` and a supplied
`--langsmith-api-key`; it is never implied by running the benchmark. The
included corpus is a transparent, history-shaped fixture set—not a claim about
production prevalence, model quality, or provider-billed cost.

## Public historical corpus

G08a adds a committed 20-record public corpus drawn from pinned LangChain, LangGraph, and LangSmith SDK Git history. It has 10 historical marker/shim removals and 10 still-present markers or compatibility shims. The `corpus` command only validates saved JSON: it never contacts GitHub, clones, checks out, imports, installs, or executes code from those repositories.

Each record names the repository's canonical Git URL, a full source commit, the collection-time HEAD, path, observed outcome, and a GitHub URL to the patch or pinned source. A historical removal establishes that a particular maintainer change happened; it does not establish that a similar candidate is safe to remove. Retained records deliberately keep contrary examples visible.

## Supported syntax

Sunset recognizes decorators on pytest-style test functions, async test
functions, and `Test*` classes:

```python
@pytest.mark.xfail(reason="blocked by upstream issue #417")
def test_timeout():
    ...


@pytest.mark.skip
def test_unavailable_feature():
    ...


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on Windows")
def test_file_locking():
    ...
```

Marker names must use the explicit `pytest.mark` form. Literal `reason` strings
are extracted. Conditions on `xfail` and `skipif` are preserved as source text;
computed reasons remain `null` rather than being executed or guessed.

Sunset scans Python files named `test_*.py` or `*_test.py` below the requested
repository directory. Common generated, virtual-environment, cache, dependency,
and build directories are excluded.

## Deterministic snapshot model

G01 scans only files committed at `HEAD`:

- Uncommitted and ignored files do not affect output.
- Source is read through Git rather than imported or executed.
- Every candidate records the repository HEAD and the blame commit for its
  marker line.
- The same target, commit, and configuration produce normalized byte-identical
  JSON and stable candidate IDs.

This model gives later investigation stages an immutable source boundary. G02
adds local artifact storage without network or model calls.

## Local agent tool contracts

G10 makes the deterministic discovery and local-Git evidence operations
available as three context-bound LangChain tools:

- `sunset_discover_candidates`
- `sunset_get_candidate_provenance`
- `sunset_read_evidence_excerpt`

They are capability boundaries for later agent graphs, not an agent. G10 makes
no model call, chooses no tool autonomously, opens no network connection, runs
no target code, and cannot modify the analyzed repository. Trusted application
code fixes the repository, committed HEAD, collector, external artifact store,
evidence grants, and call/byte budgets before it gives the tools to a model.

`sunset tools --format json` lists the versioned input schemas and effect
declarations without opening a repository or artifact store. Library setup,
receipt identity, transient evidence handling, and security boundaries are
documented in [`docs/AGENT-TOOLS.md`](docs/AGENT-TOOLS.md).

## Structured model runtime

G11 adds a library-only, single-step reasoning adapter above those tools. It
has three explicit modes: `disabled`, deterministic local `recorded` replay,
and `live` with an application-injected LangChain `BaseChatModel`. There is no
implicit model selection, credential discovery, tool dispatch, agent loop, or
cleanup recommendation.

The adapter receives compact G10 receipts and may receive one already-bounded
transient excerpt for an immediate invocation. It returns a versioned,
model-derived hypothesis with scoped citations and proposed *names* of G10
tools. Proposed names are data only; G11 cannot execute them. Checkpoints retain
only receipts and the structured result, never prompt text, raw model responses,
or transient evidence. See [`docs/MODEL-RUNTIME.md`](docs/MODEL-RUNTIME.md).

## Bounded local-evidence loop

G12 combines the three G10 tools and a G11 result in a small, resumable
LangGraph loop. Deterministic application policy—not a model—validates each
typed request, enforces declared local-read-only effects and call/byte budgets,
and records a compact receipt/reasoning trace. The heuristic-only baseline
constructs no model; recorded and injected-live modes use the same contracts.
Raw excerpts remain immediate-only, and a trace is never a cleanup authority.
See [`docs/AGENT-LOOP.md`](docs/AGENT-LOOP.md).

## Recorded-first external evidence tools

G13 adds an optional `sunset_resolve_external_reference` tool for explicit,
candidate-linked GitHub, release-note, and dependency-version evidence. The
default is a socket-free recorded provider. A live GitHub adapter requires a
host-supplied credential and explicit host allowlist; it never discovers an
environment credential. External status is a cited observation, not proof of a
safe cleanup, and raw provider bodies remain outside checkpointed agent state.
See [`docs/EXTERNAL-AGENT-TOOLS.md`](docs/EXTERNAL-AGENT-TOOLS.md).

## Human-gated validation

G14 turns a receipt-derived validation plan into an explicit human decision
before it can call the existing disposable-clone validator. Missing, denied,
expired, wrong-plan, or changed-HEAD approvals execute nothing. A valid approval
authorizes exactly the reviewed G06 experiment and returns its artifact-backed
result; it is never approval to remove code. See
[`docs/AGENT-VALIDATION.md`](docs/AGENT-VALIDATION.md).

## Compatibility collector schema version 1

`sunset collect --collector compatibility` is an additive collector family. It
does not alter the schema-v1 output of `sunset scan`.

It recognizes only these syntactic forms when both branches contain direct,
concrete imports:

```python
if sys.version_info < (3, 11):
    from legacy_runtime import Parser
else:
    from modern_runtime import Parser

if Version(importlib.metadata.version("upstream-lib")) < Version("2.4"):
    from legacy_client import Client
else:
    from modern_client import Client

try:
    from modern_api import Widget
except ImportError:
    from legacy_api import Widget
```

The dependency form also accepts the direct canonical
`importlib.metadata.version("package") < "threshold"` shape. The output
identifies its candidate family, exact guard/protected/fallback source spans,
canonical subject, comparator, literal threshold when applicable, import
targets, committed HEAD, and blame commit.

The collector intentionally ignores aliases, computed thresholds or package
names, reversed comparisons, general platform conditionals, policy-only
branches, `try` blocks with extra control-flow clauses, and arbitrary code.
It never imports target modules, evaluates a version expression, resolves the
installed dependency graph, or infers whether a guard is obsolete. A candidate
is a lead for a later investigation, not proof that a shim should be removed.

## Provenance and artifact storage

`sunset provenance` performs the selected committed-HEAD scan and records
evidence for every discovered candidate. Its default collector remains
`pytest`; use `--collector compatibility` for G03 candidates. For each it
records:

- source bytes at the scanned HEAD;
- line blame and its best-supported introduction point;
- bounded, rename-aware file history; and
- the patch for the blame commit when that object is available.

The store is explicit and must be outside the analyzed repository:

```bash
uv run sunset provenance /path/to/repository \
  --store /path/to/sunset-artifacts \
  --format json
```

Raw bytes live at `artifacts/sha256/<digest>`. Their `sha256:<digest>` IDs
are derived only from the bytes. Deterministic candidate views live separately
under `views/` and reference those artifacts; the CLI prints references and
metadata, not full history or patches.

Repeated collection at the same HEAD verifies and reuses the same immutable
artifacts. A changed HEAD creates a new derived view, while unchanged source,
history, and patch bytes keep their existing artifact IDs. This is the cache
boundary: derived conclusions are keyed to repository state; raw Git evidence is
not discarded merely because HEAD moves.

Repository identity uses `origin`'s configured URL when present, without
contacting it. Local repositories without an origin use a SHA-256 hash of their
resolved local path. A shallow clone remains usable: Sunset records the source
evidence it can read and emits structured uncertainty when history or the blame
commit patch is incomplete.

Provenance JSON has its own schema version and includes `repository_identity`,
`repository_head`, candidate artifact references, and structured errors or
uncertainties. A candidate's `introduction_commit` is currently the
blame-backed best-supported introduction point; it is not a claim that history
proves the first ever semantic rationale.

## Bounded investigation and external assumptions

G04 adds a LangGraph workflow for one explicitly selected candidate:

```bash
uv run sunset investigate /path/to/repository \
  --candidate-id sunset-v1-... \
  --store /path/to/sunset-artifacts \
  --format json
```

It resumes automatically when the repository identity, committed `HEAD`,
collector, candidate ID, and token-budget configuration identify a prior
checkpoint. `--interrupt-after retrieve_core` is available for deterministic
interruption testing; rerun without it to resume.

The graph loads provenance, retrieves source and blame-patch evidence, records
a structured ledger, retrieves focused history only when core evidence lacks a
rationale cue, optionally verifies explicit external references, then finalizes
`inconclusive`. Checkpoints and JSON include artifact IDs, compact ledger
claims, `assumption_status`, open questions, and per-node *estimated* tokens.
They never contain raw source, patches, history, or provider-response bodies.

No model is called. Its byte-based token estimate enforces the default
100,000-input/8,000-output budget and records a full-context comparison
baseline.

G05 recognizes only explicit references in selected local evidence:

```python
@pytest.mark.xfail(reason="https://github.com/example/widget/issues/417")
def test_widget():
    ...


@pytest.mark.xfail(
    reason="changelog: widget==2.4 https://docs.example.test/widget/changelog"
)
def test_widget_on_old_version():
    ...
```

`--evidence-mode offline` is the default: it performs no request and yields
`assumption_status: "unknown"`. `--evidence-mode recorded` reads a local JSON
fixture with a `responses` list; each response has `provider`, `locator`,
`outcome` (`supports_active`, `supports_expired`, `missing`, or `failed`), and
a concise `summary`. Its raw normalized response is content-addressed in the
artifact store and the ledger retains only the artifact ID. This is the default
mode for deterministic tests and demos.

`--evidence-mode live` is explicit. GitHub issue and pull-request URLs require
`GITHUB_TOKEN`; absent credentials, malformed responses, and request failures
remain `unknown`. A live release-note adapter is deliberately unavailable until
it is configured, and it likewise returns `unknown`. Sunset never uses live
network access by default.

## Approved clone validation

G06 can empirically test one selected pytest marker only after the person
running Sunset grants approval:

```bash
uv run sunset validate /path/to/repository \
  --candidate-id sunset-v1-... \
  --store /path/to/sunset-artifacts \
  --approve \
  --repeat 2 \
  --broader-command "python -m pytest -q"
```

Without `--approve`, Sunset returns `approval_required`; it creates no clone,
runs no command, and writes no artifacts. With approval, it clones the
repository locally into a temporary directory, pins the clone to the selected
committed `HEAD`, removes only the selected `pytest.mark.xfail`, `skip`, or
`skipif` AST decorator there, and runs the exact test target twice by default.
Optional `--broader-command` values are split with shell-like quoting but run
without a shell, in that clone only.

Each approved run returns one of `confirmed`, `still_failing`, `flaky`,
`environment_error`, or `inconclusive`; its output and a versioned environment
manifest are content-addressed in the external store. `confirmed` means only
that the configured clone experiment passed. It is not a removal recommendation
and does not replace an approval or skeptical review.

The disposable clone protects repository state, not the host: tests are still
the target project's code. G06 does not install dependencies, start containers,
or provide a network/security sandbox. Use commands you are willing to execute
locally.

## Scan JSON schema version 1

```json
{
  "candidates": [
    {
      "blame_commit": "6db6e746c8f62a3fd35e42271dc27e843d2b4460",
      "candidate_id": "sunset-v1-68d58f1f195f8599f24f7849",
      "column": 0,
      "condition": null,
      "line": 10,
      "marker_kind": "xfail",
      "path": "tests/test_client.py",
      "qualified_name": "test_timeout",
      "reason": "blocked by upstream issue #417",
      "repository_head": "ddbb4e7c35ab81242f544772ca1d41af71099c45"
    }
  ],
  "errors": [],
  "repository_head": "ddbb4e7c35ab81242f544772ca1d41af71099c45",
  "schema_version": "1"
}
```

Candidate IDs are derived from schema version, repository HEAD, repository-
relative path, qualified target name, marker kind, line, and column.

## Safety boundary and limitations

G06 does not:

- infer why a marker exists or whether removal is safe;
- make a network request unless `--evidence-mode live` is explicitly selected;
- execute test modules or evaluate dynamic marker arguments;
- import target modules, resolve dependency versions, or evaluate guards;
- call a model or treat an issue state, release note, or assumption status as
  proof of safety;
- run a command or create a clone without `--approve`;
- remove markers in the analyzed repository, create worktrees there, or open
  pull requests;
- write into the analyzed repository; the artifact store must be external;
- support aliased imports, module-level `pytestmark`, parameter-level marks,
  custom collection patterns, non-pytest frameworks, or non-Python languages.

A passing scan or provenance run means only that Sunset found supported markers
and recorded available local Git evidence. It is not a removal recommendation.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run sunset scan tests/fixtures/pytest_repo --format json
uv run sunset collect tests/fixtures/pytest_repo --collector compatibility --format json
uv run sunset provenance tests/fixtures/pytest_repo --store /tmp/sunset-artifacts --format json
uv run sunset investigate /path/to/repository --candidate-id CANDIDATE_ID --store /tmp/sunset-artifacts --format json
uv run sunset investigate /path/to/repository --candidate-id CANDIDATE_ID --store /tmp/sunset-artifacts --evidence-mode recorded --recorded-evidence tests/fixtures/evidence/recorded_responses.json --format json
uv run sunset validate /path/to/repository --candidate-id CANDIDATE_ID --store /tmp/sunset-artifacts --approve --format json
```

The fixture directory is part of the Sunset repository, so both fixture commands
use Sunset's committed HEAD after these files are committed. The provenance store
path remains outside that repository.
