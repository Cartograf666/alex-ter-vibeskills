from __future__ import annotations

import copy
import datetime as dt
import hashlib
import hmac
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from tests.test_contract_tools import base_contract
from tests.eval_coverage import covers_adversarial


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/run-record.schema.json"
FREEZE = ROOT / "scripts/freeze_acceptance_tests.py"
VALIDATE = ROOT / "scripts/validate_run_record.py"
ATTEST = ROOT / "scripts/attest_run_event.py"
APPROVE_CONTRACT = ROOT / "scripts/approve_contract.py"
CONTRACT_SCHEMA = ROOT / "schemas/development-contract.schema.json"


def run(*args: str, cwd: Path, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    runtime_env = os.environ.copy()
    if env:
        runtime_env.update(env)
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check, env=runtime_env)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def attestation_hmac(action: str, payload_hash: str, event_id: str, actor: str) -> str:
    message = "\n".join(["default", action, payload_hash, event_id, actor]).encode()
    return hmac.new(b"test-host-secret-with-at-least-32-bytes", message, hashlib.sha256).hexdigest()


EXECUTION_FIELDS = (
    "exit_code", "started_at", "finished_at", "log_path", "log_sha256",
    "execution_environment", "execution_event_id", "execution_hmac_sha256",
)


def not_run_result(result: dict) -> dict:
    result = copy.deepcopy(result)
    result.update({field: None for field in EXECUTION_FIELDS})
    result.update(status="not-run", failure_class="environment", note="Test runtime unavailable.")
    return result


def sign_gate_result(result: dict) -> None:
    payload = canonical_sha256({key: result[key] for key in (
        "gate_id", "command_sha256", "status", "failure_class", "resolved_inputs",
        "revision", "tree_sha256", "exit_code", "started_at", "finished_at",
        "log_sha256", "execution_environment",
    )})
    result["execution_hmac_sha256"] = attestation_hmac(
        f"gate-result:{result['gate_id']}", payload, result["execution_event_id"], "trusted-executor"
    )


def sign_run_record(record: dict) -> None:
    payload = copy.deepcopy(record)
    payload["run_attestation"] = {
        "event_id": None, "actor": None, "payload_sha256": None, "hmac_sha256": None,
    }
    payload_hash = canonical_sha256(payload)
    attestation = record["run_attestation"]
    attestation["payload_sha256"] = payload_hash
    attestation["hmac_sha256"] = attestation_hmac(
        "accepted-run", payload_hash, attestation["event_id"], attestation["actor"]
    )


def gate_schema_errors(result: dict) -> list:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        {"$defs": schema["$defs"], "$ref": "#/$defs/gateResult"}, format_checker=FormatChecker()
    )
    return list(validator.iter_errors(result))


class RunRecordToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        run("git", "init", "-b", "main", cwd=self.repo)
        run("git", "config", "user.name", "Test User", cwd=self.repo)
        run("git", "config", "user.email", "test@example.com", cwd=self.repo)
        (self.repo / "acceptance_test.py").write_text("assert 1 + 1 == 2\n", encoding="utf-8")
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Add acceptance test", cwd=self.repo)
        self.head = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        record = yaml.safe_load((ROOT / "examples/run-record.yaml").read_text(encoding="utf-8"))
        record["base_revision"] = self.head
        record["current_revision"] = self.head
        tree_listing = run("git", "ls-tree", "-r", "--full-tree", self.head, cwd=self.repo).stdout.encode()
        record["current_tree_sha256"] = hashlib.sha256(tree_listing).hexdigest()
        self.record_path = self.repo / "run.yaml"
        self.write_record(record)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_record(self, record: dict) -> None:
        self.record_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")

    def validate(self, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run(
            "python3", str(VALIDATE), str(self.record_path),
            "--schema", str(SCHEMA), "--repository", str(self.repo), "--allow-unbound",
            cwd=self.repo, check=check,
        )

    def prepare_accepted_run(
        self, gate_requires_approval: bool = False, unexplained_change: bool = False
    ) -> tuple[dict, Path]:
        contract = base_contract()
        contract["automation"]["policy_sources"] = [
            {"source": "task", "mode": "bounded-auto"}
        ]
        contract["automation"]["effective_mode"] = "bounded-auto"
        contract["quality_gates"][0]["requires_approval"] = gate_requires_approval
        (self.repo / "PRD.md").write_text(
            "# PRD\n\n- FR-1: Reject invalid input.\n- AC-1: Invalid input returns the documented validation error.\n",
            encoding="utf-8",
        )
        (self.repo / "test_runner.py").write_text("print('ok')\n", encoding="utf-8")
        contract_path = self.repo / "development-contract.yaml"
        contract_path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Add development contract", cwd=self.repo)
        run(
            "python3", str(APPROVE_CONTRACT), str(contract_path),
            "--approved-by", "owner@example.com", "--repository", str(self.repo), cwd=self.repo,
        )
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Approve development contract", cwd=self.repo)
        base_head = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        if unexplained_change:
            (self.repo / "src" / "services").mkdir(parents=True)
            (self.repo / "src" / "services" / "unexplained.py").write_text("value = 1\n", encoding="utf-8")
            run("git", "add", ".", cwd=self.repo)
            run("git", "commit", "-m", "Unexplained direct commit", cwd=self.repo)
        head = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        tree = hashlib.sha256(
            run("git", "ls-tree", "-r", "--full-tree", head, cwd=self.repo).stdout.encode()
        ).hexdigest()
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        artifacts = self.repo / ".ai" / "runs"
        artifacts.mkdir(parents=True)
        (artifacts / "gate.log").write_text("1 test passed\n", encoding="utf-8")
        (artifacts / "evidence.txt").write_text("AC-1 verified\n", encoding="utf-8")
        (artifacts / "review.md").write_text("No blocking findings.\n", encoding="utf-8")
        record = yaml.safe_load((ROOT / "examples/run-record.yaml").read_text(encoding="utf-8"))
        record.update({
            "run_id": "RUN-TEST-ACCEPTED",
            "contract_id": contract["contract_id"],
            "contract_payload_sha256": contract["approval"]["contract_payload_sha256"],
            "state": "COMPLETE", "terminal_status": "accepted",
            "base_revision": base_head, "current_revision": head, "current_tree_sha256": tree,
        })
        record["roles"] = [
            {"role": "manager", "provider": "local", "model": "manager", "model_version": "1", "context_id": "manager-1", "permissions": ["read"]},
            {"role": "tester", "provider": "local", "model": "tester", "model_version": "1", "context_id": "tester-1", "permissions": ["tests"]},
            {"role": "writer", "provider": "local", "model": "writer", "model_version": "1", "context_id": "writer-1", "permissions": ["write"]},
            {"role": "reviewer", "provider": "local", "model": "reviewer", "model_version": "1", "context_id": "reviewer-1", "permissions": ["read"]},
        ]
        record["acceptance_test_manifest"] = {
            "frozen": True, "frozen_at_state": "TEST_DESIGN", "owner_context_id": "tester-1",
            "files": [{"path": "acceptance_test.py", "sha256": hashlib.sha256((self.repo / "acceptance_test.py").read_bytes()).hexdigest()}],
        }
        record["gate_results"] = [{
            "gate_id": "GATE-TEST",
            "status": "passed", "failure_class": None, "note": None,
            "command_sha256": hashlib.sha256(b"python3 test_runner.py").hexdigest(),
            "resolved_inputs": [{"path": "test_runner.py", "sha256": hashlib.sha256((self.repo / "test_runner.py").read_bytes()).hexdigest()}],
            "revision": head, "tree_sha256": tree, "exit_code": 0,
            "started_at": "2026-07-16T00:00:00Z", "finished_at": "2026-07-16T00:00:01Z",
            "log_path": ".ai/runs/gate.log", "log_sha256": hashlib.sha256((artifacts / "gate.log").read_bytes()).hexdigest(),
            "execution_environment": {"sandbox": "applied", "network": "deny", "secrets": "none", "log_redaction": "not-required"},
            "execution_event_id": "gate-execution-1", "execution_hmac_sha256": "0" * 64,
        }]
        sign_gate_result(record["gate_results"][0])
        record["acceptance_results"] = [{
            "criterion_id": "AC-1", "status": "passed", "evidence_paths": [{
                "path": ".ai/runs/evidence.txt",
                "sha256": hashlib.sha256((artifacts / "evidence.txt").read_bytes()).hexdigest(),
                "gate_ids": ["GATE-TEST"],
            }],
        }]
        record["review"] = {
            "verdict": "approve", "reviewer_context_id": "reviewer-1", "independence": "same-provider-fresh-context",
            "reviewed_revision": head, "reviewed_tree_sha256": tree,
            "findings_path": ".ai/runs/review.md", "findings_sha256": hashlib.sha256((artifacts / "review.md").read_bytes()).hexdigest(),
            "review_event_id": "review-execution-1", "review_hmac_sha256": "0" * 64,
        }
        review_payload = canonical_sha256({
            "verdict": record["review"]["verdict"], "reviewer_context_id": record["review"]["reviewer_context_id"],
            "independence": record["review"]["independence"], "reviewed_revision": record["review"]["reviewed_revision"],
            "reviewed_tree_sha256": record["review"]["reviewed_tree_sha256"],
            "findings_sha256": record["review"]["findings_sha256"],
        })
        record["review"]["review_hmac_sha256"] = attestation_hmac(
            "review-result", review_payload, "review-execution-1", "reviewer-1"
        )
        states = ["DISCOVER", "SPECIFY", "PLAN", "TEST_DESIGN", "IMPLEMENT", "VERIFY", "REVIEW", "ACCEPT", "COMPLETE"]
        record["state_transitions"] = [
            {"from": "START" if index == 0 else states[index - 1], "to": state, "at": f"2026-07-16T00:00:{index:02d}Z", "reason": "verified transition"}
            for index, state in enumerate(states)
        ]
        record["budgets"]["implementation_attempts"] = 1
        record["budgets"]["review_rounds"] = 1
        record["budgets"]["max_observed_parallel_writers"] = 1
        record["run_attestation"] = {
            "event_id": "accepted-run-1", "actor": "trusted-orchestrator",
            "payload_sha256": None, "hmac_sha256": None,
        }
        record["attestation_key_id"] = "default"
        sign_run_record(record)
        self.record_path = artifacts / "run.yaml"
        self.write_record(record)
        return record, contract_path

    def validate_with_contract(
        self, contract_path: Path, check: bool = True, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        runtime_env = {"VIBESKILLS_RUN_HMAC_KEY": "test-host-secret-with-at-least-32-bytes"}
        if env:
            runtime_env.update(env)
        return run(
            "python3", str(VALIDATE), str(self.record_path), "--schema", str(SCHEMA),
            "--contract-schema", str(CONTRACT_SCHEMA), "--repository", str(self.repo),
            "--contract", str(contract_path), cwd=self.repo, check=check,
            env=runtime_env,
        )

    def test_attest_run_event_cli_signs_precomputed_payload(self) -> None:
        payload = "a" * 64
        result = run(
            "python3", str(ATTEST), "--payload-sha256", payload,
            "--event-id", "event-1", "--actor", "trusted-host", cwd=self.repo,
            env={"VIBESKILLS_RUN_HMAC_KEY": "test-host-secret-with-at-least-32-bytes"},
        )
        expected = attestation_hmac("accepted-run", payload, "event-1", "trusted-host")
        self.assertIn(f"payload_sha256: {payload}", result.stdout)
        self.assertIn(f"hmac_sha256: {expected}", result.stdout)

    def test_attest_run_event_cli_signs_canonical_record_payload(self) -> None:
        record = yaml.safe_load(self.record_path.read_text(encoding="utf-8"))
        payload = canonical_sha256({
            **record,
            "run_attestation": {
                "event_id": None, "actor": None, "payload_sha256": None, "hmac_sha256": None,
            },
        })
        result = run(
            "python3", str(ATTEST), "--record", str(self.record_path),
            "--event-id", "event-record-1", "--actor", "trusted-host", cwd=self.repo,
            env={"VIBESKILLS_RUN_HMAC_KEY": "test-host-secret-with-at-least-32-bytes"},
        )
        expected = attestation_hmac("accepted-run", payload, "event-record-1", "trusted-host")
        self.assertIn(f"payload_sha256: {payload}", result.stdout)
        self.assertIn(f"hmac_sha256: {expected}", result.stdout)

    def test_attest_run_event_record_input_fails_cleanly_and_is_mutually_exclusive(self) -> None:
        malformed = self.repo / "bad-run.yaml"
        malformed.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
        bad_record = run(
            "python3", str(ATTEST), "--record", str(malformed),
            "--event-id", "event-1", "--actor", "trusted-host", cwd=self.repo, check=False,
            env={"VIBESKILLS_RUN_HMAC_KEY": "test-host-secret-with-at-least-32-bytes"},
        )
        self.assertNotEqual(bad_record.returncode, 0)
        self.assertIn("run-record YAML mapping", bad_record.stderr)
        self.assertNotIn("Traceback", bad_record.stderr)
        exclusive = run(
            "python3", str(ATTEST), "--record", str(self.record_path),
            "--payload-sha256", "a" * 64, "--event-id", "event-1", "--actor", "trusted-host",
            cwd=self.repo, check=False,
        )
        self.assertNotEqual(exclusive.returncode, 0)
        self.assertIn("not allowed with argument", exclusive.stderr)

    def test_attest_run_event_rejects_yaml_native_values_without_traceback(self) -> None:
        native_value = self.repo / "native-value-run.yaml"
        native_value.write_text(
            "run_attestation:\n  event_id: null\n  actor: null\n  payload_sha256: null\n  hmac_sha256: null\ncreated: 2026-07-16\n",
            encoding="utf-8",
        )
        result = run(
            "python3", str(ATTEST), "--record", str(native_value),
            "--event-id", "event-1", "--actor", "trusted-host", cwd=self.repo, check=False,
            env={"VIBESKILLS_RUN_HMAC_KEY": "test-host-secret-with-at-least-32-bytes"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not canonically JSON-serializable", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_attest_run_event_rejects_malformed_keyring_without_traceback(self) -> None:
        result = run(
            "python3", str(ATTEST), "--payload-sha256", "a" * 64,
            "--event-id", "event-1", "--actor", "trusted-host", cwd=self.repo,
            check=False, env={"VIBESKILLS_RUN_HMAC_KEYS": "{not-json"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must contain valid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    @covers_adversarial("EVAL-WRITER-TEST-TAMPER")
    def test_frozen_test_hash_detects_tampering(self) -> None:
        run(
            "python3", str(FREEZE), str(self.record_path), "acceptance_test.py",
            "--owner-context-id", "manager-context-001",
            "--repository", str(self.repo), cwd=self.repo,
        )
        self.validate()
        (self.repo / "acceptance_test.py").write_text("assert True\n", encoding="utf-8")
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("frozen acceptance test changed", result.stderr)

    def test_artifact_inventory_rejects_missing_packet(self) -> None:
        record = yaml.safe_load(self.record_path.read_text(encoding="utf-8"))
        record["artifacts"]["task_packets"] = [{"path": ".ai/runs/missing.json", "sha256": "0" * 64}]
        self.write_record(record)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact is missing or changed", result.stderr)

    def test_contract_is_required_unless_unbound_mode_is_explicit(self) -> None:
        result = run(
            "python3", str(VALIDATE), str(self.record_path), "--schema", str(SCHEMA),
            "--repository", str(self.repo), cwd=self.repo, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --contract", result.stderr)
        unbound = self.validate()
        self.assertIn("WARNING: unbound validation", unbound.stderr)
        self.assertNotIn("WARNING: unbound validation", unbound.stdout)

    def test_schema_invalid_contract_reports_errors_without_keyerror(self) -> None:
        invalid_contract = self.repo / "invalid-contract.yaml"
        invalid_contract.write_text("schema_version: 3\n", encoding="utf-8")
        result = self.validate_with_contract(invalid_contract, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("contract.<root>", result.stderr)
        self.assertNotIn("KeyError", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    @covers_adversarial("EVAL-FAKE-INDEPENDENCE")
    def test_accepted_run_rejects_non_independent_review(self) -> None:
        record = yaml.safe_load(self.record_path.read_text(encoding="utf-8"))
        record["state"] = "COMPLETE"
        record["terminal_status"] = "accepted"
        record["review"].update(
            {
                "verdict": "approve",
                "reviewer_context_id": "manager-context-001",
                "independence": "not-independent",
                "reviewed_revision": self.head,
            }
        )
        self.write_record(record)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires an independent", result.stderr)

    def test_valid_accepted_run_is_bound_to_repository_facts(self) -> None:
        _, contract_path = self.prepare_accepted_run()
        result = self.validate_with_contract(contract_path, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Valid run record", result.stdout)

    def test_schema_2_run_record_is_rejected(self) -> None:
        record = yaml.safe_load(self.record_path.read_text(encoding="utf-8"))
        record["schema_version"] = 2
        self.write_record(record)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema_version", result.stderr)

    @covers_adversarial("EVAL-GATE-STATUS-FORGERY")
    def test_gate_status_must_match_exit_code(self) -> None:
        baseline, contract_path = self.prepare_accepted_run()
        for status, exit_code, failure_class in (
            ("passed", 1, None), ("failed", 0, "product-defect"),
        ):
            with self.subTest(status=status):
                record = copy.deepcopy(baseline)
                gate = record["gate_results"][0]
                gate.update(status=status, exit_code=exit_code, failure_class=failure_class)
                self.assertEqual(gate_schema_errors(gate), [])
                sign_gate_result(gate)
                sign_run_record(record)
                self.write_record(record)
                result = self.validate_with_contract(contract_path, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"gate GATE-TEST {status} status requires exit_code", result.stderr)
                self.assertNotIn("host attestation HMAC is invalid", result.stderr)

    def test_gate_failure_class_schema_rules(self) -> None:
        record, _ = self.prepare_accepted_run()
        original = record["gate_results"][0]
        classes = ("product-defect", "test-defect", "environment", "flaky", "pre-existing")
        for status in ("passed", "failed", "not-run"):
            for failure_class in (None,) + classes + ("unknown",):
                with self.subTest(status=status, failure_class=failure_class):
                    gate = not_run_result(original) if status == "not-run" else copy.deepcopy(original)
                    gate.update(status=status, failure_class=failure_class)
                    valid = failure_class is None if status == "passed" else failure_class in classes
                    self.assertEqual(not gate_schema_errors(gate), valid)

    def test_gate_outcome_and_state_pins_are_required(self) -> None:
        record, _ = self.prepare_accepted_run()
        for original in (record["gate_results"][0], not_run_result(record["gate_results"][0])):
            for field in ("status", "failure_class", "note", "gate_id", "command_sha256",
                          "resolved_inputs", "revision", "tree_sha256"):
                with self.subTest(status=original["status"], field=field):
                    gate = copy.deepcopy(original)
                    del gate[field]
                    self.assertTrue(gate_schema_errors(gate))
                    if field not in ("failure_class", "note"):
                        gate[field] = None
                        self.assertTrue(gate_schema_errors(gate))

    def test_executed_gate_fields_cannot_be_null(self) -> None:
        record, _ = self.prepare_accepted_run()
        for status in ("passed", "failed"):
            for field in EXECUTION_FIELDS[:6]:
                with self.subTest(status=status, field=field):
                    gate = copy.deepcopy(record["gate_results"][0])
                    gate.update(status=status, failure_class=None if status == "passed" else "test-defect")
                    gate[field] = None
                    self.assertTrue(gate_schema_errors(gate))

    def test_not_run_schema_rejects_every_execution_field(self) -> None:
        record, _ = self.prepare_accepted_run()
        original = record["gate_results"][0]
        gate = not_run_result(original)
        self.assertEqual(gate_schema_errors(gate), [])
        for field in EXECUTION_FIELDS:
            with self.subTest(field=field):
                invalid = copy.deepcopy(gate)
                invalid[field] = original[field]
                self.assertTrue(gate_schema_errors(invalid))

    def test_gate_note_schema_rules(self) -> None:
        record, _ = self.prepare_accepted_run()
        for status in ("passed", "failed", "not-run"):
            for note in (None, "", "Reason", "x" * 500, "x" * 501):
                with self.subTest(status=status, length=None if note is None else len(note)):
                    gate = not_run_result(record["gate_results"][0]) if status == "not-run" else copy.deepcopy(record["gate_results"][0])
                    gate.update(status=status, note=note)
                    if status == "failed":
                        gate["failure_class"] = "flaky"
                    valid = (note is None or len(note) <= 500) and (status != "not-run" or bool(note))
                    self.assertEqual(not gate_schema_errors(gate), valid)

    @covers_adversarial("EVAL-GATE-NOT-RUN-AS-PASS")
    def test_accepted_run_rejects_only_not_run_gate(self) -> None:
        record, contract_path = self.prepare_accepted_run(gate_requires_approval=True)
        record["gate_results"] = [not_run_result(record["gate_results"][0])]
        sign_run_record(record)
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted gate set differs from contract: missing=['GATE-TEST']", result.stderr)
        self.assertNotIn("host attestation", result.stderr)
        self.assertNotIn("payload-bound approval", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_accepted_run_allows_attested_failed_history(self) -> None:
        baseline, contract_path = self.prepare_accepted_run()
        previous = run("git", "rev-parse", "HEAD^", cwd=self.repo).stdout.strip()
        for revision in (baseline["current_revision"], previous):
            with self.subTest(revision=revision):
                record = copy.deepcopy(baseline)
                failed = copy.deepcopy(record["gate_results"][0])
                failed.update(status="failed", exit_code=1, failure_class="test-defect",
                              revision=revision, execution_event_id="gate-failed-1")
                failed["tree_sha256"] = hashlib.sha256(
                    run("git", "ls-tree", "-r", "--full-tree", revision, cwd=self.repo).stdout.encode()
                ).hexdigest()
                sign_gate_result(failed)
                record["gate_results"].insert(0, failed)
                sign_run_record(record)
                self.write_record(record)
                result = self.validate_with_contract(contract_path, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_history_still_requires_host_attestation(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        failed = copy.deepcopy(record["gate_results"][0])
        failed.update(status="failed", exit_code=1, failure_class="pre-existing",
                      execution_event_id=None, execution_hmac_sha256=None)
        record["gate_results"].append(failed)
        sign_run_record(record)
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gate-result:GATE-TEST host attestation is incomplete", result.stderr)

    def test_gate_attestation_binds_status_and_failure_class(self) -> None:
        baseline, contract_path = self.prepare_accepted_run()
        failed = copy.deepcopy(baseline["gate_results"][0])
        failed.update(status="failed", exit_code=1, failure_class="environment",
                      execution_event_id="gate-failed-1")
        sign_gate_result(failed)
        for mutation in (
            {"failure_class": "flaky"},
            {"status": "passed", "failure_class": None, "exit_code": 0},
        ):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(baseline)
                forged = copy.deepcopy(failed)
                forged.update(mutation)
                self.assertEqual(gate_schema_errors(forged), [])
                record["gate_results"] = [forged]
                if forged["status"] == "failed":
                    record["gate_results"].append(copy.deepcopy(baseline["gate_results"][0]))
                sign_run_record(record)
                self.write_record(record)
                result = self.validate_with_contract(contract_path, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("gate-result:GATE-TEST host attestation HMAC is invalid", result.stderr)
                self.assertNotIn("final run attestation payload hash", result.stderr)

    def test_accepted_run_allows_unattested_not_run_history(self) -> None:
        baseline, contract_path = self.prepare_accepted_run()
        previous = run("git", "rev-parse", "HEAD^", cwd=self.repo).stdout.strip()
        for revision in (baseline["current_revision"], previous):
            with self.subTest(revision=revision):
                record = copy.deepcopy(baseline)
                skipped = not_run_result(record["gate_results"][0])
                skipped["revision"] = revision
                skipped["tree_sha256"] = hashlib.sha256(
                    run("git", "ls-tree", "-r", "--full-tree", revision, cwd=self.repo).stdout.encode()
                ).hexdigest()
                record["gate_results"].insert(0, skipped)
                sign_run_record(record)
                self.write_record(record)
                result = self.validate_with_contract(contract_path, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_not_run_retains_command_and_input_binding(self) -> None:
        baseline, contract_path = self.prepare_accepted_run(gate_requires_approval=True)
        for mutation, error in (
            ({}, None),
            ({"command_sha256": "0" * 64}, "command hash differs from contract"),
            ({"resolved_inputs": [{"path": "other.py", "sha256": "0" * 64}]}, "resolved-input set differs from contract"),
            ({"resolved_inputs": [{"path": "test_runner.py", "sha256": "0" * 64}]}, "resolved input differs from Git"),
            ({"gate_id": "GATE-UNKNOWN"}, "run contains unknown gate results"),
        ):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(baseline)
                record.update(state="VERIFY", terminal_status="none")
                record["state_transitions"] = record["state_transitions"][:6]
                skipped = not_run_result(record["gate_results"][0])
                skipped.update(mutation)
                record["gate_results"] = [skipped]
                self.write_record(record)
                result = self.validate_with_contract(contract_path, check=False)
                if error is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(error, result.stderr)
                self.assertNotIn("payload-bound approval", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_acceptance_requires_one_current_passing_result(self) -> None:
        baseline, contract_path = self.prepare_accepted_run()
        for mutation, error in (
            ({"revision": run("git", "rev-parse", "HEAD^", cwd=self.repo).stdout.strip()}, "missing=['GATE-TEST']"),
            ({"tree_sha256": "0" * 64}, "missing=['GATE-TEST']"),
            ({}, "duplicate passing gate results: GATE-TEST"),
        ):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(baseline)
                gate = record["gate_results"][0]
                gate.update(mutation)
                sign_gate_result(gate)
                if not mutation:
                    record["gate_results"].append(copy.deepcopy(gate))
                sign_run_record(record)
                self.write_record(record)
                result = self.validate_with_contract(contract_path, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)

    def test_verified_not_attested_is_valid_with_independent_review_and_no_hmac(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["terminal_status"] = "verified-not-attested"
        record["attestation_key_id"] = None
        record["gate_results"][0]["execution_event_id"] = None
        record["gate_results"][0]["execution_hmac_sha256"] = None
        record["gate_results"].append(not_run_result(record["gate_results"][0]))
        record["review"]["review_event_id"] = None
        record["review"]["review_hmac_sha256"] = None
        record["run_attestation"] = {
            "event_id": None, "actor": None, "payload_sha256": None, "hmac_sha256": None,
        }
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Valid run record", result.stdout)

    def test_verified_not_attested_rejects_gate_host_attestation(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["terminal_status"] = "verified-not-attested"
        record["attestation_key_id"] = None
        record["review"]["review_event_id"] = None
        record["review"]["review_hmac_sha256"] = None
        record["run_attestation"] = {
            "event_id": None, "actor": None, "payload_sha256": None, "hmac_sha256": None,
        }
        record["gate_results"].append(not_run_result(record["gate_results"][0]))
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("verified-not-attested gate results must not claim host attestations", result.stderr)

    def test_verified_not_attested_rejects_fabricated_runtime_approvals(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["terminal_status"] = "verified-not-attested"
        record["attestation_key_id"] = None
        record["gate_results"][0]["execution_event_id"] = None
        record["gate_results"][0]["execution_hmac_sha256"] = None
        record["review"]["review_event_id"] = None
        record["review"]["review_hmac_sha256"] = None
        record["run_attestation"] = {
            "event_id": None, "actor": None, "payload_sha256": None, "hmac_sha256": None,
        }
        record["approvals"] = [{
            "action": "invented-approval", "decision": "approved", "decided_by": "model",
            "decided_at": "2026-07-16T00:00:00Z", "payload_sha256": "0" * 64,
            "method": "runtime-attestation", "authority_event_id": "invented-event",
            "attestation_hmac_sha256": "0" * 64,
        }]
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not contain runtime-attested approval events", result.stderr)

    def test_accepted_run_enforces_contract_reviewer_model_independence(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        writer = next(item for item in record["roles"] if item["role"] == "writer")
        reviewer = next(item for item in record["roles"] if item["role"] == "reviewer")
        reviewer["model"] = writer["model"]
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different model from every writer", result.stderr)

    def test_unknown_gate_is_rejected_before_accepted_state(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["state"] = "VERIFY"
        record["terminal_status"] = "none"
        record["gate_results"][0]["gate_id"] = "GATE-UNKNOWN"
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run contains unknown gate results", result.stderr)

    def test_malformed_run_keyring_fails_cleanly(self) -> None:
        _, contract_path = self.prepare_accepted_run()
        result = self.validate_with_contract(
            contract_path, check=False, env={"VIBESKILLS_RUN_HMAC_KEYS": "[not-an-object]"}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must contain valid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    @covers_adversarial("EVAL-BUDGET-OVERRUN")
    def test_budget_overrun_cannot_be_hidden(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["budgets"]["tool_calls_used"] = 10_000
        record["budgets"]["limits_exceeded"] = False
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("limits_exceeded does not match", result.stderr)

    @covers_adversarial("EVAL-FORGED-GATE-EVIDENCE")
    def test_accepted_run_rejects_forged_gate_command(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["gate_results"][0]["command_sha256"] = "0" * 64
        record["gate_results"][0]["log_path"] = ".ai/runs/missing-gate.log"
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("command hash differs from contract", result.stderr)
        self.assertIn("log is missing or changed", result.stderr)

    def test_accepted_run_rejects_changed_log(self) -> None:
        _, contract_path = self.prepare_accepted_run()
        (self.repo / ".ai/runs/gate.log").write_text("forged\n", encoding="utf-8")
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("log is missing or changed", result.stderr)

    @covers_adversarial("EVAL-DIRTY-AFTER-GATES")
    def test_accepted_run_rejects_dirty_source_tree(self) -> None:
        _, contract_path = self.prepare_accepted_run()
        (self.repo / "source.py").write_text("unverified = True\n", encoding="utf-8")
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty paths outside", result.stderr)

    def test_run_revalidates_contract_sources(self) -> None:
        _, contract_path = self.prepare_accepted_run()
        (self.repo / "PRD.md").write_text("# altered after approval\n", encoding="utf-8")
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source document hashes changed", result.stderr)

    def test_gate_requiring_approval_rejects_missing_attestation(self) -> None:
        _, contract_path = self.prepare_accepted_run(gate_requires_approval=True)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires exactly one payload-bound approval", result.stderr)

    def test_final_run_attestation_detects_record_tampering(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["budgets"]["tool_calls_used"] += 1
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("final run attestation payload hash", result.stderr)

    @covers_adversarial("EVAL-SELF-ATTESTED-APPROVAL")
    def test_accepted_run_rejects_missing_trusted_host_hmac(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["run_attestation"]["hmac_sha256"] = None
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted-run host attestation is incomplete", result.stderr)

    def test_gate_environment_cannot_exceed_contract_network_policy(self) -> None:
        record, contract_path = self.prepare_accepted_run()
        record["gate_results"][0]["execution_environment"]["network"] = "allowlisted"
        self.write_record(record)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broader network access", result.stderr)

    def test_final_diff_rejects_change_without_integrated_worktree(self) -> None:
        _, contract_path = self.prepare_accepted_run(unexplained_change=True)
        result = self.validate_with_contract(contract_path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not produced by integrated worktrees", result.stderr)


if __name__ == "__main__":
    unittest.main()
