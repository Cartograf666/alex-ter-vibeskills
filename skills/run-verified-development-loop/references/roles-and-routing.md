# Roles and Routing

## Contents

- Control topology
- Default model map
- Routing rules
- Isolation and concurrency
- Degraded operation

## Control topology

Use the manager pattern: one orchestrator owns state and calls specialists for bounded work. Avoid peer-to-peer free-form collaboration for code changes because it obscures ownership, retry counts, and acceptance decisions.

Keep these logical roles separate even when one available model must fill more than one role:

| Role | Responsibility | Default permissions |
|---|---|---|
| Manager | Specify, route, track state, decide escalation and acceptance | Read, delegate, run checks; avoid production-code writes |
| Scout | Map relevant code and commands | Read-only |
| Test designer | Turn criteria into tests and edge cases | Tests only |
| Writer | Implement one work package | Allowed paths in one isolated worktree |
| Verifier | Execute deterministic checks and collect evidence | Read and command execution; no product edits |
| Reviewer | Inspect final diff against criteria and evidence | Read-only |

The manager may perform mechanical inspection and verification directly. The manager should not implement the feature unless no worker exists or the user explicitly asks for a single-agent run.

## Default model map

Treat model names as defaults, not hard requirements:

| Work type | Preferred model class | Suggested models |
|---|---|---|
| Long-horizon orchestration, architectural judgment | Highest reasoning tier | Fable, Opus, strong OpenAI reasoning model in Codex |
| Normal feature work, fixes, local refactors | Strong coding tier | Sonnet, Gemini coding model, Codex coding model |
| Repository discovery, test execution, mechanical checks | Fast low-cost tier | Haiku, Flash/mini equivalent |
| Independent critique | Different context and preferably different model family | OpenAI/Codex when Claude writes; Opus when Gemini writes; Gemini when OpenAI writes |

Do not route by brand alone. Route by task difficulty, tool access, context size, latency, cost, and prior failures.

Use the approved `provider_policy.role_assignments` first. The table above supplies recommendations only when preparation records `host:best-available` or when the user explicitly delegates the choice. Apply `substitution_policy` before changing providers or models, and meet `reviewer_independence` before returning `ACCEPT`.

At runtime, resolve aliases to exact provider model IDs/versions and record them with context IDs and permissions in the run record. Do not claim reviewer independence from a role label alone.

## Routing rules

Use a fast worker for:

- file discovery and symbol mapping;
- running established commands;
- generating conventional table-driven test cases;
- classifying failures and summarizing logs.

Use a coding worker for:

- scoped feature implementation;
- ordinary bug fixes;
- local refactors with known patterns;
- writing unit and integration tests after acceptance behavior is fixed.

Escalate to the strongest model for:

- ambiguous architecture spanning multiple components;
- concurrency, transactions, security boundaries, or data migration;
- root-cause analysis after two failed attempts;
- conflicting reviewer and verifier evidence;
- changes to public APIs or backward compatibility.

Use an external alternative writer after repeated failure, not simultaneously on the same working tree. Give the alternative writer the original task packet, current diff, and failure evidence; do not give it the prior writer's hidden reasoning.

## Isolation and concurrency

Enforce these invariants:

```text
one worktree -> at most one writer
one work package -> one accountable owner
shared acceptance criteria -> manager-owned and immutable during implementation
merge -> only after package verification
```

Parallelize discovery and independent review freely because they are read-only. Parallelize writers only when file ownership is disjoint and each writer has a separate branch or worktree. Merge and rerun the complete gate set after combining packages.

## Degraded operation

When a named provider is unavailable:

1. Preserve logical role separation with fresh contexts.
2. Select the closest available capability tier.
3. Keep deterministic gates unchanged.
4. State the substitution in the final report.

If no subagent or external provider can be called, run a sequential single-model loop with explicit context boundaries for implementation and self-check plus machine verification. Never imply that independent review occurred. The strongest permitted terminal status is `READY_FOR_HUMAN_REVIEW`; a human or genuinely fresh independent reviewer is required for `ACCEPT`.
