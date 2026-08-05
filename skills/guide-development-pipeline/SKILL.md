---
name: guide-development-pipeline
description: Locate the current stage of the development pipeline from existing repository artifacts, then name the exact next step and the skill that performs it. Use when the user asks where the project stands, what to do next, how to start, which skill to run, or wants to be walked through discovery, preparation, architecture, design, approval, implementation, and review without tracking the sequence themselves.
---

# Guide the Development Pipeline

Route the user to the correct next step. Derive the position from artifacts, never from conversation memory. Do not perform, approve, or replace the stage you route to.

## Respond in the user's language

Detect the user's language from their messages and use it for all prose addressed to them: questions, explanations, recommendations, status, and the closing summary. Keep every machine token verbatim — code, commands, file paths, schema field names, stable IDs, and the status or verdict values this skill returns — and convey their meaning in the surrounding prose rather than translating the tokens. If the user's language is unclear, ask once, then continue in the chosen language.

Persisted artifacts are contracts, not chat. Keep their template headings, YAML keys, stable IDs, and status tokens exactly as specified so downstream skills and validators keep working. Narrative content inside an artifact may follow the user's language when the user asks for it.

## Load references

- Read [stage-map.md](references/stage-map.md) before deciding which stage the project is in.

## Stay read-only

This skill observes and routes. It never writes an artifact, never edits a manifest or contract, never sets an approval field, and never writes production code. Approval and implementation authority stay with the skill and the human that own them.

If the user asks this skill to approve a contract, skip a gate, or implement a change, decline and name the skill or command that legitimately performs it. A router that can approve is an authority bypass, not a convenience.

## Establish position from evidence

Inspect the repository before answering. Look for:

- `.ai/architecture.yaml` and `.ai/architecture-baseline.yaml`;
- `.ai/design-system.yaml`;
- `.ai/discovery/<slug>-decision-brief.md`;
- `.ai/specs/<slug>/` documents and `development-contract.yaml`;
- `.ai/runs/<run-id>.yaml`;
- whether the project has a user interface, an existing codebase, or neither.

Run the bundled validators of the owning skills when a shell is available, because a file existing is not the same as a file being valid or approved. In a prompt-only host, say that approval and schema state were read but not executed.

Apply the detection order in [stage-map.md](references/stage-map.md) and stop at the first unsatisfied stage. That stage is the current position.

Distinguish three things and never merge them:

- `SATISFIED`: evidence exists and validates;
- `UNSATISFIED`: evidence is missing, invalid, or unapproved;
- `NOT_APPLICABLE`: the stage does not apply, with a recorded reason.

## Report the position

Present a compact checklist covering the whole pipeline, not only the next item. For each stage show whether it is done, current, upcoming, or not applicable, and bind every done claim to the artifact path that proves it.

Then state exactly one next action:

- the skill to invoke, or the command the user must run;
- why it is next, in terms of the missing evidence;
- what it will produce and where that file will land;
- whether it needs a decision from the user or can proceed on discovered facts.

Give one next action, not a menu. When a stage is genuinely optional, say so and recommend a default.

## Handle ambiguity

Ask exactly one question at a time, and only when the answer changes the route. Common cases:

- several task slugs are in flight: list them with their stages and ask which one to continue;
- the project shape is unclear: ask whether this is an existing codebase or a new project before proposing a bootstrap;
- the task has no user interface: record design as not applicable rather than routing to design work;
- a contract is approved but its source documents changed: route back to preparation, because approval no longer binds.

Do not ask for facts that reading the repository would answer.

## Return a status

Return one of:

- `PIPELINE_NEXT`: position established and exactly one next action identified;
- `PIPELINE_BLOCKED`: the next action needs human authority, approval, or a decision this skill cannot supply;
- `PIPELINE_AMBIGUOUS`: position cannot be resolved until the user answers one routing question;
- `PIPELINE_COMPLETE`: approved work is verified and no pipeline stage remains for this task.

Include the evidence paths that justify the reported position.

## Summarize what you did

After returning the outcome, close with a short summary in the user's language that states:

- what you inspected and which stage the project is in;
- the status you returned and what it means for the user;
- where each existing artifact lives, by exact repository path, and where each created or updated file now lives once the routed skill runs;
- the recommended next step.

Name file locations explicitly and never claim a file was written that was not.

This skill writes no artifacts of its own. It reports the paths that other stages own:

- `.ai/architecture.yaml` and `.ai/architecture-baseline.yaml` from `architecture-governance`;
- `.ai/design-system.yaml` from `design-system-governance`;
- `.ai/discovery/<slug>-decision-brief.md` from `grill-requirements`;
- `.ai/specs/<slug>/` documents and `development-contract.yaml` from `prepare-development-cycle`;
- `.ai/runs/<run-id>.yaml` from `run-verified-development-loop`.
