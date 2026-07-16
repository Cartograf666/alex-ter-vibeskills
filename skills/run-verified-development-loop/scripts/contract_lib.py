#!/usr/bin/env python3
"""Shared deterministic helpers for development-contract tools."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import yaml


APPROVAL_RESET = {
    "status": "pending",
    "approved_by": None,
    "approved_at": None,
    "method": None,
    "key_id": None,
    "authority_event_id": None,
    "attestation_hmac_sha256": None,
    "source_revision": None,
    "artifact_hashes": {},
    "gate_input_hashes": {},
    "contract_payload_sha256": None,
}


def approval_attestation_message(
    key_id: str,
    contract_payload_hash: str,
    authority_event_id: str,
    approved_by: str,
    source_revision: str,
) -> bytes:
    return "\n".join(
        [key_id, contract_payload_hash, authority_event_id, approved_by, source_revision]
    ).encode("utf-8")


def approval_attestation_hmac(
    key: str,
    key_id: str,
    contract_payload_hash: str,
    authority_event_id: str,
    approved_by: str,
    source_revision: str,
) -> str:
    return hmac.new(
        key.encode("utf-8"),
        approval_attestation_message(
            key_id, contract_payload_hash, authority_event_id, approved_by, source_revision
        ),
        hashlib.sha256,
    ).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contract_payload(contract: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(contract)
    payload["status"] = "draft"
    payload["implementation_authorized"] = False
    payload["approval"] = copy.deepcopy(APPROVAL_RESET)
    return payload


def contract_payload_sha256(contract: dict[str, Any]) -> str:
    canonical = json.dumps(
        contract_payload(contract),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def source_artifact_paths(contract: dict[str, Any], repository: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for name, raw_path in contract["source_documents"].items():
        if name == "technical_brief_omission_reason" or raw_path is None:
            continue
        path = (repository / raw_path).resolve()
        try:
            path.relative_to(repository.resolve())
        except ValueError as exc:
            raise ValueError(f"source document escapes repository: {raw_path}") from exc
        result[name] = path
    return result


def source_artifact_hashes(contract: dict[str, Any], repository: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in source_artifact_paths(contract, repository).items():
        if not path.is_file():
            raise FileNotFoundError(f"missing source document: {path}")
        hashes[name] = sha256_file(path)
    return hashes


def gate_input_hashes(contract: dict[str, Any], repository: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for gate in contract["quality_gates"]:
        for raw_path in gate["resolved_input_paths"]:
            path = (repository / raw_path).resolve()
            try:
                path.relative_to(repository.resolve())
            except ValueError as exc:
                raise ValueError(f"gate input escapes repository: {raw_path}") from exc
            if not path.is_file():
                raise FileNotFoundError(f"missing gate input: {path}")
            hashes[raw_path] = sha256_file(path)
    return hashes
