# Sunset

Sunset is a conservative, evidence-driven garbage collector for source code.
It finds code whose original rationale may have expired, gathers evidence, and
eventually validates cleanup proposals for human review.

The current G01 release is deliberately narrower: it deterministically discovers
pytest skip and expected-failure markers in a committed Git snapshot. It does
not decide that a marker is obsolete and does not modify the repository.

## Quick start

Sunset supports Python 3.10 or newer and requires Git and
[`uv`](https://docs.astral.sh/uv/). This repository pins Python 3.12 for its
development environment so the verification toolchain is reproducible.

```bash
uv sync --all-groups
uv run sunset scan /path/to/repository --format json
```

The command returns `0` for a complete scan, `1` when candidate discovery
succeeds with one or more structured file errors, and `2` for a repository-level
error such as a missing Git repository or committed HEAD.

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

This model gives later investigation stages an immutable source boundary. A
future goal will add versioned evidence storage; G01 performs no network or model
calls.

## JSON schema version 1

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

G01 does not:

- infer why a marker exists or whether its rationale expired;
- access GitHub, release notes, models, embeddings, or the network;
- execute test modules or evaluate dynamic marker arguments;
- run tests, remove markers, create worktrees, or open pull requests;
- support aliased imports, module-level `pytestmark`, parameter-level marks,
  custom collection patterns, non-pytest frameworks, or non-Python languages.

A passing scan means only that Sunset found supported markers and Git provenance.
It is not a removal recommendation.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run sunset scan tests/fixtures/pytest_repo --format json
```

The fixture directory is part of the Sunset repository, so the last command
uses Sunset's committed HEAD after these files are committed.
