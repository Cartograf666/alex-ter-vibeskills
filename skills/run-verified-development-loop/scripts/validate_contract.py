#!/usr/bin/env python3
"""Validate schema, traceability, policy precedence, and approval integrity."""

from __future__ import annotations

import argparse
import hmac
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import json
from jsonschema import Draft202012Validator, FormatChecker

from architecture_lib import architecture_payload_sha256, path_patterns_overlap
from contract_lib import (
    approval_attestation_hmac,
    contract_payload_sha256,
    gate_input_hashes,
    load_yaml,
    load_hmac_keyring,
    source_artifact_paths,
    source_artifact_hashes,
)
from validate_design_system import validate_manifest as validate_design_manifest


AC_PATTERN = re.compile(r"\bAC-[1-9][0-9]*\b")
REQUIREMENT_PATTERN = re.compile(r"\b(?:FR|NFR)-[1-9][0-9]*\b")
MODE_RANK = {"manual": 0, "bounded-auto": 1, "full-auto": 2}


def default_schema_path(name: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    standalone = root / "assets" / name
    return standalone if standalone.is_file() else root / "schemas" / name


def glob_static_prefix(pattern: str) -> str:
    wildcard_positions = [position for token in ("*", "?", "[") if (position := pattern.find(token)) >= 0]
    prefix = pattern[: min(wildcard_positions)] if wildcard_positions else pattern
    return prefix.rstrip("/")


def error(message: str, errors: list[str]) -> None:
    errors.append(message)


def route_provider(route: str) -> str:
    return route.split(":", 1)[0]


def git_is_ancestor(repository: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=repository,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def validate_semantics(contract: dict[str, Any], repository: Path) -> list[str]:
    errors: list[str] = []
    try:
        source_paths = source_artifact_paths(contract, repository)
        for name, path in source_paths.items():
            if not path.is_file():
                error(f"missing source document: {path}", errors)
    except (KeyError, ValueError) as exc:
        error(str(exc), errors)
        source_paths = {}
    criteria = contract["run_spec"]["acceptance_criteria"]
    criterion_ids = [item["id"] for item in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        error("run_spec.acceptance_criteria contains duplicate IDs", errors)

    gate_ids = [item["id"] for item in contract["quality_gates"]]
    if len(gate_ids) != len(set(gate_ids)):
        error("quality_gates contains duplicate IDs", errors)
    gate_id_set = set(gate_ids)
    for criterion in criteria:
        missing = set(criterion["verification_gate_ids"]) - gate_id_set
        if missing:
            error(f"{criterion['id']} references missing gates: {sorted(missing)}", errors)

    prd_path = source_paths.get("prd", repository / "__missing_prd__")
    if prd_path.is_file():
        prd_ids = set(AC_PATTERN.findall(prd_path.read_text(encoding="utf-8")))
        contract_ids = set(criterion_ids)
        if prd_ids != contract_ids:
            error(
                f"PRD/RunSpec acceptance IDs differ: missing={sorted(prd_ids-contract_ids)}, "
                f"extra={sorted(contract_ids-prd_ids)}",
                errors,
            )
        prd_requirement_ids = set(REQUIREMENT_PATTERN.findall(prd_path.read_text(encoding="utf-8")))
        mapped_requirement_ids = {
            requirement_id
            for criterion in criteria
            for requirement_id in criterion["source_requirement_ids"]
            if requirement_id.startswith(("FR-", "NFR-"))
        }
        if prd_requirement_ids != mapped_requirement_ids:
            error(
                "PRD requirements are not fully mapped to acceptance criteria: "
                f"unmapped={sorted(prd_requirement_ids-mapped_requirement_ids)}, "
                f"unknown={sorted(mapped_requirement_ids-prd_requirement_ids)}",
                errors,
            )

    technical_brief = contract["source_documents"]["technical_brief"]
    omission_reason = contract["source_documents"]["technical_brief_omission_reason"]
    if technical_brief is None and not omission_reason:
        error("technical_brief is null but omission reason is missing", errors)
    if technical_brief is not None and omission_reason is not None:
        error("technical_brief exists but omission reason is not null", errors)

    primary = contract["change_envelope"]["primary_component"]
    allowed = contract["change_envelope"]["allowed_components"]
    if primary not in allowed:
        error("primary_component must appear in allowed_components", errors)
    conditional = contract["change_envelope"]["conditional_components"]
    forbidden = set(contract["change_envelope"]["forbidden_components"])
    component_sets = {
        "allowed": set(allowed), "conditional": set(conditional), "forbidden": forbidden
    }
    for left, right in (("allowed", "conditional"), ("allowed", "forbidden"), ("conditional", "forbidden")):
        overlap = component_sets[left] & component_sets[right]
        if overlap:
            error(f"components are both {left} and {right}: {sorted(overlap)}", errors)
    path_owners: list[tuple[str, str]] = []
    for scope_name, permissions in (("allowed", allowed), ("conditional", conditional)):
        for component, permission in permissions.items():
            for path_pattern in permission["paths"]:
                owner = f"{scope_name}.{component}"
                for existing_pattern, existing_owner in path_owners:
                    if existing_owner != owner and path_patterns_overlap(existing_pattern, path_pattern):
                        error(
                            f"path scopes overlap between {existing_owner} ({existing_pattern!r}) and {owner} ({path_pattern!r})",
                            errors,
                        )
                path_owners.append((path_pattern, owner))

    modes = [item["mode"] for item in contract["automation"]["policy_sources"]]
    expected_mode = min(modes, key=MODE_RANK.get)
    if contract["automation"]["effective_mode"] != expected_mode:
        error(
            f"effective_mode must be most restrictive policy ({expected_mode})",
            errors,
        )
    task_modes = [
        item["mode"] for item in contract["automation"]["policy_sources"]
        if item["source"] == "task"
    ]
    if task_modes != [contract["automation"]["requested_mode"]]:
        error("policy_sources must contain exactly one task mode matching requested_mode", errors)
    sources = [item["source"] for item in contract["automation"]["policy_sources"]]
    if len(sources) != len(set(sources)):
        error("policy_sources must not contain duplicate source classes", errors)

    provider_policy = contract["provider_policy"]
    allowed_providers = set(provider_policy["allowed_providers"])
    role_assignments = provider_policy["role_assignments"]
    for role, assignment in role_assignments.items():
        routes = [assignment["preferred"], *assignment["fallbacks"]]
        if assignment["preferred"] in assignment["fallbacks"]:
            error(f"provider_policy.{role}: preferred route cannot also be a fallback", errors)
        for route in routes:
            provider = route_provider(route)
            if provider not in allowed_providers:
                error(
                    f"provider_policy.{role}: route {route!r} uses provider outside allowed_providers",
                    errors,
                )
    writer_route = role_assignments["writer"]["preferred"]
    reviewer_route = role_assignments["reviewer"]["preferred"]
    independence = provider_policy["reviewer_independence"]
    if independence == "different-model" and writer_route == reviewer_route:
        error("reviewer_independence requires writer and reviewer to prefer different models", errors)
    if independence == "different-provider" and route_provider(writer_route) == route_provider(reviewer_route):
        error("reviewer_independence requires writer and reviewer to prefer different providers", errors)

    architecture_path = contract["source_documents"]["architecture_manifest"]
    if architecture_path and "architecture_manifest" in source_paths and source_paths["architecture_manifest"].is_file():
        try:
            architecture = load_yaml(source_paths["architecture_manifest"])
            project_modes = [
                item["mode"] for item in contract["automation"]["policy_sources"]
                if item["source"] == "project"
            ]
            expected_project_mode = architecture["automation"]["mode"]
            if project_modes != [expected_project_mode]:
                error("project policy source must exactly match architecture automation.mode", errors)
            architecture_components = architecture["components"]
            envelope_components = set(allowed) | set(conditional) | forbidden
            unknown_components = envelope_components - set(architecture_components)
            if unknown_components:
                error(f"change envelope references unknown architecture components: {sorted(unknown_components)}", errors)
            for component, permission in {**allowed, **conditional}.items():
                if component not in architecture_components:
                    continue
                architecture_paths = architecture_components[component]["paths"]
                for envelope_path in permission["paths"]:
                    if not any(
                        glob_static_prefix(envelope_path) == glob_static_prefix(architecture_path)
                        or glob_static_prefix(envelope_path).startswith(glob_static_prefix(architecture_path) + "/")
                        for architecture_path in architecture_paths
                    ):
                        error(
                            f"change-envelope path {envelope_path!r} is outside architecture component {component}",
                            errors,
                        )
        except (KeyError, ValueError) as exc:
            error(f"cannot read architecture automation policy: {exc}", errors)

    for gate in contract["quality_gates"]:
        if any(path == ".ai/runs" or path.startswith(".ai/runs/") for path in gate["resolved_input_paths"]):
            error(f"{gate['id']}: gate inputs cannot execute from .ai/runs", errors)
        if gate["trust"] == "untrusted":
            if not gate["requires_approval"]:
                error(f"{gate['id']}: untrusted gate requires approval", errors)
            if gate["sandbox"] != "required":
                error(f"{gate['id']}: untrusted gate requires sandbox", errors)
            if gate["secrets"] != "none":
                error(f"{gate['id']}: untrusted gate cannot receive secrets", errors)
            if gate["network"] != "deny":
                error(f"{gate['id']}: untrusted gate requires denied network", errors)
        if gate["source"] == "newly-generated":
            if not gate["requires_approval"]:
                error(f"{gate['id']}: newly generated gate requires approval", errors)
            if gate["sandbox"] != "required" or gate["secrets"] != "none" or gate["network"] != "deny":
                error(f"{gate['id']}: newly generated gate requires sandbox, denied network, and no secrets", errors)

    design_policy = contract["design_policy"]
    if design_policy["applies"]:
        design_path = source_paths.get("design_system_manifest")
        if design_path and design_path.is_file():
            try:
                design_manifest = load_yaml(design_path)
                design_schema = json.loads(
                    default_schema_path("design-system.schema.json").read_text(encoding="utf-8")
                )
                for design_error in validate_design_manifest(
                    design_manifest, design_schema, repository
                ):
                    error(f"design system: {design_error}", errors)
                if design_manifest["status"] != "approved" or design_manifest["approval"]["status"] != "approved":
                    error("UI work requires an approved design-system manifest", errors)
                source_to_status = {
                    "existing": "approved-existing", "adopted": "approved-adopted",
                    "custom": "approved-custom",
                }
                if design_policy["system_status"] != source_to_status[design_manifest["source"]["type"]]:
                    error("design_policy.system_status differs from design-system source", errors)
                required_design_gates = set(design_policy["required_gate_ids"])
                if not required_design_gates <= set(design_manifest["quality_gate_ids"]):
                    error("design policy requires gates absent from the design-system manifest", errors)
                if not required_design_gates <= gate_id_set:
                    error("design policy requires gates absent from the development contract", errors)
                criterion_gate_ids = {
                    gate_id for criterion in criteria
                    for gate_id in criterion["verification_gate_ids"]
                }
                if not required_design_gates <= criterion_gate_ids:
                    error("design gates are not mapped to RunSpec acceptance criteria", errors)
            except (KeyError, ValueError) as exc:
                error(f"cannot validate design-system manifest: {exc}", errors)

    authorized = contract["implementation_authorized"]
    approval = contract["approval"]
    if authorized:
        if contract["status"] != "approved" or approval["status"] != "approved":
            error("authorized contract must have approved status and approval", errors)
        else:
            try:
                current_hashes = source_artifact_hashes(contract, repository)
                if current_hashes != approval["artifact_hashes"]:
                    error("approval invalid: source document hashes changed", errors)
                if not any(gate["resolved_input_paths"] for gate in contract["quality_gates"]):
                    error("authorized contract requires resolved inputs for every quality gate", errors)
                elif any(not gate["resolved_input_paths"] for gate in contract["quality_gates"]):
                    error("authorized contract has a quality gate without resolved inputs", errors)
                elif gate_input_hashes(contract, repository) != approval["gate_input_hashes"]:
                    error("approval invalid: resolved gate input hashes changed", errors)
                if contract_payload_sha256(contract) != approval["contract_payload_sha256"]:
                    error("approval invalid: contract payload changed", errors)
                if not git_is_ancestor(repository, approval["source_revision"]):
                    error("approval source_revision is not an ancestor of HEAD", errors)
                if contract["run_spec"]["risk_level"] in {"high", "critical"} and approval["method"] == "local-confirmation":
                    error("high/critical risk requires runtime-attestation approval", errors)
                if approval["method"] == "runtime-attestation":
                    event_id = approval["authority_event_id"]
                    supplied_hmac = approval["attestation_hmac_sha256"]
                    key_id = approval["key_id"]
                    try:
                        keyring = load_hmac_keyring("VIBESKILLS_APPROVAL_HMAC_KEYS")
                    except ValueError as exc:
                        error(str(exc), errors)
                        keyring = {}
                    key = keyring.get(key_id) if key_id else None
                    if not key and key_id == "default":
                        key = os.environ.get("VIBESKILLS_APPROVAL_HMAC_KEY")
                    if not event_id or not supplied_hmac:
                        error("runtime-attestation approval is incomplete", errors)
                    elif not key:
                        error("runtime-attestation verification requires the selected trusted-host approval HMAC key", errors)
                    elif len(key.encode("utf-8")) < 32:
                        error("runtime-attestation approval HMAC key must contain at least 32 bytes", errors)
                    else:
                        expected_hmac = approval_attestation_hmac(
                            key,
                            key_id,
                            approval["contract_payload_sha256"],
                            event_id,
                            approval["approved_by"],
                            approval["source_revision"],
                        )
                        if not hmac.compare_digest(supplied_hmac, expected_hmac):
                            error("runtime-attestation HMAC is invalid", errors)
                elif approval["attestation_hmac_sha256"] is not None:
                    error("local-confirmation must not contain runtime attestation HMAC", errors)
                elif approval["key_id"] is not None:
                    error("local-confirmation must not select an attestation key", errors)
                if architecture_path:
                    manifest = load_yaml((repository / architecture_path).resolve())
                    manifest_approval = manifest.get("approval", {})
                    if manifest.get("status") != "approved" or manifest_approval.get("status") != "approved":
                        error("authorized contract requires an approved architecture manifest", errors)
                    elif manifest_approval.get("manifest_sha256") != architecture_payload_sha256(manifest):
                        error("architecture manifest approval hash is invalid", errors)
            except (FileNotFoundError, ValueError) as exc:
                error(str(exc), errors)
    elif approval["status"] == "approved":
        error("approval is approved while implementation_authorized is false", errors)
    elif contract["status"] == "approved":
        error("contract status is approved while implementation_authorized is false", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("--schema", type=Path, default=default_schema_path("development-contract.schema.json"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()

    repository = args.repository.resolve()
    contract = load_yaml(args.contract.resolve())
    schema = json.loads(args.schema.read_text(encoding="utf-8"))

    errors: list[str] = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for item in sorted(validator.iter_errors(contract), key=lambda err: list(err.path)):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")
    if not errors:
        errors.extend(validate_semantics(contract, repository))

    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print(f"Valid development contract: {args.contract}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
