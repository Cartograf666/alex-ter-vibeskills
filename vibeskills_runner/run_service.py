import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .errors import GitStateError, ValidationError, PersistenceError
from .git_state import (
    get_committed_tree_sha256,
    get_git_head,
    get_repo_root,
    is_git_repo,
    git_object_exists,
    git_is_ancestor,
)
from .models import create_event, create_initial_run_record
from .persistence import (
    append_event,
    load_events,
    load_yaml_safe,
    resolve_safe_path,
    save_yaml_atomic,
    validate_against_schema,
    validate_run_id,
    verify_runs_path_confinement,
)
from .state_machine import check_transition, get_allowed_next_states
from .validator_bridge import (
    run_validate_semantics,
    run_contract_payload_sha256,
    run_validator_subprocess,
)

# Trusted location of schemas and scripts
TRUSTED_ROOT = Path(__file__).resolve().parents[1]
TRUSTED_SCHEMAS_DIR = TRUSTED_ROOT / "schemas"
TRUSTED_SCRIPTS_DIR = TRUSTED_ROOT / "scripts"


def validate_contract_helper(
    contract_path: Path, repository: Path
) -> Dict[str, Any]:
    """Validate a contract using the trusted isolated validator bridge."""
    if not contract_path.is_file():
        raise ValidationError(f"Contract file not found: {contract_path}")

    try:
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Contract is not valid YAML: {exc}") from exc

    if not isinstance(contract, dict):
        raise ValidationError("Contract must be a YAML mapping")

    # Validate against JSON schema first
    schema_path = TRUSTED_SCHEMAS_DIR / "development-contract.schema.json"
    if not schema_path.is_file():
        raise ValidationError(f"Contract schema not found: {schema_path}")

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"Failed to load contract schema: {exc}") from exc

    errors = []
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for item in sorted(validator.iter_errors(contract), key=lambda err: list(err.path)):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")

    if not errors:
        # Run semantics checks using validator bridge
        errors.extend(run_validate_semantics(contract, repository, TRUSTED_SCRIPTS_DIR))

    if errors:
        raise ValidationError(
            "Contract validation failed:\n" + "\n".join(f"- {e}" for e in errors)
        )

    # Extra contract sanity checks
    if contract.get("status") != "approved":
        raise ValidationError(f"Contract status must be 'approved', got '{contract.get('status')}'")
    if contract.get("implementation_authorized") is not True:
        raise ValidationError("Contract implementation_authorized must be true")

    return contract


def find_contract_by_id(repository: Path, contract_id: str, payload_hash: str) -> Path:
    """Find the development-contract file matching the contract_id and payload hash."""
    specs_dir = repository / ".ai/specs"
    if specs_dir.is_dir():
        for path in specs_dir.rglob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("contract_id") == contract_id:
                    # Run payload hash check using validator bridge
                    if run_contract_payload_sha256(data, TRUSTED_SCRIPTS_DIR) == payload_hash:
                        return path
            except Exception:
                continue

    raise ValidationError(
        f"Could not find contract with ID '{contract_id}' and matching payload hash under {specs_dir}"
    )


def is_managed_stage_record(path: Path, run_id: str) -> bool:
    """Check if the staging run record file belongs to the given run_id."""
    try:
        if not path.is_file():
            return False
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("run_id") == run_id
    except Exception:
        return False


def is_managed_stage_dir(path: Path, run_id: str) -> bool:
    """Check if the staging run directory contains a valid marker for the given run_id."""
    try:
        if not path.is_dir():
            return False
        marker_file = path / ".stage_marker"
        if marker_file.is_file():
            data = yaml.safe_load(marker_file.read_text(encoding="utf-8"))
            return isinstance(data, dict) and data.get("run_id") == run_id
        meta_file = path / "metadata.yaml"
        if meta_file.is_file():
            data = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
            return isinstance(data, dict) and data.get("run_id") == run_id
        return False
    except Exception:
        return False


