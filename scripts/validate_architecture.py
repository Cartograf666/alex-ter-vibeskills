#!/usr/bin/env python3
"""Validate architecture schema, references, and approval hash."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from architecture_lib import architecture_payload_sha256


def glob_static_prefix(pattern: str) -> str:
    positions = [position for token in ("*", "?", "[") if (position := pattern.find(token)) >= 0]
    return pattern[: min(positions)].rstrip("/") if positions else pattern.rstrip("/")


def path_patterns_overlap(left: str, right: str) -> bool:
    left_parts, right_parts = left.strip("/").split("/"), right.strip("/").split("/")
    for left_part, right_part in zip(left_parts, right_parts):
        if "**" in {left_part, right_part}:
            return True
        left_glob = any(token in left_part for token in ("*", "?", "["))
        right_glob = any(token in right_part for token in ("*", "?", "["))
        if left_glob and not right_glob and not fnmatch.fnmatchcase(right_part, left_part):
            return False
        if right_glob and not left_glob and not fnmatch.fnmatchcase(left_part, right_part):
            return False
        if not left_glob and not right_glob and left_part != right_part:
            return False
    if len(left_parts) == len(right_parts):
        return True
    remainder = left_parts[len(right_parts):] or right_parts[len(left_parts):]
    return all(part == "**" for part in remainder)


def default_schema_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    standalone = root / "assets" / "architecture.schema.json"
    return standalone if standalone.is_file() else root / "schemas" / "architecture.schema.json"


def validate_manifest(manifest: dict, schema: dict) -> list[str]:
    errors = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for item in sorted(validator.iter_errors(manifest), key=lambda err: list(err.path)):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")

    if not errors:
        components = set(manifest["components"])
        rule_ids = []
        for rule in manifest["dependency_rules"]:
            rule_ids.append(rule["id"])
            if rule["from"] not in components or rule["to"] not in components:
                errors.append(f"{rule['id']}: references an unknown component")
        if len(rule_ids) != len(set(rule_ids)):
            errors.append("dependency_rules contains duplicate IDs")
        policy_sets = {
            name: set(manifest["automation"][name]) for name in ("auto_allow", "ask", "deny")
        }
        for left, right in (("auto_allow", "ask"), ("auto_allow", "deny"), ("ask", "deny")):
            overlap = policy_sets[left] & policy_sets[right]
            if overlap:
                errors.append(f"automation actions appear in both {left} and {right}: {sorted(overlap)}")
        path_owners = []
        for component, definition in manifest["components"].items():
            for pattern in definition["paths"]:
                for existing_pattern, existing_component in path_owners:
                    if existing_component != component and path_patterns_overlap(existing_pattern, pattern):
                        errors.append(
                            f"component path scopes overlap between {existing_component} ({existing_pattern!r}) and {component} ({pattern!r})"
                        )
                path_owners.append((pattern, component))
        if manifest["status"] == "approved":
            expected = architecture_payload_sha256(manifest)
            if manifest["approval"]["manifest_sha256"] != expected:
                errors.append("architecture approval invalid: manifest payload changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--schema", type=Path, default=default_schema_path())
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = validate_manifest(manifest, schema)

    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print(f"Valid architecture manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
