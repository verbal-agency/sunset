# G08a public collection ledger

Collected with read-only Git metadata and patches from a disposable clone of
`https://github.com/langchain-ai/langchain.git`. No target checkout, import,
dependency installation, or test execution occurred.

## Verified removal candidates

| Commit | Subject | Path | Evidence |
| --- | --- | --- | --- |
| `94509faaed18d2a32faa232bde828ef2e5e1d6c3` | remove stale sync-stream xfail | `libs/core/tests/unit_tests/runnables/test_runnable_events_v1.py` | Commit subject and patch path |
| `3ed804a5f33084563abac7e74898abee94146677` | undo xfails | `libs/partners/perplexity/tests/integration_tests/test_chat_models_standard.py` | Commit subject and patch path |
| `a7c1bccd6a14343b67ac935177e25cfb158d6dfc` | remove xfails from image token counting tests | `libs/partners/openai/tests/integration_tests/chat_models/test_base.py` | Commit subject and patch path |
| `e4f106ea623598dc0c9856be4a9ebab28a9325e1` | remove xfails | `libs/partners/groq/tests/integration_tests/test_standard.py` | Commit subject and patch path |
| `5c216ad08f0e600a610c708b3a9aee22c632e065` | un-xfail tool calling test | `libs/partners/upstage/tests/integration_tests/test_chat_models_standard.py` | Commit subject and patch path |

## Verified compatibility-shim removal candidates

| Commit | Subject | Path | Evidence |
| --- | --- | --- | --- |
| `9ac8882a2c405e1f1a75957e81782538e4894c8b` | remove code for Python < 3.10 | `libs/core/langchain_core/runnables/configurable.py` | Patch removes `str.removeprefix()` fallback |
| `9ac8882a2c405e1f1a75957e81782538e4894c8b` | remove code for Python < 3.10 | `libs/core/langchain_core/utils/aiter.py` | Patch removes pre-3.10 `__aiter__()` workaround |

## Verified retained candidates

Pinned current LangChain HEAD: `e92c8a08bf382121cc1e95f7e75ddc8cb9c01ab0`.

| Path | Line | Marker rationale |
| --- | ---: | --- |
| `libs/core/tests/unit_tests/language_models/chat_models/test_base.py` | 204 | Testing-code bug |
| `libs/core/tests/unit_tests/language_models/chat_models/test_cache.py` | 256 | Streaming cache abstraction unsupported |

These are leads, not completed corpus records, until the G08a manifest records
the marker span and pinning evidence.