def clean_managed_stage_files(repo_root: Path, run_id: str) -> None:
    """Clean up staging files if and only if they are proven to be managed by this run_id."""
    stage_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml.stage")
    stage_dir_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.stage")

    if stage_record_path.exists():
        if is_managed_stage_record(stage_record_path, run_id):
            try:
                stage_record_path.unlink()
            except OSError as e:
                raise PersistenceError(f"Failed to delete managed staging record {stage_record_path}: {e}") from e
        else:
            raise ValidationError(f"Staging record {stage_record_path} exists but is not managed by run_id '{run_id}'")

    if stage_dir_path.exists():
        if is_managed_stage_dir(stage_dir_path, run_id):
            try:
                shutil.rmtree(stage_dir_path)
            except OSError as e:
                raise PersistenceError(f"Failed to delete managed staging directory {stage_dir_path}: {e}") from e
        else:
            raise ValidationError(f"Staging directory {stage_dir_path} exists but is not managed by run_id '{run_id}'")


def check_and_recover_promotion(repo_root: Path, run_id: str, allow_rollback: bool = False) -> None:
    """Recovery protocol to fix/rollback runs interrupted between directory and file promotion renames."""
    final_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    final_dir_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}")
    stage_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml.stage")
    stage_dir_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.stage")

    # State 1: Fully completed run exists.
    if final_record_path.exists() and final_dir_path.exists():
        # Clean up any leftover staging files if they exist
        clean_managed_stage_files(repo_root, run_id)
        return

    # State 2: Interrupted between step 1 (rename dir) and step 2 (rename record).
    # final_dir_path exists, stage_record_path exists, final_record_path does not.
    if final_dir_path.exists() and stage_record_path.exists() and not final_record_path.exists():
        if is_managed_stage_record(stage_record_path, run_id) and is_managed_stage_dir(final_dir_path, run_id):
            if allow_rollback:
                # Rollback step 1
                try:
                    shutil.rmtree(final_dir_path)
                    stage_record_path.unlink()
                    print(f"Rolled back interrupted promotion for '{run_id}' during init.")
                except OSError as e:
                    raise PersistenceError(f"Failed to rollback interrupted promotion: {e}") from e
            else:
                # Complete the promotion!
                try:
                    stage_record_path.rename(final_record_path)
                    print(f"Recovered run '{run_id}' by completing interrupted record promotion.")
                except OSError as e:
                    raise PersistenceError(f"Failed to complete record promotion during recovery: {e}") from e
            return
        else:
            raise ValidationError(f"Interrupted files exist but are not managed by run_id '{run_id}'")

    # State 3: Interrupted where record was renamed but directory was not.
    # final_record_path exists, stage_dir_path exists, final_dir_path does not.
    if final_record_path.exists() and stage_dir_path.exists() and not final_dir_path.exists():
        if is_managed_stage_record(final_record_path, run_id) and is_managed_stage_dir(stage_dir_path, run_id):
            if allow_rollback:
                try:
                    final_record_path.unlink()
                    shutil.rmtree(stage_dir_path)
                    print(f"Rolled back interrupted promotion for '{run_id}' during init.")
                except OSError as e:
                    raise PersistenceError(f"Failed to rollback interrupted promotion: {e}") from e
            else:
                # Complete the promotion!
                try:
                    stage_dir_path.rename(final_dir_path)
                    print(f"Recovered run '{run_id}' by completing interrupted directory promotion.")
                except OSError as e:
                    raise PersistenceError(f"Failed to complete directory promotion during recovery: {e}") from e
            return
        else:
            raise ValidationError(f"Interrupted files exist but are not managed by run_id '{run_id}'")

    # State 4: Only staging files exist (interrupted before promotion).
    # Delete them.
    clean_managed_stage_files(repo_root, run_id)


