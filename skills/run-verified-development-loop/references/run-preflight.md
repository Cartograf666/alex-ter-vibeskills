# Runtime Preflight

Run this preflight before `DISCOVER`. Do not repeat the preparation interview and do not ask for information already bound into the approved contract.

## Validate prepared context

1. Validate the approved development contract and approval hashes.
2. Verify that interaction policy, automation budgets, model routes, provider transfer rules, approval boundaries, and reviewer independence are explicit.
3. Inspect current repository and host capabilities for facts that can only be known at runtime.
4. Resolve exact provider/model versions from the approved route preferences and record substitutions.
5. Verify worktree or isolation capability, executable gates, independent reviewer availability, permissions, sandbox, network, secret boundary, and trusted-host attestation capability when required.

## Ask only runtime decisions

Ask exactly one question at a time only when a missing runtime decision changes safety, external state, cost, independence, or the ability to satisfy the contract. Typical cases are:

- the preferred provider or model is unavailable and substitution policy is `ask`;
- a required independent reviewer cannot be provided;
- a required gate cannot run;
- a protected action or Change Envelope expansion is necessary;
- an approved budget is exhausted;
- the host cannot provide a required sandbox, credential boundary, worktree, or attestation mechanism.

Do not ask the user how to fix ordinary test or implementation failures while repair budget remains. Continue the state machine automatically according to `interaction_policy`.

## Outcomes

- `RUN_READY`: the loop can proceed to `DISCOVER`.
- `RUN_NOT_READY`: name the single blocking decision or unavailable capability.
- `READY_FOR_HUMAN_REVIEW`: implementation and machine verification are complete but independent acceptance is unavailable.

Persist state after every transition in `.ai/runs/<run-id>.yaml`. On continuation after an interruption or context compaction, reload the approved contract and run record, verify hashes, and resume from the last valid state instead of restarting completed work.
