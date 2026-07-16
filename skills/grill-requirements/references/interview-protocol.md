# Interview Protocol

## Question format

Use this compact structure:

```text
Decision: <what must be chosen>

Why now: <why later work depends on it>

Evidence: <known constraints or repository facts>

Recommendation: <recommended option> because <reason>.
Trade-off: <main downside>.

Question: <exactly one question>
```

For a simple conversational exchange, compress the labels but preserve the logic.

## Answer handling

After every answer:

1. Record the decision in the ledger.
2. Note affected downstream branches.
3. Detect contradiction with earlier decisions.
4. Ask the next highest-leverage unresolved question.

When the user says "you choose" or enables auto mode:

- choose the stated recommendation for reversible, low-risk decisions;
- mark it `ASSUMPTION-AUTO`;
- continue without asking for confirmation;
- pause for protected decisions.

## Protected decisions

Never silently choose:

- destructive or irreversible data operations;
- public API or externally visible behavior with compatibility impact;
- authentication, authorization, privacy, or credential policy;
- legal, compliance, financial, or billing commitments;
- production deployment or access;
- material recurring cost;
- scope changes that alter the stated outcome.

## Anti-patterns

Avoid:

- asking for facts available in the repository;
- asking several questions in a bullet list;
- treating the recommendation as the user's decision;
- implementing before confirmation;
- debating preferences after the user has made an informed choice;
- continuing indefinitely after the readiness conditions are met.
