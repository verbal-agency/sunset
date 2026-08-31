# Pinned LangGraph public run

G09 ran Sunset against the `libs/langgraph/tests` subtree of LangGraph at full
commit `11ee185999b86bfea2d8c0e69cef9a5e37acf686`. The initial public clone was the
only network operation. Target dependencies were not installed, target code was
not imported, and no target test was executed.
Target code was not installed or executed at any point in this workflow.

## Reproduction

```bash
git clone --no-checkout https://github.com/langchain-ai/langgraph.git /tmp/sunset-langgraph
git -C /tmp/sunset-langgraph checkout --detach 11ee185999b86bfea2d8c0e69cef9a5e37acf686

sunset scan /tmp/sunset-langgraph/libs/langgraph/tests --format json

sunset investigate /tmp/sunset-langgraph/libs/langgraph/tests \
  --candidate-id sunset-v1-ed51e3cc1b1b6c3bb84e5c5a \
  --store /tmp/sunset-langgraph-artifacts \
  --evidence-mode offline \
  --format json
```

The deterministic scan succeeded with 11 candidates and no errors. This is a
discovery success, not a cleanup recommendation. The selected candidate is the
retained `skipif` in `libs/langgraph/tests/test_utils.py` already represented by
G08a's `lg-async-context-skipif` corpus case.

The offline investigation completed as `inconclusive` with assumption status
`unknown`. Local source and blame-patch evidence established the exact condition
and provenance lead, but contained no explicit supported external reference.
Sunset therefore rejected age and Git history as proof and requested external
evidence plus approved isolated validation.

The target Git tree was `10eb6105430f2551a0f49a55904f625b6877ac85`
before and after, and the working tree remained clean. Exact executed argv,
saved result paths, SHA-256 digests, and safety assertions are recorded in
`releases/G09-public-run.json` and can be verified offline:

```bash
sunset release-check --manifest docs/releases/G09-public-run.json
```

The saved artifact IDs in the investigation output identify raw evidence from
the run's external local store. Those raw bytes are intentionally not committed
or embedded in public reports.
