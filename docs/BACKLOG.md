# Sunset backlog

This file contains valuable unscheduled work that is not required by a named
roadmap goal. Findings that already belong to G01–G09 should be added only to
that goal, not duplicated here.

| Priority | Item | Why it matters | Dependencies / destination trigger |
| --- | --- | --- | --- |
| Medium | JavaScript/TypeScript test-marker support | Broadens the maintainer audience after the Python workflow is validated | Consider after G09; requires a language-neutral candidate model proven by G01–G08 |
| Medium | Feature-flag collector | Stale flags are common temporal debt but have distinct runtime evidence and established competitors | Consider only after Sunset demonstrates differentiation on rationale expiry |
| Low | IDE extension | Makes line-level review convenient but does not validate the core thesis | Only after stable CLI and case-file contracts |
| Low | Automatic pull-request creation | Reduces cleanup friction but increases external side effects and trust requirements | Requires proven precision, explicit approval, and G09 safety evidence |
| Low | Jira, Slack, and internal RFC evidence providers | Enterprise rationale often lives outside GitHub | Requires a real design partner and privacy model |
| Low | Scheduled repository collection | Enables continuous maintenance | Requires incremental invalidation, rate limits, and operational ownership |
| Low | Cross-repository workaround analysis | Could connect local workarounds to upstream fixes across ecosystems | Requires mature dependency and provenance models |
