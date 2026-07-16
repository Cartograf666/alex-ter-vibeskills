#!/usr/bin/env python3
"""Canonical hashing helpers for design-system manifests."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def design_system_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(manifest)
    payload["status"] = "provisional"
    payload["approval"] = {
        "status": "pending", "approved_by": None, "approved_at": None,
        "artifact_hashes": {}, "manifest_sha256": None,
    }
    return payload


def design_system_payload_sha256(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(
        design_system_payload(manifest), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def design_system_artifact_paths(manifest: dict[str, Any]) -> list[str]:
    return sorted(set(
        manifest["tokens"]["source_paths"]
        + manifest["components"]["registry_paths"]
        + manifest["components"]["documentation_paths"]
    ))


def sha256_path(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return digest.hexdigest()
    raise FileNotFoundError(path)


def design_system_artifact_hashes(
    manifest: dict[str, Any], repository: Path
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for raw_path in design_system_artifact_paths(manifest):
        path = (repository / raw_path).resolve()
        try:
            path.relative_to(repository.resolve())
        except ValueError as exc:
            raise ValueError(f"design-system artifact escapes repository: {raw_path}") from exc
        hashes[raw_path] = sha256_path(path)
    return hashes
