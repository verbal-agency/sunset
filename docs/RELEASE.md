# Sunset release guide

Sunset 0.1.0 is an alpha, local-first Python CLI. This repository is the release
source of truth; no package registry or hosted service is implied.

## Clean install

Prerequisites are Python 3.10 or newer, Git, and `uv`. The repository pins its
development and verification environment to Python 3.12.

```bash
git clone https://github.com/verbal-agency/sunset.git
cd sunset
uv sync --all-groups
uv run --locked sunset --version
uv run --locked sunset scan tests/fixtures/pytest_repo --format json
```

To test the distribution rather than the editable checkout:

```bash
uv build
python -m venv /tmp/sunset-wheel-smoke
/tmp/sunset-wheel-smoke/bin/python -m pip install dist/sunset_gc-0.1.0-py3-none-any.whl
cd /tmp
/tmp/sunset-wheel-smoke/bin/sunset --version
/tmp/sunset-wheel-smoke/bin/sunset scan /path/to/committed/repository --format json
```

The wheel smoke test must run outside the checkout so Python cannot accidentally
import `src/sunset`. Build artifacts are local and are not published.

## Release verification

```bash
uv lock --check
uv run --locked pytest -q
uv run --locked sunset benchmark --corpus tests/fixtures/benchmarks/corpus-v1.json --format markdown
uv run --locked sunset corpus --manifest tests/fixtures/public_corpus/langchain-ecosystem-v1.json
uv run --locked sunset release-check --manifest docs/releases/G09-public-run.json
git diff --check
```

See [SAFETY.md](SAFETY.md), [DEMO.md](DEMO.md), and
[PUBLIC-RUN.md](PUBLIC-RUN.md) before using Sunset on a repository you maintain.

## Supported release boundary

The release supports committed Python snapshots, explicit `pytest.mark.xfail`,
`skip`, and `skipif` decorators, and the bounded compatibility collectors
documented in the README. It does not support arbitrary dead code, dynamic
marker forms, non-Python languages, automatic cleanup, or automatic pull
requests. A missing candidate is not evidence that a repository has no temporal
debt.
