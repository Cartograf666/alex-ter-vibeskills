# New project prompt

```text
Use $prepare-development-cycle.

I may provide only a short idea. Inspect what you can discover, then interview
me one question at a time for every remaining material product, architecture,
design, delivery, automation, model-routing, budget, approval, and acceptance
decision. Recommend an answer and explain its main trade-off.

I want to build a subscription-management web product in TypeScript with PostgreSQL.
The first release needs APIs and a responsive dashboard to create, view, and cancel a subscription.

Treat this as a new project:
- use FULL_PRD;
- use grill-requirements for material decisions;
- bootstrap architecture-governance before implementation;
- use design-system-governance to discover or select the UI foundation;
- if no system exists, ask one question at a time and recommend from current
  platform-appropriate systems rather than silently choosing a theme;
- start in manual automation mode;
- do not write production code until I approve the architecture, design system,
  PRD, Technical Brief, Design Brief, RunSpec, and Change Envelope.
```

After approval:

```text
Use $run-verified-development-loop with
.ai/specs/subscription-management/development-contract.yaml.

Use the configured manager, writer, tester, and independent reviewer roles.
Do not expand into a conditional layer without following its approval policy.
Rerun architecture and ordinary quality gates after combining worktrees.
For UI packages, also run token, accessibility, responsive interaction, visual
regression, and independent design review gates from the approved contract.
```
