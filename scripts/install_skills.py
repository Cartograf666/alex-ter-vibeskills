#!/usr/bin/env python3
"""Install the repository's skills into supported agent discovery paths."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILLS = ROOT / "skills"
TARGET_PATHS = {
    "codex": {"user": Path("~/.agents/skills"), "project": Path(".agents/skills")},
    "claude": {"user": Path("~/.claude/skills"), "project": Path(".claude/skills")},
    "gemini": {"user": Path("~/.gemini/skills"), "project": Path(".gemini/skills")},
}


def copy_skill(source: Path, destination: Path, force: bool) -> None:
    if destination.exists():
        if not force:
            raise FileExistsError(
                f"{destination} already exists; rerun with --force to replace it"
            )
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def resolve_destinations(
    target: str, scope: str, project_root: Path, destination: Path | None
) -> dict[str, Path]:
    targets = list(TARGET_PATHS) if target == "all" else [target]
    if destination:
        if len(targets) != 1:
            raise ValueError("--destination cannot be combined with --target all")
        return {targets[0]: destination.expanduser().resolve()}
    resolved = {}
    for name in targets:
        configured = TARGET_PATHS[name][scope]
        base = configured.expanduser() if scope == "user" else project_root / configured
        resolved[name] = base.resolve()
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install all Verified Development Skills for an agent host."
    )
    parser.add_argument(
        "--target", choices=[*TARGET_PATHS, "all"], required=True,
        help="Agent host whose discovery path should receive the skills.",
    )
    parser.add_argument(
        "--scope", choices=["user", "project"], default="project",
        help="Install for the current project or the current user (default: project).",
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(),
        help="Project root used for project-scoped installation.",
    )
    parser.add_argument(
        "--destination", type=Path,
        help="Advanced: override the discovery directory for one target.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Replace skill directories that already exist.",
    )
    args = parser.parse_args()

    try:
        destinations = resolve_destinations(
            args.target, args.scope, args.project_root.resolve(), args.destination
        )
        skills = sorted(path for path in SOURCE_SKILLS.iterdir() if path.is_dir())
        for target, base in destinations.items():
            base.mkdir(parents=True, exist_ok=True)
            for skill in skills:
                copy_skill(skill, base / skill.name, args.force)
            print(f"Installed {len(skills)} skills for {target}: {base}")
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
