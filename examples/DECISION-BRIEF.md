# Decision Brief: Webhook Retry

Status: RESOLVED

## Problem

Temporary receiver failures currently lose webhook deliveries.

## Desired outcome

Retry temporary failures within a bounded schedule while preserving the public webhook contract.

## Decisions

| ID | Decision | Choice | Rationale | Source |
|---|---|---|---|---|
| D-1 | Retry scope | Temporary receiver failures only | Permanent failures should remain terminal | USER |

## Readiness recommendation

READY_FOR_PREPARATION
