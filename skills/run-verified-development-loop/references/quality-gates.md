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

Repository evidence is not automatically trusted. Inspect the resolved command, package lifecycle hooks, and any changed script before execution. List every resolved script, package manifest, lockfile, hook, and configuration file in the gate's `resolved_input_paths`; approval freezes their hashes and each gate result rebinds them to its Git revision. Never execute gate code from `.ai/runs/`. Apply the trust, approval, sandbox, network, secrets, and timeout fields from the canonical development contract.

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

Adapt the order when compilation is required before tests. Capture the exact command and exit code for every executed required gate. Record gates that cannot execute using the `not-run` rules below.

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
- modifies a frozen manager-approved acceptance test or its manifest without a separate tester-owned approval.

Allow legitimate test updates when acceptance behavior intentionally changed, but require the manager to connect each update to a criterion.

Haiku or another low-cost model may draft and execute routine tests. Require a stronger review for authorization, cryptography, concurrency, financial calculations, destructive migration, cross-version compatibility, or tests whose correctness depends on subtle invariants.

## Repair rules

For each failure:

1. Record `status: failed` and classify it with `failure_class`: product defect → `product-defect`, test defect → `test-defect`, environment failure → `environment`, flaky test → `flaky`, or unrelated pre-existing failure → `pre-existing`.
2. Preserve evidence for the classification.
3. Repair only the causal issue within the task scope.
4. Rerun the focused failing gate.
5. Rerun all required gates after the focused gate passes.

Record an unrun gate as `status: not-run` with a non-null `failure_class` from the same five values and a non-empty `note` explaining why (maximum 500 characters). Never omit it or count it as passing. Set all execution fields to null: `exit_code`, `started_at`, `finished_at`, `log_path`, `log_sha256`, `execution_environment`, `execution_event_id`, and `execution_hmac_sha256`. Retain `gate_id`, `command_sha256`, `resolved_inputs`, `revision`, and `tree_sha256` to pin the intended verification state. Escalate according to the risk.

A passing executed gate uses `status: passed`, `exit_code: 0`, and `failure_class: null`; a failed executed gate requires a non-zero exit code. Both retain non-null execution evidence (exit code, timestamps, log path/hash, and environment); their `note` may be null or a string of at most 500 characters. Execution attestation fields remain nullable, but an accepted run requires host attestations for every executed result, including failed history. A `not-run` result never carries an execution attestation. Acceptance requires exactly one current passing result per contract gate; failed and not-run history never counts. Staleness is derived from `revision` and `tree_sha256`, not a stored field.

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
