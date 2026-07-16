#!/usr/bin/env python3
"""Generate a stable architecture finding fingerprint."""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any


def finding_fingerprint(finding: dict[str, Any]) -> str:
    payload = {
        "rule_id": finding["rule_id"],
        "rule_version": finding["rule_version"],
        "source": finding["source"],
        "target": finding["target"],
        "edge_kind": finding["edge_kind"],
        "location": finding["location"],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--rule-version", required=True, type=int)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--edge-kind", required=True)
    parser.add_argument("--location", required=True)
    args = parser.parse_args()
    print(finding_fingerprint(vars(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
