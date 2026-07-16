# Technical Brief: Webhook retry

Status: APPROVED
Related PRD: examples/PRD.md
Architecture manifest: examples/architecture.yaml

## Technical outcome

Add bounded retry orchestration for temporary webhook delivery failures while preserving the public payload and existing successful-delivery path.

## Current architecture and evidence

The service layer owns delivery orchestration. External client adapters own HTTP protocol handling. Repositories persist delivery state, and controllers do not participate in retry policy.

## Proposed approach

Classify temporary transport failures in the external client adapter, return a typed result to the service, and let the service schedule bounded attempts. Persist attempt state through the existing repository contract. Treat any schema change as conditional scope requiring human approval.

## Affected layers and interfaces

| Layer/component | Intended change | Depth | Contract impact |
|---|---|---|---|
| services | Retry orchestration | full | Internal only |
| external clients | Failure classification | methods-only | Internal typed result |
| repositories | Retry-state methods | methods-only | Internal repository contract |
| database | Only if current state is insufficient | conditional | Human approval required |

## Data and migration

Use the current delivery record if it already stores attempt count and next-attempt time. Otherwise stop and submit an Architecture Change Request before changing the schema.

## External integrations

Keep the public webhook payload unchanged. Do not retry permanent receiver failures. Use bounded timeouts and the existing delivery identifier for every attempt.

## Failure handling and observability

Emit attempt number, classification, next-attempt time, and terminal outcome without logging payload secrets.

## Security and privacy

Do not expose webhook payloads to external model providers. Run gates without secrets and with network disabled.

## Alternatives considered

| Option | Benefits | Costs/risks | Decision |
|---|---|---|---|
| Retry in service | Clear policy ownership | Requires persisted scheduling state | Selected |
| Retry inside HTTP client | Fewer service changes | Mixes protocol and business policy | Rejected |

## Test and verification strategy

Map all four PRD criteria to contract, integration, architecture, and build gates. Freeze manager-approved acceptance tests after `TEST_DESIGN`.

## Rollout and rollback

Use an internal switch and monitor retry volume, success-after-retry rate, exhausted deliveries, and duplicate-delivery signals. Disable the switch to return to single-attempt behavior.

## Architectural consequences

No new dependency direction is permitted. Any database schema change requires a separate approved request and updated Change Envelope.
