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

## Delivery branches

1. Release boundary
2. Feature flags and staged rollout
3. Backfill or migration
4. Monitoring and alerting
5. Rollback criteria
6. Human approvals

Stop exploring a branch when its answer cannot materially affect the planned work.
