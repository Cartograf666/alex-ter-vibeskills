#!/usr/bin/env python3
"""Canonical hashing helpers for architecture manifests."""

from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
from typing import Any


def architecture_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(manifest)
    payload["status"] = "provisional"
    payload["approval"] = {
        "status": "pending",
        "approved_by": None,
        "approved_at": None,
        "manifest_sha256": None,
    }
    return payload


def architecture_payload_sha256(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(
        architecture_payload(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def path_patterns_overlap(left: str, right: str) -> bool:
    """Conservatively detect whether two repository path globs can overlap."""
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
