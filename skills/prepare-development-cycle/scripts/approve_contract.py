#!/usr/bin/env python3
"""Bind a user's approval to exact contract inputs and repository revision."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

from contract_lib import (
    approval_attestation_hmac,
    contract_payload_sha256,
    dump_yaml,
    gate_input_hashes,
    load_yaml,
    load_hmac_keyring,
    source_artifact_hashes,
)
from jsonschema import Draft202012Validator, FormatChecker
from validate_contract import default_schema_path, validate_semantics


def git_head(repository: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument(
        "--method",
        choices=["local-confirmation", "runtime-attestation"],
        default="local-confirmation",
    )
    parser.add_argument("--authority-event-id")
    parser.add_argument("--key-id", default="default")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()

    repository = args.repository.resolve()
    contract_path = args.contract.resolve()
    contract = load_yaml(contract_path)
    schema = json.loads(default_schema_path("development-contract.schema.json").read_text(encoding="utf-8"))
    initial_errors = [
        f"{'.'.join(str(part) for part in item.path) or '<root>'}: {item.message}"
        for item in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(contract)
    ]
    if not initial_errors:
        initial_errors.extend(validate_semantics(contract, repository))
    if initial_errors:
        raise SystemExit(
            "refusing to approve invalid contract:\n"
            + "\n".join(f"- {item}" for item in initial_errors)
        )

    if args.method == "runtime-attestation" and not args.authority_event_id:
        raise SystemExit("runtime-attestation requires --authority-event-id")
    if contract["run_spec"]["risk_level"] in {"high", "critical"} and args.method == "local-confirmation":
        raise SystemExit("high/critical risk requires runtime-attestation approval")

    attestation_hmac = None
    payload_hash = contract_payload_sha256(contract)
    source_revision = git_head(repository)
    if args.method == "runtime-attestation":
        try:
            keyring = load_hmac_keyring("VIBESKILLS_APPROVAL_HMAC_KEYS")
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        key = keyring.get(args.key_id)
        if not key and args.key_id == "default":
            key = os.environ.get("VIBESKILLS_APPROVAL_HMAC_KEY")
        if not key:
            raise SystemExit("runtime-attestation requires the selected trusted-host approval HMAC key")
        if len(key.encode("utf-8")) < 32:
            raise SystemExit("runtime-attestation HMAC key must contain at least 32 bytes")
        attestation_hmac = approval_attestation_hmac(
            key, args.key_id, payload_hash, args.authority_event_id, args.approved_by, source_revision
        )

    approval = {
        "status": "approved",
        "approved_by": args.approved_by,
        "approved_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "method": args.method,
        "key_id": args.key_id if args.method == "runtime-attestation" else None,
        "authority_event_id": args.authority_event_id,
        "attestation_hmac_sha256": attestation_hmac,
        "source_revision": source_revision,
        "artifact_hashes": source_artifact_hashes(contract, repository),
        "gate_input_hashes": gate_input_hashes(contract, repository),
        "contract_payload_sha256": payload_hash,
    }
    contract["approval"] = approval
    contract["status"] = "approved"
    contract["implementation_authorized"] = True
    errors = [
        f"{'.'.join(str(part) for part in item.path) or '<root>'}: {item.message}"
        for item in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(contract)
    ]
    if not errors:
        errors.extend(validate_semantics(contract, repository))
    if errors:
        raise SystemExit("refusing to approve invalid contract:\n" + "\n".join(f"- {item}" for item in errors))
    dump_yaml(contract_path, contract)
    print(f"Approved {contract_path} at {approval['source_revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
