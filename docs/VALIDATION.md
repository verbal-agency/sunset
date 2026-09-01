# Validation corpus protocol

G21's validation corpus is a provenance-bound input to later empirical
evaluation. Each case preserves a pinned repository snapshot, candidate path,
historical outcome, evidence pointers, proof obligations, and a fixed
development or holdout split.

The corpus does not contain protected-condition ground truth. A historical
removal is evidence that a change occurred, not proof that the condition behind
similar code is absent or that removal is safe. Cases remain non-authoritative
and `gate_ready` is false until G22 records independent human adjudication.

Audit the committed packet locally:

```bash
sunset validation-corpus audit \
  --manifest tests/fixtures/validation_corpus/langchain-validation-v1.json
```

The audit performs no network access, model call, subprocess, repository
checkout, target-code import, or mutation. It reports missing evidence
requirements, exclusions, stable corpus identity, processed/unprocessed case
IDs, and the explicit non-authority limitation. A bounded `--max-cases` run is
reported as incomplete rather than being treated as full coverage.

G22 is responsible for independent condition and proof-obligation review. G23
may evaluate only a frozen adjudicated manifest, and G24 may optimize only on
its development partition; holdout results remain sealed until the declared
release decision.
