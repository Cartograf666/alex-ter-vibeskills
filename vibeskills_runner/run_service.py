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
)
from .state_machine import check_transition, get_allowed_next_states

# Trusted location of schemas and scripts
TRUSTED_ROOT = Path(__file__).resolve().parents[1]
TRUSTED_SCHEMAS_DIR = TRUSTED_ROOT / "schemas"
TRUSTED_SCRIPTS_DIR = TRUSTED_ROOT / "scripts"


def validate_contract_helper(
    contract_path: Path, repository: Path
) -> Dict[str, Any]:
    """Validate a contract using the trusted scripts and schemas."""
    if not contract_path.is_file():
        raise ValidationError(f"Contract file not found: {contract_path}")

    try:
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Contract is not valid YAML: {exc}") from exc

    if not isinstance(contract, dict):
        raise ValidationError("Contract must be a YAML mapping")

    # Add trusted scripts to sys.path
    scripts_path = str(TRUSTED_SCRIPTS_DIR)
    sys_path_added = False
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
        sys_path_added = True

    try:
        from validate_contract import validate_semantics
        from jsonschema import Draft202012Validator, FormatChecker

        schema_path = TRUSTED_SCHEMAS_DIR / "development-contract.schema.json"
        if not schema_path.is_file():
            raise ValidationError(f"Contract schema not found: {schema_path}")

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValidationError(f"Failed to load contract schema: {exc}") from exc

        errors = []
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for item in sorted(validator.iter_errors(contract), key=lambda err: list(err.path)):
            location = ".".join(str(part) for part in item.path) or "<root>"
            errors.append(f"{location}: {item.message}")

        if not errors:
            errors.extend(validate_semantics(contract, repository))

        if errors:
            raise ValidationError(
                "Contract validation failed:\n" + "\n".join(f"- {e}" for e in errors)
            )

    finally:
        if sys_path_added:
            sys.path.pop(0)

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
        # Import contract_payload_sha256 from trusted scripts
        scripts_path = str(TRUSTED_SCRIPTS_DIR)
        sys_path_added = False
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
            sys_path_added = True

        try:
            from contract_lib import contract_payload_sha256
            for path in specs_dir.rglob("*.yaml"):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("contract_id") == contract_id:
                        if contract_payload_sha256(data) == payload_hash:
                            return path
                except Exception:
                    continue
        finally:
            if sys_path_added:
                sys.path.pop(0)

    raise ValidationError(
        f"Could not find contract with ID '{contract_id}' and matching payload hash under {specs_dir}"
    )


