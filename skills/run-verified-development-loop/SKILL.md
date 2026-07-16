---
name: run-verified-development-loop
description: Execute an approved PRD and development contract through bounded multi-model implementation cycles with architecture-aware work packages, isolated worktrees, separate coding and testing roles, deterministic architecture and quality gates, repair limits, and independent review. Use when the user asks to implement approved work automatically with an orchestrator such as Fable, Opus, or ChatGPT; workers such as Sonnet or Gemini; testers such as Haiku; or explicit requirements that the result be structurally clean, tested, and working.
---

# Run a Verified Development Loop

Use one manager-controlled state machine. Let models propose changes; let deterministic tools decide whether the code works.

## Load supporting material

Read only the references needed for the current run:

- Read [roles-and-routing.md](references/roles-and-routing.md) before assigning models or agents.
- Read [contracts.md](references/contracts.md) before delegating any work package.
- Read [quality-gates.md](references/quality-gates.md) before implementing or verifying changes.
- Read [architecture-integration.md](references/architecture-integration.md) when a PRD, architecture manifest, baseline, or Change Envelope exists.
- Read [provider-adapters.md](references/provider-adapters.md) when configuring Claude, Gemini, ChatGPT, Codex, or cross-provider execution.
- Read [prompt-library.md](references/prompt-library.md) when constructing prompts for an external worker or reviewer.

## Establish control

1. Designate exactly one manager for the run.
2. Keep user communication, run state, routing, retries, and final acceptance with that manager.
3. Use specialists as bounded tools. Do not let a specialist silently redefine the goal or take permanent control.
4. Treat another orchestrator-class model as an adviser or independent reviewer unless control is explicitly handed off through a recorded state transition.
5. Never allow two writers to modify the same working tree concurrently.

If the environment cannot call the requested provider, report that limitation and use an available model with the same role. Do not claim cross-provider execution occurred when it did not.

## Require an approved development contract

Prefer input produced by `prepare-development-cycle`:

```text
.ai/specs/<slug>/PRD.md
.ai/specs/<slug>/TECHNICAL-BRIEF.md
.ai/specs/<slug>/development-contract.yaml
```

Do not implement when `implementation_authorized` is false. For a trivial, explicit request without documents, create a lean RunSpec and Change Envelope, show material assumptions, and continue only when the user's request itself clearly authorizes implementation. Return to preparation when behavior, public contracts, data, architecture, or protected scope remains ambiguous.

Treat the approved PRD as the authority for desired behavior, the Technical Brief as the approved approach, the RunSpec as the verification contract, and the Change Envelope as the scope contract. Workers may not silently rewrite them.

## Inspect before planning

Inspect the repository and its local instructions. Determine:

- repository status and unrelated user changes;
- relevant architecture and neighboring implementation patterns;
- approved architecture manifest, baseline exceptions, and Change Envelope;
- package manager, build system, and existing test commands;
- formatter, linter, type checker, security checks, and CI configuration;
- files likely to change and files that must remain untouched;
- whether an isolated branch, sandbox, or worktree is available.

Preserve existing changes. Do not commit, push, deploy, modify remote state, or weaken repository protections unless the user explicitly requests it.

## Load or create the run specification

Load the approved `RunSpec` and `ChangeEnvelope`. If a lean contract is permitted, create them containing:

- objective and non-goals;
- observable acceptance criteria;
- constraints and compatibility requirements;
- verification commands grounded in the repository;
- risk level and human-approval boundaries;
- maximum attempts and escalation route.

Also identify the primary architectural layer, allowed change depth, conditional layers, forbidden layers, protected interfaces, and architecture acceptance criteria.

Ask the user only when an unresolved choice would materially change behavior, data, public interfaces, security, cost, or external state. Otherwise record a conservative assumption and proceed.

## Execute the state machine

Use these states and do not skip their exit conditions:

