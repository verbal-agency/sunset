# G34 historical-removal backtest report

**Run:** `g34-recorded-20261011-v6`
**Mode:** recorded heuristic baseline; no live-model call
**Manifest:** `67c2a72245a87f718d02b78b20a04eef0eaf66f646bfc798004c95f2c5a44a29`
**Authority:** non-authoritative; no target repository was modified

## Result

Sunset mined 924 historical marker observations from three pinned public
repositories and included 54 cases after deterministic exclusions:

| Repository | Pinned head | Included | Excluded | Classes |
| --- | --- | ---: | ---: | --- |
| `pytest` | `4e64e831268758cf0040c52c144e0f09f46cd8a3` | 31 | 797 | 13 marker-only, 10 fix-with-removal, 8 retained |
| `attrs` | `644b4e165bfbeee7e127de6fcbda08b64014316f` | 16 | 40 | 0 marker-only, 10 fix-with-removal, 6 retained |
| `click` | `2247b35ea1c47c727d7a06e51fa280e12a863ff6` | 7 | 33 | 0 marker-only, 2 fix-with-removal, 5 retained |

Pinned sources were cloned from:

- `https://github.com/pytest-dev/pytest.git`
- `https://github.com/python-attrs/attrs.git`
- `https://github.com/pallets/click.git`

The event, case, and split manifests reproduced the committed fixtures
byte-for-byte. The split contains 34 development and 20 holdout cases.

## Clone execution

The disposable-clone run attempted all 54 cases. It produced:

| Outcome | Cases |
| --- | ---: |
| `confirmed` (unmarked test passed twice) | 40 |
| `still_failing` (unmarked test failed twice) | 12 |
| `environment_error` | 2 |

The declared case-level environment-failure stop threshold for this run was
25%; the observed rate was 3.7% for the two cases that could not be matched to
a runnable test node. The run cleared the environment stop rule. Those cases
remain recorded as unknown rather than converted into condition labels.

The report distinguishes maintainer-derived classes from clone outcomes:
removal is corroboration, not proof; `retained` means only `not_removed`; and a
passing disposable test establishes only the exercised validation scope.

## Agent status

No live agent run was made. A model identifier, call cap, and authorization were
not supplied for this cycle, so the run stayed in recorded heuristic mode. The
report records agent counts as zero rather than fabricating judgments.

## Reproduction

The frozen artifacts are:

- `tests/fixtures/backtest/g34-events-v1.json`
- `tests/fixtures/backtest/g34-cases-v1.json`
- `tests/fixtures/backtest/g34-split-manifest-v1.json`
- `tests/fixtures/backtest/g34-runs-v1.json`
- `tests/fixtures/backtest/g34-report-v1.json`

The locked focused tests and offline report-replay test pass. The report is
non-authoritative and does not authorize cleanup, approval, or a claim that
Sunset's protected-condition inference is accurate outside this sample. It is
a heuristic-only measurement because no live model credential, model
identifier, or call cap was authorized for this run.
