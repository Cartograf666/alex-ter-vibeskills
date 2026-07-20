import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from .errors import GitStateError, ValidationError, PersistenceError
from .git_state import (
    get_committed_tree_sha256,
    get_git_head,
    get_repo_root,
    is_git_repo,
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


def validate_contract_helper(
    contract_path: Path, repository: Path, schema_path: Path
) -> Dict[str, Any]:
    """Validate a contract using the project's existing validator script."""
    if not contract_path.is_file():
        raise ValidationError(f"Contract file not found: {contract_path}")

    try:
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Contract is not valid YAML: {exc}") from exc

    if not isinstance(contract, dict):
        raise ValidationError("Contract must be a YAML mapping")

    # Add scripts to sys.path to load validate_contract
    scripts_path = str(repository / "scripts")
    sys_path_added = False
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
        sys_path_added = True

    try:
        from validate_contract import validate_semantics
        from jsonschema import Draft202012Validator, FormatChecker

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

    # Extra contract sanity checks requested by task
    if contract.get("status") != "approved":
        raise ValidationError(f"Contract status must be 'approved', got '{contract.get('status')}'")
    if contract.get("implementation_authorized") is not True:
        raise ValidationError("Contract implementation_authorized must be true")

    return contract


def find_contract_by_id(repository: Path, contract_id: str, payload_hash: str) -> Path:
    """Find the development-contract file matching the contract_id and payload hash."""
    specs_dir = repository / ".ai/specs"
    if specs_dir.is_dir():
        # Import contract_payload_sha256 from contract_lib to compute payload hash
        scripts_path = str(repository / "scripts")
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
    """Initialize a run record, create the event log, and store metadata."""
    if not is_git_repo(repository_path):
        raise ValidationError(f"Path is not a Git repository: {repository_path}")

    repo_root = get_repo_root(repository_path)

    # Resolve paths safely to prevent escaping the repository root
    contract_path = resolve_safe_path(repo_root, contract_rel_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    run_dir = resolve_safe_path(repo_root, f".ai/runs/{run_id}")

    # Check if run already exists
    if run_record_path.exists() or run_dir.exists():
        raise ValidationError(f"Run ID '{run_id}' already exists and cannot be re-initialized.")

    # Validate contract
    contract_schema = repo_root / "schemas/development-contract.schema.json"
    contract = validate_contract_helper(contract_path, repo_root, contract_schema)

    # Obtain HEAD and tree hashes
    head_commit = get_git_head(repo_root)
    tree_hash = get_committed_tree_sha256(repo_root, head_commit)

    # Calculate contract payload hash
    scripts_path = str(repo_root / "scripts")
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

    # Atomically save run record YAML
    run_record_schema = repo_root / "schemas/run-record.schema.json"
    save_yaml_atomic(run_record_path, record, run_record_schema)

    # Create journal directory and files
    run_dir.mkdir(parents=True, exist_ok=True)
    events_path = run_dir / "events.jsonl"
    metadata_path = run_dir / "metadata.yaml"

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
    append_event(events_path, initial_event)

    # Save metadata
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
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    print(f"Run {run_id} initialized successfully.")
    print("WARNING: This is a foundation/kernel and not a finished cross-provider runner.")


def get_status(repository_path: Path, run_id: str, as_json: bool = False) -> Optional[str]:
    """Retrieve and display the status of a run record."""
    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")

    record = load_yaml_safe(run_record_path)
    run_record_schema = repo_root / "schemas/run-record.schema.json"
    validate_against_schema(record, run_record_schema)

    if as_json:
        return json.dumps(record, indent=2, ensure_ascii=False)

    # Otherwise print human-readable status
    state_transitions = record.get("state_transitions", [])
    last_event = state_transitions[-1] if state_transitions else None
    last_event_str = (
        f"{last_event['from']} -> {last_event['to']} ({last_event['at']}): {last_event['reason']}"
        if last_event
        else "none"
    )

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

    record = load_yaml_safe(run_record_path)
    run_record_schema = repo_root / "schemas/run-record.schema.json"
    validate_against_schema(record, run_record_schema)

    # 1. Load event journal
    events = load_events(events_path)

    # 2. Check consistency between record and event journal
    journal_transitions = [e for e in events if e.get("type") == "state_transition"]
    if len(record.get("state_transitions", [])) != len(journal_transitions):
        raise ValidationError(
            "Consistency check failed: State transition count mismatch between record and event journal."
        )

    for record_t, journal_t in zip(record.get("state_transitions", []), journal_transitions):
        j_data = journal_t.get("data", {})
        if (
            record_t.get("from") != j_data.get("from")
            or record_t.get("to") != j_data.get("to")
            or record_t.get("at") != j_data.get("at")
        ):
            raise ValidationError(
                f"Consistency check failed: Mismatched transition record. "
                f"Record has {record_t}, journal event has {j_data}"
            )

    # 3. Check contract payload hash
    contract_id = record.get("contract_id", "")
    contract_payload_hash = record.get("contract_payload_sha256", "")
    contract_path = find_contract_by_id(repo_root, contract_id, contract_payload_hash)

    # 4. Check Git base/current revision
    head_commit = get_git_head(repo_root)

    # Validate that current revision exists in the repo
    # Check if run record's current_revision matches HEAD
    is_head_matching = (record.get("current_revision") == head_commit)

    # 5. Determine last valid state
    last_valid_state = record.get("state", "DISCOVER")

    # 6. Report status and resume options
    print(f"Run record and event journal are consistent for run '{run_id}'.")
    print(f"Contract: {contract_path.relative_to(repo_root)}")
    print(f"Current Git HEAD revision: {head_commit}")
    print(f"Run current_revision matches HEAD: {is_head_matching}")
    print(f"Last valid state: {last_valid_state}")

    # Next state planning
    state_to_next = {
        "DISCOVER": "SPECIFY",
        "SPECIFY": "PLAN",
        "PLAN": "TEST_DESIGN",
        "TEST_DESIGN": "IMPLEMENT",
        "IMPLEMENT": "VERIFY",
        "VERIFY": "REVIEW",
        "REVIEW": "ACCEPT",
        "ACCEPT": "COMPLETE",
    }
    next_state = state_to_next.get(last_valid_state)

    if next_state:
        print(f"Can resume from state '{last_valid_state}' to transition to '{next_state}'.")
        print(
            f"Action required for '{next_state}' requires a future execution adapter (not implemented in this kernel MVP)."
        )
    else:
        print(f"State '{last_valid_state}' is terminal or has no automated transition path.")

    # State remains unchanged, no action taken on this MVP level.
    print("State remains unchanged (idempotent resume).")
    print("Notice: This is a foundation/kernel and not a finished cross-provider runner.")


def verify_run(repository_path: Path, run_id: str, contract_rel_path: str) -> None:
    """Run the existing run record validator with the target contract."""
    repo_root = get_repo_root(repository_path)
    run_record_path = resolve_safe_path(repo_root, f".ai/runs/{run_id}.yaml")
    contract_path = resolve_safe_path(repo_root, contract_rel_path)

    validator_script = repo_root / "scripts/validate_run_record.py"
    if not validator_script.is_file():
        raise ValidationError(f"Repository validation script not found: {validator_script}")

    cmd = [
        "python3",
        str(validator_script),
        str(run_record_path),
        "--contract",
        str(contract_path),
        "--repository",
        str(repo_root),
        "--schema",
        str(repo_root / "schemas/run-record.schema.json"),
        "--contract-schema",
        str(repo_root / "schemas/development-contract.schema.json"),
    ]

    res = subprocess.run(cmd, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip()
        raise ValidationError(f"Run verification failed:\n{err_msg}")

    print(res.stdout.strip())
