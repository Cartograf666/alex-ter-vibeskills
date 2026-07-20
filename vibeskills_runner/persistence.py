import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .errors import PersistenceError, ValidationError


def resolve_safe_path(base_dir: Path, relative_path_str: str) -> Path:
    """Ensure a path relative to the base directory does not escape it."""
    base_resolved = base_dir.resolve()
    resolved = (base_resolved / relative_path_str).resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValidationError(
            f"Path escapes repository root: {relative_path_str}"
        ) from exc
    return resolved


def load_yaml_safe(path: Path) -> Dict[str, Any]:
    """Load a YAML file safely. Raises PersistenceError on failure."""
    if not path.is_file():
        raise PersistenceError(f"File not found: {path}")
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise PersistenceError(f"YAML content is not a mapping: {path}")
        return data
    except yaml.YAMLError as exc:
        raise PersistenceError(f"Failed to parse YAML file {path}: {exc}") from exc
    except OSError as exc:
        raise PersistenceError(f"OS error reading YAML file {path}: {exc}") from exc


def validate_against_schema(data: Dict[str, Any], schema_path: Path) -> None:
    """Validate a record dictionary against the JSON schema."""
    if not schema_path.is_file():
        raise PersistenceError(f"Schema file not found: {schema_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PersistenceError(f"Failed to parse JSON schema {schema_path}: {exc}") from exc

    errors = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for item in sorted(validator.iter_errors(data), key=lambda err: list(err.path)):
        location = ".".join(str(part) for part in item.path) or "<root>"
        errors.append(f"{location}: {item.message}")
    if errors:
        raise ValidationError(
            "Schema validation errors:\n" + "\n".join(f"- {e}" for e in errors)
        )


def save_yaml_atomic(path: Path, data: Dict[str, Any], schema_path: Path) -> None:
    """Atomically save a YAML mapping after validating it against the schema."""
    validate_against_schema(data, schema_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        os.replace(temp_path, path)
    except Exception as exc:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise PersistenceError(f"Atomic write to {path} failed: {exc}") from exc


def load_events(path: Path) -> List[Dict[str, Any]]:
    """Load and validate the append-only event journal from JSONL format."""
    if not path.is_file():
        return []
    events = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise PersistenceError(
                            f"Line {line_num} in event journal is not a JSON object"
                        )
                    events.append(event)
                except json.JSONDecodeError as exc:
                    raise PersistenceError(
                        f"Failed to decode JSON event at line {line_num} in {path}: {exc}"
                    ) from exc
    except OSError as exc:
        raise PersistenceError(f"OS error reading event journal {path}: {exc}") from exc

    # Validate monotonic sequence numbers and event ID uniqueness
    seen_ids = set()
    last_seq = 0
    for idx, event in enumerate(events):
        seq = event.get("seq")
        evt_id = event.get("event_id")
        if seq is None or not isinstance(seq, int):
            raise PersistenceError(
                f"Missing or invalid sequence number in event at index {idx}"
            )
        if evt_id is None or not isinstance(evt_id, str):
            raise PersistenceError(
                f"Missing or invalid event ID in event at index {idx}"
            )

        if seq != last_seq + 1:
            raise PersistenceError(
                f"Event sequence number is not monotonic: expected {last_seq + 1}, got {seq}"
            )
        if evt_id in seen_ids:
            raise PersistenceError(f"Duplicate event ID in journal: {evt_id}")

        seen_ids.add(evt_id)
        last_seq = seq

    return events


def append_event(path: Path, event: Dict[str, Any]) -> None:
    """Load the journal, validate the new event's sequence and uniqueness, and append it."""
    existing_events = load_events(path)

    expected_seq = len(existing_events) + 1
    new_seq = event.get("seq")
    if new_seq != expected_seq:
        raise PersistenceError(
            f"New event sequence number must be {expected_seq}, got {new_seq}"
        )

    new_id = event.get("event_id")
    if not new_id:
        raise PersistenceError("New event must have an event_id")
    if any(e.get("event_id") == new_id for e in existing_events):
        raise PersistenceError(f"Event ID {new_id} already exists in the journal")

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise PersistenceError(f"Failed to append to event journal {path}: {exc}") from exc
