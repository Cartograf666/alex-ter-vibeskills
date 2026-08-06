import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from vibeskills_runner.errors import ValidationError
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


class TestRunnerService(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)

        # 1. Initialize a git repository
        run_git("init", "-b", "main", cwd=self.repo)
        run_git("config", "user.name", "Test User", cwd=self.repo)
        run_git("config", "user.email", "test@example.com", cwd=self.repo)

        # 2. Copy the scripts, schemas, and examples to test repo to ensure existing validator scripts run correctly
        shutil.copytree(ROOT / "schemas", self.repo / "schemas")
        shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        shutil.copytree(ROOT / "examples", self.repo / "examples")

        # 3. Create specs directory for the contract
        self.specs_dir = self.repo / ".ai/specs/my-slug"
        self.specs_dir.mkdir(parents=True)
        self.contract_path = self.specs_dir / "development-contract.yaml"

        # 4. Copy the real example contract to contract path
        shutil.copy(self.repo / "examples/development-contract.yaml", self.contract_path)

        # Commit everything to have a clean initial git state
        run_git("add", ".", cwd=self.repo)
        run_git("commit", "-m", "Initial commit with all project fixtures", cwd=self.repo)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_contract(self, data: dict) -> None:
        self.contract_path.write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )

    def approve_contract(self) -> None:
        # 1. Approve the architecture manifest
        try:
            subprocess.run(
                [
                    "python3",
                    str(self.repo / "scripts/approve_architecture.py"),
                    str(self.repo / "examples/architecture.yaml"),
                    "--approved-by",
                    "owner@example.com",
                ],
                cwd=self.repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            print("ARCH STDOUT:", exc.stdout)
            print("ARCH STDERR:", exc.stderr)
            raise exc

        # 2. Approve the contract
        try:
            res = subprocess.run(
                [
                    "python3",
                    str(self.repo / "scripts/approve_contract.py"),
                    str(self.contract_path),
                    "--approved-by",
                    "owner@example.com",
                    "--repository",
                    str(self.repo),
                ],
                cwd=self.repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            print("CONTRACT STDOUT:", exc.stdout)
            print("CONTRACT STDERR:", exc.stderr)
            raise exc
        run_git("add", ".", cwd=self.repo)
        run_git("commit", "-m", "Approve architecture and contract", cwd=self.repo)

    def test_init_run_success(self) -> None:
        self.approve_contract()

        run_id = "RUN-TEST-INIT-01"
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"

        init_run(
            repository_path=self.repo,
            contract_rel_path=contract_rel,
            run_id=run_id,
            manager_provider="anthropic",
            manager_model="opus",
            manager_model_version="1.0",
            manager_context_id="manager-ctx-01",
        )

        # Check run files exist
        run_yaml = self.repo / f".ai/runs/{run_id}.yaml"
        self.assertTrue(run_yaml.is_file())
        run_dir = self.repo / f".ai/runs/{run_id}"
        self.assertTrue((run_dir / "events.jsonl").is_file())
        self.assertTrue((run_dir / "metadata.yaml").is_file())

        # Load run record and check fields
        record = yaml.safe_load(run_yaml.read_text(encoding="utf-8"))
        self.assertEqual(record["schema_version"], 2)
        self.assertEqual(record["run_id"], run_id)
        self.assertEqual(record["state"], "DISCOVER")
        self.assertEqual(record["terminal_status"], "none")
        self.assertEqual(len(record["state_transitions"]), 1)
        self.assertEqual(record["state_transitions"][0]["from"], "START")
        self.assertEqual(record["state_transitions"][0]["to"], "DISCOVER")

        # Verify real HEAD and tree hashes are set
        head_commit = run_git("rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        self.assertEqual(record["base_revision"], head_commit)
        self.assertEqual(record["current_revision"], head_commit)

    def test_init_run_rejects_unauthorized_contract(self) -> None:
        # Do not approve contract (status remains draft and implementation_authorized false)
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"
        with self.assertRaises(ValidationError):
            init_run(
                repository_path=self.repo,
                contract_rel_path=contract_rel,
                run_id="RUN-FAIL",
                manager_provider="anthropic",
                manager_model="opus",
                manager_model_version="1.0",
                manager_context_id="manager-ctx-01",
            )

    def test_init_run_fails_on_duplicate_run_id(self) -> None:
        self.approve_contract()
        run_id = "RUN-TEST-DUP"
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"

        # First initialization
        init_run(
            repository_path=self.repo,
            contract_rel_path=contract_rel,
            run_id=run_id,
            manager_provider="anthropic",
            manager_model="opus",
            manager_model_version="1.0",
            manager_context_id="manager-ctx-01",
        )

        # Repeated initialization should fail
        with self.assertRaises(ValidationError):
            init_run(
                repository_path=self.repo,
                contract_rel_path=contract_rel,
                run_id=run_id,
                manager_provider="anthropic",
                manager_model="opus",
                manager_model_version="1.0",
                manager_context_id="manager-ctx-01",
            )

    def test_status_text_and_json(self) -> None:
        self.approve_contract()
        run_id = "RUN-STATUS"
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"

        init_run(
            repository_path=self.repo,
            contract_rel_path=contract_rel,
            run_id=run_id,
            manager_provider="anthropic",
            manager_model="opus",
            manager_model_version="1.0",
            manager_context_id="manager-ctx-01",
        )

        # Get status human-readable
        status_txt = get_status(self.repo, run_id, as_json=False)
        self.assertIn("Run ID: RUN-STATUS", status_txt)
        self.assertIn("State: DISCOVER", status_txt)

        # Get status JSON
        status_json_str = get_status(self.repo, run_id, as_json=True)
        status_json = json.loads(status_json_str)
        self.assertEqual(status_json["run_id"], run_id)
        self.assertEqual(status_json["state"], "DISCOVER")

    def test_verify_run_success(self) -> None:
        self.approve_contract()
        run_id = "RUN-VERIFY"
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"

        init_run(
            repository_path=self.repo,
            contract_rel_path=contract_rel,
            run_id=run_id,
            manager_provider="anthropic",
            manager_model="opus",
            manager_model_version="1.0",
            manager_context_id="manager-ctx-01",
        )

        # Should complete without error (raises exception if fails)
        verify_run(self.repo, run_id, contract_rel)

    def test_resume_run_success(self) -> None:
        self.approve_contract()
        run_id = "RUN-RESUME"
        contract_rel = ".ai/specs/my-slug/development-contract.yaml"

        init_run(
            repository_path=self.repo,
            contract_rel_path=contract_rel,
            run_id=run_id,
            manager_provider="anthropic",
            manager_model="opus",
            manager_model_version="1.0",
            manager_context_id="manager-ctx-01",
        )

        # resume should output messages and leave state unchanged
        resume_run(self.repo, run_id)
        # check state is still DISCOVER
        status_json_str = get_status(self.repo, run_id, as_json=True)
        status_json = json.loads(status_json_str)
        self.assertEqual(status_json["state"], "DISCOVER")
