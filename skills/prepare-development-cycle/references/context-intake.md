# Context Intake

Build the fullest material context the user can provide without turning the conversation into a static questionnaire.

## Intake sequence

1. Parse everything the user has already said.
2. Inspect repository instructions, documentation, architecture and design manifests, code, tests, CI, configuration, and prior decisions.
3. Create an internal coverage matrix for the decision groups below.
4. Mark every relevant item as `FACT`, `DECISION`, `ASSUMPTION`, `NOT_APPLICABLE`, or `OPEN`, with its source.
5. Ask exactly one highest-leverage `OPEN` decision at a time.
6. After every answer, update the matrix, detect contradictions, and choose the next question.
7. Finish with a material-context summary and ask the user to confirm it before drafting or approving the contract.

Never ask the user for a fact that can be discovered safely from the project. Never ask an irrelevant branch merely to complete a checklist.

## Decision groups

Cover each group when it can change behavior, scope, architecture, risk, cost, verification, or delivery.

| Group | Material context to resolve |
|---|---|
| Outcome | New or existing project; problem; target actor; desired observable result; success measure |
| Scope | In-scope behavior; non-goals; priority; deadline; compatibility promises |
| Behavior | Main flow; inputs and outputs; errors, empty states, permissions, concurrency, idempotency, localization |
| Architecture | Primary component; dependency direction; public and protected interfaces; allowed, conditional, and forbidden layers |
| Data | Source of truth; sensitivity; retention; migration; consistency; deletion and rollback |
| Integrations | Providers; contracts; authentication; retries; rate limits; partial failure; external code or data transfer |
| Design | UI applicability; existing design authority; target platforms; visual direction; states; accessibility; responsive evidence |
| Delivery | Environment; rollout; feature flags; observability; alerting; rollback; production and external actions |
| Verification | Acceptance criteria; test ownership; existing and new gates; required evidence; independent review |
| Automation | Manual, bounded-auto, or full-auto; retry, review, concurrency, tool-call, time, and cost budgets |
| Interaction | Intake mode; progress cadence; events that must interrupt; terminal goal; resumability expectation |
| Model routing | Preferred manager, scout, tester, writer, verifier, and reviewer routes; fallbacks; substitution policy; reviewer independence |
| Authority | Who may approve; protected decisions; credential, billing, legal, production, destructive, and public-contract boundaries |

## First-turn behavior

Accept a short prompt. Do not require the user to know the schema or list every field.

If the prompt does not specify an intake preference, first inspect the repository and then ask whether to use:

- `guided`: ask for every material decision that cannot be discovered;
- `recommended-defaults`: choose reversible low-risk recommendations, record them as assumptions, and ask only protected or materially preference-dependent decisions.

Recommend `guided` for greenfield, high-risk, public-contract, data, security, migration, or unclear product work. Recommend `recommended-defaults` for bounded low-risk work in a well-documented repository.

## Question policy

Use the `grill-requirements` question format. Each turn contains one decision, one recommendation, its main trade-off, and exactly one question. Do not send a form or a long batch of questions.

Ask preferences only when they matter. For example, do not ask for a frontend style on a backend-only task, an exact model when the host cannot route models, or a deployment plan for a local prototype that will not be deployed.

If the user says “choose for me,” use the recommendation only for reversible low-risk items and mark it `ASSUMPTION-AUTO`. Never auto-decide protected matters.

## Completeness gate

Context is complete only when every relevant item is:

- supported by repository evidence;
- explicitly decided by the user;
- explicitly defaulted as a reversible assumption;
- marked not applicable with a reason; or
- retained as an open item with an owner and a deliberate `NOT_READY` outcome.

Before drafting, summarize material facts, decisions, assumptions, non-applicable branches, and remaining open items. Ask the user to confirm the summary. Confirmation does not authorize implementation; contract approval remains a separate action.

A current user-confirmed Decision Brief from `grill-requirements` satisfies this confirmation when repository discovery found no material contradiction or new decision. Reuse its ledger as the initial coverage matrix and do not repeat its questions.
