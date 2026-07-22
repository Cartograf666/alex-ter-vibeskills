import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from vibeskills_runner.errors import ValidationError, PersistenceError
from vibeskills_runner.run_transaction import RunTransaction
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


_orig_promote_directory = RunTransaction.promote_directory
_orig_promote_record = RunTransaction.promote_record
_orig_cleanup_transaction = RunTransaction.cleanup_transaction


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

        stage_record = self.repo / f".ai/runs/{run_id}.yaml.stage"
        stage_dir = self.repo / f".ai/runs/{run_id}.stage"
        stage_record.parent.mkdir(parents=True, exist_ok=True)
        stage_record.write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / ".stage_marker").write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")

        # Without transaction marker, init_run must fail closed (cannot delete markerless staging)
        with self.assertRaises(ValidationError):
            self.init_valid_run(run_id)

        # Staging files must remain untouched
        self.assertTrue(stage_record.exists())
        self.assertTrue(stage_dir.exists())

        # Now write a valid transaction marker with STAGED phase and hashes
        from vibeskills_runner.run_transaction import RunTransaction, compute_file_sha256
        tx_test = RunTransaction(self.repo, run_id)
        events_file = stage_dir / "events.jsonl"
        events_file.write_text("{}\n", encoding="utf-8")
        meta_file = stage_dir / "metadata.yaml"
        meta_file.write_text(yaml.safe_dump({"run_id": run_id}), encoding="utf-8")

        hashes = {
            "record": compute_file_sha256(stage_record),
            "journal": compute_file_sha256(events_file),
            "metadata": compute_file_sha256(meta_file),
        }

        tx_test.write_transaction_phase("STAGED", hashes)

        # Now, call init_run. It should rollback staging and initialize successfully
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

    @patch("vibeskills_runner.run_transaction.RunTransaction.promote_directory", autospec=True)
    def test_first_rename_failure(self, mock_promote) -> None:
        self.approve_contract()
        raise_error = True

        def side_effect(self_tx):
            if raise_error:
                raise OSError("First rename failed")
            _orig_promote_directory(self_tx)

        mock_promote.side_effect = side_effect
        run_id = "RUN-FIRST-FAIL"

        with self.assertRaises((PersistenceError, OSError)):
            init_run(
                self.repo,
                ".ai/specs/my-slug/development-contract.yaml",
                run_id,
                "anthropic",
                "opus",
                "1.0",
                "manager-ctx-01"
            )

        # Reset mock side effect to allow retry promotion to succeed
        raise_error = False

        init_run(
            self.repo,
            ".ai/specs/my-slug/development-contract.yaml",
            run_id,
            "anthropic",
            "opus",
            "1.0",
            "manager-ctx-01"
        )
        self.assertTrue((self.repo / f".ai/runs/{run_id}.yaml").is_file())
        self.assertTrue((self.repo / f".ai/runs/{run_id}").is_dir())

    @patch("vibeskills_runner.run_transaction.RunTransaction.promote_record", autospec=True)
    def test_second_rename_failure(self, mock_promote) -> None:
        self.approve_contract()
        raise_error = True

        def side_effect(self_tx):
            if raise_error:
                raise OSError("Second rename failed")
            _orig_promote_record(self_tx)

        mock_promote.side_effect = side_effect
        run_id = "RUN-SECOND-FAIL"

        with self.assertRaises((PersistenceError, OSError)):
            init_run(
                self.repo,
                ".ai/specs/my-slug/development-contract.yaml",
                run_id,
                "anthropic",
                "opus",
                "1.0",
                "manager-ctx-01"
            )

        # Reset mock side effect to allow resume to succeed
        raise_error = False

        resume_run(self.repo, run_id)

        self.assertTrue((self.repo / f".ai/runs/{run_id}.yaml").is_file())
        self.assertTrue((self.repo / f".ai/runs/{run_id}").is_dir())
        self.assertFalse((self.repo / f".ai/runs/{run_id}.yaml.stage").exists())

    def test_marker_phase_write_failure(self) -> None:
        self.approve_contract()
        run_id = "RUN-PHASE-FAIL"

        from vibeskills_runner.run_transaction import RunTransaction
        original_write_phase = RunTransaction.write_transaction_phase

        def side_effect(self_tx, phase, hashes):
            if phase == "DIRECTORY_PROMOTED":
                raise OSError("Write phase failed")
            original_write_phase(self_tx, phase, hashes)

        with patch.object(RunTransaction, "write_transaction_phase", side_effect):
            with self.assertRaises((PersistenceError, OSError)):
                init_run(
                    self.repo,
                    ".ai/specs/my-slug/development-contract.yaml",
                    run_id,
                    "anthropic",
                    "opus",
                    "1.0",
                    "manager-ctx-01"
                )

        # Outside the with-block, the mock is removed. Call resume_run to complete.
        resume_run(self.repo, run_id)

        self.assertTrue((self.repo / f".ai/runs/{run_id}.yaml").is_file())
        self.assertTrue((self.repo / f".ai/runs/{run_id}").is_dir())

    @patch("vibeskills_runner.run_transaction.RunTransaction.cleanup_transaction", autospec=True)
    def test_cleanup_failure(self, mock_cleanup) -> None:
        self.approve_contract()
        raise_error = True

        def side_effect(self_tx):
            if raise_error:
                raise OSError("Cleanup failed")
            _orig_cleanup_transaction(self_tx)

        mock_cleanup.side_effect = side_effect
        run_id = "RUN-CLEANUP-FAIL"

        with self.assertRaises((PersistenceError, OSError)):
            init_run(
                self.repo,
                ".ai/specs/my-slug/development-contract.yaml",
                run_id,
                "anthropic",
                "opus",
                "1.0",
                "manager-ctx-01"
            )

        # Reset mock side effect to allow cleanup on resume
        raise_error = False

        resume_run(self.repo, run_id)
        self.assertFalse((self.repo / f".ai/runs/{run_id}.transaction.yaml").exists())

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

    def test_staged_rename_outside_runs(self) -> None:
        self.approve_contract()
        run_id = "RUN-STAGED-RENAME"
        self.init_valid_run(run_id)

        # Create a file inside .ai/runs/
        source_file = self.repo / f".ai/runs/{run_id}/source.py"
        source_file.write_text("print('hello')", encoding="utf-8")

        # Commit it so it is tracked
        run_git("add", str(source_file), cwd=self.repo)
        run_git("commit", "-m", "add source file", cwd=self.repo)

        # Do a staged git rename outside runs
        target_file = self.repo / "outside.py"
        run_git("mv", str(source_file), str(target_file), cwd=self.repo)

        # resume_run must fail because of dirty tree (file renamed outside runs)
        try:
            with self.assertRaises(ValidationError):
                resume_run(self.repo, run_id)
        finally:
            # Clean up repo state
            run_git("reset", "HEAD", "--hard", cwd=self.repo)
            run_git("reset", "HEAD^", "--hard", cwd=self.repo)

    def test_malicious_local_modules_ignored(self) -> None:
        self.approve_contract()
        run_id = "RUN-MALICIOUS-MODULES"

        # Create malicious validate_contract.py and hmac.py in repo root
        mal_val = self.repo / "validate_contract.py"
        mal_val.write_text("raise Exception('Malicious validate_contract loaded!')\n", encoding="utf-8")

        mal_hmac = self.repo / "hmac.py"
        sentinel_path = self.repo / "hmac_sentinel.txt"
        mal_hmac.write_text(
            f"from pathlib import Path\nPath('{sentinel_path}').write_text('poisoned')\nraise Exception('Malicious hmac loaded!')\n",
            encoding="utf-8"
        )

        # init_run should ignore the local malicious validate_contract and hmac files due to PYTHONSAFEPATH=1
        init_run(
            self.repo,
            ".ai/specs/my-slug/development-contract.yaml",
            run_id,
            "anthropic",
            "opus",
            "1.0",
            "manager-ctx-01"
        )

        # Verify successful initialization and no sentinel creation
        self.assertTrue((self.repo / f".ai/runs/{run_id}.yaml").is_file())
        self.assertFalse(sentinel_path.exists())

    def test_missing_duplicate_manager(self) -> None:
        self.approve_contract()
        run_id = "RUN-BAD-MANAGER"
        self.init_valid_run(run_id)

        record_path = self.repo / f".ai/runs/{run_id}.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))

        # Scenario 1: Zero manager roles
        record["roles"] = []
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

        # Scenario 2: Two manager roles
        record["roles"] = [
            {"role": "manager", "provider": "anthropic", "model": "opus", "model_version": "1.0", "context_id": "manager-ctx-01"},
            {"role": "manager", "provider": "anthropic", "model": "opus", "model_version": "1.0", "context_id": "manager-ctx-02"}
        ]
        record_path.write_text(yaml.safe_dump(record), encoding="utf-8")

        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_transaction_path_tampering(self) -> None:
        self.approve_contract()
        run_id = "RUN-TAMPER-PATH"

        from vibeskills_runner.run_transaction import RunTransaction

        original_execute = RunTransaction.execute_promotion

        def tampered_execute(self_tx, hashes, *args, **kwargs):
            self_tx.write_marker("STAGED", hashes)
            # Tamper the marker file to reference an escaped directory path
            marker_path = self_tx.marker_path
            marker_data = yaml.safe_load(marker_path.read_text(encoding="utf-8"))
            marker_data["stage_dir_path"] = "/tmp/escaped"
            marker_path.write_text(yaml.safe_dump(marker_data), encoding="utf-8")

            self_tx.promote_directory()
            self_tx.promote_record()

        with patch.object(RunTransaction, "execute_promotion", tampered_execute):
            init_run(
                self.repo,
                ".ai/specs/my-slug/development-contract.yaml",
                run_id,
                "anthropic",
                "opus",
                "1.0",
                "manager-ctx-01"
            )

        # Calling resume_run should trigger recover, detect the path tampering, and fail-closed
        with self.assertRaises(ValidationError):
            resume_run(self.repo, run_id)

    def test_manager_identity_validation(self) -> None:
        self.approve_contract()
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"

        invalid_params_list = [
            ("", "opus", "1.0", "ctx-01"),
            ("anthropic", "  ", "1.0", "ctx-01"),
            ("anthropic", "opus", "", "ctx-01"),
            ("anthropic", "opus", "1.0", "   "),
        ]

        for i, (prov, mod, ver, ctx) in enumerate(invalid_params_list):
            run_id = f"RUN-BAD-MGR-{i}"
            with self.assertRaises(ValidationError):
                init_run(self.repo, contract_rel, run_id, prov, mod, ver, ctx)

            # Assert zero files left on disk
            for p in [
                self.repo / f".ai/runs/{run_id}.yaml",
                self.repo / f".ai/runs/{run_id}",
                self.repo / f".ai/runs/{run_id}.yaml.stage",
                self.repo / f".ai/runs/{run_id}.stage",
                self.repo / f".ai/runs/{run_id}.transaction.yaml",
                self.repo / f".ai/runs/{run_id}.lock",
            ]:
                self.assertFalse(p.exists(), f"Leftover file found: {p}")

    def test_lock_protocol_security(self) -> None:
        self.approve_contract()
        run_id = "RUN-LOCK-TEST"

        from vibeskills_runner.run_transaction import RunLock

        # 1. Lock acquisition & duplicate lock rejection
        lock1 = RunLock(self.repo, run_id)
        lock1.acquire()
        self.assertTrue(lock1.acquired)

        lock2 = RunLock(self.repo, run_id)
        with self.assertRaises(ValidationError):
            lock2.acquire()

        # 2. Independent run IDs can lock concurrently
        lock_other = RunLock(self.repo, "RUN-OTHER-LOCK")
        lock_other.acquire()
        self.assertTrue(lock_other.acquired)
        lock_other.release()

        # 3. Nonce tampering prevents releasing someone else's lock
        lock1.lock_path.write_text(yaml.safe_dump({"run_id": run_id, "nonce": "tampered-nonce"}), encoding="utf-8")
        with self.assertRaises(ValidationError):
            lock1.release()

        # Clean up lock file
        if lock1.lock_path.exists():
            lock1.lock_path.unlink()

        # 4. Context manager releases lock on success and error
        with RunLock(self.repo, run_id) as l:
            self.assertTrue(l.acquired)
        self.assertFalse((self.repo / f".ai/runs/{run_id}.lock").exists())

        try:
            with RunLock(self.repo, run_id) as l:
                raise RuntimeError("Operation error inside lock context")
        except RuntimeError:
            pass
        self.assertFalse((self.repo / f".ai/runs/{run_id}.lock").exists())

        # 5. Stale lock blocks execution
        stale_lock = self.repo / f".ai/runs/{run_id}.lock"
        stale_lock.write_text(yaml.safe_dump({"run_id": run_id, "nonce": "old"}), encoding="utf-8")
        with self.assertRaises(ValidationError):
            self.init_valid_run(run_id)
        stale_lock.unlink()

    def test_symlink_attacks_matrix(self) -> None:
        self.approve_contract()
        run_id = "RUN-SYMLINK-TEST"
        sentinel = Path(tempfile.gettempdir()) / "vibeskills_symlink_sentinel.txt"
        if sentinel.exists():
            sentinel.unlink()

        sentinel.write_text("sentinel content", encoding="utf-8")

        try:
            # 1. stage record is a symlink
            stage_rec = self.repo / f".ai/runs/{run_id}.yaml.stage"
            stage_rec.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(sentinel, stage_rec)

            with self.assertRaises(ValidationError):
                self.init_valid_run(run_id)
            stage_rec.unlink()

            # 2. lock file is a symlink
            lock_path = self.repo / f".ai/runs/{run_id}.lock"
            os.symlink(sentinel, lock_path)

            with self.assertRaises(ValidationError):
                self.init_valid_run(run_id)
            lock_path.unlink()

            # 3. transaction marker is a symlink
            marker_path = self.repo / f".ai/runs/{run_id}.transaction.yaml"
            os.symlink(sentinel, marker_path)

            with self.assertRaises(ValidationError):
                self.init_valid_run(run_id)
            marker_path.unlink()

            # Sentinel file must remain completely unmodified
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "sentinel content")
        finally:
            if sentinel.exists():
                sentinel.unlink()

    def test_subprocess_isolation_and_limits(self) -> None:
        from vibeskills_runner.validator_bridge import run_isolated_python, get_isolated_env
        import sys

        # 1. Environment allowlist filtering
        os.environ["SECRET_AWS_KEY"] = "super-secret"
        os.environ["VIBESKILLS_APPROVAL_HMAC_KEY"] = "approval-secret"
        env = get_isolated_env({"VIBESKILLS_APPROVAL_HMAC_KEY"})
        self.assertNotIn("SECRET_AWS_KEY", env)
        self.assertEqual(env["VIBESKILLS_APPROVAL_HMAC_KEY"], "approval-secret")
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["PYTHONSAFEPATH"], "1")

        # 2. Subprocess timeout kills child process
        cmd_timeout = [sys.executable, "-c", "import time; time.sleep(20)"]
        with self.assertRaises(ValidationError) as ctx:
            run_isolated_python(cmd_timeout, cwd=self.repo, env=env, timeout_seconds=0.2)
        self.assertIn("timed out", str(ctx.exception))

        # 3. Output stream overflow (>1 MiB) rejected
        cmd_overflow = [sys.executable, "-c", "print('A' * (1024 * 1024 + 100))"]
        with self.assertRaises(ValidationError) as ctx:
            run_isolated_python(cmd_overflow, cwd=self.repo, env=env, max_stdout_bytes=1024 * 1024)
        self.assertIn("overflow", str(ctx.exception))

    def test_transaction_fault_injection_matrix(self) -> None:
        self.approve_contract()
        run_id = "RUN-FAULT-MATRIX"

        from vibeskills_runner.run_transaction import RunTransaction, TransactionPhase

        # Test failure of promote_directory during execute_promotion
        def failing_promote_directory(self_tx):
            raise OSError("Injected directory promote failure")

        with patch.object(RunTransaction, "promote_directory", failing_promote_directory):
            with self.assertRaises(Exception):
                self.init_valid_run(run_id)

        # Check phase and topology after failure
        tx = RunTransaction(self.repo, run_id)
        self.assertTrue(tx.marker_path.exists())
        marker_data = yaml.safe_load(tx.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker_data["phase"], TransactionPhase.STAGED.value)
        self.assertTrue(tx.stage_record_path.exists())
        self.assertTrue(tx.stage_dir_path.exists())
        self.assertFalse(tx.final_record_path.exists())
        self.assertFalse(tx.final_dir_path.exists())

        # Calling resume_run should recover from STAGED phase to completion!
        resume_run(self.repo, run_id)
        self.assertTrue(tx.final_record_path.exists())
        self.assertTrue(tx.final_dir_path.exists())
        self.assertFalse(tx.marker_path.exists())
