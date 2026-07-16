#!/usr/bin/env python3
"""Run repository-level structural and contract validation."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^]]*\]\(([^)]+)\)")


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def validate_skills() -> None:
    for skill in sorted((ROOT / "skills").iterdir()):
        if not skill.is_dir():
            continue
        skill_file = skill / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise ValueError(f"{skill_file}: missing leading frontmatter")
        _, raw_frontmatter, _ = text.split("---", 2)
        frontmatter = yaml.safe_load(raw_frontmatter)
        if set(frontmatter) != {"name", "description"}:
            raise ValueError(f"{skill_file}: frontmatter must contain only name and description")
        if frontmatter["name"] != skill.name:
            raise ValueError(f"{skill_file}: name must match directory")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill.name):
            raise ValueError(f"{skill_file}: invalid skill name")
        if text.count("\n") > 500:
            raise ValueError(f"{skill_file}: exceeds 500 lines")


def validate_links() -> None:
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        for target in LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            raw_target = target.split("#", 1)[0]
            if raw_target and not (path.parent / raw_target).resolve().exists():
                raise ValueError(f"{path}: broken local link {target}")


def validate_json() -> None:
    for path in (ROOT / "schemas").glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if schema_id and not schema_id.startswith(
            "https://raw.githubusercontent.com/Cartograf666/alex-ter-vibeskills/main/schemas/"
        ):
            raise ValueError(f"{path}: $id must use the resolvable canonical raw GitHub URL")


def validate_yaml_syntax() -> None:
    for path in list(ROOT.rglob("*.yaml")) + list(ROOT.rglob("*.yml")):
        if ".git" not in path.parts:
            yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_whitespace() -> None:
    text_suffixes = {".md", ".py", ".json", ".yaml", ".yml", ".txt"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "packages" in path.parts:
            continue
        if path.suffix not in text_suffixes and path.name not in {"VERSION", "SECURITY.md"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.endswith((" ", "\t")):
                raise ValueError(f"{path}:{number}: trailing whitespace")


def main() -> int:
    try:
        validate_skills()
        validate_links()
        validate_json()
        validate_yaml_syntax()
        validate_whitespace()
        run("python3", "scripts/sync_shared_assets.py", "--check")
        run("python3", "scripts/validate_contract.py", "examples/development-contract.yaml")
        run("python3", "scripts/validate_architecture.py", "examples/architecture.yaml")
        run("python3", "scripts/validate_baseline.py", "examples/architecture-baseline.yaml")
        run("python3", "scripts/validate_design_system.py", "examples/design-system.yaml")
        run("python3", "scripts/validate_yaml.py", "examples/run-record.yaml", "schemas/run-record.schema.json")
        run("python3", "scripts/validate_yaml.py", "evals/adversarial-cases.yaml", "schemas/adversarial-evals.schema.json")
        run("python3", "scripts/validate_yaml.py", "templates/development-contract-template.yaml", "schemas/development-contract.schema.json")
        run("python3", "-m", "unittest", "discover", "-s", "tests", "-v")
        run("python3", "scripts/package_skills.py", "--check")
        run("git", "diff", "--check")
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("Repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
