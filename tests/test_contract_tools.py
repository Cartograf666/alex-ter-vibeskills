from __future__ import annotations

import copy
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.eval_coverage import covers_adversarial


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/development-contract.schema.json"
APPROVE = ROOT / "scripts/approve_contract.py"
VALIDATE = ROOT / "scripts/validate_contract.py"
APPROVE_DESIGN = ROOT / "scripts/approve_design_system.py"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, text=True, capture_output=True, check=check
    )


def base_contract() -> dict:
    return {
        "schema_version": 3,
        "contract_id": "TEST-CONTRACT-V1",
        "status": "draft",
        "implementation_authorized": False,
        "document_depth": "LEAN_BRIEF",
        "discovery_mode": "direct",
        "source_documents": {
            "decision_brief": None,
            "prd": "PRD.md",
            "technical_brief": None,
            "technical_brief_omission_reason": "No material technical choice exists for this local fix.",
            "architecture_manifest": None,
            "architecture_baseline": None,
            "design_system_manifest": None,
            "design_brief": None,
        },
        "run_spec": {
            "objective": "Return a clear validation error for an invalid input value",
            "non_goals": ["Change the public function signature"],
            "acceptance_criteria": [
                {
                    "id": "AC-1",
                    "statement": "Invalid input returns the documented validation error",
                    "source_requirement_ids": ["FR-1"],
                    "verification_gate_ids": ["GATE-TEST"],
                }
            ],
            "constraints": ["Keep the patch local"],
            "compatibility_requirements": ["Preserve valid-input behavior"],
            "risk_level": "low",
            "human_approval_required_for": [],
        },
        "change_envelope": {
            "primary_component": "services",
            "allowed_components": {
                "services": {
                    "reason": "Owns input validation behavior",
                    "depth": "methods-only",
                    "paths": ["src/services/**"],
                },
                "tests": {
                    "reason": "Covers the acceptance behavior",
                    "depth": "full",
                    "paths": ["tests/**"],
                },
            },
            "conditional_components": {},
            "forbidden_components": [],
            "protected_interfaces": ["public_function_signature"],
            "architecture_acceptance": ["Validation remains in the service"],
        },
        "quality_gates": [
            {
                "id": "GATE-TEST",
                "command": "python3 test_runner.py",
                "source": "existing-repository",
                "trust": "reviewed",
                "requires_approval": False,
                "sandbox": "required",
                "network": "deny",
                "secrets": "none",
                "timeout_seconds": 60,
                "resolved_input_paths": ["test_runner.py"],
            }
        ],
        "test_policy": {
            "acceptance_test_owner": "tester",
            "writer_may_modify_acceptance_tests": False,
            "freeze_after_state": "TEST_DESIGN",
            "acceptance_tests_required": True,
        },
        "design_policy": {
            "applies": False,
            "reason": "This test contract has no user interface work.",
            "system_status": "not-applicable",
            "required_gate_ids": [],
            "acceptance": [],
        },
        "automation": {
            "requested_mode": "bounded-auto",
            "effective_mode": "manual",
            "policy_sources": [
                {"source": "project", "mode": "manual"},
                {"source": "task", "mode": "bounded-auto"},
            ],
            "max_implementation_attempts": 3,
            "max_review_rounds": 2,
            "max_parallel_writers": 1,
            "max_tool_calls": 50,
            "max_elapsed_minutes": 30,
            "max_budget_usd": 5,
        },
        "interaction_policy": {
            "intake_mode": "guided",
            "progress_updates": "state-transitions",
            "interrupt_for": [
                "protected-decision",
                "contract-change",
                "change-envelope-expansion",
                "budget-exhaustion",
                "required-gate-unavailable",
                "provider-substitution",
                "terminal-failure",
            ],
            "continue_until": "accepted-or-terminal",
            "resume_from_run_record": True,
        },
        "provider_policy": {
            "allowed_providers": ["local"],
            "sensitive_path_policy": "deny",
            "allow_external_code_transfer": False,
            "role_assignments": {
                "manager": {"preferred": "local:manager", "fallbacks": []},
                "scout": {"preferred": "local:scout", "fallbacks": []},
                "tester": {"preferred": "local:tester", "fallbacks": []},
                "writer": {"preferred": "local:writer", "fallbacks": []},
                "verifier": {"preferred": "local:verifier", "fallbacks": []},
                "reviewer": {"preferred": "local:reviewer", "fallbacks": []},
            },
            "substitution_policy": "deny",
            "reviewer_independence": "different-model",
        },
        "approval": {
            "status": "pending",
            "approved_by": None,
            "approved_at": None,
            "method": None,
            "key_id": None,
            "authority_event_id": None,
            "attestation_hmac_sha256": None,
            "source_revision": None,
            "artifact_hashes": {},
            "gate_input_hashes": {},
            "contract_payload_sha256": None,
        },
    }


class ContractToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        run("git", "init", "-b", "main", cwd=self.repo)
        run("git", "config", "user.name", "Test User", cwd=self.repo)
        run("git", "config", "user.email", "test@example.com", cwd=self.repo)
        (self.repo / "PRD.md").write_text(
            "# PRD\n\n- FR-1: Reject invalid input.\n- AC-1: Invalid input returns the documented validation error.\n",
            encoding="utf-8",
        )
        (self.repo / "test_runner.py").write_text("print('ok')\n", encoding="utf-8")
        self.contract_path = self.repo / "development-contract.yaml"
        self.write_contract(base_contract())
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Prepare contract", cwd=self.repo)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_contract(self, contract: dict) -> None:
        self.contract_path.write_text(
            yaml.safe_dump(contract, sort_keys=False), encoding="utf-8"
        )

    def validate(self, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run(
            "python3",
            str(VALIDATE),
            str(self.contract_path),
            "--schema",
            str(SCHEMA),
            "--repository",
            str(self.repo),
            cwd=self.repo,
            check=check,
        )

    def test_draft_contract_is_valid(self) -> None:
        self.assertIn("Valid development contract", self.validate().stdout)

    def test_grilled_contract_requires_and_hashes_decision_brief(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["discovery_mode"] = "grilled"
        contract["source_documents"]["decision_brief"] = "DECISION-BRIEF.md"
        (self.repo / "DECISION-BRIEF.md").write_text(
            "# Decision Brief\n\nStatus: RESOLVED\n", encoding="utf-8"
        )
        self.write_contract(contract)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Add decision brief", cwd=self.repo)
        run(
            "python3", str(APPROVE), str(self.contract_path), "--approved-by", "user@example.com",
            "--repository", str(self.repo), cwd=self.repo,
        )
        approved = yaml.safe_load(self.contract_path.read_text(encoding="utf-8"))
        self.assertIn("decision_brief", approved["approval"]["artifact_hashes"])
        self.assertIn("Valid development contract", self.validate().stdout)

    def test_grilled_contract_rejects_missing_decision_brief_path(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["discovery_mode"] = "grilled"
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source_documents.decision_brief", result.stderr)

    def test_interaction_policy_requires_mandatory_interruptions(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["interaction_policy"]["interrupt_for"].remove("required-gate-unavailable")
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interaction_policy.interrupt_for", result.stderr)
        self.assertIn("does not contain", result.stderr)

    def test_role_route_provider_must_be_allowed(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["provider_policy"]["role_assignments"]["writer"]["fallbacks"] = [
            "google:gemini-coding"
        ]
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside allowed_providers", result.stderr)

    def test_reviewer_independence_rejects_same_preferred_provider(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["provider_policy"]["reviewer_independence"] = "different-provider"
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prefer different providers", result.stderr)

    @covers_adversarial("EVAL-STALE-APPROVAL")
    def test_approval_is_bound_to_artifacts_and_payload(self) -> None:
        run(
            "python3",
            str(APPROVE),
            str(self.contract_path),
            "--approved-by",
            "user@example.com",
            "--repository",
            str(self.repo),
            cwd=self.repo,
        )
        self.validate()

        (self.repo / "PRD.md").write_text("# Changed\n- AC-1: Changed.\n", encoding="utf-8")
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source document hashes changed", result.stderr)

    @covers_adversarial("EVAL-REQUIREMENT-DROP")
    def test_traceability_rejects_missing_prd_criterion(self) -> None:
        (self.repo / "PRD.md").write_text(
            "# PRD\n- AC-1: First.\n- AC-2: Missing from RunSpec.\n",
            encoding="utf-8",
        )
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PRD/RunSpec acceptance IDs differ", result.stderr)

    @covers_adversarial("EVAL-POLICY-DOWNGRADE")
    def test_policy_cannot_be_weakened_by_task(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["automation"]["effective_mode"] = "bounded-auto"
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("most restrictive policy", result.stderr)

    def test_untrusted_gate_requires_sandbox_approval_and_no_secrets(self) -> None:
        contract = copy.deepcopy(base_contract())
        gate = contract["quality_gates"][0]
        gate.update(
            {
                "trust": "untrusted",
                "requires_approval": False,
                "sandbox": "recommended",
                "secrets": "allowlisted",
            }
        )
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("untrusted gate requires approval", result.stderr)
        self.assertIn("untrusted gate requires sandbox", result.stderr)
        self.assertIn("untrusted gate cannot receive secrets", result.stderr)

    def test_high_risk_contract_rejects_local_confirmation(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["run_spec"]["risk_level"] = "high"
        self.write_contract(contract)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Raise risk", cwd=self.repo)
        result = run(
            "python3", str(APPROVE), str(self.contract_path),
            "--approved-by", "user@example.com", "--repository", str(self.repo),
            cwd=self.repo, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("high/critical risk requires", result.stderr)

    @covers_adversarial("EVAL-UNTRUSTED-GATE")
    def test_newly_generated_gate_requires_explicit_isolation(self) -> None:
        contract = copy.deepcopy(base_contract())
        gate = contract["quality_gates"][0]
        gate["source"] = "newly-generated"
        gate["requires_approval"] = False
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("newly generated gate requires approval", result.stderr)

    def test_runtime_attestation_requires_trusted_host_secret(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["run_spec"]["risk_level"] = "high"
        self.write_contract(contract)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Raise contract risk", cwd=self.repo)
        result = subprocess.run(
            ["python3", str(APPROVE), str(self.contract_path), "--approved-by", "owner@example.com",
             "--method", "runtime-attestation", "--authority-event-id", "host-event-1",
             "--repository", str(self.repo)],
            cwd=self.repo, text=True, capture_output=True,
            env={
                key: value for key, value in os.environ.items()
                if key not in {"VIBESKILLS_APPROVAL_HMAC_KEY", "VIBESKILLS_APPROVAL_HMAC_KEYS"}
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("selected trusted-host approval HMAC key", result.stderr)

    def test_runtime_attestation_rejects_malformed_keyring_without_traceback(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["run_spec"]["risk_level"] = "high"
        self.write_contract(contract)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Prepare malformed keyring test", cwd=self.repo)
        env = os.environ.copy()
        env["VIBESKILLS_APPROVAL_HMAC_KEYS"] = "{not-json"
        result = subprocess.run(
            ["python3", str(APPROVE), str(self.contract_path), "--approved-by", "owner@example.com",
             "--method", "runtime-attestation", "--authority-event-id", "host-event-1",
             "--repository", str(self.repo)],
            cwd=self.repo, text=True, capture_output=True, env=env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must contain valid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_runtime_attestation_uses_selected_keyring_key(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["run_spec"]["risk_level"] = "high"
        self.write_contract(contract)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Prepare high-risk contract", cwd=self.repo)
        env = os.environ.copy()
        env["VIBESKILLS_APPROVAL_HMAC_KEYS"] = '{"rotation-2026":"a-strong-test-key-with-more-than-32-bytes"}'
        approved = subprocess.run(
            ["python3", str(APPROVE), str(self.contract_path), "--approved-by", "owner@example.com",
             "--method", "runtime-attestation", "--authority-event-id", "host-event-2",
             "--key-id", "rotation-2026", "--repository", str(self.repo)],
            cwd=self.repo, text=True, capture_output=True, env=env,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        validated = subprocess.run(
            ["python3", str(VALIDATE), str(self.contract_path), "--schema", str(SCHEMA),
             "--repository", str(self.repo)],
            cwd=self.repo, text=True, capture_output=True, env=env,
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)

    def test_contract_validation_rejects_malformed_keyring_without_traceback(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["run_spec"]["risk_level"] = "high"
        self.write_contract(contract)
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-m", "Prepare validation keyring test", cwd=self.repo)
        valid_env = os.environ.copy()
        valid_env["VIBESKILLS_APPROVAL_HMAC_KEY"] = "a-strong-test-key-with-more-than-32-bytes"
        approved = subprocess.run(
            ["python3", str(APPROVE), str(self.contract_path), "--approved-by", "owner@example.com",
             "--method", "runtime-attestation", "--authority-event-id", "host-event-3",
             "--repository", str(self.repo)],
            cwd=self.repo, text=True, capture_output=True, env=valid_env,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        invalid_env = os.environ.copy()
        invalid_env["VIBESKILLS_APPROVAL_HMAC_KEYS"] = "{not-json"
        validated = subprocess.run(
            ["python3", str(VALIDATE), str(self.contract_path), "--schema", str(SCHEMA),
             "--repository", str(self.repo)],
            cwd=self.repo, text=True, capture_output=True, env=invalid_env,
        )
        self.assertNotEqual(validated.returncode, 0)
        self.assertIn("must contain valid JSON", validated.stderr)
        self.assertNotIn("Traceback", validated.stderr)

    def test_broad_allowed_glob_cannot_cover_conditional_scope(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["change_envelope"]["allowed_components"]["services"]["paths"] = ["src/**"]
        contract["change_envelope"]["conditional_components"]["database"] = {
            "condition": "Persistence change is necessary",
            "approval_class": "human",
            "maximum_depth": "full",
            "paths": ["src/db/**"],
        }
        self.write_contract(contract)
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("path scopes overlap", result.stderr)

    def test_disjoint_dynamic_globs_are_allowed(self) -> None:
        contract = copy.deepcopy(base_contract())
        contract["change_envelope"]["allowed_components"] = {
            "controllers": {
                "reason": "Transport adapters", "depth": "methods-only",
                "paths": ["src/*/controllers/**"],
            },
            "repositories": {
                "reason": "Persistence adapters", "depth": "methods-only",
                "paths": ["src/*/repositories/**"],
            },
        }
        contract["change_envelope"]["primary_component"] = "controllers"
        self.write_contract(contract)
        self.assertIn("Valid development contract", self.validate().stdout)

    @covers_adversarial("EVAL-UI-WITHOUT-DESIGN-SYSTEM")
    def test_ui_contract_requires_approved_design_system_and_declared_gates(self) -> None:
        (self.repo / "tokens.css").write_text(":root { --color-text: #111; }\n", encoding="utf-8")
        (self.repo / "components").mkdir()
        design = yaml.safe_load((ROOT / "examples/design-system.yaml").read_text(encoding="utf-8"))
        design["tokens"]["source_paths"] = ["tokens.css"]
        design["components"]["registry_paths"] = ["components"]
        design["components"]["documentation_paths"] = []
        design["quality_gate_ids"] = ["GATE-TEST"]
        design_path = self.repo / "design-system.yaml"
        design_path.write_text(yaml.safe_dump(design, sort_keys=False), encoding="utf-8")
        (self.repo / "DESIGN-BRIEF.md").write_text(
            "# Design Brief\n\nUse approved tokens and verify responsive states.\n", encoding="utf-8"
        )
        contract = copy.deepcopy(base_contract())
        contract["source_documents"]["design_system_manifest"] = "design-system.yaml"
        contract["source_documents"]["design_brief"] = "DESIGN-BRIEF.md"
        contract["design_policy"] = {
            "applies": True, "reason": "The feature contains an interactive user interface.",
            "system_status": "approved-custom", "required_gate_ids": ["GATE-TEST"],
            "acceptance": ["The interface uses approved tokens and components."],
        }
        self.write_contract(contract)
        provisional = self.validate(check=False)
        self.assertNotEqual(provisional.returncode, 0)
        self.assertIn("requires an approved design-system manifest", provisional.stderr)

        run(
            "python3", str(APPROVE_DESIGN), str(design_path), "--approved-by", "owner@example.com",
            "--repository", str(self.repo), cwd=self.repo,
        )
        self.assertIn("Valid development contract", self.validate().stdout)

        contract = yaml.safe_load(self.contract_path.read_text(encoding="utf-8"))
        extra_gate = copy.deepcopy(contract["quality_gates"][0])
        extra_gate["id"] = "GATE-BUILD"
        contract["quality_gates"].append(extra_gate)
        contract["run_spec"]["acceptance_criteria"][0]["verification_gate_ids"] = ["GATE-BUILD"]
        self.write_contract(contract)
        missing_mapping = self.validate(check=False)
        self.assertNotEqual(missing_mapping.returncode, 0)
        self.assertIn("design gates are not mapped", missing_mapping.stderr)


if __name__ == "__main__":
    unittest.main()
