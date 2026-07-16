#!/usr/bin/env python3
"""Trusted-host helper for signing a precomputed run-event payload hash."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import json
from pathlib import Path

import yaml

from validate_run_record import run_payload_sha256


SHA256 = re.compile(r"^[a-f0-9]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", default="accepted-run")
    payload_group = parser.add_mutually_exclusive_group(required=True)
    payload_group.add_argument("--payload-sha256")
    payload_group.add_argument("--record", type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--key-id", default="default")
    args = parser.parse_args()
    payload_hash = args.payload_sha256
    if args.record:
        record = yaml.safe_load(args.record.read_text(encoding="utf-8"))
        payload_hash = run_payload_sha256(record)
    if not SHA256.fullmatch(payload_hash):
        raise SystemExit("--payload-sha256 must be a lowercase SHA-256 digest")
    keyring_raw = os.environ.get("VIBESKILLS_RUN_HMAC_KEYS")
    keyring = json.loads(keyring_raw) if keyring_raw else {}
    key = keyring.get(args.key_id)
    if not key and args.key_id == "default":
        key = os.environ.get("VIBESKILLS_RUN_HMAC_KEY")
    if not key:
        raise SystemExit("trusted-host VIBESKILLS_RUN_HMAC_KEY is required")
    if len(key.encode("utf-8")) < 32:
        raise SystemExit("trusted-host run HMAC key must contain at least 32 bytes")
    message = "\n".join(
        [args.key_id, args.action, payload_hash, args.event_id, args.actor]
    ).encode("utf-8")
    signature = hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    print(f"payload_sha256: {payload_hash}")
    print(f"hmac_sha256: {signature}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