def check_dirty_worktree(repository: Path) -> None:
    """Validate that repository has no uncommitted changes, ignoring only .ai/runs/** files."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        lines = res.stdout.strip().split("\n")
        dirty_files = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            path_str = parts[1].strip('"')
            # Normalize path delimiters and ignore files inside .ai/runs/
            normalized = path_str.replace("\\", "/")
            if normalized.startswith(".ai/runs/"):
                continue
            dirty_files.append(path_str)

        if dirty_files:
            raise ValidationError(f"Repository has uncommitted changes (dirty worktree): {', '.join(dirty_files)}")
    except subprocess.SubprocessError as e:
        raise ValidationError(f"Failed to check git worktree status: {e}")


def init_run(
    repository_path: Path,
    contract_rel_path: str,
    run_id: str,
    manager_provider: str,
    manager_model: str,
    manager_model_version: str,
    manager_context_id: str,
) -> None:
    """Initialize a run record and event log using recoverable staging renames and strict validation."""
    validate_run_id(run_id)

    if not is_git_repo(repository_path):
        raise ValidationError(f"Path is not a Git repository: {repository_path}")

    repo_root = get_repo_root(repository_path)

    # Validate paths confinement
    contract_path = resolve_safe_path(repo_root, contract_rel_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")
    verify_runs_path_confinement(run_record_path, repo_root)
    verify_runs_path_confinement(run_dir, repo_root)

    # Staging paths
    stage_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml.stage")
    stage_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}.stage")
    verify_runs_path_confinement(stage_record_path, repo_root)
    verify_runs_path_confinement(stage_dir, repo_root)

    # 1. Recover/Rollback any incomplete staging from previous interrupted run
    check_and_recover_promotion(repo_root, run_id, allow_rollback=True)

    # If completed run files still exist, reject
    if run_record_path.exists() or run_dir.exists():
        raise ValidationError(f"Run ID '{run_id}' already exists and cannot be re-initialized.")

    try:
        # Validate contract
        contract = validate_contract_helper(contract_path, repo_root)

        # Git hashes
        head_commit = get_git_head(repo_root)
        tree_hash = get_committed_tree_sha256(repo_root, head_commit)

        # Get payload hash via bridge
        contract_payload_hash = run_contract_payload_sha256(contract, TRUSTED_SCRIPTS_DIR)

        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        reason = f"Run initialized from contract {contract_path.name} by manager context {manager_context_id}."

        # Create record
        record = create_initial_run_record(
            run_id=run_id,
            contract_id=contract.get("contract_id", ""),
            contract_payload_hash=contract_payload_hash,
            head_commit=head_commit,
            tree_hash=tree_hash,
            manager_provider=manager_provider,
            manager_model=manager_model,
            manager_model_version=manager_model_version,
            manager_context_id=manager_context_id,
            timestamp=timestamp,
            reason=reason,
        )

        # Save record atomically to staging path
        run_record_schema = TRUSTED_SCHEMAS_DIR / "run-record.schema.json"
        save_yaml_atomic(stage_record_path, record, run_record_schema)

        # Create stage directory
        stage_dir.mkdir(parents=True, exist_ok=True)
        stage_events_path = stage_dir / "events.jsonl"
        stage_metadata_path = stage_dir / "metadata.yaml"
        stage_marker_path = stage_dir / ".stage_marker"

        # Create stage marker file containing run_id
        stage_marker_path.write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")

        # Append first event
        initial_event = create_event(
            seq=1,
            event_id=f"EVT-{run_id}-INIT",
            event_type="state_transition",
            actor=manager_context_id,
            data={
                "from": "START",
                "to": "DISCOVER",
                "at": timestamp,
                "reason": reason,
            },
            timestamp=timestamp,
        )
        append_event(stage_events_path, initial_event)

        # Write metadata atomically
        metadata = {
            "created_at": timestamp,
            "run_id": run_id,
            "contract_id": contract.get("contract_id", ""),
            "manager": {
                "provider": manager_provider,
                "model": manager_model,
                "model_version": manager_model_version,
                "context_id": manager_context_id,
            },
        }
        temp_fd, temp_path = tempfile.mkstemp(dir=str(stage_dir), suffix=".tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(metadata, f, sort_keys=False, allow_unicode=True)
            os.replace(temp_path, stage_metadata_path)
        except Exception as exc:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise exc

        # 3. Verify staging files before promoting
        stage_record = load_yaml_safe(stage_record_path)
        validate_against_schema(stage_record, run_record_schema)

        stage_events = load_events(stage_events_path)
        if len(stage_events) != 1 or stage_events[0]["event_id"] != f"EVT-{run_id}-INIT":
            raise PersistenceError("Verification of staging event journal failed.")

        # 4. Promote staging files
        stage_dir.rename(run_dir)
        stage_record_path.rename(run_record_path)

    except Exception as e:
        # Rollback staging files upon failure
        if stage_record_path.exists():
            try:
                stage_record_path.unlink()
            except OSError:
                pass
        if stage_dir.exists():
            try:
                shutil.rmtree(stage_dir)
            except OSError:
                pass
        raise e

    print(f"Run {run_id} initialized successfully.")
    print("WARNING: This is a foundation/kernel and not a finished cross-provider runner.")


def get_status(repository_path: Path, run_id: str, as_json: bool = False) -> Optional[str]:
    """Retrieve and display the status of a run record."""
    validate_run_id(run_id)

    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    verify_runs_path_confinement(run_record_path, repo_root)

    record = load_yaml_safe(run_record_path)
    run_record_schema = TRUSTED_SCHEMAS_DIR / "run-record.schema.json"
    validate_against_schema(record, run_record_schema)

    # Load and validate event journal
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")
    verify_runs_path_confinement(run_dir, repo_root)
    events_path = run_dir / "events.jsonl"
    events = load_events(events_path)

    # Get last event
    last_journal_event = events[-1] if events else None

    if as_json:
        status_dict = copy.deepcopy(record)
        status_dict["last_event"] = last_journal_event
        return json.dumps(status_dict, indent=2, ensure_ascii=False)

    if last_journal_event:
        last_event_str = (
            f"#{last_journal_event.get('seq')} [{last_journal_event.get('type')}] "
            f"ID: {last_journal_event.get('event_id')} by {last_journal_event.get('actor')}: "
            f"{json.dumps(last_journal_event.get('data'), ensure_ascii=False)}"
        )
    else:
        last_event_str = "none"

    budgets = record.get("budgets", {})
    budgets_str = (
        f"usd: {budgets.get('cost_usd', 0.0)}, tool_calls: {budgets.get('tool_calls_used', 0)}, "
        f"minutes: {budgets.get('elapsed_minutes', 0.0)}, limits_exceeded: {budgets.get('limits_exceeded', False)}"
    )

    out = [
        f"Run ID: {record.get('run_id')}",
        f"Contract ID: {record.get('contract_id')}",
        f"State: {record.get('state')}",
        f"Terminal Status: {record.get('terminal_status')}",
        f"Base Revision: {record.get('base_revision')}",
        f"Current Revision: {record.get('current_revision')}",
        f"Last Event: {last_event_str}",
        f"Budgets: {budgets_str}",
        "Notice: This is a foundation/kernel and not a finished cross-provider runner.",
    ]
    return "\n".join(out)


def resume_run(repository_path: Path, run_id: str) -> None:
    """Verify run/journal consistency, metadata, Git revisions, and state machine transition ledger prefix."""
    validate_run_id(run_id)

    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")
    verify_runs_path_confinement(run_record_path, repo_root)
    verify_runs_path_confinement(run_dir, repo_root)

    # 1. Recovery step for interrupted promotions (without rollback, complete renames)
    check_and_recover_promotion(repo_root, run_id, allow_rollback=False)

    events_path = run_dir / "events.jsonl"
    metadata_path = run_dir / "metadata.yaml"

    # -- STAGE 1: Verify schema run record --
    record = load_yaml_safe(run_record_path)
    run_record_schema = TRUSTED_SCHEMAS_DIR / "run-record.schema.json"
    validate_against_schema(record, run_record_schema)

    # Load and validate event journal
    events = load_events(events_path)

    # -- STAGE 2: Validate metadata mapping and values consistency --
    if not metadata_path.is_file():
        raise ValidationError(f"Metadata file not found: {metadata_path}")
    try:
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Metadata is corrupted: {exc}")

    if not isinstance(metadata, dict):
        raise ValidationError("Metadata is not a mapping")

    if metadata.get("run_id") != record.get("run_id"):
        raise ValidationError(
            f"Metadata run_id '{metadata.get('run_id')}' does not match record run_id '{record.get('run_id')}'"
        )
    if metadata.get("contract_id") != record.get("contract_id"):
        raise ValidationError(
            f"Metadata contract_id '{metadata.get('contract_id')}' does not match record contract_id '{record.get('contract_id')}'"
        )

    meta_manager = metadata.get("manager", {})
    if not isinstance(meta_manager, dict):
        raise ValidationError("Metadata manager is not a mapping")

    rec_manager = {}
    for r in record.get("roles", []):
        if r.get("role") == "manager":
            rec_manager = r
            break

    if (
        meta_manager.get("provider") != rec_manager.get("provider")
        or meta_manager.get("model") != rec_manager.get("model")
        or meta_manager.get("model_version") != rec_manager.get("model_version")
        or meta_manager.get("context_id") != rec_manager.get("context_id")
    ):
        raise ValidationError("Metadata manager details do not match record manager details.")

    # -- STAGE 3: Verify exact development contract and payload hash --
    contract_id = record.get("contract_id", "")
    contract_payload_hash = record.get("contract_payload_sha256", "")
    contract_path = find_contract_by_id(repo_root, contract_id, contract_payload_hash)
    validate_contract_helper(contract_path, repo_root)

    # -- STAGE 4: Validate transitions prefix and ledger contiguity --
    transitions = record.get("state_transitions", [])
    if not transitions:
        raise ValidationError("State transitions list is empty.")

    # Rule: First transition must be exactly START -> DISCOVER
    first_t = transitions[0]
    if first_t.get("from") != "START" or first_t.get("to") != "DISCOVER":
        raise ValidationError(
            f"Invalid transition ledger start: first transition must be 'START' -> 'DISCOVER', "
            f"got '{first_t.get('from')}' -> '{first_t.get('to')}'."
        )

    # Validate transition admissibility
    for i, t in enumerate(transitions):
        check_transition(t["from"], t["to"])

    # Ledger contiguity
    for i in range(1, len(transitions)):
        if transitions[i - 1]["to"] != transitions[i]["from"]:
            raise ValidationError(
                f"Ledger contiguity failed: transition {i} from '{transitions[i]['from']}' "
                f"does not match previous target '{transitions[i - 1]['to']}'."
            )

    # Timestamp monotonicity
    for i in range(1, len(transitions)):
        prev_t = dt.datetime.fromisoformat(transitions[i - 1]["at"].replace("Z", "+00:00"))
        curr_t = dt.datetime.fromisoformat(transitions[i]["at"].replace("Z", "+00:00"))
        if curr_t < prev_t:
            raise ValidationError(
                f"Monotonicity check failed: transition {i} timestamp '{transitions[i]['at']}' "
                f"is earlier than previous '{transitions[i - 1]['at']}'."
            )

    # Last transition target matches state
    if transitions[-1]["to"] != record.get("state"):
        raise ValidationError(
            f"State mismatch: last transition target '{transitions[-1]['to']}' "
            f"does not match record state '{record.get('state')}'."
        )

    # -- STAGE 5: Validate journal event identity & actor matching --
    journal_transitions = [e for e in events if e.get("type") == "state_transition"]
    if len(transitions) != len(journal_transitions):
        raise ValidationError(
            f"State transition count mismatch: record lists {len(transitions)} transitions, "
            f"but event journal contains {len(journal_transitions)} transition events."
        )

    # First event matches START -> DISCOVER
    first_j_t = journal_transitions[0].get("data", {})
    if (
        first_j_t.get("from") != "START"
        or first_j_t.get("to") != "DISCOVER"
        or first_j_t.get("at") != first_t.get("at")
        or first_j_t.get("reason") != first_t.get("reason")
    ):
        raise ValidationError("First transition event in journal does not match the first record transition.")

    # Match actor role contexts
    authorized_actors = set()
    manager_ctx = record.get("manager", {}).get("context_id")
    if manager_ctx:
        authorized_actors.add(manager_ctx)
    for role_info in record.get("roles", []):
        ctx_id = role_info.get("context_id")
        if ctx_id:
            authorized_actors.add(ctx_id)

    for i, (rec_t, j_t) in enumerate(zip(transitions, journal_transitions)):
        j_actor = j_t.get("actor")
        if j_actor not in authorized_actors:
            raise ValidationError(
                f"Unauthorized transition event actor at step {i}: '{j_actor}' is not in authorized contexts."
            )

        if j_t.get("timestamp") != rec_t.get("at"):
            raise ValidationError(
                f"Timestamp mismatch at step {i}: event timestamp '{j_t.get('timestamp')}' "
                f"does not match record transition at timestamp '{rec_t.get('at')}'"
            )

        j_data = j_t.get("data", {})
        if (
            rec_t.get("from") != j_data.get("from")
            or rec_t.get("to") != j_data.get("to")
            or rec_t.get("at") != j_data.get("at")
            or rec_t.get("reason") != j_data.get("reason")
        ):
            raise ValidationError(
                f"Journal mismatch at step {i}:\n"
                f"  Record Transition: {rec_t}\n"
                f"  Journal Event data: {j_data}"
            )

    # -- STAGE 6: Verify Git revisions, HEAD sync, tree hashes, and dirty worktree status --
    check_dirty_worktree(repo_root)

    base_rev = record.get("base_revision", "")
    curr_rev = record.get("current_revision", "")

    if not git_object_exists(repo_root, base_rev):
        raise ValidationError(f"base_revision '{base_rev}' does not exist as a commit in the repository.")
    if not git_object_exists(repo_root, curr_rev):
        raise ValidationError(f"current_revision '{curr_rev}' does not exist as a commit in the repository.")

    # Ancestry check
    if not git_is_ancestor(repo_root, base_rev, curr_rev):
        raise ValidationError(f"base_revision '{base_rev}' is not an ancestor of current_revision '{curr_rev}'.")

    # HEAD revision match
    head_commit = get_git_head(repo_root)
    if curr_rev != head_commit:
        raise ValidationError(
            f"current_revision '{curr_rev}' does not match repository HEAD commit '{head_commit}'."
        )

    # Committed tree SHA match
    actual_tree = get_committed_tree_sha256(repo_root, head_commit)
    if record.get("current_tree_sha256") != actual_tree:
        raise ValidationError(
            f"current_tree_sha256 '{record.get('current_tree_sha256')}' does not match "
            f"committed HEAD tree SHA-256 '{actual_tree}'."
        )

    # -- SUCCESS BLOCK --
    last_valid_state = record.get("state", "DISCOVER")
    print(f"Run record and event journal are consistent for run '{run_id}'.")
    print(f"Contract: {contract_path.relative_to(repo_root)}")
    print(f"Current Git HEAD revision: {head_commit}")
    print(f"Run current_revision matches HEAD: True")
    print(f"Last valid state: {last_valid_state}")

    next_states = get_allowed_next_states(last_valid_state)
    if next_states:
        print(f"Can resume from state '{last_valid_state}' to transition to one of: {sorted(list(next_states))}.")
        print(
            f"Action required for state transitions requires a future execution adapter (not implemented in this kernel MVP)."
        )
    else:
        print(f"State '{last_valid_state}' is terminal or has no automated transition path.")

    print("State remains unchanged (idempotent resume).")
    print("Notice: This is a foundation/kernel and not a finished cross-provider runner.")


def verify_run(repository_path: Path, run_id: str, contract_rel_path: str) -> None:
    """Run the existing run record validator with the target contract using trusted validator bridge."""
    validate_run_id(run_id)

    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    contract_path = resolve_safe_path(repo_root, contract_rel_path)
    verify_runs_path_confinement(run_record_path, repo_root)

    res = run_validator_subprocess(
        run_record_path,
        contract_path,
        repo_root,
        TRUSTED_ROOT,
        TRUSTED_SCRIPTS_DIR,
        TRUSTED_SCHEMAS_DIR,
    )
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip()
        raise ValidationError(f"Run verification failed:\n{err_msg}")

    print(res.stdout.strip())
