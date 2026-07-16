# Readiness Gate

Return `READY` only if all required checks pass.

## Product readiness

- The problem and desired outcome are unambiguous.
- Target actors and primary behavior are identified.
- Scope and non-goals are explicit.
- Every required behavior has an observable acceptance criterion.
- Success or completion can be evaluated.
- Material error, empty, permission, and concurrency states are addressed when relevant.

## Technical readiness

- Repository facts are separated from assumptions.
- Affected components and architectural layers are identified.
- Data, API, integration, migration, security, observability, and rollout impacts are covered when relevant.
- The verification expectations correspond to available project gates or explicitly requested new gates.
- The Change Envelope names allowed, conditional, forbidden, and protected scope.

## Decision readiness

- Critical decisions have owners and outcomes.
- Protected decisions have explicit approval boundaries.
- Remaining assumptions are low-risk and have a validation plan.
- No unresolved contradiction exists between PRD, Technical Brief, architecture manifest, and development contract.
- The user explicitly approved the final material summary.

If a check fails, return `NOT_READY` with the single highest-leverage next decision or investigation.
