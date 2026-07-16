#!/usr/bin/env python3
"""Bind human approval to the exact architecture manifest payload."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import yaml

from architecture_lib import architecture_payload_sha256
from validate_architecture import default_schema_path, validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    schema = json.loads(default_schema_path().read_text(encoding="utf-8"))
    initial_errors = validate_manifest(manifest, schema)
    if initial_errors:
        raise SystemExit(
            "refusing to approve invalid architecture manifest:\n"
            + "\n".join(f"- {item}" for item in initial_errors)
        )
    digest = architecture_payload_sha256(manifest)
    manifest["status"] = "approved"
    manifest["approval"] = {
        "status": "approved",
        "approved_by": args.approved_by,
        "approved_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_sha256": digest,
    }
    errors = validate_manifest(
        manifest, schema
    )
    if errors:
        raise SystemExit(
            "refusing to approve invalid architecture manifest:\n"
            + "\n".join(f"- {item}" for item in errors)
        )
    args.manifest.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"Approved architecture manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
