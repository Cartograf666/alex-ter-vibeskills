# New project prompt

```text
Use $prepare-development-cycle.

I want to build a subscription-management service in TypeScript with PostgreSQL.
The first release needs APIs to create, view, and cancel a subscription.

Treat this as a new project:
- use FULL_PRD;
- use grill-requirements for material decisions;
- bootstrap architecture-governance before implementation;
- start in manual automation mode;
- do not write production code until I approve the architecture, PRD,
  Technical Brief, RunSpec, and Change Envelope.
```

After approval:

```text
Use $run-verified-development-loop with
.ai/specs/subscription-management/development-contract.yaml.

Use the configured manager, writer, tester, and independent reviewer roles.
Do not expand into a conditional layer without following its approval policy.
Rerun architecture and ordinary quality gates after combining worktrees.
```
