#!/usr/bin/env python3
"""Freeze manager-approved acceptance tests into a run record."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--owner-context-id", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()

    repository = args.repository.resolve()
    record = yaml.safe_load(args.record.read_text(encoding="utf-8"))
    files = []
    for raw_path in args.files:
        path = (repository / raw_path).resolve()
        try:
            relative = path.relative_to(repository)
        except ValueError as exc:
            raise SystemExit(f"test path escapes repository: {raw_path}") from exc
        if not path.is_file():
            raise SystemExit(f"missing test file: {raw_path}")
        files.append({"path": str(relative), "sha256": sha256_file(path)})
    record["acceptance_test_manifest"] = {
        "frozen": True,
        "frozen_at_state": "TEST_DESIGN",
        "owner_context_id": args.owner_context_id,
        "files": sorted(files, key=lambda item: item["path"]),
    }
    args.record.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    print(f"Frozen {len(files)} acceptance test file(s) in {args.record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
