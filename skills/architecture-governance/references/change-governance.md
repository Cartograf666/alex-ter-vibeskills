# Change Governance

## Change depth

Use consistent depth labels:

- `none`: no change allowed;
- `wiring-only`: dependency registration or configuration only;
- `adapter-only`: transport/protocol mapping without business behavior;
- `methods-only`: extend existing internal contract without structural redesign;
- `full`: responsibility-consistent implementation allowed;
- `manifest-change`: architecture rule itself changes and requires approval.

## Automation modes

### manual

Ask before any undeclared layer or protected interface changes.

### bounded-auto

Auto-approve reversible low-risk scope such as tests, internal DTOs, wiring, generated types, or adapter mapping when allowlisted. Ask for database schema, public API, security boundary, external contract, new dependency, cross-module edge, or deployment topology changes.

### full-auto

Allow the manager to extend internal scope when acceptance criteria and public behavior remain fixed, checks exist, and the decision is recorded. Still require human approval for destructive data operations, production actions, credentials, protected security policy, legal/financial decisions, or explicit project protections.

## Architecture Change Request

Require:

- triggering acceptance criterion;
- current and requested layers;
- limitation of the approved envelope;
- proposed files, interfaces, and dependency edges;
- alternatives and trade-offs;
- compatibility, migration, security, and operational impact;
- recommendation;
- required new checks;
- requested approval class.

After approval:

1. update the Change Envelope;
2. record the decision;
3. create a new work package when ownership changes;
4. add relevant gates;
5. continue implementation.

Reject the request if it merely moves business logic into a convenient but incorrect layer.

## Routine adjacent changes

Do not interrupt the user for adjacent changes already authorized, such as:

- tests for an allowed layer;
- dependency-injection registration;
- internal DTO or mapper updates;
- generated artifacts from an approved contract;
- local documentation and fixtures.

Always record their paths in the ResultPacket.
