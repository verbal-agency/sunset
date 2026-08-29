# Sunset

Sunset is a conservative, evidence-driven garbage collector for source code.
It finds code whose original rationale may have expired, gathers evidence, and
eventually validates cleanup proposals for human review.

The current G03 release deterministically discovers pytest skip and
expected-failure markers plus a deliberately narrow family of Python
compatibility guards in a committed Git snapshot. It then records local Git
provenance as immutable artifacts. It does not decide that any candidate is
obsolete and does not modify the analyzed repository.

## Quick start

Sunset supports Python 3.10 or newer and requires Git and
[`uv`](https://docs.astral.sh/uv/). This repository pins Python 3.12 for its
development environment so the verification toolchain is reproducible.

```bash
uv sync --all-groups
uv run sunset scan /path/to/repository --format json
uv run sunset collect /path/to/repository --collector compatibility --format json
uv run sunset provenance /path/to/repository --store /path/outside/repository --format json
uv run sunset provenance /path/to/repository --collector compatibility --store /path/outside/repository --format json
```

Both commands return `0` for a complete result, `1` when useful output is
available with one or more structured errors, and `2` for a repository-level
error such as a missing Git repository, missing committed HEAD, or an artifact
store placed inside the analyzed repository.

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

G03 does not:

- infer why a marker exists or whether its rationale expired;
- access GitHub, release notes, models, embeddings, or the network;
- execute test modules or evaluate dynamic marker arguments;
- import target modules, resolve dependency versions, or evaluate guards;
- run tests, remove markers, create worktrees, or open pull requests;
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
```

The fixture directory is part of the Sunset repository, so both fixture commands
use Sunset's committed HEAD after these files are committed. The provenance store
path remains outside that repository.
