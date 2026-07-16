# Existing project prompts

Run once:

```text
Use $architecture-governance in BOOTSTRAP_EXISTING mode.

Document the actual as-is architecture. Do not refactor production code.
Create .ai/architecture.yaml and .ai/architecture-baseline.yaml.
Record current violations as exact baseline exceptions, then configure policy
to block new or expanded violations. Start in manual automation mode.
```

For each task:

```text
Use $prepare-development-cycle.

Add retries for webhook delivery after temporary receiver failures.
Use the approved project architecture and baseline. Do not change the public API.
Create the appropriate PRD depth, Technical Brief when needed, RunSpec, and
Change Envelope. Ask me only for material decisions and do not implement yet.
If the task affects UI, discover and preserve the existing design system first;
create a Design Brief and required accessibility/visual gates. If it does not,
record design_policy as not applicable with a reason.
```

After approval:

```text
Use $run-verified-development-loop with
.ai/specs/webhook-retry/development-contract.yaml.

Preserve baseline architecture exceptions but block new ones. Create worktrees
per coherent work package, not per layer. Run combined architecture and quality
verification before acceptance.
```
