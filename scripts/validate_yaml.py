#!/usr/bin/env python3
"""Validate any YAML document against a JSON Schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("schema", type=Path)
    args = parser.parse_args()

    document = yaml.safe_load(args.document.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        for item in errors:
            location = ".".join(str(part) for part in item.path) or "<root>"
            print(f"ERROR: {location}: {item.message}", file=sys.stderr)
        return 1
    print(f"Valid {args.document} against {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
