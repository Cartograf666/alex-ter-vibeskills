---
name: prepare-development-cycle
description: Convert a new product idea, feature request, bug, refactor, or architecture change into an evidence-backed and user-approved PRD, Technical Brief, RunSpec, and architecture-aware Change Envelope before implementation. Use when starting a new project, preparing a development task, writing or refining a PRD, clarifying requirements, scoping work, or creating a handoff for an automated coding cycle.
---

# Prepare a Development Cycle

Produce an approved development contract. Do not write production code.

## Load references and templates

- Read [document-depth.md](references/document-depth.md) to select full, compact, or lean documentation.
- Read [context-intake.md](references/context-intake.md) before asking for missing context.
- Read [preparation-workflow.md](references/preparation-workflow.md) for the state machine.
- Read [readiness-gate.md](references/readiness-gate.md) before requesting approval.
- Read [handoff-contract.md](references/handoff-contract.md) before producing the final handoff.
- Validate the contract with [development-contract.schema.json](assets/development-contract.schema.json) and bundled `scripts/validate_contract.py`.
- Before using bundled Python validators in a shell-capable host, install the hash-locked packages with `python3 -m pip install --require-hashes -r requirements.txt`. In prompt-only hosts, apply the same invariants manually and disclose that executable validation did not run.
- Copy and fill [prd-template.md](assets/prd-template.md) for full or compact PRDs.
- Copy and fill [technical-brief-template.md](assets/technical-brief-template.md) when technical planning is needed.
- Use `design-system-governance` for any user interface or generated visual artifact. Reuse `.ai/design-system.yaml`; if none exists, discover or select a foundation and create a task `DESIGN-BRIEF.md` before approval.

## Establish context

Inspect repository instructions, documentation, current behavior, architecture manifests, relevant code, tests, CI commands, and prior decisions. Distinguish facts from inference. Preserve unrelated user changes.

Accept an incomplete or very short initial prompt. Build the coverage matrix from [context-intake.md](references/context-intake.md), reuse everything the user already supplied, discover repository facts yourself, and interview for every remaining material decision. Do not require the user to know which fields belong in the prompt.

For a new project, gather product intent and bootstrap architecture through `architecture-governance` when available. For an existing project, treat the approved architecture manifest and baseline as project constraints.

Classify design applicability explicitly. For UI work, inspect the approved design system, tokens, component explorer, design files, current screens, accessibility setup, and visual tests. For non-UI work, record a concrete not-applicable reason in `design_policy`.

## Resolve ambiguity

Use `grill-requirements` when available if material product, UX, behavior, scope, data, architecture, rollout, or approval decisions remain. If that skill is unavailable, follow the same one-question-at-a-time protocol:

- look up discoverable facts;
- ask exactly one decision question at a time;
- provide a recommended answer and trade-off;
- wait for the answer unless low-risk auto mode is enabled;
- never silently choose protected decisions.

Do not ask questions whose answers cannot materially alter the document or implementation boundary.

Do not draft the document set until the context completeness gate passes or the outcome is deliberately `NOT_READY`. A user-confirmed context summary is not implementation approval.

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
├── DESIGN-BRIEF.md
└── development-contract.yaml
```

For `LEAN_BRIEF`, `PRD.md` may be a compact problem-and-acceptance brief. Omit `TECHNICAL-BRIEF.md` only when there are no meaningful technical choices; explain the omission in the contract.

Create `DESIGN-BRIEF.md` only when `design_policy.applies` is true. It must reference an approved `.ai/design-system.yaml`, enumerate required interaction/content/responsive states, and map design acceptance to deterministic and visual gate IDs.

### PRD

Define the problem and outcome rather than prescribing implementation. Include users or actors, evidence, goals, non-goals, journeys or behavior, functional requirements, quality attributes, success measures, rollout, risks, decisions, assumptions, and testable acceptance criteria.

Use stable IDs:

```text
GOAL-1, FR-1, NFR-1, AC-1, RISK-1, DEC-1
```

### Technical Brief

Translate the approved behavior into a technical approach grounded in the actual project. Include affected components and layers, interfaces, data and migration, external integrations, failure handling, security, observability, rollout, alternatives, test strategy, and architectural consequences.

Do not invent repository facts. Mark uncertain design choices explicitly.

### Design system and Design Brief

Invoke `design-system-governance` to discover an existing system before proposing one. When absent, conduct its one-question-at-a-time selection interview; do not silently choose a fashionable library. Separate component foundation from visual direction and obtain explicit approval for the resulting project manifest.

For UI tasks, include token/component reuse, new extensions, viewport and content-state matrices, accessibility, interaction, motion, localization, screenshot references, and visual-regression strategy. Treat new tokens, primitives, public component APIs, or intentional deviations as protected design-system changes.

### Development contract

Produce the canonical versioned contract defined by [development-contract.schema.json](assets/development-contract.schema.json) and [handoff-contract.md](references/handoff-contract.md). The RunSpec states what must work. The Change Envelope states where and how deeply implementation may change the project. Quality gates, automation limits, provider policy, and test ownership belong to the same contract; do not create a second incompatible schema.

Require complete traceability:

```text
PRD requirement ID -> PRD acceptance ID -> RunSpec acceptance ID -> quality gate ID
```

The set of PRD and RunSpec `AC-*` IDs must match exactly. Run the bundled validator before requesting approval.

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
- design-system status, visual direction, and UI evidence requirements when applicable;
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

Do not toggle these fields manually. Run bundled `scripts/approve_contract.py` so approval binds to source-document hashes, the canonical contract payload hash, and the repository revision. Rerun `scripts/validate_contract.py` immediately afterward. Any material document or contract change invalidates approval and returns the work to preparation.

Do not automatically begin implementation unless the user explicitly asks to continue into `run-verified-development-loop`.

## Return status

Return exactly one readiness outcome:

- `READY`: documents approved and implementation authorized;
- `DRAFT`: useful documents exist but approval is pending;
- `NOT_READY`: material decisions or evidence remain unresolved;
- `REJECTED`: user chose not to proceed.
