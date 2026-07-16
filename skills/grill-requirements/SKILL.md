---
name: grill-requirements
description: Resolve product, UX, technical, architecture, risk, and scope decisions through a disciplined one-question-at-a-time interview before implementation. Use when the user asks to grill, challenge, stress-test, clarify, interrogate, or pressure-test an idea, PRD, feature, project plan, architecture proposal, or ambiguous development request.
---

# Grill Requirements

Interview until the important decisions are explicit. Do not implement the idea.

## Load references

- Read [decision-tree.md](references/decision-tree.md) to select relevant question branches.
- Read [interview-protocol.md](references/interview-protocol.md) before asking the first question.
- Read [output-contract.md](references/output-contract.md) before concluding.

## Separate facts from decisions

Inspect available files, code, documentation, tools, and connected sources before asking the user. Look up discoverable facts. Ask only for decisions, preferences, priorities, trade-offs, authority, or unavailable business context.

Accept a short or incomplete prompt. Build a coverage view from the relevant branches in [decision-tree.md](references/decision-tree.md); the user is not responsible for knowing which context fields to list up front.

Do not ask the user to restate information already provided. Distinguish:

- `FACT`: supported by evidence;
- `INFERENCE`: plausible but not confirmed;
- `DECISION`: chosen by the user;
- `ASSUMPTION`: temporarily accepted to make progress;
- `OPEN`: unresolved and material.

## Ask one question at a time

For each material decision:

1. State the decision in one sentence.
2. Explain why it matters now.
3. Present relevant evidence or constraints.
4. Give a recommended answer and its main trade-off.
5. Ask exactly one question.
6. Wait for the user's answer before continuing.

Do not present a batch questionnaire. Do not hide several decisions inside one question.

Continue until every relevant material branch is resolved, explicitly defaulted, marked not applicable, or retained as a blocking open decision. Do not stop merely because the initial request was answered at a superficial level.

If the user chooses auto mode, answer low-risk decisions with the recommendation, record them as assumptions, and continue. Still pause for decisions involving public behavior, data loss, security boundaries, legal or financial exposure, irreversible actions, production access, or material cost.

## Follow dependencies

Resolve upstream decisions before dependent ones. Example:

```text
target user -> problem -> outcome -> scope -> behavior -> edge cases
-> data/API/architecture constraints -> rollout -> success measurement
```

Skip irrelevant branches. Reopen an earlier branch if a later answer contradicts it.

## Challenge constructively

Test whether:

- the stated problem is supported;
- software work is the right intervention;
- a smaller solution reaches the outcome;
- proposed behavior has a clear user or system owner;
- success and failure are observable;
- scope, non-goals, and compatibility are explicit;
- security, privacy, migration, operations, and rollback are addressed where relevant;
- requirements are mutually consistent.

Do not force artificial certainty. Preserve important unknowns.

## Conclude only with shared understanding

Before concluding, summarize the decision ledger and ask the user to confirm that shared understanding has been reached. Do not initiate implementation.

Return one of:

- `RESOLVED`: material decisions are explicit;
- `PARTIALLY_RESOLVED`: progress is useful but material open decisions remain;
- `REJECTED`: the user deliberately decides not to proceed.

Produce the output defined in [output-contract.md](references/output-contract.md). The result is input for `prepare-development-cycle`; it is not itself an implementation authorization.
