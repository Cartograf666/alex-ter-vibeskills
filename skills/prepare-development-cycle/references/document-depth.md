# Document Depth

## FULL_PRD

Use for:

- a new product or service;
- a new project with no approved architecture;
- an epic spanning multiple workflows or teams;
- major user-visible behavior;
- high-risk security, financial, compliance, migration, or operational work.

Require every PRD section and a Technical Brief. Include measurable success and rollout plans.

## COMPACT_PRD

Use for:

- a bounded feature;
- a meaningful API, workflow, or data change;
- a change spanning several architectural layers;
- work whose requirements are known but still require explicit scope and behavior.

Keep the PRD concise. Require problem, outcome, actors, scope, non-goals, functional behavior, acceptance criteria, risks, rollout, and decisions. Require a Technical Brief when more than one component or layer changes.

## LEAN_BRIEF

Use for:

- a reproducible local bug;
- maintenance with no behavior ambiguity;
- a constrained refactor preserving behavior;
- dependency or configuration work with a clear desired state.

Require:

- current and desired behavior;
- reproduction or evidence;
- scope and non-goals;
- acceptance criteria;
- compatibility and risk;
- verification expectations;
- RunSpec and Change Envelope.

Do not inflate a trivial task into a product strategy document. Escalate to a deeper document when discovery reveals cross-layer, public-contract, data, security, or rollout decisions.
