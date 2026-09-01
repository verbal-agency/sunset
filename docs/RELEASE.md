# Release evidence

Sunset release claims are gated by a versioned historical evaluation, not by
model confidence or a passing cleanup experiment. The calibration evaluator
compares heuristic-only and agentic runs over the same labeled cases and
reports condition accuracy, contradiction detection, proof-obligation quality,
citation accuracy, unsupported claims, cost, latency, and false-removal risk.

Thresholds are declared before evaluation and are part of the release-gate
identity. Missing or conflicting labels reduce recorded coverage and make the
gate inconclusive when required coverage is unmet. A passing gate means only
that the implementation met its declared historical benchmark thresholds; it
does not establish that any production condition is absent or authorize a
cleanup.
