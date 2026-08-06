import json
import unittest
import tempfile
from pathlib import Path
from vibeskills_runner.persistence import (
    load_yaml_safe,
    save_yaml_atomic,
    load_events,
    append_event,
    resolve_safe_path,
)
from vibeskills_runner.errors import PersistenceError, ValidationError


class TestRunnerPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.tempdir.name)
        # Create a mock schema file for testing
        self.schema_path = self.temp_path / "test-schema.json"
        self.schema_path.write_text(json.dumps({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["name", "value"],
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "integer"}
            }
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_load_yaml_safe_success(self) -> None:
        file_path = self.temp_path / "valid.yaml"
        file_path.write_text("name: test\nvalue: 42\n", encoding="utf-8")
        data = load_yaml_safe(file_path)
        self.assertEqual(data, {"name": "test", "value": 42})

    def test_load_yaml_safe_nonexistent(self) -> None:
        with self.assertRaises(PersistenceError):
            load_yaml_safe(self.temp_path / "missing.yaml")

    def test_load_yaml_safe_invalid_format(self) -> None:
        file_path = self.temp_path / "invalid.yaml"
        file_path.write_text("this is: : not valid yaml\n", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            load_yaml_safe(file_path)

    def test_save_yaml_atomic_success(self) -> None:
        file_path = self.temp_path / "output.yaml"
        data = {"name": "atomic", "value": 100}
        save_yaml_atomic(file_path, data, self.schema_path)
        # Check loaded data
        loaded = load_yaml_safe(file_path)
        self.assertEqual(loaded, data)

    def test_save_yaml_atomic_validation_failure(self) -> None:
        file_path = self.temp_path / "output.yaml"
        invalid_data = {"name": "invalid"}  # missing "value"
        with self.assertRaises(ValidationError):
            save_yaml_atomic(file_path, invalid_data, self.schema_path)
        # Check that file was not created
        self.assertFalse(file_path.exists())

    def test_load_events_empty(self) -> None:
        events_path = self.temp_path / "events.jsonl"
        self.assertEqual(load_events(events_path), [])

    def test_append_event_success(self) -> None:
        events_path = self.temp_path / "events.jsonl"
        event1 = {"seq": 1, "event_id": "EVT-1", "type": "test", "actor": "tester", "timestamp": "2026-07-20T12:00:00Z", "data": {}}
        event2 = {"seq": 2, "event_id": "EVT-2", "type": "test", "actor": "tester", "timestamp": "2026-07-20T12:01:00Z", "data": {}}
        append_event(events_path, event1)
        append_event(events_path, event2)

        loaded = load_events(events_path)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0], event1)
        self.assertEqual(loaded[1], event2)

    def test_append_event_out_of_sequence(self) -> None:
        events_path = self.temp_path / "events.jsonl"
        event1 = {"seq": 1, "event_id": "EVT-1", "type": "test", "actor": "tester", "timestamp": "2026-07-20T12:00:00Z", "data": {}}
        event3 = {"seq": 3, "event_id": "EVT-3", "type": "test", "actor": "tester", "timestamp": "2026-07-20T12:02:00Z", "data": {}}
        append_event(events_path, event1)
        with self.assertRaises(PersistenceError):
            append_event(events_path, event3)

    def test_append_event_duplicate_id(self) -> None:
        events_path = self.temp_path / "events.jsonl"
        event1 = {"seq": 1, "event_id": "EVT-1", "type": "test", "actor": "tester", "timestamp": "2026-07-20T12:00:00Z", "data": {}}
        event2 = {"seq": 2, "event_id": "EVT-1", "type": "test", "actor": "tester", "timestamp": "2026-07-20T12:01:00Z", "data": {}}  # duplicate ID
        append_event(events_path, event1)
        with self.assertRaises(PersistenceError):
            append_event(events_path, event2)

    def test_load_events_corrupted_jsonl(self) -> None:
        events_path = self.temp_path / "events.jsonl"
        events_path.write_text('{"seq": 1, "event_id": "EVT-1"}\n{invalid-json}\n', encoding="utf-8")
        with self.assertRaises(PersistenceError):
            load_events(events_path)

    def test_resolve_safe_path_valid(self) -> None:
        base = self.temp_path / "repo"
        base.mkdir()
        resolved = resolve_safe_path(base, "sub/dir/file.txt")
        self.assertEqual(resolved, (base / "sub/dir/file.txt").resolve())

    def test_resolve_safe_path_traversal(self) -> None:
        base = self.temp_path / "repo"
        base.mkdir()
        with self.assertRaises(ValidationError):
            resolve_safe_path(base, "../escaping.txt")
        with self.assertRaises(ValidationError):
            resolve_safe_path(base, "/etc/passwd")

    def test_validate_rfc3339_strict(self) -> None:
        from vibeskills_runner.persistence import validate_rfc3339

        # Valid cases
        self.assertTrue(validate_rfc3339("2026-07-20T12:00:00Z"))
        self.assertTrue(validate_rfc3339("2026-07-20T12:00:00.123Z"))
        self.assertTrue(validate_rfc3339("2026-07-20T12:00:00+03:00"))
        self.assertTrue(validate_rfc3339("2026-07-20T12:00:00-05:30"))

        # Invalid cases (must raise PersistenceError)
        with self.assertRaises(PersistenceError):
            validate_rfc3339("2026-02-31T12:00:00Z")  # invalid date (calendar check)
        with self.assertRaises(PersistenceError):
            validate_rfc3339("2026-07-20T25:00:00Z")  # invalid hour
        with self.assertRaises(PersistenceError):
            validate_rfc3339("2026-07-20 12:00:00Z")  # space separator
        with self.assertRaises(PersistenceError):
            validate_rfc3339("2026-07-20")  # date-only
        with self.assertRaises(PersistenceError):
            validate_rfc3339("2026-07-20T12:00:00")  # naive datetime
        with self.assertRaises(PersistenceError):
            validate_rfc3339(12345)  # non-string
