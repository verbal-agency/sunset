# Sunset backlog

This file contains valuable unscheduled work that is not required by a named
roadmap goal. Findings that already belong to a named roadmap goal should be added only to
that goal, not duplicated here.

| Priority | Item | Why it matters | Dependencies / destination trigger |
| --- | --- | --- | --- |
| High | Choose and add an explicit project license | G09's distribution audit found no `LICENSE` file or package license metadata, leaving reuse terms unclear; the license choice requires human legal intent | Resolve before publishing to a package registry or inviting third-party redistribution |
| Medium | JavaScript/TypeScript test-marker support | Broadens the maintainer audience after the Python workflow is validated | Consider after G20; requires the epistemic contracts to remain language-neutral |
| Medium | Feature-flag collector | Stale flags are common temporal debt but have distinct runtime evidence and established competitors | Consider after G20; G15 may model feature-flag-like conditions but does not add a collector |
| Low | IDE extension | Makes line-level review convenient but does not validate the core thesis | Only after G20 stabilizes condition and case-file contracts |
| Low | Automatic pull-request creation | Reduces cleanup friction but increases external side effects and trust requirements | Requires G20 calibration evidence, a separate explicit approval design, and human authorization |
| Low | Jira, Slack, and internal RFC evidence providers | Enterprise rationale often lives outside GitHub | Consider after G18 establishes provider contracts and a design partner supplies a privacy model |
| Low | Scheduled repository collection | Enables continuous maintenance | Requires G20, incremental invalidation, rate limits, and operational ownership |
| Low | Cross-repository workaround analysis | Could connect local workarounds to upstream fixes across ecosystems | Requires mature dependency and provenance models |