def init_run(
    repository_path: Path,
    contract_rel_path: str,
    run_id: str,
    manager_provider: str,
    manager_model: str,
    manager_model_version: str,
    manager_context_id: str,
) -> None:
    """Initialize a run record, create the event log, and store metadata using staging/atomic promotion."""
    if not is_git_repo(repository_path):
        raise ValidationError(f"Path is not a Git repository: {repository_path}")

    repo_root = get_repo_root(repository_path)

    # Resolve paths safely to prevent escaping the repository root
    contract_path = resolve_safe_path(repo_root, contract_rel_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")

    # Check if a completed/final run already exists
    if run_record_path.exists() or run_dir.exists():
        raise ValidationError(f"Run ID '{run_id}' already exists and cannot be re-initialized.")

    # 1. Staging paths
    stage_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml.stage")
    stage_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}.stage")

    # Interrupted initialization recovery: clean up any leftover staging files
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

    # 2. Staging write block with rollback
    try:
        # Validate contract
        contract = validate_contract_helper(contract_path, repo_root)

        # Obtain HEAD and tree hashes
        head_commit = get_git_head(repo_root)
        tree_hash = get_committed_tree_sha256(repo_root, head_commit)

        # Calculate contract payload hash using trusted scripts
        scripts_path = str(TRUSTED_SCRIPTS_DIR)
        sys_path_added = False
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
            sys_path_added = True
        try:
            from contract_lib import contract_payload_sha256
            contract_payload_hash = contract_payload_sha256(contract)
        finally:
            if sys_path_added:
                sys.path.pop(0)

        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        reason = f"Run initialized from contract {contract_path.name} by manager context {manager_context_id}."

        # Create run record dict
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

        # Write run record atomically to stage
        run_record_schema = TRUSTED_SCHEMAS_DIR / "run-record.schema.json"
        save_yaml_atomic(stage_record_path, record, run_record_schema)

        # Create staging run directory
        stage_dir.mkdir(parents=True, exist_ok=True)
        stage_events_path = stage_dir / "events.jsonl"
        stage_metadata_path = stage_dir / "metadata.yaml"

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

        # Save metadata atomically
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
        # Rollback staging artifacts upon error
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
    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")

    record = load_yaml_safe(run_record_path)
    run_record_schema = TRUSTED_SCHEMAS_DIR / "run-record.schema.json"
    validate_against_schema(record, run_record_schema)

    # Load and validate event journal
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")
    events_path = run_dir / "events.jsonl"
    events = load_events(events_path)

    if as_json:
        return json.dumps(record, indent=2, ensure_ascii=False)

    # Show the actual last event in the journal, whether it is a transition or not
    last_journal_event = events[-1] if events else None
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
    """Verify run/journal consistency, contract hashes, Git revisions, and state progress."""
    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")
    events_path = run_dir / "events.jsonl"
    metadata_path = run_dir / "metadata.yaml"

    # -- STAGE 1: Verify schema run record --
    record = load_yaml_safe(run_record_path)
    run_record_schema = TRUSTED_SCHEMAS_DIR / "run-record.schema.json"
    validate_against_schema(record, run_record_schema)

    # Load event journal & metadata
    events = load_events(events_path)
    if not metadata_path.is_file():
        raise ValidationError(f"Metadata file not found: {metadata_path}")
    try:
        yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Metadata is corrupted: {exc}")

    # -- STAGE 2: Verify exact development contract and payload hash --
    contract_id = record.get("contract_id", "")
    contract_payload_hash = record.get("contract_payload_sha256", "")
    contract_path = find_contract_by_id(repo_root, contract_id, contract_payload_hash)
    # Perform strict contract schema & semantics checks
    validate_contract_helper(contract_path, repo_root)

    # -- STAGE 3: Validate transitions, ledger contiguity, monotonicity, matching state --
    transitions = record.get("state_transitions", [])
    if not transitions:
        raise ValidationError("State transitions list is empty.")

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

    # -- STAGE 4: Match transitions and events directly --
    journal_transitions = [e for e in events if e.get("type") == "state_transition"]
    if len(transitions) != len(journal_transitions):
        raise ValidationError(
            f"State transition count mismatch: record lists {len(transitions)} transitions, "
            f"but event journal contains {len(journal_transitions)} transition events."
        )

    for i, (rec_t, j_t) in enumerate(zip(transitions, journal_transitions)):
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

    # -- STAGE 5: Verify Git revisions, HEAD sync, tree hashes --
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
    # Now all checks have passed, we can print confirmation and state info
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
    """Run the existing run record validator with the target contract using trusted validator scripts."""
    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    contract_path = resolve_safe_path(repo_root, contract_rel_path)

    validator_script = TRUSTED_SCRIPTS_DIR / "validate_run_record.py"
    if not validator_script.is_file():
        raise ValidationError(f"Repository validation script not found: {validator_script}")

    cmd = [
        sys.executable,
        str(validator_script),
        str(run_record_path),
        "--contract",
        str(contract_path),
        "--repository",
        str(repo_root),
        "--schema",
        str(TRUSTED_SCHEMAS_DIR / "run-record.schema.json"),
        "--contract-schema",
        str(TRUSTED_SCHEMAS_DIR / "development-contract.schema.json"),
    ]

    res = subprocess.run(cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip()
        raise ValidationError(f"Run verification failed:\n{err_msg}")

    print(res.stdout.strip())
