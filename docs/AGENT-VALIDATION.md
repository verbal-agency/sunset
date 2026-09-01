# Human-gated agent validation

G14 adds `AgentValidationGate`, a small LangGraph pause/resume boundary between
bounded investigation receipts and the existing G06 disposable validator. It
does not make a cleanup decision and does not create a new execution adapter.

## Reviewable plan

`build_validation_plan` derives exactly one plan from a current provenance
receipt, the trusted G10 repository context, and a host-supplied G06
`ValidationConfig`. The plan records only the candidate ID, committed HEAD,
collector, evidence-receipt IDs, and configured narrow/broader command policy.
Its stable ID changes when any reviewed input changes.

Models cannot supply a command, repository path, clone location, environment
variable, budget, approval token, or candidate. External evidence can be linked
through its receipt IDs, but it remains evidence—not permission to validate.

## Explicit approval

The host must provide a `ValidationApproval` containing an approval ID, the
exact plan ID, an `approve` or `deny` decision, and an expiry instant. With no
approval the gate returns `awaiting_approval`; a denial returns `denied`.
Malformed, wrong-plan, expired, or changed-HEAD approvals return a structured
incompatible/expired result and invoke no validator.

An approved plan calls G06 with `approved=True` only after those checks. G06
still creates the disposable clone, applies its single marker transform, runs
its configured commands without a shell, and supplies the artifact-backed
`confirmed`, `still_failing`, `flaky`, `environment_error`, or `inconclusive`
classification. The target repository is never edited.

## Replay and data boundary

The gate writes immutable checkpoint views containing the compact plan,
decision, result class, validation artifact references, and structured errors.
It does not retain raw test output, logs, credentials, framework messages, or a
mutable worktree path. Reopening a completed compatible gate returns its saved
result and does not run G06 again. A different plan—including changed candidate,
receipts, HEAD, or validation configuration—uses a different identity and
cannot reuse the old approval.

Human approval authorizes one bounded experiment only. It is not approval to
remove code, create a pull request, or make any external write.
