#!/usr/bin/env python3
"""Canonical hashing helpers for architecture manifests."""

from __future__ import annotations

import copy
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
