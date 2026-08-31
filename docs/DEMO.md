# Short terminal demonstration

This two-minute demonstration uses only committed fixtures and locked local
dependencies. It makes no network request, executes no target repository, and
does not modify a target working tree. The recorded evidence is illustrative,
not a production-quality claim.

From the Sunset checkout:

```bash
uv run --locked sunset --version

uv run --locked sunset casefile \
  --investigation-result tests/fixtures/release_demo/expired-investigation.json \
  --validation-result tests/fixtures/release_demo/confirmed-validation.json \
  --store tests/fixtures/release_demo/store \
  --format json
# recommendation: eligible_for_human_cleanup

uv run --locked sunset casefile \
  --investigation-result tests/fixtures/release_demo/unknown-investigation.json \
  --store tests/fixtures/release_demo/store \
  --format json
# recommendation: inconclusive

uv run --locked sunset casefile \
  --investigation-result tests/fixtures/release_demo/unknown-investigation.json \
  --store tests/fixtures/release_demo/store \
  --format html > /tmp/sunset-casefile.html
```

The eligible result combines a recorded `expired` assumption with a recorded
approved clone experiment. It still says a human must decide. The unknown result
has no validation, so skeptical review blocks eligibility. The final command
creates a passive standalone viewer; opening it is optional and outside the
demonstration's default workflow.