```text
DISCOVER -> SPECIFY -> PLAN -> TEST_DESIGN -> IMPLEMENT
    -> VERIFY -> REVIEW -> ACCEPT
                    |          |
                    +-> REPAIR +
                           |
                           +-> ESCALATE
```

### DISCOVER

Collect repository evidence with a read-only scout. Exit when the manager knows the relevant files, conventions, and real verification commands.

### SPECIFY

Validate the approved criteria, non-goals, and protected scope against repository evidence. Do not broaden or reinterpret them. Exit when every criterion can be verified by a test, command, or focused inspection.

### PLAN

Split work into the smallest coherent functional packages, not one package per layer. Define dependencies, layer ownership, change depth, and allowed paths. Prefer sequential execution when packages overlap; parallelize only independent packages in isolated worktrees.

### TEST_DESIGN

Design acceptance tests before implementation where practical. Let a low-cost tester draft conventional tests and edge cases, but route security-, concurrency-, migration-, and compatibility-sensitive tests to a stronger reviewer. Record the intended tests so an implementer cannot silently weaken them.

### IMPLEMENT

Send one architecture-aware `TaskPacket` to one writer. Require a minimal diff that follows local patterns and stays inside the Change Envelope. Do not send the entire conversation when the task packet and relevant evidence are sufficient.

If the worker needs an undeclared layer or deeper change, stop that branch and use `architecture-governance` to create an Architecture Change Request. Apply the configured approval mode before continuing.

### VERIFY

Run deterministic checks in the repository environment. Execute scope and architecture checks before ordinary quality gates, following [architecture-integration.md](references/architecture-integration.md) and [quality-gates.md](references/quality-gates.md). Capture commands, exit codes, and concise failure output. A model's claim that checks passed is not evidence.

### REPAIR

Return the failing command, relevant error, changed-file list, and original acceptance criterion to the writer. Require the smallest causal fix. Do not allow suppression directives, test deletion, broad rewrites, or configuration weakening as shortcuts.

Use this default retry policy unless the user or repository requires stricter limits:

```yaml
max_implementation_attempts: 3
max_review_rounds: 2
attempt_1: same_writer
attempt_2: same_writer_with_focused_failure_packet
attempt_3: alternative_writer_or_stronger_model
after_limit: escalate_to_manager_or_human
```

Reset the attempt counter only when the manager deliberately changes the plan or root-cause hypothesis.

### REVIEW

Give a fresh-context reviewer the PRD, Technical Brief, RunSpec, Change Envelope, architecture manifest, baseline, final diff, test changes, and machine verification results. Keep the reviewer read-only. Require findings to identify a violated criterion, architecture rule, concrete defect, or material risk. Do not accept style-only churn as a blocker when the code follows repository conventions.

### ACCEPT

Accept only when:

- all acceptance criteria are satisfied;
- the final diff remains inside the approved or formally extended Change Envelope;
- architecture checks pass and no new unapproved baseline violation exists;
- required formatter, lint, type, test, and build checks pass;
- tests and quality configuration were not weakened;
- no unexplained changes exist outside allowed paths;
- independent review has no blocking findings;
- remaining risks and unrun checks are disclosed.

## Escalate safely

Stop automatic repair and request human direction for:

- conflicting or untestable requirements;
- an unapproved architecture expansion or protected-interface change;
- destructive migrations or irreversible external actions;
- credential, permission, production, billing, or legal decisions;
- repeated failure after the configured attempt limit;
- a required check that cannot run in the available environment;
- disagreement between evidence and reviewer judgment that the manager cannot resolve.

Do not mark the task complete merely because the retry budget is exhausted.

## Report the outcome

Lead with the result. Include:

- what changed;
- which checks ran and their outcomes;
- which model or agent performed each material role;
- any deviations from the requested routing;
- remaining risks, assumptions, and unrun checks;
- whether the result is ready for review, merge, or release.

Keep intermediate reasoning internal. Preserve task packets, result packets, command output, and reviewer verdicts as the auditable run record.
