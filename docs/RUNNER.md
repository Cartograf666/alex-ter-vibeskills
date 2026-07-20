# Vibeskills Runner (Alpha Kernel)

> [!WARNING]
> The `vibeskills-runner` is currently in **alpha** and implements only the core foundation/kernel. It does not execute language models (such as Claude, Gemini, or Codex), run production code writers, perform sandbox containment, or execute automated quality gates.

The kernel is responsible for:
1. Validating development contracts via the project's existing validators.
2. Initializing safe, schema-compliant run records.
3. Keeping a monotonic event transition log.
4. Ensuring atomic file storage of the state and journal to prevent corruptions.
5. Verifying that all state transitions follow the governance state machine.

Subsequent implementation phases will introduce provider execution adapters, automated writer processes, and gate integration.

## Locations

- **Run Record File**: `.ai/runs/<run-id>.yaml` (Must conform to `run-record.schema.json`)
- **Event Journal**: `.ai/runs/<run-id>/events.jsonl` (Append-only JSON lines log)
- **Runtime Metadata**: `.ai/runs/<run-id>/metadata.yaml`

## Command Usage Examples

### 1. Initialize a Run

To prepare a new run from an approved development contract:

```bash
python3 -m vibeskills_runner init \
  --contract .ai/specs/my-slug/development-contract.yaml \
  --run-id RUN-MY-FEATURE-001 \
  --manager-provider anthropic \
  --manager-model opus \
  --manager-model-version explicit-model-id-required-at-runtime \
  --manager-context-id manager-context-001
```

### 2. View Run Status

To inspect state, revisions, budgets, and the last transitions of a run record:

```bash
python3 -m vibeskills_runner status \
  --run-id RUN-MY-FEATURE-001
```

To output machine-readable JSON format, append the `--json` flag:

```bash
python3 -m vibeskills_runner status \
  --run-id RUN-MY-FEATURE-001 --json
```

### 3. Resume a Run

To verify consistency of the event journal and contract hashes before continuing:

```bash
python3 -m vibeskills_runner resume \
  --run-id RUN-MY-FEATURE-001
```

### 4. Verify a Run Record

To run the repository's strict validators to verify a record matches the contract details:

```bash
python3 -m vibeskills_runner verify \
  --run-id RUN-MY-FEATURE-001 \
  --contract .ai/specs/my-slug/development-contract.yaml
```

*(Note: Every command accepts an optional `--repository` flag to override the default repository path which defaults to the current working directory.)*
