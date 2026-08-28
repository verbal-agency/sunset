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
