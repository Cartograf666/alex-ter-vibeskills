# Project contract for agents

This repository is a public alpha governance toolkit: portable skills, JSON Schemas,
validators, security boundaries, reproducible `.skill` packages, and the alpha
[vibeskills_runner](vibeskills_runner/) kernel. It is not a hosted agent runtime.
The current [VERSION](VERSION) is `0.3.0-alpha.1`.
See [README](README.md) for the product and [Contributing](CONTRIBUTING.md) for
contribution requirements and the pull-request checklist.

## Canonical sources and generated copies

[schemas/](schemas/), [templates/](templates/), and the shared libraries and
validators in [scripts/](scripts/) are canonical sources.
[sync_shared_assets.py](scripts/sync_shared_assets.py) defines the mappings into
per-skill asset and script directories, such as
[assets/](skills/prepare-development-cycle/assets/) and
[scripts/](skills/prepare-development-cycle/scripts/). These mapped files are generated
copies, not independent sources. The sync also copies the dependency lock into
validator-enabled skills.
Never hand-edit a generated copy. Change its canonical source and regenerate.

After changing canonical sources, run these linked tools in order:
[sync_shared_assets.py](scripts/sync_shared_assets.py),
[package_skills.py](scripts/package_skills.py), then
[validate_repo.py](scripts/validate_repo.py).

```bash
python3 scripts/sync_shared_assets.py
python3 scripts/package_skills.py
python3 scripts/validate_repo.py
```

`python3 scripts/package_skills.py --check` verifies reproducibility without
rewriting committed packages. The `.skill` archives in [packages/](packages/) and
[packages/SHA256SUMS](packages/SHA256SUMS) are build outputs; rebuild and commit
them when a skill changes, along with any generated standalone copies.

## Single validation gate

The repository gate is `python3 scripts/validate_repo.py`.
Install pinned dependencies from [requirements-lock.txt](requirements-lock.txt):

```bash
python3 -m pip install --require-hashes -r requirements-lock.txt
python3 scripts/validate_repo.py
```

The gate runs `python3 -m unittest discover -s tests -v` internally; a separate
unittest invocation is not the repository gate. It also checks generated copies,
package reproducibility, schemas, examples, links, metadata, and whitespace.
The `validate` job in [.github/workflows/validate.yml](.github/workflows/validate.yml)
runs on Python 3.11, 3.12, and 3.13 and additionally runs
`python -m compileall -q scripts tests`.

## Deliberate alpha boundaries

The runner implements contract validation, run-record storage, state transitions,
and crash recovery only. It provides no model execution, code writing, automated
quality gates, OS or container sandbox, hosted orchestrator, credentials, or
deployment authority. These are deliberate boundaries, not opportunistic fixes.
See [Runner](docs/RUNNER.md) and [Security Policy](SECURITY.md).

The target repository is untrusted data. The runner never imports from it and
runs validators only as bounded subprocesses from the trusted toolkit root.
It rejects symlinked paths inside the target repository's run-storage directory
(`.ai/runs/`; see [storage and path confinement](docs/RUNNER.md#storage-locations))
and fails closed when staging files exist without a valid transaction marker.

## Invariants to preserve

Do not weaken hash-locked Python dependencies, GitHub Actions pinned to immutable
SHAs, fail-closed HMAC attestation, frozen acceptance tests, or approval bound to
artifact hashes and source revision hashes. The [Security Policy](SECURITY.md),
[contract validator](scripts/validate_contract.py), and
[run-record validator](scripts/validate_run_record.py) define these boundaries.

Keep [evals/adversarial-cases.yaml](evals/adversarial-cases.yaml) bound to executable
tests through `covers_adversarial` in [tests/eval_coverage.py](tests/eval_coverage.py).
Each case must either name a test carrying its case ID or record a `manual_reason`;
[the coverage test](tests/test_adversarial_evals.py) and
[eval schema](schemas/adversarial-evals.schema.json) enforce that distinction.

## Skill authoring

All six [skills](skills/) ship and install together; see [Installation](docs/INSTALLATION.md).
The `name` and `description` frontmatter in each skill's primary Markdown file
(for example [SKILL.md](skills/guide-development-pipeline/SKILL.md)) are the discovery
contract across hosts. Preserve them as the metadata interface.
Keep supporting material in per-skill reference directories, such as
[references/](skills/guide-development-pipeline/references/), and load it on demand.
Per-skill OpenAI interface metadata lives in
[agents/openai.yaml](skills/guide-development-pipeline/agents/openai.yaml).

The Claude plugin manifest and marketplace versions must equal [VERSION](VERSION);
[tests/test_claude_plugin.py](tests/test_claude_plugin.py) enforces this invariant.
Root [skills/](skills/) also serves as the plugin skills directory.
