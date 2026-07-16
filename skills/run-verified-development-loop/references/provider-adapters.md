# Provider Adapters

These adapters describe integration contracts. Installing the skill does not automatically connect providers or enforce a sandbox. Use provider-native permissions or a code-controlled runtime and report degraded operation honestly.

## Contents

- Portable layout
- Claude Code
- Gemini CLI
- OpenAI Codex surfaces
- Cross-provider controller

## Portable layout

Keep the directory unchanged:

```text
run-verified-development-loop/
├── SKILL.md
├── agents/openai.yaml
└── references/
```

The `SKILL.md` frontmatter is the shared discovery contract. Provider-specific metadata may be ignored by providers that do not recognize it.

## Claude Code

Install for one project:

```text
<repo>/.claude/skills/run-verified-development-loop/
```

Install for the current user:

```text
~/.claude/skills/run-verified-development-loop/
```

Invoke explicitly with `/run-verified-development-loop` or mention a verified multi-model development loop. Configure custom subagents separately when specific model pinning or tool allowlists are required.

Recommended Claude role map (conceptual, not a copy-paste configuration):

```yaml
manager:
  model: Fable, Opus, or strongest available orchestrator
  permissions: read, search, safe shell, delegate
worker:
  model: sonnet
  permissions: read, search, edit, safe shell in assigned worktree
tester:
  model: haiku
  permissions: read, search, safe shell, edits restricted to test paths
reviewer:
  model: opus
  permissions: read, search, safe shell
```

Create concrete Claude subagents as separate `.claude/agents/*.md` files. Use actual model aliases or full model IDs supported by the installed Claude Code version and actual Claude Code tool names such as `Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write`, and `Agent(...)`. Enforce path restrictions with permissions or hooks; a prose role name such as `test-only-edit` is not a real tool. Do not grant the manager or reviewer write tools merely for convenience.

Do not use permission-bypass modes for autonomous repository work. Use default/auto permissions plus hooks, or a disposable secret-free sandbox.

## Gemini CLI

Install for one project:

```text
<repo>/.gemini/skills/run-verified-development-loop/
```

Install for the current user:

```text
~/.gemini/skills/run-verified-development-loop/
```

Refresh discovery with `/skills reload` when necessary. For automated worker calls, use headless structured output and sandboxing. Conceptually:

```bash
gemini --sandbox --model MODEL \
  --prompt "TASK_PACKET_JSON" \
  --output-format stream-json
```

Parse the terminal exit code and final structured event. Treat model text as a ResultPacket proposal; independently execute repository quality gates.

Enable the strongest available sandbox and policy rules. Headless operation must not imply automatic approval of untrusted commands.

## OpenAI Codex surfaces

Treat local Codex discovery and the Skills UI in ChatGPT as two delivery surfaces for the same OpenAI skill. The workflow, schemas, supporting files, and model roles do not change between them.

### Skills UI delivery

When the OpenAI Skills UI is enabled in ChatGPT, upload the packaged skill from the Skills interface. Keep all reference files in the package. Use the default prompt or say:

```text
Use $run-verified-development-loop to implement this request.
Act as the sole manager and use connected coding agents as bounded workers.
```

If Skills are unavailable, create a project or custom GPT, place the core manager instructions from `SKILL.md` in its instructions, and upload the files under `references/` as knowledge. This fallback provides the workflow but does not itself grant repository, shell, Claude, or Gemini access.

For API orchestration, expose external coding workers as bounded tools. Prefer manager-style agent-as-tool calls over conversation handoffs because the OpenAI manager must retain the state machine and final acceptance decision.

Use durable human-in-the-loop interruptions for protected calls and tracing for tool, handoff, and approval evidence. Keep secrets out of serialized run context.

### Local Codex delivery

Install for one project using the shared agent-skills directory when supported:

```text
<repo>/.agents/skills/run-verified-development-loop/
```

Install for the current Codex user:

```text
~/.agents/skills/run-verified-development-loop/
```

Invoke with `$run-verified-development-loop`. The `agents/openai.yaml` file supplies the user-facing name and default prompt. Let Codex call external providers only through tools or CLIs that are actually installed and authorized.

Apply provider policy before every delegation; do not send sensitive code merely because a provider tool is available.

## Cross-provider controller

Use a small code-controlled runner when automatic Claude + Gemini + OpenAI collaboration is required. The runner, not a model, must own:

- run state and attempt counters;
- worktree creation and ownership;
- provider credentials and timeouts;
- schema validation for packets;
- subprocess exit codes and full logs;
- deterministic gates;
- approval boundaries and cancellation.
- provider/model/context identity and code-transfer audit;
- budget, concurrency, network, and secret policies.

Expose narrow operations to the manager:

```text
inspect_repository(request) -> EvidencePacket
run_claude_worker(TaskPacket) -> ResultPacket
run_gemini_worker(TaskPacket) -> ResultPacket
run_openai_reviewer(ReviewPacket) -> ReviewVerdict
run_quality_gate(command_id, worktree_id) -> GateResult
request_human_approval(action, reason) -> Decision
```

Do not give a model raw provider keys. Keep secrets in the controller environment and return sanitized errors. Validate canonical schemas before and after calls, enforce per-call timeouts and budgets, bound output, and support explicit cancellation. Run every writer in an isolated filesystem or worktree and re-verify the exact combined revision before acceptance.
