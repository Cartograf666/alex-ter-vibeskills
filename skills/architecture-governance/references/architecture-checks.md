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

The machine-readable list passed to `validate_baseline.py --findings` must use exactly the normalized fingerprint inputs plus severity:

```yaml
rule_id: ARCH-NO_DB
rule_version: 1
severity: high
source: controllers
target: database
edge_kind: data-access
location: src/controllers/order.ts:12
```

Allowed `edge_kind` values are `import`, `call`, `data-access`, `network`, `type-leak`, and `responsibility`. Normalize component names and locations consistently before fingerprinting.

A stored baseline entry adds `id`, `fingerprint`, `first_seen_revision`, `reason`, `policy`, `owner`, and `review_after` as defined by `assets/architecture-baseline.schema.json`. Human-facing evidence, impact, smallest fix, and verdict may appear in a separate review report, but they do not replace the normalized machine fields above.

Generate a fingerprint with bundled `scripts/finding_fingerprint.py`, or let the validator recompute it. A malformed current finding fails with a field-specific validation error rather than being treated as a new baseline item.
