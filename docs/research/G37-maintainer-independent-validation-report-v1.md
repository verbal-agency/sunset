# G37 maintainer-independent validation report

## Result

G37 successfully replayed the benchmark through the recorded, pinned-clone
path. It demonstrates deterministic orchestration and bounded validation
receipts. It does **not** establish that Sunset correctly inferred a protected
condition or that any cleanup is safe for production users.

## Scope

- Nine LangChain candidates at commit
  `5c1f28271295bb13034f4cf8964f74c117357d40`.
- Eighteen recorded G33-path receipts: nine heuristic and nine
  recorded-agentic.
- G34 historical proxy comparison across 35 non-retained cases from pytest,
  attrs, and click.
- Zero live model calls and zero network calls during replay.

## Mechanical results

| Measure | Result |
| --- | ---: |
| Exact-SHA cases | 9 |
| Complete receipts | 18/18 |
| Target snapshots unchanged | 18/18 |
| Heuristic replays | 9 |
| Recorded-agentic replays | 9 |
| Byte-identical replay | yes |

## Bounded validation results

The LangChain recorded outcomes were one `confirmed` and seven
`still_failing`; one case had no validation outcome because the recorded agent
did not request escalation. These outcomes apply only to the declared test
commands and their disposable environments.

## Historical proxy result

The heuristic agreed with the G34 historical event class in 22 of 35 eligible
non-retained cases (62.86%). This is a proxy comparison, not a condition-label
accuracy score: a marker removal does not prove that its protected condition
expired, and a retained marker does not prove that its condition remains
active.

## Evidence limits

- No protected-condition label was human adjudicated.
- The benchmark contains one natural clone-runnable repository; it does not
  estimate repository-wide recall.
- Recorded agent traces measure replay behavior, not live-model quality.
- External deployment and customer-support scope remain unproven.
- A passing disposable validation proves only the declared test scope.

The replay suite also covers contradictory evidence, malformed responses,
moving refs, unavailable runtimes, and holdout tuning attempts. Each fails
closed or remains explicitly non-authoritative.

## Non-authority

The fixtures and report are evidence artifacts, not cleanup authorization. G27
still requires a consenting maintainer for human-confirmed pilot conclusions.
