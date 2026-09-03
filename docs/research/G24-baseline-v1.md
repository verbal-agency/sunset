# G24 baseline evaluation

The frozen G23 manifest was evaluated offline with paired heuristic and
recorded-agentic traces. The report is identified by evaluation digest
`e1be4e54a6ae8dee812fa66bbf73989d35a84680a4acd2a676a69324773d2c44`.

| Mode | Completed included denominator | Condition accuracy | Proof-obligation recall | Citation accuracy | Unsupported-claim rate | Median input tokens | Median latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic | 4 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 180 | 4 |
| agentic_recorded | 3 | 0.6667 | 1.0000 | 0.9167 | 0.3333 | 620 | 30 |

The report contains all 20 frozen cases and both modes. Fifteen exclusions are
materialized as `excluded` and contribute no accuracy denominator. The fixture
also exercises unknown, contradictory, malformed, interrupted, budget-exhausted,
and unsupported-claim outcomes. Cost is explicitly recorded as unavailable in
this offline replay; safety signals are counted rather than hidden in accuracy.
Per-family included and completed denominators are also retained in the JSON
report for later split-safe optimization.

Six pinned public repository references (Kubernetes, CPython, Pydantic AI,
Piranha, TransformerLens, and spaCy) are criterion fixtures only. Their exact
commit SHAs and paths are verified, but they are `reference_only`: they do not
provide labels, denominators, or proof of removability.

The baseline is exploratory. G23 uses one owner-authorized reviewer, so this is
not independent ground truth. Holdout identity is sealed by the frozen manifest;
G25 may tune only predeclared bounded changes against development cases.
