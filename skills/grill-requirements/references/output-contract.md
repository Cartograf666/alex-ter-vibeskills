# Output Contract

Produce a decision brief:

```markdown
# Decision Brief: <name>

Status: RESOLVED | PARTIALLY_RESOLVED | REJECTED

## Problem
<evidence-backed problem>

## Desired outcome
<observable outcome>

## Decisions
| ID | Decision | Choice | Rationale | Source |
|---|---|---|---|---|
| D-1 | ... | ... | ... | USER / AUTO / EVIDENCE |

## Assumptions
| ID | Assumption | Risk | Validation |
|---|---|---|---|

## Constraints
- ...

## Automation and interaction
- Intake mode: guided | recommended-defaults
- Automation mode and budgets: ...
- Progress and interruption policy: ...
- Model routes, fallbacks, and reviewer independence: ...

## Non-goals
- ...

## Open decisions
| ID | Decision | Why blocking | Recommended next action |
|---|---|---|---|

## Contradictions resolved
- ...

## Readiness recommendation
READY_FOR_PREPARATION | NEEDS_MORE_DISCOVERY | DO_NOT_PROCEED
```

Do not label the brief as a PRD and do not authorize implementation. `prepare-development-cycle` converts this decision record and repository evidence into the appropriate PRD and development contracts.
