#!/usr/bin/env python3
"""Validate an auditable development run against repository and contract facts."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fnmatch
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from contract_lib import contract_payload_sha256, load_hmac_keyring, load_yaml
from validate_contract import default_schema_path as default_contract_schema_path
from validate_contract import validate_semantics as validate_contract_semantics


ALLOWED_TRANSITIONS = {
    "START": {"DISCOVER"},
    "DISCOVER": {"SPECIFY", "ESCALATE"},
    "SPECIFY": {"PLAN", "ESCALATE"},
    "PLAN": {"TEST_DESIGN", "IMPLEMENT", "ESCALATE"},
    "TEST_DESIGN": {"IMPLEMENT", "ESCALATE"},
    "IMPLEMENT": {"VERIFY", "ESCALATE"},
    "VERIFY": {"REPAIR", "REVIEW", "ESCALATE"},
    "REPAIR": {"IMPLEMENT", "VERIFY", "ESCALATE"},
    "REVIEW": {"REPAIR", "ACCEPT", "ESCALATE"},
    "ACCEPT": {"COMPLETE", "ESCALATE"},
    "ESCALATE": {"COMPLETE"},
}


def default_schema_path(name: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    standalone = root / "assets" / name
    return standalone if standalone.is_file() else root / "schemas" / name


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def run_payload_sha256(record: dict[str, Any]) -> str:
    payload = copy.deepcopy(record)
    payload["run_attestation"] = {
        "event_id": None, "actor": None, "payload_sha256": None, "hmac_sha256": None
    }
    return canonical_sha256(payload)


def git(repository: Path, *args: str, text: bool = False) -> bytes | str:
    return subprocess.check_output(["git", *args], cwd=repository, text=text)


def git_head(repository: Path) -> str:
    return str(git(repository, "rev-parse", "HEAD", text=True)).strip()


def git_object_exists(repository: Path, revision: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=repository,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def git_is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repository,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def git_file_at(repository: Path, revision: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"], cwd=repository,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return result.stdout if result.returncode == 0 else None


def committed_tree_sha256(repository: Path, revision: str) -> str:
    return sha256_bytes(bytes(git(repository, "ls-tree", "-r", "--full-tree", revision)))


def contained_file(repository: Path, raw_path: str) -> Path | None:
    path = (repository / raw_path).resolve()
    try:
        path.relative_to(repository.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def dirty_paths(repository: Path, record_path: Path) -> list[str]:
    output = bytes(git(repository, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"))
    allowed_record = record_path.resolve()
    dirty: list[str] = []
    for entry in output.split(b"\0"):
        if not entry:
            continue
        raw = entry[3:].decode("utf-8", errors="surrogateescape")
        candidate = (repository / raw).resolve()
        relative = candidate.relative_to(repository.resolve()).as_posix()
        if candidate == allowed_record or relative.startswith(".ai/runs/"):
            continue
        dirty.append(relative)
    return dirty


def event_hmac(key_id: str, action: str, payload_hash: str, event_id: str, decided_by: str, key: str) -> str:
    message = "\n".join([key_id, action, payload_hash, event_id, decided_by]).encode("utf-8")
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def resolve_run_key(key_id: str | None) -> str | None:
    if not key_id:
        return None
    keyring = load_hmac_keyring("VIBESKILLS_RUN_HMAC_KEYS")
    key = keyring.get(key_id)
    if not key and key_id == "default":
        key = os.environ.get("VIBESKILLS_RUN_HMAC_KEY")
    return key if key and len(key.encode("utf-8")) >= 32 else None


def verify_host_attestation(
    key_id: str | None,
    action: str, payload_hash: str, event_id: str | None, actor: str,
    supplied_hmac: str | None, errors: list[str],
) -> bool:
    try:
        key = resolve_run_key(key_id)
    except ValueError as exc:
        errors.append(str(exc))
        return False
    if not key:
        errors.append(f"{action} verification requires the selected trusted-host run HMAC key")
        return False
    if not event_id or not supplied_hmac:
        errors.append(f"{action} host attestation is incomplete")
        return False
    expected = event_hmac(key_id or "", action, payload_hash, event_id, actor, key)
    if not hmac.compare_digest(expected, supplied_hmac):
        errors.append(f"{action} host attestation HMAC is invalid")
        return False
    return True


def valid_attested_approval(
    approvals: list[dict[str, Any]], key_id: str | None, action: str, payload_hash: str, errors: list[str],
    must_precede: str | None = None,
) -> bool:
    matches = [
        item for item in approvals
        if item["action"] == action and item["decision"] == "approved"
        and item["payload_sha256"] == payload_hash
    ]
    if len(matches) != 1:
        errors.append(f"{action} requires exactly one payload-bound approval event")
        return False
    item = matches[0]
    if must_precede:
        decision_time = dt.datetime.fromisoformat(item["decided_at"].replace("Z", "+00:00"))
        action_time = dt.datetime.fromisoformat(must_precede.replace("Z", "+00:00"))
        if decision_time > action_time:
            errors.append(f"{action} approval was recorded after execution began")
            return False
    return verify_host_attestation(
        key_id, action, payload_hash, item["authority_event_id"], item["decided_by"],
        item["attestation_hmac_sha256"], errors,
    )


def validate_contract_document(
    contract: dict[str, Any], repository: Path, schema_path: Path
) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = []
    for item in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(contract):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"contract.{location}: {item.message}")
    if not errors:
        errors.extend(f"contract: {item}" for item in validate_contract_semantics(contract, repository))
    return errors


def validate_semantics(
    record: dict[str, Any], repository: Path, record_path: Path,
    contract: dict[str, Any] | None, contract_schema: Path,
) -> list[str]:
    errors: list[str] = []
    terminal = record["terminal_status"]
    key_id = record["attestation_key_id"]
    head = git_head(repository)

    if record["current_revision"] != head:
        errors.append("current_revision does not match repository HEAD")
    if not git_object_exists(repository, record["base_revision"]):
        errors.append("base_revision is not a repository commit")
    elif not git_is_ancestor(repository, record["base_revision"], head):
        errors.append("base_revision is not an ancestor of current HEAD")
    actual_tree = committed_tree_sha256(repository, head)
    if record["current_tree_sha256"] != actual_tree:
        errors.append("current_tree_sha256 does not match committed HEAD tree")

    transitions = record["state_transitions"]
    for index, transition in enumerate(transitions):
        if transition["to"] not in ALLOWED_TRANSITIONS[transition["from"]]:
            errors.append(f"invalid state transition {transition['from']} -> {transition['to']}")
        if index and transitions[index - 1]["to"] != transition["from"]:
            errors.append("state transition ledger is not contiguous")
        if index:
            previous = dt.datetime.fromisoformat(transitions[index - 1]["at"].replace("Z", "+00:00"))
            current = dt.datetime.fromisoformat(transition["at"].replace("Z", "+00:00"))
            if current < previous:
                errors.append("state transition timestamps are not monotonic")
    if transitions and transitions[-1]["to"] != record["state"]:
        errors.append("last state transition does not match current state")

    manifest = record["acceptance_test_manifest"]
    if manifest["frozen"]:
        if manifest["frozen_at_state"] != "TEST_DESIGN" or not manifest["owner_context_id"]:
            errors.append("frozen acceptance tests require TEST_DESIGN state and an owner")
        for item in manifest["files"]:
            path = contained_file(repository, item["path"])
            if path is None or sha256_file(path) != item["sha256"]:
                errors.append(f"frozen acceptance test changed or is missing: {item['path']}")

    context_ids = [item["context_id"] for item in record["roles"]]
    if len(context_ids) != len(set(context_ids)):
        errors.append("role context IDs must be unique")
    reviewer_context = record["review"]["reviewer_context_id"]
    reviewer_roles = [item for item in record["roles"] if item["role"] == "reviewer"]
    manager_roles = [item for item in record["roles"] if item["role"] == "manager"]
    authors = {
        item["context_id"] for item in record["roles"]
        if item["role"] in {"manager", "scout", "tester", "writer"}
    }
    if reviewer_context and reviewer_context in authors:
        errors.append("reviewer context is shared with an authoring role")
    if manifest["owner_context_id"]:
        owners = [item for item in record["roles"] if item["context_id"] == manifest["owner_context_id"]]
        if len(owners) != 1:
            errors.append("acceptance-test owner context does not match exactly one role")
        elif contract and owners[0]["role"] != contract["test_policy"]["acceptance_test_owner"]:
            errors.append("acceptance-test owner role differs from contract test policy")

    for transfer in record["provider_transfers"]:
        if transfer["context_id"] not in context_ids:
            errors.append("provider transfer references an unknown context")
        payload = contained_file(repository, transfer["retained_payload_path"])
        if payload is None or sha256_file(payload) != transfer["payload_sha256"]:
            errors.append("retained provider-transfer payload is missing or changed")

    for category, artifacts in record["artifacts"].items():
        for artifact in artifacts:
            if not artifact["path"].startswith(".ai/runs/"):
                errors.append(f"{category} artifact must be retained under .ai/runs: {artifact['path']}")
                continue
            path = contained_file(repository, artifact["path"])
            if path is None or sha256_file(path) != artifact["sha256"]:
                errors.append(f"{category} artifact is missing or changed: {artifact['path']}")

    if contract is not None:
        if not contract["implementation_authorized"] or contract["approval"]["status"] != "approved":
            errors.append("run record cannot rely on an unauthorized contract")
        if record["contract_id"] != contract["contract_id"]:
            errors.append("run record contract_id does not match contract")
        if record["contract_payload_sha256"] != contract_payload_sha256(contract):
            errors.append("run record contract payload hash does not match contract")

        allowed_providers = set(contract["provider_policy"]["allowed_providers"])
        for role in record["roles"]:
            if role["provider"] not in allowed_providers:
                errors.append(f"role provider is not allowed by contract: {role['provider']}")
        actual_writers = [item for item in record["roles"] if item["role"] == "writer"]
        if reviewer_context and len(reviewer_roles) == 1 and actual_writers:
            actual_reviewer = reviewer_roles[0]
            required_independence = contract["provider_policy"]["reviewer_independence"]
            if required_independence == "different-model" and any(
                (writer["provider"], writer["model"]) ==
                (actual_reviewer["provider"], actual_reviewer["model"])
                for writer in actual_writers
            ):
                errors.append("contract requires reviewer to use a different model from every writer")
            if required_independence == "different-provider" and any(
                writer["provider"] == actual_reviewer["provider"]
                for writer in actual_writers
            ):
                errors.append("contract requires reviewer to use a different provider from every writer")
        transfers = record["provider_transfers"]
        if transfers and not contract["provider_policy"]["allow_external_code_transfer"]:
            errors.append("provider transfers exist while external code transfer is denied")
        for transfer in transfers:
            if transfer["provider"] not in allowed_providers:
                errors.append(f"transfer provider is not allowed: {transfer['provider']}")
            if transfer["redaction_policy"] != contract["provider_policy"]["sensitive_path_policy"]:
                errors.append("provider transfer redaction policy differs from contract")

        limits = contract["automation"]
        budgets = record["budgets"]
        exceeded = any((
            budgets["tool_calls_used"] > limits["max_tool_calls"],
            budgets["elapsed_minutes"] > limits["max_elapsed_minutes"],
            budgets["cost_usd"] > limits["max_budget_usd"],
            budgets["implementation_attempts"] > limits["max_implementation_attempts"],
            budgets["review_rounds"] > limits["max_review_rounds"],
            budgets["active_writers"] > limits["max_parallel_writers"],
            budgets["max_observed_parallel_writers"] > limits["max_parallel_writers"],
        ))
        if budgets["limits_exceeded"] != exceeded:
            errors.append("limits_exceeded does not match contract budget usage")

        contract_paths = {
            path
            for permission in contract["change_envelope"]["allowed_components"].values()
            for path in permission["paths"]
        }
        conditional_paths = {
            path
            for permission in contract["change_envelope"]["conditional_components"].values()
            for path in permission["paths"]
        }
        for worktree in record["worktrees"]:
            for allowed_path in worktree["allowed_paths"]:
                if allowed_path not in contract_paths | conditional_paths:
                    errors.append(f"worktree path is outside contract envelope: {allowed_path}")
                elif allowed_path in conditional_paths:
                    payload = canonical_sha256({
                        "package_id": worktree["package_id"], "path": allowed_path,
                        "revision": record["current_revision"], "tree_sha256": record["current_tree_sha256"],
                    })
                    valid_attested_approval(
                        record["approvals"], key_id, f"expand-envelope:{worktree['package_id']}:{allowed_path}",
                        payload, errors,
                    )

    criterion_result_ids = [item["criterion_id"] for item in record["acceptance_results"]]
    if len(criterion_result_ids) != len(set(criterion_result_ids)):
        errors.append("acceptance_results contains duplicate criterion IDs")

    gate_results_by_id: dict[str, list[dict[str, Any]]] = {}
    contract_gates = {item["id"]: item for item in contract["quality_gates"]} if contract else {}
    for result in record["gate_results"]:
        gate_results_by_id.setdefault(result["gate_id"], []).append(result)
        gate = contract_gates.get(result["gate_id"])
        if gate:
            expected_command_hash = sha256_bytes(gate["command"].encode("utf-8"))
            if result["command_sha256"] != expected_command_hash:
                errors.append(f"gate {result['gate_id']} command hash differs from contract")
            resolved_by_path = {item["path"]: item["sha256"] for item in result["resolved_inputs"]}
            if set(resolved_by_path) != set(gate["resolved_input_paths"]):
                errors.append(f"gate {result['gate_id']} resolved-input set differs from contract")
            for input_path, recorded_hash in resolved_by_path.items():
                content = git_file_at(repository, result["revision"], input_path)
                if content is None or sha256_bytes(content) != recorded_hash:
                    errors.append(f"gate {result['gate_id']} resolved input differs from Git: {input_path}")
            environment = result["execution_environment"]
            if gate["sandbox"] == "required" and environment["sandbox"] != "applied":
                errors.append(f"gate {result['gate_id']} did not use required sandbox")
            if gate["network"] == "deny" and environment["network"] != "deny":
                errors.append(f"gate {result['gate_id']} used broader network access than allowed")
            if gate["secrets"] == "none" and environment["secrets"] != "none":
                errors.append(f"gate {result['gate_id']} received secrets contrary to contract")
            if environment["secrets"] != "none" and environment["log_redaction"] != "applied":
                errors.append(f"gate {result['gate_id']} used secrets without log redaction")
            started = dt.datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))
            finished = dt.datetime.fromisoformat(result["finished_at"].replace("Z", "+00:00"))
            duration = (finished - started).total_seconds()
            if duration < 0 or duration > gate["timeout_seconds"]:
                errors.append(f"gate {result['gate_id']} execution duration violates timeout")
        log = contained_file(repository, result["log_path"])
        if log is None or sha256_file(log) != result["log_sha256"]:
            errors.append(f"gate {result['gate_id']} log is missing or changed")
        if gate and gate["requires_approval"]:
            payload = canonical_sha256({
                "gate_id": result["gate_id"], "command_sha256": result["command_sha256"],
                "resolved_inputs": result["resolved_inputs"],
                "revision": result["revision"], "tree_sha256": result["tree_sha256"],
            })
            valid_attested_approval(
                record["approvals"], key_id, f"execute-gate:{result['gate_id']}", payload,
                errors, must_precede=result["started_at"],
            )
        if terminal == "accepted":
            execution_payload = canonical_sha256({
                "gate_id": result["gate_id"], "command_sha256": result["command_sha256"],
                "resolved_inputs": result["resolved_inputs"],
                "revision": result["revision"], "tree_sha256": result["tree_sha256"],
                "exit_code": result["exit_code"], "started_at": result["started_at"],
                "finished_at": result["finished_at"], "log_sha256": result["log_sha256"],
                "execution_environment": result["execution_environment"],
            })
            verify_host_attestation(
                key_id, f"gate-result:{result['gate_id']}", execution_payload,
                result["execution_event_id"], "trusted-executor",
                result["execution_hmac_sha256"], errors,
            )

    if contract is not None:
        unknown_results = set(gate_results_by_id) - set(contract_gates)
        if unknown_results:
            errors.append(f"run contains unknown gate results: {sorted(unknown_results)}")

    worktree_changed_paths: dict[str, set[str]] = {}
    for worktree in record["worktrees"]:
        base, worktree_head = worktree["base_revision"], worktree["head_revision"]
        if not git_object_exists(repository, base) or not git_object_exists(repository, worktree_head):
            errors.append(f"worktree commits do not exist: {worktree['package_id']}")
            continue
        if not git_is_ancestor(repository, base, worktree_head):
            errors.append(f"worktree base is not an ancestor of head: {worktree['package_id']}")
        if not git_is_ancestor(repository, record["base_revision"], base):
            errors.append(f"worktree base predates or diverges from run base: {worktree['package_id']}")
        if worktree["status"] == "integrated" and not git_is_ancestor(repository, worktree_head, record["current_revision"]):
            errors.append(f"integrated worktree head is not an ancestor of current revision: {worktree['package_id']}")
        patch_bytes = bytes(git(repository, "diff", "--binary", f"{base}..{worktree_head}"))
        patch_path = contained_file(repository, worktree["patch_artifact_path"])
        if patch_path is None or patch_path.read_bytes() != patch_bytes:
            errors.append(f"worktree patch artifact differs from git diff: {worktree['package_id']}")
        if sha256_bytes(patch_bytes) != worktree["patch_sha256"]:
            errors.append(f"worktree patch hash differs from git diff: {worktree['package_id']}")
        changed = str(git(repository, "diff", "--name-only", f"{base}..{worktree_head}", text=True)).splitlines()
        worktree_changed_paths[worktree["package_id"]] = set(changed)
        for changed_path in changed:
            if not any(fnmatch.fnmatch(changed_path, pattern) for pattern in worktree["allowed_paths"]):
                errors.append(f"worktree changed path outside allowed_paths: {changed_path}")

    if terminal in {"accepted", "verified-not-attested"}:
        if contract is None:
            errors.append(f"{terminal} run validation requires --contract")
        if record["state"] != "COMPLETE":
            errors.append(f"{terminal} run must be COMPLETE")
        if not transitions or transitions[0]["from"] != "START" or transitions[-1]["to"] != "COMPLETE":
            errors.append(f"{terminal} run requires a complete START-to-COMPLETE transition ledger")
        if dirty_paths(repository, record_path):
            errors.append(f"{terminal} run has dirty paths outside .ai/runs: {dirty_paths(repository, record_path)}")
        review = record["review"]
        if review["verdict"] != "approve" or review["independence"] == "not-independent":
            errors.append("accepted run requires an independent approving review")
        if len(reviewer_roles) != 1 or reviewer_roles[0]["context_id"] != reviewer_context:
            errors.append("accepted run requires exactly one matching reviewer role")
        if len(manager_roles) != 1:
            errors.append("accepted run requires exactly one manager role")
        author_providers = {
            item["provider"] for item in record["roles"]
            if item["role"] in {"manager", "scout", "tester", "writer"}
        }
        reviewer_provider = reviewer_roles[0]["provider"] if len(reviewer_roles) == 1 else None
        if review["independence"] == "independent" and reviewer_provider in author_providers:
            errors.append("independent review must use a provider outside the authoring providers")
        if review["independence"] == "same-provider-fresh-context" and reviewer_provider not in author_providers:
            errors.append("same-provider-fresh-context review must share an authoring provider")
        if review["reviewed_revision"] != record["current_revision"]:
            errors.append("reviewed revision must equal current revision")
        if review["reviewed_tree_sha256"] != record["current_tree_sha256"]:
            errors.append("reviewed tree must equal current tree")
        findings = contained_file(repository, review["findings_path"] or "")
        if findings is None or sha256_file(findings) != review["findings_sha256"]:
            errors.append("review findings are missing or changed")
        review_payload = canonical_sha256({
            "verdict": review["verdict"], "reviewer_context_id": review["reviewer_context_id"],
            "independence": review["independence"], "reviewed_revision": review["reviewed_revision"],
            "reviewed_tree_sha256": review["reviewed_tree_sha256"],
            "findings_sha256": review["findings_sha256"],
        })
        if terminal == "accepted":
            verify_host_attestation(
                key_id, "review-result", review_payload, review["review_event_id"],
                review["reviewer_context_id"] or "", review["review_hmac_sha256"], errors,
            )
        elif review["review_event_id"] is not None or review["review_hmac_sha256"] is not None:
            errors.append("verified-not-attested review must not claim a host attestation")
        if not manifest["frozen"]:
            errors.append("accepted run requires frozen acceptance tests")
        if contract and contract["test_policy"]["acceptance_tests_required"] and not manifest["files"]:
            errors.append("contract requires at least one frozen acceptance test")
        if record["budgets"]["limits_exceeded"]:
            errors.append("accepted run cannot exceed configured budgets")
        if record["budgets"]["active_writers"] != 0:
            errors.append("accepted run must have zero active writers")
        implementation_count = sum(item["to"] == "IMPLEMENT" for item in transitions)
        review_count = sum(item["to"] == "REVIEW" for item in transitions)
        if record["budgets"]["implementation_attempts"] != implementation_count:
            errors.append("implementation_attempts does not match transition ledger")
        if record["budgets"]["review_rounds"] != review_count:
            errors.append("review_rounds does not match transition ledger")
        writer_roles = [item for item in record["roles"] if item["role"] == "writer"]
        if implementation_count and not writer_roles:
            errors.append("implementation transitions require at least one writer role")
        if record["budgets"]["max_observed_parallel_writers"] > len(writer_roles):
            errors.append("max_observed_parallel_writers exceeds recorded writer contexts")
        if any(item["status"] != "integrated" for item in record["worktrees"]):
            errors.append("accepted run has non-integrated worktrees")
        if git_object_exists(repository, record["base_revision"]):
            final_changed_paths = set(
                str(git(repository, "diff", "--name-only", f"{record['base_revision']}..{record['current_revision']}", text=True)).splitlines()
            )
            integrated_union = set().union(
                *(worktree_changed_paths.get(item["package_id"], set()) for item in record["worktrees"])
            ) if record["worktrees"] else set()
            unexplained = final_changed_paths - integrated_union
            if unexplained:
                errors.append(f"final diff contains paths not produced by integrated worktrees: {sorted(unexplained)}")
            if contract:
                allowed_patterns = {
                    pattern for permission in contract["change_envelope"]["allowed_components"].values()
                    for pattern in permission["paths"]
                }
                conditional_patterns = {
                    pattern for permission in contract["change_envelope"]["conditional_components"].values()
                    for pattern in permission["paths"]
                }
                for changed_path in final_changed_paths:
                    if not any(fnmatch.fnmatch(changed_path, pattern) for pattern in allowed_patterns | conditional_patterns):
                        errors.append(f"final diff path is outside the Change Envelope: {changed_path}")
            for changed_path in final_changed_paths:
                producers = [
                    item for item in record["worktrees"]
                    if changed_path in worktree_changed_paths.get(item["package_id"], set())
                ]
                final_content = git_file_at(repository, record["current_revision"], changed_path)
                if producers and not any(
                    git_file_at(repository, item["head_revision"], changed_path) == final_content
                    for item in producers
                ):
                    errors.append(f"final content differs from every producing worktree: {changed_path}")

        passed_gates = set()
        for gate_id, results in gate_results_by_id.items():
            current_results = [
                result for result in results
                if result["exit_code"] == 0
                and result["revision"] == record["current_revision"]
                and result["tree_sha256"] == record["current_tree_sha256"]
            ]
            if len(current_results) == 1:
                passed_gates.add(gate_id)
            elif len(current_results) > 1:
                errors.append(f"accepted run has duplicate passing gate results: {gate_id}")
        if contract:
            expected_gates = set(contract_gates)
            if expected_gates != passed_gates:
                errors.append(f"accepted gate set differs from contract: missing={sorted(expected_gates-passed_gates)}, extra={sorted(passed_gates-expected_gates)}")
            criteria = {item["id"]: item for item in contract["run_spec"]["acceptance_criteria"]}
            results = {item["criterion_id"]: item for item in record["acceptance_results"]}
            if set(criteria) != set(results):
                errors.append("accepted run must contain exactly one result for every acceptance criterion")
            for criterion_id, criterion in criteria.items():
                result = results.get(criterion_id)
                if not result or result["status"] != "passed" or not result["evidence_paths"]:
                    errors.append(f"acceptance criterion lacks passed evidence: {criterion_id}")
                    continue
                required_gates = set(criterion["verification_gate_ids"])
                for evidence in result["evidence_paths"]:
                    path = contained_file(repository, evidence["path"])
                    if path is None or sha256_file(path) != evidence["sha256"]:
                        errors.append(f"acceptance evidence is missing or changed: {evidence['path']}")
                    if not set(evidence["gate_ids"]) <= passed_gates or not required_gates <= set(evidence["gate_ids"]):
                        errors.append(f"acceptance evidence is not bound to required passing gates: {criterion_id}")
        attestation = record["run_attestation"]
        if terminal == "accepted":
            payload_hash = run_payload_sha256(record)
            if attestation["payload_sha256"] != payload_hash:
                errors.append("final run attestation payload hash does not match run record")
            verify_host_attestation(
                key_id, "accepted-run", payload_hash, attestation["event_id"], attestation["actor"] or "",
                attestation["hmac_sha256"], errors,
            )
        else:
            if key_id is not None:
                errors.append("verified-not-attested run must not select an attestation key")
            if record["approvals"]:
                errors.append("verified-not-attested run must not contain runtime-attested approval events")
            if any(value is not None for value in attestation.values()):
                errors.append("verified-not-attested run must not claim a final host attestation")
            if any(
                result["execution_event_id"] is not None or result["execution_hmac_sha256"] is not None
                for result in record["gate_results"]
            ):
                errors.append("verified-not-attested gate results must not claim host attestations")

    if terminal == "ready-for-human-review" and record["review"]["independence"] != "not-independent":
        errors.append("ready-for-human-review is only for missing independent review")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--schema", type=Path, default=default_schema_path("run-record.schema.json"))
    parser.add_argument("--contract-schema", type=Path, default=default_contract_schema_path("development-contract.schema.json"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path)
    parser.add_argument(
        "--allow-unbound", action="store_true",
        help="Validate only run-record and repository invariants without contract-bound checks.",
    )
    args = parser.parse_args()

    repository = args.repository.resolve()
    record_path = args.record.resolve()
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = []
    for item in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(record):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")
    contract = None
    if not args.contract and not args.allow_unbound:
        errors.append("run validation requires --contract; use --allow-unbound only for an unbound scaffold")
    elif args.contract:
        try:
            contract = load_yaml(args.contract.resolve())
            errors.extend(validate_contract_document(contract, repository, args.contract_schema))
        except (FileNotFoundError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
            errors.append(f"cannot load contract: {exc}")
    if not errors:
        errors.extend(validate_semantics(record, repository, record_path, contract, args.contract_schema))
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    if contract is None:
        print("WARNING: unbound validation skipped contract gates, envelope, budgets, and provider policy")
    print(f"Valid run record: {args.record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
