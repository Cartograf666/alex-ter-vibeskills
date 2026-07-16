#!/usr/bin/env python3
"""Validate architecture baseline provenance and deterministic fingerprints."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from finding_fingerprint import finding_fingerprint


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def default_schema_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    standalone = root / "assets" / "architecture-baseline.schema.json"
    return standalone if standalone.is_file() else root / "schemas" / "architecture-baseline.schema.json"


def commit_exists(repository: Path, revision: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=repository,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repository,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--schema", type=Path, default=default_schema_path())
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--findings", type=Path, help="Optional current findings YAML list for exact-set comparison")
    args = parser.parse_args()
    baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = []
    for item in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(baseline):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")
    if not errors:
        repository = args.repository.resolve()
        ids = [item["id"] for item in baseline["known_violations"]]
        fingerprints = [item["fingerprint"] for item in baseline["known_violations"]]
        if len(ids) != len(set(ids)):
            errors.append("known_violations contains duplicate IDs")
        if len(fingerprints) != len(set(fingerprints)):
            errors.append("known_violations contains duplicate fingerprints")
        if not commit_exists(repository, baseline["source_revision"]):
            errors.append("baseline source_revision is not a repository commit")
        else:
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repository, text=True
            ).strip()
            if not is_ancestor(repository, baseline["source_revision"], head):
                errors.append("baseline source_revision is not an ancestor of HEAD")
        for finding in baseline["known_violations"]:
            if finding["fingerprint"] != finding_fingerprint(finding):
                errors.append(f"{finding['id']}: fingerprint does not match normalized finding")
            if not commit_exists(repository, finding["first_seen_revision"]):
                errors.append(f"{finding['id']}: first_seen_revision is not a repository commit")
            elif commit_exists(repository, baseline["source_revision"]) and not is_ancestor(
                repository, finding["first_seen_revision"], baseline["source_revision"]
            ):
                errors.append(f"{finding['id']}: first_seen_revision is not an ancestor of source_revision")
        if args.findings:
            current = yaml.safe_load(args.findings.read_text(encoding="utf-8"))
            if not isinstance(current, list):
                errors.append("--findings must contain a YAML list")
            else:
                current_fingerprints = {finding_fingerprint(item) for item in current}
                baseline_fingerprints = set(fingerprints)
                unexpected = current_fingerprints - baseline_fingerprints
                if unexpected:
                    errors.append(f"current findings contain new violations: {sorted(unexpected)}")
                baseline_by_fingerprint = {
                    item["fingerprint"]: item for item in baseline["known_violations"]
                }
                for finding in current:
                    fingerprint = finding_fingerprint(finding)
                    baseline_finding = baseline_by_fingerprint.get(fingerprint)
                    if baseline_finding and SEVERITY_RANK[finding["severity"]] > SEVERITY_RANK[baseline_finding["severity"]]:
                        errors.append(
                            f"current finding severity increased for {fingerprint}: "
                            f"{baseline_finding['severity']} -> {finding['severity']}"
                        )
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print(f"Valid architecture baseline: {args.baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
