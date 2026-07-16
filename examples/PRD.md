# PRD: Webhook retry

Status: APPROVED
Document depth: COMPACT_PRD

## Executive summary

Webhook delivery currently fails permanently when a receiver has a temporary outage. Add bounded retries so transient failures recover without changing the public webhook contract or retrying permanent failures.

## Evidence and current state

The delivery service performs one outbound request. Timeouts and server-side receiver failures are returned as terminal failures. Existing successful delivery behavior is stable and must remain unchanged.

## Users and use cases

- Integrators need temporary receiver outages to recover automatically.
- Operators need to observe pending attempts and terminal failure.

## Goals

- GOAL-1: Recover delivery from temporary receiver failures within a bounded period.

## Non-goals

- Change the webhook payload or endpoint contract.
- Retry authentication, validation, or other permanent receiver errors.
- Provide user-configurable retry schedules in this release.

## Functional requirements

- FR-1: Classify transport timeouts and configured receiver 5xx responses as temporary.
- FR-2: Retry temporary failures with bounded exponential backoff.
- FR-3: Mark delivery terminal after the configured maximum attempt count.
- FR-4: Emit observable attempt and terminal-outcome events.

## Acceptance criteria

- AC-1: Temporary receiver failures are retried according to the configured schedule.
- AC-2: Successful, permanent-failure, and exhausted-retry outcomes are distinguishable.
- AC-3: Permanent receiver failures are not retried.
- AC-4: Existing successful delivery behavior and public payload remain compatible.

## Rollout and rollback

Release behind an internal configuration switch. Monitor retry volume, success-after-retry rate, and terminal failures. Disable the switch to return to single-attempt behavior.

## Risks and mitigations

- RISK-1: Retry amplification — Mitigation: bounded attempts, backoff, and metrics.
- RISK-2: Duplicate receiver processing — Mitigation: preserve delivery identifier and document idempotency expectations.

## Decisions

- DEC-1: Retry policy belongs to the service layer; transport classification belongs to the external client adapter.
