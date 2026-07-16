# Quality Gates

## Contents

- Gate selection
- Execution order
- Test integrity
- Repair rules
- Review gate
- Risk-specific additions

## Gate selection

Discover commands from repository evidence in this order:

1. Local agent or contributor instructions.
2. CI workflow definitions.
3. Package/build configuration and documented scripts.
4. Existing developer documentation.
5. Tool-native defaults only when the repository provides no command.

Do not invent a command and report it as the project's official gate.

## Execution order

Run the cheapest high-signal gates first, then broader gates:

```text
scope check
-> architecture dependency and baseline checks
-> format check
-> lint/static analysis
-> type check
-> focused unit tests
-> affected integration tests
-> full required test suite
-> build/package
-> security/dependency checks
-> independent code and architecture review
```

Adapt the order when compilation is required before tests. Capture the exact command and exit code for every required gate.

Use deterministic tools for deterministic questions:

- use the formatter to decide formatting;
- use the compiler/type checker to decide type correctness;
- use tests to decide tested behavior;
- use the build to decide whether packaging succeeds;
- use a model reviewer for semantic gaps not covered by these tools.

## Test integrity

Compare test and configuration changes against the pre-implementation baseline. Block completion when a worker:

- deletes or skips a relevant test without an approved specification change;
- weakens assertions or reduces coverage to make a failure disappear;
- adds sleeps, retries, or nondeterminism instead of fixing a race;
- broadly mocks the behavior under test;
- adds suppression directives without a documented reason;
- lowers lint, type, coverage, security, or compiler strictness;
- changes snapshots without explaining the behavior change.

Allow legitimate test updates when acceptance behavior intentionally changed, but require the manager to connect each update to a criterion.

Haiku or another low-cost model may draft and execute routine tests. Require a stronger review for authorization, cryptography, concurrency, financial calculations, destructive migration, cross-version compatibility, or tests whose correctness depends on subtle invariants.

## Repair rules

For each failure:

1. Classify it as product defect, test defect, environment failure, flaky test, or unrelated pre-existing failure.
2. Preserve evidence for the classification.
3. Repair only the causal issue within the task scope.
4. Rerun the focused failing gate.
5. Rerun all required gates after the focused gate passes.

Never silently treat an unrun check as passing. If a check cannot run, disclose why and escalate according to the risk.

Do not use these shortcuts unless the user explicitly approves a justified exception:

```text
skip / xfail / only
eslint-disable / type-ignore / no-check
empty catch / swallowed exception
reduced compiler strictness
removed assertion
disabled CI job
unbounded retry
```

## Review gate

Give the reviewer:

- the original RunSpec;
- final diff and changed-file inventory;
- acceptance-test mapping;
- verification commands with exit codes;
- relevant unrun checks and known risks.

Keep the reviewer read-only. Require fresh context: do not include the writer's chain of thought or persuasive self-assessment. Review the combined diff after merging parallel work packages.

## Risk-specific additions

Add gates when relevant:

| Risk | Additional gate |
|---|---|
| Authentication/authorization | negative permission tests and privilege-boundary review |
| Data migration | forward/backward migration test, backup/rollback plan, human approval |
| Concurrency | race detector, deterministic concurrency tests, idempotency review |
| Public API | contract tests and backward-compatibility check |
| Dependencies | lockfile review, license/security scan, explicit approval |
| Performance | representative benchmark with baseline |
| UI/accessibility | interaction test, keyboard/focus check, accessibility scan |
| Deployment | dry run, rollback verification, explicit user authorization |
