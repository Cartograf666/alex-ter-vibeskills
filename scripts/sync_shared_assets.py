#!/usr/bin/env python3
"""Synchronize canonical schemas and validators into standalone skill folders."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MAPPINGS = {
    "prepare-development-cycle": {
        "assets": ["development-contract.schema.json", "design-system.schema.json"],
        "scripts": [
            "contract_lib.py", "architecture_lib.py", "approve_contract.py", "validate_contract.py",
            "design_system_lib.py", "validate_design_system.py"
        ],
    },
    "run-verified-development-loop": {
        "assets": ["development-contract.schema.json", "run-record.schema.json", "design-system.schema.json"],
        "scripts": [
            "contract_lib.py", "architecture_lib.py", "validate_contract.py", "validate_yaml.py",
            "validate_run_record.py", "freeze_acceptance_tests.py", "attest_run_event.py",
            "design_system_lib.py", "validate_design_system.py"
        ],
    },
    "architecture-governance": {
        "assets": ["architecture.schema.json", "architecture-baseline.schema.json"],
        "scripts": [
            "validate_yaml.py", "finding_fingerprint.py", "architecture_lib.py",
            "approve_architecture.py", "validate_architecture.py", "validate_baseline.py"
        ],
    },
    "design-system-governance": {
        "assets": ["design-system.schema.json"],
        "scripts": [
            "design_system_lib.py", "validate_design_system.py", "approve_design_system.py"
        ],
    },
}

SPECIAL_FILES = {
    "prepare-development-cycle": {
        "assets/development-contract-template.yaml": ROOT / "templates/development-contract-template.yaml",
    },
}

RUNTIME_REQUIREMENTS = [
    "prepare-development-cycle", "run-verified-development-loop", "architecture-governance",
    "design-system-governance",
]


def sync(check: bool) -> int:
    drift: list[str] = []
    for skill, groups in MAPPINGS.items():
        skill_root = ROOT / "skills" / skill
        for group, names in groups.items():
            destination_dir = skill_root / group
            destination_dir.mkdir(parents=True, exist_ok=True)
            for name in names:
                source_dir = ROOT / ("schemas" if group == "assets" else "scripts")
                source = source_dir / name
                destination = destination_dir / name
                if check:
                    if not destination.is_file() or source.read_bytes() != destination.read_bytes():
                        drift.append(str(destination.relative_to(ROOT)))
                else:
                    shutil.copy2(source, destination)
    for skill, files in SPECIAL_FILES.items():
        for relative, source in files.items():
            destination = ROOT / "skills" / skill / relative
            if check:
                if not destination.is_file() or source.read_bytes() != destination.read_bytes():
                    drift.append(str(destination.relative_to(ROOT)))
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    requirements = ROOT / "requirements-lock.txt"
    for skill in RUNTIME_REQUIREMENTS:
        destination = ROOT / "skills" / skill / "requirements.txt"
        if check:
            if not destination.is_file() or requirements.read_bytes() != destination.read_bytes():
                drift.append(str(destination.relative_to(ROOT)))
        else:
            shutil.copy2(requirements, destination)
    if drift:
        print("Shared assets are out of sync:")
        for item in drift:
            print(f"- {item}")
        return 1
    if check:
        print("Shared skill assets are in sync")
    else:
        print("Synchronized shared skill assets")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return sync(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
