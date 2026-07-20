import datetime as dt
from typing import Any, Dict, List


def create_initial_run_record(
    run_id: str,
    contract_id: str,
    contract_payload_hash: str,
    head_commit: str,
    tree_hash: str,
    manager_provider: str,
    manager_model: str,
    manager_model_version: str,
    manager_context_id: str,
    timestamp: str,
    reason: str
) -> Dict[str, Any]:
    """Create a default run record in accordance with the run record schema version 2."""
    return {
        "schema_version": 2,
        "run_id": run_id,
        "contract_id": contract_id,
        "contract_payload_sha256": contract_payload_hash,
        "state": "DISCOVER",
        "terminal_status": "none",
        "base_revision": head_commit,
        "current_revision": head_commit,
        "current_tree_sha256": tree_hash,
        "budgets": {
            "tool_calls_used": 0,
            "elapsed_minutes": 0.0,
            "cost_usd": 0.0,
            "implementation_attempts": 0,
            "review_rounds": 0,
            "active_writers": 0,
            "max_observed_parallel_writers": 0,
            "limits_exceeded": False
        },
        "roles": [
            {
                "role": "manager",
                "provider": manager_provider,
                "model": manager_model,
                "model_version": manager_model_version,
                "context_id": manager_context_id,
                "permissions": ["read", "delegate", "safe-shell"]
            }
        ],
        "worktrees": [],
        "acceptance_test_manifest": {
            "frozen": False,
            "frozen_at_state": "none",
            "owner_context_id": None,
            "files": []
        },
        "acceptance_results": [],
        "gate_results": [],
        "approvals": [],
        "review": {
            "verdict": "pending",
            "reviewer_context_id": None,
            "independence": "not-independent",
            "reviewed_revision": None,
            "reviewed_tree_sha256": None,
            "findings_path": None,
            "findings_sha256": None,
            "review_event_id": None,
            "review_hmac_sha256": None
        },
        "provider_transfers": [],
        "state_transitions": [
            {
                "from": "START",
                "to": "DISCOVER",
                "at": timestamp,
                "reason": reason
            }
        ],
        "attestation_key_id": None,
        "run_attestation": {
            "event_id": None,
            "actor": None,
            "payload_sha256": None,
            "hmac_sha256": None
        },
        "artifacts": {
            "task_packets": [],
            "failure_packets": [],
            "result_packets": [],
            "logs": []
        }
    }


def create_event(
    seq: int,
    event_id: str,
    event_type: str,
    actor: str,
    data: Dict[str, Any],
    timestamp: str
) -> Dict[str, Any]:
    """Create a structured event log record."""
    return {
        "seq": seq,
        "event_id": event_id,
        "type": event_type,
        "actor": actor,
        "timestamp": timestamp,
        "data": data
    }
