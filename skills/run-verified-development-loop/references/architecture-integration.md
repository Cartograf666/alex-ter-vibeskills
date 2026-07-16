# Architecture Integration

## Inputs

Load when present:

```text
.ai/architecture.yaml
.ai/architecture-baseline.yaml
.ai/specs/<slug>/development-contract.yaml
```

Require `implementation_authorized: true` for prepared work.

## Work-package design

Package by coherent behavior and ownership, not mechanically by layer. One work package may touch a service, its repository port, and tests when those changes form one contract. Separate packages when they can be implemented and verified through stable interfaces without overlapping files or decisions.

For each package, derive:

- primary layer or component;
- allowed paths and change depth;
- acceptance criteria owned by the package;
- dependency edges it may introduce;
- architecture and ordinary quality gates;
- conditions that require an Architecture Change Request.

## Architecture gate

Before ordinary gates:

1. inventory changed files;
2. map them to declared layers;
3. compare them with the Change Envelope;
4. detect protected-interface changes;
5. run deterministic dependency and cycle checks;
6. compare findings with the exact existing-project baseline;
7. run semantic responsibility review.

Block new or expanded architecture violations even when tests pass.

## Scope expansion

When a worker needs an undeclared layer:

1. stop that implementation branch;
2. preserve current verified changes;
3. create an Architecture Change Request;
4. apply manual, bounded-auto, or full-auto policy;
5. after approval, update the Change Envelope and run state;
6. create a separate work package if ownership or risk changes;
7. attach new gates and continue.

Do not rewrite the architecture manifest merely to legalize an accidental dependency.

## Integration of worktrees

Verify each package independently. After merging or combining worktrees, rerun the entire architecture and quality gate set against the combined diff. Review interface compatibility between packages and confirm that no individually valid change forms a cycle or responsibility leak when combined.
