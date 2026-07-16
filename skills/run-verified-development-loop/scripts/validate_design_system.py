#!/usr/bin/env python3
"""Validate a project design-system manifest and approval binding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from design_system_lib import design_system_artifact_hashes, design_system_payload_sha256


REQUIRED_TOKEN_CATEGORIES = {
    "color", "typography", "spacing", "sizing", "radius", "motion", "breakpoint"
}


def default_schema_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    standalone = root / "assets" / "design-system.schema.json"
    return standalone if standalone.is_file() else root / "schemas" / "design-system.schema.json"


def contained_path(repository: Path, raw_path: str) -> Path | None:
    path = (repository / raw_path).resolve()
    try:
        path.relative_to(repository.resolve())
    except ValueError:
        return None
    return path


def validate_manifest(
    manifest: dict[str, Any], schema: dict[str, Any], repository: Path
) -> list[str]:
    errors: list[str] = []
    for item in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(manifest):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")
    if errors:
        return errors

    categories = set(manifest["tokens"]["categories"])
    missing = REQUIRED_TOKEN_CATEGORIES - categories
    if missing:
        errors.append(f"tokens are missing required categories: {sorted(missing)}")
    paths = (
        manifest["tokens"]["source_paths"]
        + manifest["components"]["registry_paths"]
        + manifest["components"]["documentation_paths"]
    )
    for raw_path in paths:
        if contained_path(repository, raw_path) is None:
            errors.append(f"design-system path escapes repository: {raw_path}")
    if manifest["status"] == "approved":
        missing_paths = [
            raw_path for raw_path in paths
            if (path := contained_path(repository, raw_path)) is None or not path.exists()
        ]
        if missing_paths:
            errors.append(f"approved design system references missing paths: {sorted(missing_paths)}")
        else:
            try:
                if manifest["approval"]["artifact_hashes"] != design_system_artifact_hashes(manifest, repository):
                    errors.append("design-system approval invalid: artifact contents changed")
            except (FileNotFoundError, ValueError) as exc:
                errors.append(str(exc))
        if manifest["approval"]["manifest_sha256"] != design_system_payload_sha256(manifest):
            errors.append("design-system approval invalid: manifest payload changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--schema", type=Path, default=default_schema_path())
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = validate_manifest(manifest, schema, args.repository.resolve())
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print(f"Valid design-system manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
