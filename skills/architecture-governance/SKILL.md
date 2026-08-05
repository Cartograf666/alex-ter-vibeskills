---
name: architecture-governance
description: Bootstrap, document, enforce, and review a project's architecture through layer responsibilities, dependency direction, architecture manifests, legacy baselines, Change Envelopes, cross-layer approval policy, and deterministic architecture checks. Use when starting a project, auditing an existing codebase, planning cross-layer work, preventing architecture erosion, reviewing structural changes, or deciding whether implementation may expand into another layer.
---

# Govern Project Architecture

Use an explicit architecture manifest as the source of truth. Passing tests does not excuse an architectural violation.

## Respond in the user's language

Detect the user's language from their messages and use it for all prose addressed to them: questions, explanations, recommendations, status, and the closing summary. Keep every machine token verbatim — code, commands, file paths, schema field names, stable IDs, and the status or verdict values this skill returns — and convey their meaning in the surrounding prose rather than translating the tokens. If the user's language is unclear, ask once, then continue in the chosen language.

Persisted artifacts are contracts, not chat. Keep their template headings, YAML keys, stable IDs, and status tokens exactly as specified so downstream skills and validators keep working. Narrative content inside an artifact may follow the user's language when the user asks for it.

## Load references and templates

- Read [bootstrap.md](references/bootstrap.md) when the project lacks an approved manifest.
- Read [change-governance.md](references/change-governance.md) for task-level Change Envelopes and cross-layer requests.
- Read [architecture-checks.md](references/architecture-checks.md) before defining or executing gates.
- Copy [architecture-template.yaml](assets/architecture-template.yaml) to `.ai/architecture.yaml` when bootstrapping.
- Copy [baseline-template.yaml](assets/baseline-template.yaml) to `.ai/architecture-baseline.yaml` for existing projects with known violations.
- Use [architecture-change-request.md](assets/architecture-change-request.md) when implementation needs undeclared scope.
- Validate manifests with bundled `scripts/validate_architecture.py` and baselines with `scripts/validate_baseline.py`.
- Before using bundled Python validators in a shell-capable host, install the hash-locked packages with `python3 -m pip install --require-hashes -r requirements.txt`. In prompt-only hosts, disclose that schema and Git-provenance checks were not executed.

## Select operating mode

Use one of:

- `BOOTSTRAP_GREENFIELD`: propose architecture before implementation;
- `BOOTSTRAP_EXISTING`: document actual architecture and baseline existing violations without refactoring them;
- `PLAN_CHANGE`: classify a proposed task and create or validate its Change Envelope;
- `ENFORCE_CHANGE`: monitor implementation against approved boundaries;
- `REVIEW_ARCHITECTURE`: review a diff or project without changing code.

Do not mix bootstrap with a broad cleanup unless the user explicitly authorizes refactoring.

## Establish evidence

Inspect repository instructions, directory structure, imports, dependency injection, runtime entry points, persistence, external clients, schemas, build and test configuration, deployment topology, and existing architecture documentation.

Label rules as:

- `APPROVED`: explicitly established by project authority;
- `OBSERVED`: consistently reflected in code;
- `PROVISIONAL`: inferred and awaiting approval;
- `BASELINE_EXCEPTION`: existing violation allowed only at its current location;
- `FORBIDDEN`: prohibited for new changes.

Never present inferred architecture as approved.

Use bundled `scripts/approve_architecture.py` for explicit approval and `scripts/validate_architecture.py` before relying on the manifest. Any payload change invalidates the approval hash and returns the manifest to provisional review.

## Define architecture boundaries

For each layer or component, define:

- paths and ownership;
- responsibilities;
- allowed dependencies;
- forbidden dependencies;
- public and internal interfaces;
- transaction or orchestration boundaries;
- required checks;
- approval policy for changes.

Model the project's actual architecture. Do not force a layered template on event-driven, hexagonal, modular monolith, microservice, frontend, data, or infrastructure projects when another vocabulary fits better.

For frontend projects, keep structural ownership here and visual/component contracts in `design-system-governance`. Architecture defines where shared primitives, feature UI, state, and adapters live; the design system defines tokens, component behavior, accessibility, responsive rules, and visual evidence. Require both approvals when a change affects both boundaries.

## Govern task scope

Every implementation task must have a Change Envelope identifying:

- primary layer or component;
- allowed layers with reason and change depth;
- conditional layers and approval policy;
- forbidden layers;
- protected interfaces and behaviors;
- architecture acceptance criteria.

When implementation needs undeclared scope, stop that branch and create an Architecture Change Request. Apply the project's `manual`, `bounded-auto`, or `full-auto` policy as defined in [change-governance.md](references/change-governance.md).

Do not ask the user for routine changes already permitted by the envelope. Do ask when a protected decision, conditional layer, or architecture rule would change.

## Enforce architecture

Run deterministic checks when possible:

- changed-path scope;
- forbidden imports or dependency edges;
- dependency cycles;
- direct persistence access outside declared adapters;
- outbound network calls outside integration adapters;
- public API/schema changes;
- new dependencies;
- migration changes;
- framework or ORM types crossing protected boundaries.

Use model review for semantic responsibilities that static checks cannot decide. Record exact evidence for every blocker.

For an existing project, block new violations while allowing recorded baseline exceptions. Do not let a baseline exception authorize new copies of the same violation.

Record each exception with stable rule ID and version, severity, normalized edge kind, source, target, precise location, first-seen revision, and deterministic fingerprint. Reject placeholder or evidence-free baseline entries.

## Update governance artifacts

Change `.ai/architecture.yaml` only for an intentional architecture decision, not merely because a worker violated it. Require explicit approval for protected architecture changes. Record accepted deviations with rationale, owner, date, and removal or review condition.

## Return a verdict

Return one of:

- `APPROVED`: architecture or change conforms;
- `APPROVED_WITH_RECORDED_EXCEPTION`: an authorized deviation is documented;
- `BLOCKED`: concrete unapproved violation exists;
- `NEEDS_HUMAN`: protected decision requires authority;
- `PROVISIONAL`: bootstrap proposal awaits approval.

Include manifest path, affected layers, check results, baseline effects, change requests, and next action.

## Summarize what you did

After returning the outcome, close with a short summary in the user's language that states:

- what you did and what it decided or produced;
- the status or verdict you returned and what it means for the user;
- where each created or updated file now lives, by exact repository path;
- the recommended next step.

Name file locations explicitly and never claim a file was written that was not. When repository writes were unavailable and the output was returned in chat only, say so and name where it should be persisted.

This skill normally writes:

- `.ai/architecture.yaml` — the architecture manifest;
- `.ai/architecture-baseline.yaml` — recorded baseline exceptions for an existing project;
- any Architecture Change Request document you created, at its repository path.
