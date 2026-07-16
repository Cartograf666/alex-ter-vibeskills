# Verified Development Skills

Portable Agent Skills for moving software work from an ambiguous idea to an architecture-safe, tested implementation.

The repository follows the open `SKILL.md` layout used by Claude Code, Gemini CLI, Codex, and ChatGPT Skills.

## Skills

| Skill | Responsibility | Main output |
|---|---|---|
| `grill-requirements` | Resolve material decisions one at a time | Decision Brief |
| `prepare-development-cycle` | Research and prepare approved work | PRD, Technical Brief, RunSpec, Change Envelope |
| `architecture-governance` | Bootstrap and enforce project structure | Architecture manifest, baseline, architecture verdicts |
| `run-verified-development-loop` | Implement through bounded multi-model cycles | Verified code and auditable run record |

The normal user-facing workflow uses two commands:

```text
/prepare-development-cycle <idea or task>
/run-verified-development-loop <approved specification path>
```

`prepare-development-cycle` uses the grilling protocol and architecture governance as needed. `run-verified-development-loop` enforces the approved Change Envelope and includes architecture checks in verification.

## Workflow

```text
idea or request
  -> decision interview when needed
  -> PRD
  -> Technical Brief
  -> RunSpec + Change Envelope
  -> user approval
  -> work packages and isolated writers
  -> architecture checks
  -> format/lint/types/tests/build/security
  -> independent review
  -> combined verification
```

Models propose changes. Deterministic commands decide whether executable checks pass. One manager owns the state machine and acceptance decision.

## New project

1. Install all four skills.
2. Run `prepare-development-cycle` with the product idea and initial constraints.
3. Answer one-at-a-time decision questions.
4. Approve the proposed `.ai/architecture.yaml`.
5. Approve the PRD, Technical Brief, and development contract.
6. Run `run-verified-development-loop` with the approved contract.
7. Answer only protected product or Architecture Change Requests.

Example prompt: [examples/new-project.md](examples/new-project.md).

## Existing project

1. Install all four skills.
2. Once, run `architecture-governance` in `BOOTSTRAP_EXISTING` mode.
3. Approve the as-is architecture manifest and baseline existing violations.
4. For each task, run `prepare-development-cycle`.
5. Approve the resulting PRD or lean brief and Change Envelope.
6. Run `run-verified-development-loop`.

Example prompt: [examples/existing-project.md](examples/existing-project.md).

## Install

### Portable project installation

Copy the four directories under `skills/` into:

```text
<repo>/.agents/skills/
```

Gemini CLI and Codex can discover this portable location. Provider-specific locations are also supported.

### Claude Code

```text
<repo>/.claude/skills/<skill-name>/
~/.claude/skills/<skill-name>/
```

### Gemini CLI

```text
<repo>/.gemini/skills/<skill-name>/
~/.gemini/skills/<skill-name>/
```

Gemini can also use `.agents/skills/`.

### Codex

```text
<repo>/.agents/skills/<skill-name>/
~/.codex/skills/<skill-name>/
```

### ChatGPT

Upload the corresponding `.skill` archive from `packages/` through the Skills interface. If Skills are unavailable, use `SKILL.md` as project/custom-GPT instructions and attach the relevant reference files as knowledge.

## Project artifacts

The skills create or consume:

```text
.ai/
├── architecture.yaml
├── architecture-baseline.yaml
├── specs/
│   └── <feature>/
│       ├── PRD.md
│       ├── TECHNICAL-BRIEF.md
│       └── development-contract.yaml
└── runs/
    └── <run-id>.yaml
```

Templates are available under [examples](examples/) and inside each skill's `assets/` directory.

## Automation modes

- `manual`: ask before undeclared cross-layer or protected changes.
- `bounded-auto`: automatically permit allowlisted reversible internal changes; recommended default after bootstrap.
- `full-auto`: allow recorded internal scope expansion while preserving hard human-approval boundaries.

None of these modes automatically authorizes production deployment, destructive migration, credential changes, or other explicitly protected actions.

## Model routing

The workflow is provider-neutral. A common mapping is:

```text
manager: Fable, Opus, or strong ChatGPT reasoning model
writer: Sonnet, Gemini coding model, or Codex coding model
tester/scout: Haiku or fast equivalent
reviewer: fresh context, preferably another model family
```

Keep logical roles separate even if the environment has only one provider.

## License

MIT
