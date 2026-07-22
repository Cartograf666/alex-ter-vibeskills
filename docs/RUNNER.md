# Vibeskills Runner (Alpha Kernel)

> [!WARNING]
> The `vibeskills-runner` is currently in **alpha** and implements only the core foundation/kernel. It does not execute language models (such as Claude, Gemini, or Codex), run production code writers, perform sandbox containment, or execute automated quality gates (Phase 5 functions).

The kernel is responsible for:
1. Validating development contracts via trusted isolated subprocesses.
2. Initializing safe, schema-compliant run records using atomic multi-stage promotion.
3. Keeping a monotonic event transition log.
4. Ensuring atomic file storage of the state and journal to prevent corruptions.
5. Verifying that all state transitions follow the governance state machine.
6. Reconciling transaction markers, filesystem topology, and file SHA-256 hashes during recovery.

---

## Storage Locations

- **Run Record File**: `.ai/runs/<run-id>.yaml` (Must conform to `run-record.schema.json`)
- **Event Journal**: `.ai/runs/<run-id>/events.jsonl` (Append-only JSON lines log)
- **Runtime Metadata**: `.ai/runs/<run-id>/metadata.yaml`
- **Transaction Marker**: `.ai/runs/<run-id>.transaction.yaml`
- **Run Lock File**: `.ai/runs/<run-id>.lock`

---

## Subprocess-Only Trust Boundary & Security Architecture

### Subprocess Trust Boundary

The runner defines a strict trust boundary at the target repository perimeter. The target repository (`--repository`) is treated as untrusted data.
- **No Direct Import**: The runner never imports Python scripts or modules from the target repository.
- **Trusted Subprocesses**: Validator scripts, schemas, and helper workers are executed exclusively as isolated Python subprocesses (`sys.executable`) from the trusted toolkit directory (`TRUSTED_ROOT`).
- **Bounded Subprocess Execution**: Subprocesses are executed with `shell=False`, `cwd=TRUSTED_ROOT`, a strict 10-second timeout, 1 MiB per-stream output limits (stdout and stderr), non-blocking pipe draining, and child process killing on timeout or overflow.

### Environment Allowlisting

Subprocesses do not inherit the host environment. Each tool receives a minimal allowlisted environment:
- **Hash Worker**: Receives no HMAC secrets (`VIBESKILLS_*` keys stripped).
- **Contract Validator**: Receives only `VIBESKILLS_APPROVAL_HMAC_KEY` and `VIBESKILLS_APPROVAL_HMAC_KEYS`.
- **Run-Record Validator**: Receives only `VIBESKILLS_APPROVAL_HMAC_KEY(S)` and `VIBESKILLS_RUN_HMAC_KEY(S)`.
- **Python Flags**: All subprocesses enforce `PYTHONNOUSERSITE=1`, `PYTHONSAFEPATH=1`, and `PYTHONDONTWRITEBYTECODE=1`. Cloud credentials, provider API keys, and arbitrary environment variables are never passed.
- **Runtime Dependencies**: The isolated dependency root is selected only from the active Python runtime's `site` locations after verifying the required packages are present; it never uses `sys.modules`, `find_spec`, or the target repository's `sys.path`.

---

## Transaction Phase State Machine & Staging Ownership

### Transaction Phases

Promotion transactions proceed through explicit, monotonic phases:
1. `STAGED`: Staging files (`.yaml.stage` and `.stage/`) created and validated.
2. `DIRECTORY_PROMOTED`: Staging directory renamed to final directory (`.ai/runs/<run_id>/`).
3. `RECORD_PROMOTED`: Staging record renamed to final record (`.ai/runs/<run_id>.yaml`).
4. `COMPLETE`: Final record, journal, and metadata SHA-256 values still match the marker and full published-run validation succeeded; marker updated to `COMPLETE`.
5. `Controlled Cleanup`: `.stage_marker` unlinked from final directory, transaction marker unlinked last.

### Marker & Topology Reconciliation Matrix

