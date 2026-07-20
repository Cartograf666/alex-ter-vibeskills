import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from vibeskills_runner.errors import ValidationError, PersistenceError
from vibeskills_runner.run_service import (
    init_run,
    get_status,
    resume_run,
    verify_run,
)


ROOT = Path(__file__).resolve().parents[1]
APPROVE_CONTRACT = ROOT / "scripts/approve_contract.py"


def run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
    )


class TestRunnerAdversarial(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)

        # Initialize test repo
        run_git("init", "-b", "main", cwd=self.repo)
        run_git("config", "user.name", "Test User", cwd=self.repo)
        run_git("config", "user.email", "test@example.com", cwd=self.repo)

        # Copy toolkit schemas/scripts/examples to support testing
        shutil.copytree(ROOT / "schemas", self.repo / "schemas")
        shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        shutil.copytree(ROOT / "examples", self.repo / "examples")

        # Create specs path and copy development contract
        self.specs_dir = self.repo / ".ai/specs/my-slug"
        self.specs_dir.mkdir(parents=True)
        self.contract_path = self.specs_dir / "development-contract.yaml"
        shutil.copy(self.repo / "examples/development-contract.yaml", self.contract_path)

        # Commit initial assets
        run_git("add", ".", cwd=self.repo)
        run_git("commit", "-m", "Initial commit", cwd=self.repo)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def approve_contract(self, repo_path: Path = None, contract_path: Path = None) -> None:
        if repo_path is None:
            repo_path = self.repo
        if contract_path is None:
            contract_path = self.contract_path
        # Approve architecture first
        subprocess.run(
            [
                "python3",
                str(repo_path / "scripts/approve_architecture.py"),
                str(repo_path / "examples/architecture.yaml"),
                "--approved-by",
                "owner@example.com",
            ],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        # Approve contract
        subprocess.run(
            [
                "python3",
                str(repo_path / "scripts/approve_contract.py"),
                str(contract_path),
                "--approved-by",
                "owner@example.com",
                "--repository",
                str(repo_path),
            ],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        run_git("add", ".", cwd=repo_path)
        run_git("commit", "-m", "Approve contract", cwd=repo_path)

    def init_valid_run(self, run_id: str) -> None:
        init_run(
            repository_path=self.repo,
            contract_rel_path=".ai/specs/my-slug/development-contract.yaml",
            run_id=run_id,
            manager_provider="anthropic",
            manager_model="opus",
            manager_model_version="1.0",
            manager_context_id="ctx-1",
        )

    def test_invalid_transition_in_resume(self) -> None:
        # Rejects START -> PLAN recorded in record and journal
        self.approve_contract()
        run_id = "RUN-BAD-TRANSITION"
        self.init_valid_run(run_id)

        # Modify record and journal to contain invalid transition START -> PLAN
        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["state"] = "PLAN"
        record["state_transitions"] = [
            {"from": "START", "to": "PLAN", "at": "2026-07-20T12:00:00Z", "reason": "Bad transition"}
        ]
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        events_path = self.repo / f".ai/runs/{run_id}/events.jsonl"
        events_path.write_text(json.dumps({
            "seq": 1,
            "event_id": f"EVT-{run_id}-INIT",
            "type": "state_transition",
            "actor": "ctx-1",
            "timestamp": "2026-07-20T12:00:00Z",
            "data": {"from": "START", "to": "PLAN", "at": "2026-07-20T12:00:00Z", "reason": "Bad transition"}
        }) + "\n", encoding="utf-8")

        from vibeskills_runner.errors import RunnerError
        with self.assertRaises(RunnerError):
            resume_run(self.repo, run_id)

    def test_discontinuous_transition_ledger_in_resume(self) -> None:
        # Rejects transitions that bypass steps (ledger not contiguous)
        self.approve_contract()
        run_id = "RUN-DISCONTINUOUS"
        self.init_valid_run(run_id)

        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["state"] = "PLAN"
        record["state_transitions"] = [
            {"from": "START", "to": "DISCOVER", "at": "2026-07-20T12:00:00Z", "reason": "Init"},
            {"from": "SPECIFY", "to": "PLAN", "at": "2026-07-20T12:01:00Z", "reason": "Discontinuity"}
        ]
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        events_path = self.repo / f".ai/runs/{run_id}/events.jsonl"
        events_path.write_text(
            json.dumps({
                "seq": 1,
                "event_id": "EVT-1",
                "type": "state_transition",
                "actor": "ctx-1",
                "timestamp": "2026-07-20T12:00:00Z",
                "data": {"from": "START", "to": "DISCOVER", "at": "2026-07-20T12:00:00Z", "reason": "Init"}
            }) + "\n" +
            json.dumps({
                "seq": 2,
                "event_id": "EVT-2",
                "type": "state_transition",
                "actor": "ctx-1",
                "timestamp": "2026-07-20T12:01:00Z",
                "data": {"from": "SPECIFY", "to": "PLAN", "at": "2026-07-20T12:01:00Z", "reason": "Discontinuity"}
            }) + "\n",
            encoding="utf-8"
        )

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_state_mismatch_with_last_transition(self) -> None:
        self.approve_contract()
        run_id = "RUN-STATE-MISMATCH"
        self.init_valid_run(run_id)

        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["state"] = "SPECIFY"  # Mismatch: state says SPECIFY, but transitions last is DISCOVER
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_tempered_transition_reason(self) -> None:
        self.approve_contract()
        run_id = "RUN-TEMPERED-REASON"
        self.init_valid_run(run_id)

        # Modify record's reason to differ from the journal's reason
        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["state_transitions"][0]["reason"] = "Modifying reason unilaterally"
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_nonexistent_base_revision(self) -> None:
        self.approve_contract()
        run_id = "RUN-FAKE-BASE"
        self.init_valid_run(run_id)

        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["base_revision"] = "a" * 40  # fake commit
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_nonexistent_current_revision(self) -> None:
        self.approve_contract()
        run_id = "RUN-FAKE-CURRENT"
        self.init_valid_run(run_id)

        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["current_revision"] = "b" * 40  # fake commit
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_current_revision_not_matching_head(self) -> None:
        self.approve_contract()
        run_id = "RUN-MISMATCHED-HEAD"
        self.init_valid_run(run_id)

        # Create a new commit to move HEAD forward, making run current_revision out of sync
        (self.repo / "extra.txt").write_text("extra", encoding="utf-8")
        run_git("add", ".", cwd=self.repo)
        run_git("commit", "-m", "Forward commit", cwd=self.repo)

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_incorrect_tree_sha256(self) -> None:
        self.approve_contract()
        run_id = "RUN-BAD-TREE"
        self.init_valid_run(run_id)

        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["current_tree_sha256"] = "c" * 64  # invalid tree SHA
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_hash_invalid_contract_rejected(self) -> None:
        # First approve contract normally
        self.approve_contract()

        # Modify contract payload without re-approving (invalidates approval hash)
        contract = yaml.safe_load(self.contract_path.read_text(encoding="utf-8"))
        contract["run_spec"]["objective"] = "Tampered objective statement"
        self.contract_path.write_text(yaml.safe_dump(contract), encoding="utf-8")

        run_id = "RUN-INVALID-CONTRACT-HASH"
        with self.assertRaises(ValidationError):
            self.init_valid_run(run_id)

        # Verify no run record or dir were created
        self.assertFalse((self.repo / f".ai/runs/{run_id}.yaml").exists())
        self.assertFalse((self.repo / f".ai/runs/{run_id}").exists())

    def test_corrupt_metadata_and_journal(self) -> None:
        self.approve_contract()
        run_id = "RUN-CORRUPT-FILES"
        self.init_valid_run(run_id)

        # Corrupt journal JSONL
        events_path = self.repo / f".ai/runs/{run_id}/events.jsonl"
        events_path.write_text("corrupted json data \n", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            resume_run(self.repo, run_id)

        # Corrupt metadata.yaml
        self.init_valid_run("RUN-CORRUPT-META")
        meta_path = self.repo / "RUN-CORRUPT-META/metadata.yaml"  # wait, correct path:
        meta_path = self.repo / ".ai/runs/RUN-CORRUPT-META/metadata.yaml"
        meta_path.write_text("unbalanced: : yaml", encoding="utf-8")
        with self.assertRaises(ValidationError):
            resume_run(self.repo, "RUN-CORRUPT-META")

    def test_incomplete_init_rollback(self) -> None:
        self.approve_contract()
        run_id = "RUN-INTERRUPTED"

        # We can trigger error during initialization by making the runs folder read-only or similar,
        # or we can test that leftover staging files from interrupted run are cleaned up.
        # Let's write leftover staging files
        stage_record = self.repo / f".ai/runs/{run_id}.yaml.stage"
        stage_dir = self.repo / f".ai/runs/{run_id}.stage"
        stage_record.parent.mkdir(parents=True, exist_ok=True)
        stage_record.write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / ".stage_marker").write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")

        # Now, call init_run. It should clean them up and succeed!
        self.init_valid_run(run_id)

        # Check final files exist, staging files are deleted
        self.assertTrue((self.repo / f".ai/runs/{run_id}.yaml").exists())
        self.assertTrue((self.repo / f".ai/runs/{run_id}").exists())
        self.assertFalse(stage_record.exists())
        self.assertFalse(stage_dir.exists())

    def test_malicious_scripts_ignored(self) -> None:
        # Prepare a separate repository to act as target repository.
        target_repo_dir = tempfile.TemporaryDirectory()
        target_repo = Path(target_repo_dir.name)

        try:
            # Init target repo
            run_git("init", "-b", "main", cwd=target_repo)
            run_git("config", "user.name", "Test User", cwd=target_repo)
            run_git("config", "user.email", "test@example.com", cwd=target_repo)

            # Copy schemas and examples to support approval
            shutil.copytree(ROOT / "schemas", target_repo / "schemas")
            shutil.copytree(ROOT / "examples", target_repo / "examples")

            # Create malicious scripts directory inside target repo
            malicious_scripts_dir = target_repo / "scripts"
            malicious_scripts_dir.mkdir()

            # Write malicious script to target repo
            malicious_script = malicious_scripts_dir / "validate_contract.py"
            malicious_script.write_text(
                "raise RuntimeError('MALICIOUS TARGET SCRIPT EXECUTED')\n",
                encoding="utf-8"
            )

            # Copy approve_contract.py to support contract approval
            shutil.copy(ROOT / "scripts/approve_contract.py", target_repo / "scripts/approve_contract.py")
            shutil.copy(ROOT / "scripts/approve_architecture.py", target_repo / "scripts/approve_architecture.py")
            shutil.copy(ROOT / "scripts/contract_lib.py", target_repo / "scripts/contract_lib.py")
            shutil.copy(ROOT / "scripts/architecture_lib.py", target_repo / "scripts/architecture_lib.py")
            shutil.copy(ROOT / "scripts/design_system_lib.py", target_repo / "scripts/design_system_lib.py")
            shutil.copy(ROOT / "scripts/validate_architecture.py", target_repo / "scripts/validate_architecture.py")
            shutil.copy(ROOT / "scripts/validate_design_system.py", target_repo / "scripts/validate_design_system.py")
            shutil.copy(ROOT / "scripts/finding_fingerprint.py", target_repo / "scripts/finding_fingerprint.py")
            shutil.copy(ROOT / "scripts/validate_contract.py", target_repo / "scripts/validate_contract_trusted.py")

            # To approve the contract inside target_repo, we temporarily rename scripts/validate_contract.py to trusted version so approve_contract works
            os.rename(malicious_script, malicious_scripts_dir / "validate_contract_malicious.py")
            shutil.copy(ROOT / "scripts/validate_contract.py", malicious_script)

            # Create and approve contract in target repo
            specs_dir = target_repo / ".ai/specs/my-slug"
            specs_dir.mkdir(parents=True)
            contract_path = specs_dir / "development-contract.yaml"
            shutil.copy(target_repo / "examples/development-contract.yaml", contract_path)

            run_git("add", ".", cwd=target_repo)
            run_git("commit", "-m", "Fixture commits", cwd=target_repo)

            self.approve_contract(repo_path=target_repo, contract_path=contract_path)

            # Now swap in the malicious validate_contract.py script
            malicious_script.unlink()
            os.rename(malicious_scripts_dir / "validate_contract_malicious.py", malicious_script)

            # Call init_run using target_repo as repository
            # Since the runner must use trusted scripts and ignore target repo's scripts, it should complete successfully
            # without raising the RuntimeError!
            init_run(
                repository_path=target_repo,
                contract_rel_path=".ai/specs/my-slug/development-contract.yaml",
                run_id="RUN-MALICIOUS-TEST",
                manager_provider="anthropic",
                manager_model="opus",
                manager_model_version="1.0",
                manager_context_id="ctx-1",
            )

            # Check that files were created successfully
            self.assertTrue((target_repo / ".ai/runs/RUN-MALICIOUS-TEST.yaml").is_file())

        finally:
            target_repo_dir.cleanup()

    def test_no_scripts_or_schemas_in_target_repo(self) -> None:
        # Target repository lacks scripts/ and schemas/ entirely
        target_repo_dir = tempfile.TemporaryDirectory()
        target_repo = Path(target_repo_dir.name)

        try:
            # Init target repo
            run_git("init", "-b", "main", cwd=target_repo)
            run_git("config", "user.name", "Test User", cwd=target_repo)
            run_git("config", "user.email", "test@example.com", cwd=target_repo)

            # Copy examples (PRD, brief etc) to support contract approval
            shutil.copytree(ROOT / "examples", target_repo / "examples")

            # Copy schemas and scripts to support the approval process in target repo
            shutil.copytree(ROOT / "schemas", target_repo / "schemas")
            shutil.copytree(ROOT / "scripts", target_repo / "scripts")

            specs_dir = target_repo / ".ai/specs/my-slug"
            specs_dir.mkdir(parents=True)
            contract_path = specs_dir / "development-contract.yaml"
            shutil.copy(target_repo / "examples/development-contract.yaml", contract_path)

            run_git("add", ".", cwd=target_repo)
            run_git("commit", "-m", "Commit before approval", cwd=target_repo)

            # Approve contract
            self.approve_contract(repo_path=target_repo, contract_path=contract_path)

            # Now delete the scripts/ and schemas/ directories from target repo!
            shutil.rmtree(target_repo / "scripts")
            shutil.rmtree(target_repo / "schemas")

            # Commit the deletions
            run_git("add", ".", cwd=target_repo)
            run_git("commit", "-m", "Remove schemas and scripts from target", cwd=target_repo)

            # Running init_run should succeed since it loads schemas and scripts from the trusted toolkit directory!
            init_run(
                repository_path=target_repo,
                contract_rel_path=".ai/specs/my-slug/development-contract.yaml",
                run_id="RUN-NO-TOOLKIT-FILES",
                manager_provider="anthropic",
                manager_model="opus",
                manager_model_version="1.0",
                manager_context_id="ctx-1",
            )

            # Verify status and verify commands also work!
            status_txt = get_status(target_repo, "RUN-NO-TOOLKIT-FILES", as_json=False)
            self.assertIn("RUN-NO-TOOLKIT-FILES", status_txt)

            # verify command works
            verify_run(target_repo, "RUN-NO-TOOLKIT-FILES", ".ai/specs/my-slug/development-contract.yaml")

        finally:
            target_repo_dir.cleanup()

    def test_run_id_traversal_victim(self) -> None:
        self.approve_contract()
        # Verify a run_id containing traversal is rejected
        run_id = "../../victim"

        # Create a sentinel file to prove it is not touched
        victim_stage = self.repo.parent / "victim.stage"
        if victim_stage.exists():
            victim_stage.unlink()

        with self.assertRaises(ValidationError):
            init_run(
                repository_path=self.repo,
                contract_rel_path=".ai/specs/my-slug/development-contract.yaml",
                run_id=run_id,
                manager_provider="anthropic",
                manager_model="opus",
                manager_model_version="1.0",
                manager_context_id="ctx-1",
            )

        self.assertFalse(victim_stage.exists())

    def test_sys_modules_poisoning(self) -> None:
        self.approve_contract()

        # Poison sys.modules with a fake sentinel object
        import sys
        sys.modules["validate_contract"] = object()

        try:
            # init_run should succeed by bypassing this poisoned module
            self.init_valid_run("RUN-POISON-SYS-MODULES")
            self.assertTrue((self.repo / ".ai/runs/RUN-POISON-SYS-MODULES.yaml").is_file())
        finally:
            # Clean up sys.modules poisoning
            if "validate_contract" in sys.modules:
                del sys.modules["validate_contract"]

    def test_malicious_path_precedence(self) -> None:
        self.approve_contract()

        # Create a temporary directory and place a poisoned validate_contract.py inside
        import sys
        malpath_dir = tempfile.TemporaryDirectory()
        try:
            poisoned_script = Path(malpath_dir.name) / "validate_contract.py"
            poisoned_script.write_text("raise RuntimeError('MALICIOUS PATH EXECUTION')\n", encoding="utf-8")

            # Inject to the front of sys.path
            sys.path.insert(0, malpath_dir.name)

            try:
                # init_run should bypass the poisoned path in sys.path
                self.init_valid_run("RUN-MALPATH-PRECEDENCE")
                self.assertTrue((self.repo / ".ai/runs/RUN-MALPATH-PRECEDENCE.yaml").is_file())
            finally:
                if malpath_dir.name in sys.path:
                    sys.path.remove(malpath_dir.name)
        finally:
            malpath_dir.cleanup()

    def test_disallowed_ledger_prefix(self) -> None:
        self.approve_contract()
        run_id = "RUN-DISALLOWED-PREFIX"
        self.init_valid_run(run_id)

        # Modify run transitions to start with DISCOVER -> SPECIFY instead of START -> DISCOVER
        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        record["state"] = "SPECIFY"
        record["state_transitions"] = [
            {"from": "DISCOVER", "to": "SPECIFY", "at": "2026-07-20T12:00:00Z", "reason": "Bypass start"}
        ]
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        events_path = self.repo / f".ai/runs/{run_id}/events.jsonl"
        events_path.write_text(
            json.dumps({
                "seq": 1,
                "event_id": "EVT-1",
                "type": "state_transition",
                "actor": "ctx-1",
                "timestamp": "2026-07-20T12:00:00Z",
                "data": {"from": "DISCOVER", "to": "SPECIFY", "at": "2026-07-20T12:00:00Z", "reason": "Bypass start"}
            }) + "\n",
            encoding="utf-8"
        )

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_promotion_failures_recovery(self) -> None:
        self.approve_contract()
        run_id = "RUN-PROMOTION-FAIL"

        # 1. Simulate Failure between rename 1 and rename 2 (Dir renamed, Record stage left)
        # We write stage record and final directory.
        stage_record_path = self.repo / f".ai/runs/{run_id}.yaml.stage"
        final_dir_path = self.repo / f".ai/runs/{run_id}"

        stage_record_path.parent.mkdir(parents=True, exist_ok=True)
        final_dir_path.mkdir(parents=True, exist_ok=True)

        # Add metadata and stage markers to prove they are managed
        stage_record_path.write_text(yaml.safe_dump({
            "run_id": run_id,
            "contract_id": "my-contract",
            "contract_payload_sha256": "hash",
            "state": "DISCOVER",
            "base_revision": "rev",
            "current_revision": "rev",
            "current_tree_sha256": "tree",
            "roles": [{"role": "manager", "provider": "anthropic", "model": "opus", "model_version": "1.0", "context_id": "manager-ctx-01"}]
        }), encoding="utf-8")

        (final_dir_path / ".stage_marker").write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")
        (final_dir_path / "metadata.yaml").write_text(yaml.safe_dump({
            "run_id": run_id,
            "contract_id": "my-contract",
            "manager": {"provider": "anthropic", "model": "opus", "model_version": "1.0", "context_id": "manager-ctx-01"}
        }), encoding="utf-8")

        # Recovery through resume (allow_rollback = False) should complete the promotion
        from vibeskills_runner.run_service import check_and_recover_promotion
        check_and_recover_promotion(self.repo, run_id, allow_rollback=False)

        self.assertTrue((self.repo / f".ai/runs/{run_id}.yaml").is_file())
        self.assertTrue(final_dir_path.is_dir())
        self.assertFalse(stage_record_path.exists())

        # Clean up
        (self.repo / f".ai/runs/{run_id}.yaml").unlink()
        shutil.rmtree(final_dir_path)

        # 2. Simulate same failure, but init_run (allow_rollback = True) should clean/rollback
        stage_record_path.write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")
        final_dir_path.mkdir(parents=True, exist_ok=True)
        (final_dir_path / ".stage_marker").write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")
        (final_dir_path / "metadata.yaml").write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")

        check_and_recover_promotion(self.repo, run_id, allow_rollback=True)
        self.assertFalse(stage_record_path.exists())
        self.assertFalse(final_dir_path.exists())

    def test_dirty_tree_validation(self) -> None:
        self.approve_contract()
        run_id = "RUN-DIRTY-TREE"
        self.init_valid_run(run_id)

        # Create an untracked file outside .ai/runs/ to make tree dirty
        dirty_file = self.repo / "uncommitted_file.txt"
        dirty_file.write_text("uncommitted content", encoding="utf-8")

        # resume should fail because repository has uncommitted changes
        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

        # Clean the dirty file
        dirty_file.unlink()

        # resume should succeed now
        resume_run(self.repo, run_id)
