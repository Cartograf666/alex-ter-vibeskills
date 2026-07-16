#!/usr/bin/env python3
"""Install the repository's skills into supported agent discovery paths."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILLS = ROOT / "skills"
TARGET_PATHS = {
    "codex": {"user": Path("~/.agents/skills"), "project": Path(".agents/skills")},
    "claude": {"user": Path("~/.claude/skills"), "project": Path(".claude/skills")},
    "gemini": {"user": Path("~/.gemini/skills"), "project": Path(".gemini/skills")},
}
MANAGED_MARKER = ".vibeskills-managed.json"


def assert_managed_install(destination: Path, expected_skill: str) -> None:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError(f"refusing to replace non-directory or symlink: {destination}")
    marker = destination / MANAGED_MARKER
    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"refusing to replace unmanaged directory: {destination}; remove it manually after review"
        ) from exc
    if metadata != {"installer": "alex-ter-vibeskills", "skill": expected_skill}:
        raise ValueError(f"refusing to replace directory with an invalid ownership marker: {destination}")


def stage_skill(source: Path, staging_root: Path) -> Path:
    staged = staging_root / source.name
    shutil.copytree(
        source,
        staged,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )
    (staged / MANAGED_MARKER).write_text(
        json.dumps({"installer": "alex-ter-vibeskills", "skill": source.name}) + "\n",
        encoding="utf-8",
    )
    return staged


def swap_staged_skill(staged: Path, destination: Path, backup: Path) -> bool:
    had_previous = destination.exists()
    if had_previous:
        destination.rename(backup)
    try:
        staged.rename(destination)
    except OSError:
        if had_previous and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    return had_previous


def install_all(skills: list[Path], destinations: dict[str, Path], force: bool) -> None:
    """Stage every skill, then swap all destinations with operation-wide rollback."""
    preflight_install(skills, destinations, force)
    staging_roots: list[Path] = []
    preserve_recovery = False
    try:
        staged_items: list[tuple[Path, Path, Path, Path]] = []
        for target, base in destinations.items():
            base.mkdir(parents=True, exist_ok=True)
            staging_root = Path(
                tempfile.mkdtemp(prefix=f".vibeskills-{target}-", dir=base)
            )
            staging_roots.append(staging_root)
            for skill in skills:
                staged = stage_skill(skill, staging_root)
                destination = base / skill.name
                backup = staging_root / f"{skill.name}.previous"
                staged_items.append((staged, destination, backup, staging_root))

        completed: list[tuple[Path, Path, bool, Path]] = []
        try:
            for staged, destination, backup, staging_root in staged_items:
                had_previous = swap_staged_skill(staged, destination, backup)
                completed.append((destination, backup, had_previous, staging_root))
        except OSError as exc:
            rollback_errors: list[str] = []
            for index, (destination, backup, had_previous, staging_root) in enumerate(
                reversed(completed), 1
            ):
                try:
                    if destination.exists():
                        destination.rename(staging_root / f"rollback-new-{index}")
                    if had_previous and backup.exists():
                        backup.rename(destination)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{destination}: {rollback_exc}")
            retained = [
                str(backup) for _, _, backup, _ in staged_items if backup.exists()
            ]
            if rollback_errors or retained:
                preserve_recovery = True
                details = "; ".join([*rollback_errors, *retained])
                raise OSError(
                    f"installation failed; recovery data retained for manual restore: {details}"
                ) from exc
            raise
    finally:
        if not preserve_recovery:
            for staging_root in staging_roots:
                shutil.rmtree(staging_root, ignore_errors=True)


def preflight_install(skills: list[Path], destinations: dict[str, Path], force: bool) -> None:
    """Validate every replacement before changing any destination."""
    for base in destinations.values():
        for skill in skills:
            destination = base / skill.name
            if not destination.exists():
                continue
            if not force:
                raise FileExistsError(
                    f"{destination} already exists; rerun with --force to replace it"
                )
            assert_managed_install(destination, skill.name)


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
        install_all(skills, destinations, args.force)
        for target, base in destinations.items():
            print(f"Installed {len(skills)} skills for {target}: {base}")
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
