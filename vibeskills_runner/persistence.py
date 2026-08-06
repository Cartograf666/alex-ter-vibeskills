import json
import os
import re
import tempfile
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .errors import PersistenceError, ValidationError

RUN_ID_PATTERN = re.compile(r"^RUN-[A-Z0-9][A-Z0-9._-]*$")

# Strictly compliant RFC3339 timezone mandatory pattern: YYYY-MM-DDTHH:MM:SS[.fraction](Z|+HH:MM|-HH:MM)
RFC3339_REGEX = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(?:(Z)|([+-])(\d{2}):(\d{2}))$"
)


def validate_run_id(run_id: str) -> None:
    """Validate that the run ID matches the strict canonical pattern."""
    if not isinstance(run_id, str):
        raise ValidationError("run_id must be a string")
    if not RUN_ID_PATTERN.match(run_id):
        raise ValidationError(f"Invalid run_id format: '{run_id}'")


def verify_runs_path_confinement(resolved_path: Path, repository: Path) -> None:
    """Ensure that the resolved path lies strictly inside <repository>/.ai/runs/ and no symlinks exist."""
    ai_dir = repository / ".ai"
    runs_dir = ai_dir / "runs"
    if ai_dir.is_symlink() or os.path.islink(str(ai_dir)):
        raise ValidationError(f"Security breach: '{ai_dir}' is a symbolic link.")
    if runs_dir.is_symlink() or os.path.islink(str(runs_dir)):
        raise ValidationError(f"Security breach: '{runs_dir}' is a symbolic link.")

    runs_dir_resolved = runs_dir.resolve()
    resolved_abs = resolved_path.resolve()
    try:
        resolved_abs.relative_to(runs_dir_resolved)
    except ValueError as exc:
        raise ValidationError(
            f"Access denied: Path '{resolved_path}' is not within '{runs_dir_resolved}'"
        ) from exc


def validate_rfc3339(timestamp: Any) -> bool:
    """Validate if the string is a strictly compliant RFC3339 timestamp with mandatory timezone and calendar validation."""
    if not isinstance(timestamp, str):
        raise PersistenceError("Timestamp must be a string")

    match = RFC3339_REGEX.match(timestamp)
    if not match:
        raise PersistenceError(
            f"Timestamp '{timestamp}' does not match strict RFC3339 format."
        )

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    second = int(match.group(6))

    if not (1 <= month <= 12):
        raise PersistenceError(f"Invalid month in timestamp: {month}")

    try:
        # Check calendar date validity (rejects Feb 31, etc.)
        dt.date(year, month, day)
    except ValueError as e:
        raise PersistenceError(f"Invalid calendar date in timestamp: {e}") from e

    if hour >= 24 or minute >= 60 or second >= 60:
        raise PersistenceError(
            f"Time value out of range in timestamp: {hour:02d}:{minute:02d}:{second:02d}"
        )

    if match.group(8) != 'Z':
        tz_hours = int(match.group(10))
        tz_minutes = int(match.group(11))
        if tz_hours >= 24 or tz_minutes >= 60:
            raise PersistenceError(
                f"Timezone offset out of range: {match.group(9)}{tz_hours:02d}:{tz_minutes:02d}"
            )

    try:
        t = timestamp.replace("Z", "+00:00")
        dt.datetime.fromisoformat(t)
        return True
    except Exception as exc:
        raise PersistenceError(f"Invalid datetime parsing result: {exc}") from exc


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
    """Load, validate, and perform structural checks on the event journal."""
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

    # Structural validation of event objects and journal monotonicity
    seen_ids = set()
    last_seq = 0
    last_ts = None
    for idx, event in enumerate(events):
        seq = event.get("seq")
        evt_id = event.get("event_id")
        etype = event.get("type")
        actor = event.get("actor")
        timestamp = event.get("timestamp")
        data = event.get("data")

        if seq is None or not isinstance(seq, int) or seq <= 0:
            raise PersistenceError(
                f"Missing or invalid sequence number in event at index {idx}"
            )
        if evt_id is None or not isinstance(evt_id, str) or not evt_id:
            raise PersistenceError(
                f"Missing or invalid event ID in event at index {idx}"
            )
        if etype is None or not isinstance(etype, str) or not etype:
            raise PersistenceError(
                f"Missing or invalid type in event at index {idx}"
            )
        if actor is None or not isinstance(actor, str) or not actor:
            raise PersistenceError(
                f"Missing or invalid actor in event at index {idx}"
            )
        if timestamp is None:
            raise PersistenceError(
                f"Missing timestamp in event at index {idx}"
            )

        # Will raise PersistenceError if invalid RFC3339 format
        validate_rfc3339(timestamp)

        if data is None or not isinstance(data, dict):
            raise PersistenceError(
                f"Missing or invalid data payload in event at index {idx}"
            )

        # Monotonicity check of sequence numbers
        if seq != last_seq + 1:
            raise PersistenceError(
                f"Event sequence number is not monotonic: expected {last_seq + 1}, got {seq}"
            )
        # Duplicate check of event IDs
        if evt_id in seen_ids:
            raise PersistenceError(f"Duplicate event ID in journal: {evt_id}")

        # Monotonicity check of event timestamps
        current_dt = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if last_ts is not None:
            if current_dt < last_ts:
                raise PersistenceError(
                    f"Journal event timestamps are not monotonic: {timestamp} is earlier than previous."
                )
        last_ts = current_dt

        # Structural check for state transition type
        if etype == "state_transition":
            from_state = data.get("from")
            to_state = data.get("to")
            at_ts = data.get("at")
            reason = data.get("reason")
            if not isinstance(from_state, str) or not from_state:
                raise PersistenceError(f"Invalid from_state in transition event at index {idx}")
            if not isinstance(to_state, str) or not to_state:
                raise PersistenceError(f"Invalid to_state in transition event at index {idx}")
            if at_ts is None:
                raise PersistenceError(f"Missing at timestamp in transition event at index {idx}")
            validate_rfc3339(at_ts)
            if not isinstance(reason, str) or not reason:
                raise PersistenceError(f"Invalid reason in transition event at index {idx}")

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

    # Validate structure of the new event before writing
    temp_events = existing_events + [event]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "test_events.jsonl"
        with tmp_file.open("w", encoding="utf-8") as f:
            for ev in temp_events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        load_events(tmp_file)  # Will raise if invalid

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise PersistenceError(f"Failed to append to event journal {path}: {exc}") from exc
