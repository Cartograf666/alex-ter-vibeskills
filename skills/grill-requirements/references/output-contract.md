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
