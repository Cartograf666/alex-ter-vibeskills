#!/usr/bin/env python3
"""Build byte-reproducible .skill archives and their checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
PACKAGES = ROOT / "packages"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_archive(skill_dir: Path, destination: Path) -> None:
    symlinks = [path for path in skill_dir.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError(f"skill contains symlinks: {', '.join(str(path) for path in symlinks)}")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(skill_dir).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.create_system = 3
            info.external_attr = (0o755 if path.suffix == ".py" else 0o644) << 16
            archive.writestr(info, path.read_bytes())
        license_info = zipfile.ZipInfo("LICENSE", FIXED_TIME)
        license_info.create_system = 3
        license_info.external_attr = 0o644 << 16
        archive.writestr(license_info, (ROOT / "LICENSE").read_bytes())
        version_info = zipfile.ZipInfo("VERSION", FIXED_TIME)
        version_info.create_system = 3
        version_info.external_attr = 0o644 << 16
        archive.writestr(version_info, (ROOT / "VERSION").read_bytes())


def build_all(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    archives = []
    for skill_dir in sorted(path for path in SKILLS.iterdir() if path.is_dir()):
        archive = destination / f"{skill_dir.name}.skill"
        build_archive(skill_dir, archive)
        archives.append(archive)
    manifest = destination / "SHA256SUMS"
    manifest.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in archives), encoding="utf-8"
    )
    return archives + [manifest]


def check() -> int:
    with tempfile.TemporaryDirectory() as raw_temp:
        generated = Path(raw_temp)
        expected = build_all(generated)
        drift = []
        for path in expected:
            committed = PACKAGES / path.name
            if not committed.is_file() or committed.read_bytes() != path.read_bytes():
                drift.append(path.name)
        expected_names = {path.name for path in expected}
        committed_names = {path.name for path in PACKAGES.iterdir() if path.is_file()}
        for extra in sorted(committed_names - expected_names):
            drift.append(f"unexpected:{extra}")
        if drift:
            print("Generated packages differ from committed artifacts:")
            for name in drift:
                print(f"- {name}")
            return 1
    print("Committed packages are reproducible and current")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    build_all(PACKAGES)
    print(f"Built packages in {PACKAGES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
