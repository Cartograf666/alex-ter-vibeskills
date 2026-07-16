# Decision Tree

Select only branches that can change the outcome, design, risk, or scope.

## Product branches

1. Target user or actor
2. Problem and current workaround
3. Desired outcome
4. Success metric and observation window
5. Scope and non-goals
6. Priority among time, quality, cost, and flexibility

## Behavior branches

1. Primary journey or use case
2. Inputs and outputs
3. Error and empty states
4. Permissions and ownership
5. Concurrency and idempotency
6. Accessibility and localization
7. Compatibility expectations

## Data branches

1. Data source and authority
2. Data model and lifecycle
3. Retention and deletion
4. Privacy and sensitivity
5. Migration and rollback
6. Consistency and transaction requirements

## Integration branches

1. Contract and versioning
2. Authentication
3. Timeouts, retries, and rate limits
4. Partial failure and fallback
5. Observability and auditability
6. Vendor or operational dependency

## Architecture branches

1. Primary layer or component
2. Permitted dependency direction
3. Public versus internal interfaces
4. Transaction and orchestration boundary
5. Cross-layer changes
6. Deployment topology

## Experience and design-system branches

1. Existing approved design system, tokens, component library, or prototype authority
2. Target platforms, input methods, viewport classes, and host-ecosystem conventions
3. Product character, information density, brand maturity, and color modes
4. Reused components versus new patterns or public component APIs
5. Loading, empty, error, permission, success, destructive, and offline states
6. Accessibility, keyboard/focus, reduced motion, zoom/reflow, and localization

Explore this branch for user interfaces or generated visual artifacts. If no usable design system exists, hand the selection decision to `design-system-governance` and continue one question at a time. Do not ask visual-preference questions for backend-only work; record design as not applicable.

## Delivery branches

1. Release boundary
2. Feature flags and staged rollout
3. Backfill or migration
4. Monitoring and alerting
5. Rollback criteria
6. Human approvals

## Automation and interaction branches

1. Manual, bounded-auto, or full-auto operation
2. Retry, review, concurrency, tool-call, elapsed-time, and cost limits
3. Progress-update cadence and events that interrupt the run
4. Terminal goal and whether a run must resume from persisted state
5. Preferred manager, scout, tester, writer, verifier, and reviewer models
6. Provider fallbacks, substitution policy, code-transfer boundary, and reviewer independence

Stop exploring a branch when its answer cannot materially affect the planned work.
