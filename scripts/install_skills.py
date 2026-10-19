#!/usr/bin/env python3
"""Install the repository's skills into supported agent discovery paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILLS = ROOT / "skills"
TARGET_PATHS = {
    "codex": {"user": Path("~/.agents/skills"), "project": Path(".agents/skills")},
    "claude": {"user": Path("~/.claude/skills"), "project": Path(".claude/skills")},
    "gemini": {"user": Path("~/.gemini/skills"), "project": Path(".gemini/skills")},
}
MANAGED_MARKER = ".vibeskills-managed.json"
IGNORE_SKILL_FILES = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def read_managed_marker(destination: Path, expected_skill: str) -> dict:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError(f"refusing to replace non-directory or symlink: {destination}")
    marker = destination / MANAGED_MARKER
    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"refusing to replace unmanaged directory: {destination}; remove it manually after review"
        ) from exc
    legacy = {"installer": "alex-ter-vibeskills", "skill": expected_skill}
    if metadata == legacy:
        return metadata
    if isinstance(metadata, dict):
        version = metadata.get("marker_version")
        if isinstance(version, (int, float)) and version > 2:
            raise ValueError(f"refusing to replace directory written by a newer installer: {destination}")
        if (
            set(metadata) == {
                "installer", "marker_version", "skill", "toolkit_version",
                "source_revision", "source_dirty", "installed_at", "files",
            }
            and metadata["installer"] == legacy["installer"]
            and type(version) is int and version == 2
            and metadata["skill"] == expected_skill
            and isinstance(metadata["toolkit_version"], str)
            and isinstance(metadata["installed_at"], str)
            and (
                metadata["source_revision"] is None
                or isinstance(metadata["source_revision"], str)
                and re.fullmatch(r"[0-9a-fA-F]{40}", metadata["source_revision"])
            )
            and (metadata["source_dirty"] is None or type(metadata["source_dirty"]) is bool)
            and isinstance(metadata["files"], dict)
            and all(
                isinstance(path, str) and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-fA-F]{64}", digest)
                for path, digest in metadata["files"].items()
            )
        ):
            return metadata
    raise ValueError(f"refusing to replace directory with an invalid ownership marker: {destination}")


def assert_managed_install(destination: Path, expected_skill: str) -> None:
    read_managed_marker(destination, expected_skill)


def toolkit_state() -> dict:
    revision = None
    dirty = None
    try:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            check=True, capture_output=True, text=True,
        ).stdout
        if re.fullmatch(r"[0-9a-fA-F]{40}", head):
            revision = head
            dirty = bool(status)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        pass
    return {
        "toolkit_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "source_revision": revision,
        "source_dirty": dirty,
    }


def file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path != directory / MANAGED_MARKER
        and not IGNORE_SKILL_FILES(directory, path.relative_to(directory).parts)
    }


def stage_skill(source: Path, staging_root: Path) -> Path:
    staged = staging_root / source.name
    shutil.copytree(
        source,
        staged,
        ignore=IGNORE_SKILL_FILES,
    )
    (staged / MANAGED_MARKER).write_text(
        json.dumps({
            "installer": "alex-ter-vibeskills",
            "marker_version": 2,
            "skill": source.name,
            **toolkit_state(),
            "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "files": file_hashes(staged),
        }, sort_keys=True) + "\n",
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


def check_skill(destination: Path, expected_skill: str, current: dict) -> tuple[str, str]:
    if not destination.exists() and not destination.is_symlink():
        return "missing", "skill directory does not exist"
    try:
        metadata = read_managed_marker(destination, expected_skill)
    except ValueError as exc:
        return "unmanaged", str(exc)
    if "marker_version" not in metadata:
        return "outdated", "legacy marker; installed version unknown"
    try:
        actual = file_hashes(destination)
    except OSError as exc:
        return "modified", f"cannot read installed files: {exc}"
    recorded = metadata["files"]
    changed = sum(actual.get(path) != recorded.get(path) for path in actual.keys() | recorded.keys())
    if changed:
        return "modified", f"{changed} changed, missing or added files"
    reasons = []
    for key in ("toolkit_version", "source_revision"):
        if metadata[key] != current[key]:
            reasons.append(f"{key}: installed {metadata[key]}, current {current[key]}")
    if metadata["source_dirty"] is True:
        reasons.append("installed from a dirty checkout")
    if reasons:
        return "outdated", "; ".join(reasons)
    return "current", f"version {metadata['toolkit_version']}; file hashes match"


def check_all(skills: list[Path], destinations: dict[str, Path]) -> int:
    current = toolkit_state()
    all_current = True
    for target, base in destinations.items():
        counts = dict.fromkeys(("missing", "unmanaged", "modified", "outdated", "current"), 0)
        for skill in skills:
            status, reason = check_skill(base / skill.name, skill.name, current)
            counts[status] += 1
            all_current = all_current and status == "current"
            print(f"{status} {target} {skill.name}: {reason}")
        print(f"Summary {target}: " + ", ".join(f"{status}={count}" for status, count in counts.items()))
    return 0 if all_current else 1


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
    parser.add_argument(
        "--check", action="store_true",
        help="Report installation freshness without changing any destination.",
    )
    args = parser.parse_args()
    if args.check and args.force:
        parser.error("--check cannot be combined with --force")

    try:
        destinations = resolve_destinations(
            args.target, args.scope, args.project_root.resolve(), args.destination
        )
        skills = sorted(path for path in SOURCE_SKILLS.iterdir() if path.is_dir())
        if args.check:
            return check_all(skills, destinations)
        install_all(skills, destinations, args.force)
        for target, base in destinations.items():
            print(f"Installed {len(skills)} skills for {target}: {base}")
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
