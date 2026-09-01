# Sunset repository instructions

Sunset is developed as a sequence of independently verifiable goals using the
`cycle` skill.

## Planning source of truth

Read these files before changing the project:

1. `docs/PROJECT.md` — product purpose, outcomes, canonical scenarios, and
   architecture constraints.
2. `docs/ROADMAP.md` — ordered goals, dependencies, and current status.
3. `docs/goals/<active-goal>.md` — complete specification for the active goal.
4. `docs/BACKLOG.md` — unscheduled work that is not required by an active goal.

The active goal is the single roadmap entry marked `active`. Complete exactly
one goal per cycle unless the user explicitly authorizes more.

## Cycle discipline

- Keep implementation within the active goal's scope and exclusions.
- Require every roadmap goal and detailed goal specification to state a
  `Purpose` explaining why the goal exists, distinct from its concrete
  `Objective`.
- Treat project scenarios as project-level outcomes and goal acceptance
  criteria as the binary completion checks for one goal.
- Record incidental findings in exactly one future goal or in the backlog.
- Do not mark a goal complete until each acceptance criterion has verification
  evidence and all required checks pass.
- When a goal completes, change its roadmap status to `complete` and prepare the
  next eligible goal as `proposed`; do not begin it without user authorization.
- Never delete code, open a pull request, or mutate an analyzed repository
  without explicit human approval.

## Goal specification standard

Every roadmap entry must be executable at the level its status promises:

- A `complete` or `active` goal has a detailed specification containing
  `Purpose`, `Objective`, dependencies, project outcomes and scenarios,
  architecture constraints, in-scope work, explicit exclusions, deliverables,
  binary goal-level acceptance criteria, criterion-to-evidence mapping,
  verification commands, and carried-forward risks.
- A `proposed` downstream goal may remain an outline, but it must still state
  `Purpose`, `Objective`, dependencies, scope boundary, exclusions, the
  outcomes and scenarios it is expected to advance, and the capability it
  unlocks for the next goal. An outline is not an implementation instruction.
- The next goal alone may include an execution contract. That contract must
  identify the expected implementation surface, public/domain contracts and
  invariants, fixture and test locations, authority/network/side-effect
  boundaries, and terminal or stop conditions. Equivalent module names are
  allowed only when the specification records the substitution and preserves
  the same contracts.
- Acceptance criteria must be binary, scoped, and independently verifiable.
  Prose such as “support,” “handle,” or “improve” must be paired with an
  observable artifact, test, invariant, or explicit negative case.
- If no roadmap entry is `active`, do not implement a proposed goal merely
  because it is next in dependency order. Report the next eligible goal and
  request authorization to activate it.
