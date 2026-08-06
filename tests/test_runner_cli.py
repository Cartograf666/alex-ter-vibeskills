import unittest
from unittest.mock import patch
from vibeskills_runner.cli import main
from vibeskills_runner.errors import ValidationError


class TestRunnerCli(unittest.TestCase):
    @patch("vibeskills_runner.cli.init_run")
    def test_cli_init_delegation(self, mock_init_run) -> None:
        args = [
            "init",
            "--contract", "specs/slug/contract.yaml",
            "--run-id", "RUN-1",
            "--manager-provider", "gemini",
            "--manager-model", "pro",
            "--manager-model-version", "1.5",
            "--manager-context-id", "ctx-1",
            "--repository", "/test/repo"
        ]
        exit_code = main(args)
        self.assertEqual(exit_code, 0)
        mock_init_run.assert_called_once()
        kwargs = mock_init_run.call_args[1]
        self.assertEqual(kwargs["contract_rel_path"], "specs/slug/contract.yaml")
        self.assertEqual(kwargs["run_id"], "RUN-1")
        self.assertEqual(kwargs["manager_provider"], "gemini")
        self.assertEqual(kwargs["manager_model"], "pro")
        self.assertEqual(kwargs["manager_model_version"], "1.5")
        self.assertEqual(kwargs["manager_context_id"], "ctx-1")

    @patch("vibeskills_runner.cli.get_status")
    def test_cli_status_delegation(self, mock_get_status) -> None:
        mock_get_status.return_value = "Status OK"
        args = [
            "status",
            "--run-id", "RUN-1",
            "--repository", "/test/repo"
        ]
        exit_code = main(args)
        self.assertEqual(exit_code, 0)
        # Check mock_get_status call (repository_path should match parsed Path)
        self.assertEqual(mock_get_status.call_count, 1)

    @patch("vibeskills_runner.cli.resume_run")
    def test_cli_resume_delegation(self, mock_resume_run) -> None:
        args = [
            "resume",
            "--run-id", "RUN-1",
            "--repository", "/test/repo"
        ]
        exit_code = main(args)
        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_resume_run.call_count, 1)

    @patch("vibeskills_runner.cli.verify_run")
    def test_cli_verify_delegation(self, mock_verify_run) -> None:
        args = [
            "verify",
            "--run-id", "RUN-1",
            "--contract", "specs/slug/contract.yaml",
            "--repository", "/test/repo"
        ]
        exit_code = main(args)
        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_verify_run.call_count, 1)

    @patch("vibeskills_runner.cli.init_run")
    def test_cli_failure_traceback_free(self, mock_init_run) -> None:
        mock_init_run.side_effect = ValidationError("Mocked validation failure")
        args = [
            "init",
            "--contract", "specs/slug/contract.yaml",
            "--run-id", "RUN-1",
            "--manager-provider", "gemini",
            "--manager-model", "pro",
            "--manager-model-version", "1.5",
            "--manager-context-id", "ctx-1"
        ]
        # Redirect stdout/stderr to capture output
        with patch("sys.stderr") as mock_stderr:
            exit_code = main(args)
            self.assertEqual(exit_code, 1)
            mock_stderr.write.assert_any_call("ERROR: Mocked validation failure")
