---
name: prepare-development-cycle
description: Convert a new product idea, feature request, bug, refactor, or architecture change into an evidence-backed and user-approved PRD, Technical Brief, RunSpec, and architecture-aware Change Envelope before implementation. Use when starting a new project, preparing a development task, writing or refining a PRD, clarifying requirements, scoping work, or creating a handoff for an automated coding cycle.
---

# Prepare a Development Cycle

Produce an approved development contract. Do not write production code.

## Load references and templates

- Read [document-depth.md](references/document-depth.md) to select full, compact, or lean documentation.
- Read [preparation-workflow.md](references/preparation-workflow.md) for the state machine.
- Read [readiness-gate.md](references/readiness-gate.md) before requesting approval.
- Read [handoff-contract.md](references/handoff-contract.md) before producing the final handoff.
- Copy and fill [prd-template.md](assets/prd-template.md) for full or compact PRDs.
- Copy and fill [technical-brief-template.md](assets/technical-brief-template.md) when technical planning is needed.

## Establish context

Inspect repository instructions, documentation, current behavior, architecture manifests, relevant code, tests, CI commands, and prior decisions. Distinguish facts from inference. Preserve unrelated user changes.

For a new project, gather product intent and bootstrap architecture through `architecture-governance` when available. For an existing project, treat the approved architecture manifest and baseline as project constraints.

## Resolve ambiguity

Use `grill-requirements` when available if material product, UX, behavior, scope, data, architecture, rollout, or approval decisions remain. If that skill is unavailable, follow the same one-question-at-a-time protocol:

- look up discoverable facts;
- ask exactly one decision question at a time;
- provide a recommended answer and trade-off;
- wait for the answer unless low-risk auto mode is enabled;
- never silently choose protected decisions.

Do not ask questions whose answers cannot materially alter the document or implementation boundary.

## Choose document depth

Select one level using [document-depth.md](references/document-depth.md):

- `FULL_PRD`: new product, epic, major workflow, multiple stakeholders, or high-risk behavior;
- `COMPACT_PRD`: bounded feature or meaningful behavior change;
- `LEAN_BRIEF`: local bug, maintenance task, or constrained refactor with understood behavior.

Never omit observable acceptance criteria, non-goals, constraints, risks, or approval boundaries. Record the selected depth and reason.

## Produce the document set

Create one authoritative specification directory, normally:

```text
.ai/specs/<slug>/
├── PRD.md
├── TECHNICAL-BRIEF.md
└── development-contract.yaml
```

For `LEAN_BRIEF`, `PRD.md` may be a compact problem-and-acceptance brief. Omit `TECHNICAL-BRIEF.md` only when there are no meaningful technical choices; explain the omission in the contract.

### PRD

Define the problem and outcome rather than prescribing implementation. Include users or actors, evidence, goals, non-goals, journeys or behavior, functional requirements, quality attributes, success measures, rollout, risks, decisions, assumptions, and testable acceptance criteria.

Use stable IDs:

```text
GOAL-1, FR-1, NFR-1, AC-1, RISK-1, DEC-1
```

### Technical Brief

Translate the approved behavior into a technical approach grounded in the actual project. Include affected components and layers, interfaces, data and migration, external integrations, failure handling, security, observability, rollout, alternatives, test strategy, and architectural consequences.

Do not invent repository facts. Mark uncertain design choices explicitly.

### Development contract

Produce machine-readable `RunSpec` and `ChangeEnvelope` using [handoff-contract.md](references/handoff-contract.md). The RunSpec states what must work. The Change Envelope states where and how deeply the implementation may change the project.

## Apply architecture governance

Invoke `architecture-governance` when available to:

- classify the primary layer or component;
- validate intended dependency direction;
- establish allowed, conditional, forbidden, and protected scope;
- set cross-layer approval behavior;
- attach architecture checks to verification expectations.

If no architecture manifest exists, do not fabricate an approved architecture. Create a provisional proposal and require explicit approval before development.

## Request approval

Run the readiness gate. Present a concise summary of:

- outcome and non-goals;
- material product and architecture decisions;
- acceptance criteria;
- Change Envelope;
- protected decisions and human-approval boundaries;
- unresolved assumptions and risks.

Request explicit approval. Until approval, set:

```yaml
status: draft
implementation_authorized: false
```

After approval, set:

```yaml
status: approved
implementation_authorized: true
approved_by: user
```

Do not automatically begin implementation unless the user explicitly asks to continue into `run-verified-development-loop`.

## Return status

Return exactly one readiness outcome:

- `READY`: documents approved and implementation authorized;
- `DRAFT`: useful documents exist but approval is pending;
- `NOT_READY`: material decisions or evidence remain unresolved;
- `REJECTED`: user chose not to proceed.
