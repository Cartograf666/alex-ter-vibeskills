#!/usr/bin/env python3
"""Bind explicit approval to a valid design-system manifest payload."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import yaml

from design_system_lib import design_system_artifact_hashes, design_system_payload_sha256
from validate_design_system import default_schema_path, validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    schema = json.loads(default_schema_path().read_text(encoding="utf-8"))
    initial_errors = validate_manifest(manifest, schema, args.repository.resolve())
    if initial_errors:
        raise SystemExit(
            "refusing to approve invalid design-system manifest:\n"
            + "\n".join(f"- {item}" for item in initial_errors)
        )
    digest = design_system_payload_sha256(manifest)
    manifest["status"] = "approved"
    manifest["approval"] = {
        "status": "approved", "approved_by": args.approved_by,
        "approved_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact_hashes": design_system_artifact_hashes(manifest, args.repository.resolve()),
        "manifest_sha256": digest,
    }
    final_errors = validate_manifest(manifest, schema, args.repository.resolve())
    if final_errors:
        raise SystemExit(
            "refusing to approve invalid design-system manifest:\n"
            + "\n".join(f"- {item}" for item in final_errors)
        )
    args.manifest.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"Approved design-system manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
