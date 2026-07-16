# Preparation Workflow

Use this state machine:

```text
DISCOVER -> CLASSIFY -> GRILL -> DRAFT_PRD -> DRAFT_TECH
-> GOVERN_ARCHITECTURE -> READINESS_REVIEW -> USER_APPROVAL -> HANDOFF
```

## DISCOVER

Gather business and repository evidence. For a greenfield project, identify constraints, deployment environment, expected scale, and chosen stack only when they affect the first delivery boundary.

## CLASSIFY

Choose document depth and risk level. Record why.

## GRILL

Resolve only material open decisions. Preserve an explicit decision ledger.

## DRAFT_PRD

Describe problem, outcome, behavior, and acceptance independently from implementation. Avoid architecture-first requirements unless architecture itself is the product requirement.

## DRAFT_TECH

Ground technical choices in the approved PRD and actual project. Document alternatives for material decisions.

## GOVERN_ARCHITECTURE

Classify affected layers and create the Change Envelope. For greenfield, require approval of a provisional architecture manifest. For existing projects, preserve baseline violations but prohibit new unapproved ones.

## READINESS_REVIEW

Check traceability:

```text
goal -> requirement -> acceptance criterion -> verification expectation
requirement -> affected component -> allowed change scope
risk -> mitigation -> gate or approval
```

## USER_APPROVAL

Ask for explicit approval after presenting material decisions, not the entire document verbatim. Reopen preparation if the user changes outcome, scope, or protected behavior.

## HANDOFF

Freeze stable IDs and produce the development contract. Subsequent implementation discoveries may extend the Change Envelope through an Architecture Change Request, but workers may not silently rewrite the PRD.
