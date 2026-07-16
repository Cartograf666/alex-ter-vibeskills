# Installation

Verified Development Skills follows the open Agent Skills directory format. Install all five skills so preparation, architecture, design, execution, and verification can hand work to one another without losing their contracts.

## Requirements

You need:

- Git;
- Python 3.9 or newer for the installer and bundled validators;
- at least one supported agent host: Claude Code, Gemini CLI, or an OpenAI Codex environment.

The workflow can describe cross-provider routing, but this repository does not provide provider credentials or a cross-provider transport runtime.

## Clone and verify

Clone the repository and verify that the committed packages match their sources:

```bash
git clone https://github.com/Cartograf666/alex-ter-vibeskills.git
cd alex-ter-vibeskills
python3 scripts/package_skills.py --check
```

You can also verify archive checksums directly:

```bash
cd packages
shasum -a 256 -c SHA256SUMS   # macOS
sha256sum -c SHA256SUMS        # Linux
```

## Install for Claude Code

Install into the current repository:

```bash
python3 scripts/install_skills.py \
  --target claude \
  --scope project \
  --project-root /path/to/your-project
```

This creates `.claude/skills/<skill-name>/`. For personal skills available in every project, use:

```bash
python3 scripts/install_skills.py --target claude --scope user
```

Claude Code discovers project skills from `.claude/skills/` and personal skills from `~/.claude/skills/`. Restart Claude Code only if a newly created top-level skills directory is not detected in the current session.

## Install for OpenAI Codex

OpenAI uses the same Agent Skills format across Codex surfaces. Choose local discovery for Codex CLI, IDE, desktop projects, and repositories, or upload the packaged archive through the Skills UI available in ChatGPT. These are two delivery paths for the same skills.

### Local Codex installation

Install into the current repository:

```bash
python3 scripts/install_skills.py \
  --target codex \
  --scope project \
  --project-root /path/to/your-project
```

This creates `.agents/skills/<skill-name>/`. For personal skills available in every repository, use:

```bash
python3 scripts/install_skills.py --target codex --scope user
```

Codex discovers repository skills from `.agents/skills/` between the working directory and repository root, and personal skills from `~/.agents/skills/`.

### OpenAI Skills UI

The Skills UI uses the reproducible archives under `packages/`:

1. Open your profile menu in ChatGPT.
2. Select **Skills**.
3. Select **Create**, then **Upload from your computer**.
4. Upload each `.skill` file from `packages/`.
5. Review the scan result before enabling the skill.

Skills UI availability depends on your plan and workspace settings. OpenAI scans uploaded skills, but that scan does not replace your own source and security review.

## Install for Gemini CLI

Agent Skills require Gemini CLI 0.26.0 or newer. Install into the current repository:

```bash
python3 scripts/install_skills.py \
  --target gemini \
  --scope project \
  --project-root /path/to/your-project
```

This creates `.gemini/skills/<skill-name>/`. For personal skills available in every project, use:

```bash
python3 scripts/install_skills.py --target gemini --scope user
```

Gemini CLI discovers workspace skills from `.gemini/skills/` and personal skills from `~/.gemini/skills/`.

## Install for every local CLI

Install personal copies for Claude Code, local Codex environments, and Gemini CLI at once:

```bash
python3 scripts/install_skills.py --target all --scope user
```

The installer refuses to replace an existing skill directory. Review changes first, then add `--force` when you intentionally want to update an installation.

Every installed skill receives a `.vibeskills-managed.json` ownership marker. Even with `--force`, the installer refuses to delete a same-named directory without a valid matching marker; review and remove legacy or unrelated directories manually.

Updates stage every skill before replacing anything and roll back the whole operation on failure. If a concurrent process prevents restoration, the installer fails with the retained `.vibeskills-*/<skill>.previous` recovery path instead of deleting the previous installation; restore or remove that directory manually after inspection.

## Install validator dependencies

The interview-only `grill-requirements` skill needs no Python packages. Skills containing validators include a hash-locked `requirements.txt`. Install it from the installed skill directory when the host can execute Python:

```bash
python3 -m pip install --require-hashes \
  -r /path/to/installed-skill/requirements.txt
```

A prompt-only host can still follow the workflow, but it must disclose that executable schema, Git-provenance, and artifact checks did not run.

## Confirm discovery

Start the agent inside your project and ask it to list or invoke a skill:

```text
Use $prepare-development-cycle to prepare a lean contract for this task.
```

Claude Code also exposes skills as `/skill-name`. Codex supports `$skill-name` mentions and its skill picker. Gemini CLI activates a matching skill on demand.

## Update or uninstall

To update, pull the reviewed repository version and reinstall intentionally:

```bash
git pull --ff-only
python3 scripts/package_skills.py --check
python3 scripts/install_skills.py --target codex --scope user --force
```

Version `0.3.0-alpha.1` uses development-contract schema 3. Do not silently upgrade or reuse an earlier approval. Run `prepare-development-cycle` again, bind any persisted Decision Brief, resolve interaction and role-routing fields, review the resulting contract, and approve it as a new version.

To uninstall, delete only the five installed directories from the corresponding discovery directory. The installer never edits agent settings, credentials, or project source files outside the chosen skills directory.

## Troubleshooting

### A skill is not visible

- Confirm that the directory contains `SKILL.md` directly under `<skill-name>/`.
- Start the agent from the expected project root.
- Restart the agent after creating a new top-level skills directory.
- Check for another installed skill with the same `name`.

### Validators cannot import dependencies

Install the hash-locked `requirements.txt` bundled with that installed skill. Do not replace it with unpinned packages.

### An existing installation blocks the installer

This is intentional. Compare the installed directory with the reviewed source. Use `--force` only when replacement is expected.

## Official host documentation

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [OpenAI Codex skills](https://developers.openai.com/codex/skills/)
- [Gemini CLI Agent Skills announcement](https://github.com/google-gemini/gemini-cli/discussions/17790)
- [OpenAI Skills UI in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)
- [Agent Skills specification](https://agentskills.io/specification)