During `resume` or recovery, the runner reconciles `marker.phase`, file topology, SHA-256 hashes, and `.stage_marker`:

| Marker Phase | Filesystem Topology | Allowed Recovery Action |
| :--- | :--- | :--- |
| `STAGED` | Stage record + Stage directory | Rollback (if `ROLLBACK_ONLY_IF_UNPUBLISHED`) or complete directory promotion |
| `STAGED` | Stage record + Final directory | Directory rename succeeded, phase write failed -> continue record promotion |
| `DIRECTORY_PROMOTED` | Stage record + Final directory | Perform record promotion -> validate -> COMPLETE |
| `DIRECTORY_PROMOTED` | Final record + Final directory | Record rename succeeded, phase write failed -> validate -> COMPLETE |
| `RECORD_PROMOTED` | Final record + Final directory | Perform full published run validation -> COMPLETE |
| `COMPLETE` | Final record + Final directory | Execute controlled cleanup (`.stage_marker` -> marker) |

> [!IMPORTANT]
> **Rollback Rule**: Rollback is strictly allowed **only** when the topology is fully unpublished (`STAGED` phase with stage files and no final directory or record). Once directory promotion begins, rollback is forbidden and recovery can only proceed forward or stop.

### Staging Ownership

Staging files are owned strictly by validated transaction markers. If staging files (`.yaml.stage` or `.stage/`) exist without a valid matching transaction marker, the runner **fails closed** (`ValidationError`). The sole exception is the still-running initializer immediately after its first marker write fails: it may remove only the exact, hash-verified staging artifacts it created while holding the run lock. Automatic markerless cleanup on later commands remains disabled.

---

## Filesystem & Symlink Boundary Enforcement

Before any file reads, writes, lock acquisitions, or directory renames:
- The runner verifies that `.ai` and `.ai/runs` are real directories and **not symbolic links** (`os.lstat()`).
- All target paths, staging paths, lock paths, and transaction markers are checked with `is_symlink()` / `lstat()`. Symbolic links are immediately rejected with `ValidationError`.
- Lexical and resolved path confinement checks ensure all paths remain strictly inside `.ai/runs/`.

---

## Lock Protocol & Stale Lock Recovery

To prevent race conditions and concurrent operations on the same run:
- **Lock File**: `.ai/runs/<run_id>.lock`
- **Acquisition**: Created atomically using `os.open` with `os.O_CREAT | os.O_EXCL | os.O_WRONLY`.
- **Lock Payload**: Contains YAML with `run_id`, process `pid`, UTC RFC3339 `created_at`, and a random 128-bit `nonce`.
- **Ownership Verification**: Before releasing a lock, the runner verifies that the lock file contains the matching process `nonce`.
- **No Guaranteed Auto-Release**: If a runner process is forcibly killed or crashes unexpectedly, the lock file will remain on disk. The runner does not perform age-based or PID-based auto-deletion of locks.

### Stale Lock Manual Recovery Procedure

If a command fails due to an existing stale lock file:
1. Verify that no other runner process is currently executing for the `run_id`.
2. Inspect the transaction marker (`.ai/runs/<run_id>.transaction.yaml`) and `.ai/runs/` directory topology.
3. Save a diagnostic backup of the lock file and transaction marker.
4. Manually remove the stale lock file:
   ```bash
   rm .ai/runs/<run_id>.lock
   ```
5. Execute `resume` to complete recovery:
   ```bash
   python3 -m vibeskills_runner resume --run-id <run_id>
   ```

---

## Command Usage Examples

### 1. Initialize a Run

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

```bash
python3 -m vibeskills_runner status \
  --run-id RUN-MY-FEATURE-001
```

### 3. Resume a Run

```bash
python3 -m vibeskills_runner resume \
  --run-id RUN-MY-FEATURE-001
```

### 4. Verify a Run Record

```bash
python3 -m vibeskills_runner verify \
  --run-id RUN-MY-FEATURE-001 \
  --contract .ai/specs/my-slug/development-contract.yaml
```
