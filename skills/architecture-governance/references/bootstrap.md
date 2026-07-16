# Architecture Bootstrap

## Greenfield

1. Derive product and operational constraints from the approved PRD.
2. Select the smallest architecture that supports the first delivery boundary.
3. Define components, dependency direction, interfaces, data ownership, and deployment boundaries.
4. Identify decisions that are expensive to reverse.
5. Propose `.ai/architecture.yaml` as `PROVISIONAL`.
6. Ask for approval of material decisions one at a time.
7. Mark the manifest `APPROVED` before implementation.

Avoid speculative layers, generic repositories, service abstractions, or distributed components without a current requirement.

## Existing project

1. Inventory entry points, modules, layers, imports, data access, external calls, and runtime boundaries.
2. Describe the `as-is` architecture before recommending a target architecture.
3. Compare documentation with observed code.
4. Classify established patterns and inconsistencies.
5. Create `.ai/architecture.yaml` for rules that future changes must follow.
6. Create `.ai/architecture-baseline.yaml` for existing violations.
7. Enable enforcement progressively.

Use enforcement stages:

```text
report-only -> block-new-violations -> changed-modules-strict -> whole-project-strict
```

Do not fix legacy violations during bootstrap unless explicitly requested.

## Evidence report

For every proposed rule, include:

- supporting paths or dependency edges;
- whether the rule is documented, observed, or inferred;
- exceptions and their prevalence;
- recommended decision;
- migration cost if the rule becomes strict.
