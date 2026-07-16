# Architecture Checks

## Gate categories

### Scope

- changed files are within the Change Envelope;
- protected files and interfaces are unchanged;
- no unrelated cleanup is mixed into the task.

### Dependency structure

- imports follow allowed directions;
- no new dependency cycle exists;
- module boundaries are respected;
- internal implementation types do not leak across protected interfaces.

### Responsibility

- transport adapters do not own business rules;
- application services do not own persistence protocol details;
- repositories do not orchestrate business workflows;
- domain code does not depend on transport, persistence, or vendor frameworks unless declared;
- external calls use the declared integration boundary.

### Change-sensitive gates

- schema/migration changes include forward and rollback review;
- public API changes include contract and compatibility checks;
- security-boundary changes include negative authorization tests;
- dependency changes include lockfile, license, and vulnerability review;
- deployment-boundary changes include rollout and rollback validation.

## Enforcement order

```text
changed-path scope
-> deterministic dependency checks
-> responsibility review
-> risk-specific gates
-> combined-diff architecture review
```

## Existing-project baseline

Compare violations against stable baseline IDs. A violation is allowed only when:

- its exact source and target remain within the recorded exception;
- severity does not increase;
- the changed task does not extend or duplicate it.

Compute the fingerprint from rule ID/version, normalized source and target, edge kind, and location. Severity increases, rule-version changes, expanded source/target scope, or a different fingerprint are new findings rather than an exact baseline match.

Fail new or expanded violations. Report reduced violations as improvement without requiring unrelated cleanup.

## Finding format

```yaml
id: ARCH-FINDING-1
rule: controllers-must-not-import-database
location: src/controllers/order.ts:12
evidence: Direct import of database connection
baseline_status: new
impact: Transport layer now owns persistence dependency
smallest_fix: Call existing order service instead
verdict: block
```
