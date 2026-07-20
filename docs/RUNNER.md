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

---

## Trust Boundary & Threat Model

### Trust Boundary

The runner defines a strict trust boundary at the target repository perimeter. The target repository (`--repository`) is treated as untrusted data.
- **No Script Execution**: The runner never imports or executes Python scripts from the target repository.
- **Trusted Toolkit**: The runner exclusively utilizes schemas and validator scripts located within the trusted toolkit installation directory (determined relative to `vibeskills_runner/__file__`).

### Threat Model

The kernel mitigates several attack vectors:

| Threat | Attack Vector | Mitigation |
| :--- | :--- | :--- |
| **Malicious Target Code** | An attacker injects a rogue `scripts/validate_contract.py` or `scripts/validate_run_record.py` into the target repository to hijack the validation process. | The runner imports and calls validators exclusively from the trusted toolkit directory, ignoring the target repository's local scripts. |
| **Path Traversal** | Malicious paths (e.g. `../../etc/passwd` or outside the repo) are supplied via flags or contract inputs to read/write system files. | All target file paths are resolved using `resolve_safe_path` which strictly validates that resolved paths do not escape the repository root. |
| **Interrupted Initialization** | An initialization process is cut short (e.g., due to power loss or write failure), leaving incomplete run record files that block the run ID. | Staging is used: all files are created under `.stage` suffixes and promoted only after full verification. Existing staging files are cleaned up on a retry. |
| **Forged State Transitions** | A malicious agent directly edits `.ai/runs/<run-id>.yaml` to force a jump in the state machine (e.g., `START -> PLAN` or `ACCEPT -> ESCALATE`). | The state machine transition rules are strictly checked. In addition, the record's transitions ledger is compared 1-to-1 (including timestamps, actions, and reasons) with the event journal. |
| **Mismatched Revisions** | An agent makes changes without committing, or checks out a different branch, which is then verified against the wrong state. | The `resume` command strictly checks that the recorded `current_revision` matches repository HEAD, that the `base_revision` is a valid ancestor of HEAD, and that the `current_tree_sha256` matches the actual committed tree SHA. |

---

## Storage & Atomicity Properties

- **Atomic Record Saving**: The Run Record YAML is written atomically. The runner writes data to a temporary file in the same directory and then uses `os.replace` to replace the target file. If a write fails midway, the original record remains completely untouched.
- **Append-only Event Journal**: The event journal (`events.jsonl`) is append-only. Appending is not fully atomic on write, but file integrity is secured by strict load-time validation that rejects corrupted JSON entries, duplicate event IDs, or non-monotonic sequence numbers.
- **Atomic Metadata**: The `metadata.yaml` is written atomically using temporary staging files.

---

## Negative/Adversarial Cases Covered

The runner has explicit unit and integration tests proving rejection of:
1. **START -> PLAN** transition (direct state bypass).
2. **Discontinuous transition ledger** (broken transition chain).
3. **State mismatch** (record state different from the last transition target).
4. **Tampered transition reason** (mismatch between run record transition reason and event journal reason).
5. **Nonexistent base_revision** (invalid Git commit reference).
6. **Nonexistent current_revision** (invalid Git commit reference).
7. **current_revision out of sync with HEAD** (uncommitted changes or switched branch).
8. **Mismatched committed tree SHA** (tree contents modified).
9. **Tampered/invalid contract** (approval hash mismatch).
10. **Corrupted metadata or journal** (failed JSONL/YAML parsing).
11. **Interrupted staging recovery** (correct cleanup and successful re-initialization).
12. **Target repository scripts intrusion** (verifying that target repository's custom validation scripts are completely ignored and not executed).
13. **Target repository missing toolkit files** (verifying that the runner works correctly even if the target repository has no `scripts/` or `schemas/` directory).

---

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
