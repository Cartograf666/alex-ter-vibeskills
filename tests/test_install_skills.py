from __future__ import annotations

import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts import install_skills


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install_skills.py"


class InstallSkillsTests(unittest.TestCase):
    def test_installs_every_skill_and_refuses_unforced_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "skills"
            command = [
                "python3", str(INSTALLER), "--target", "codex",
                "--scope", "project", "--destination", str(destination),
            ]
            first = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}
            installed = {path.name for path in destination.iterdir() if path.is_dir()}
            self.assertEqual(installed, expected)
            for name in expected:
                self.assertTrue((destination / name / "SKILL.md").is_file())
                self.assertTrue((destination / name / ".vibeskills-managed.json").is_file())
            self.assertTrue(
                (destination / "prepare-development-cycle" / "assets" / "development-contract-template.yaml").is_file()
            )

            second = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("--force", second.stderr)

            forced = subprocess.run([*command, "--force"], text=True, capture_output=True)
            self.assertEqual(forced.returncode, 0, forced.stderr)

    def test_force_refuses_to_delete_unmanaged_skill_named_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "skills"
            victim = destination / "grill-requirements"
            victim.mkdir(parents=True)
            (victim / "important.txt").write_text("user data\n", encoding="utf-8")
            result = subprocess.run(
                [
                    "python3", str(INSTALLER), "--target", "codex", "--scope", "project",
                    "--destination", str(destination), "--force",
                ],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unmanaged directory", result.stderr)
            self.assertEqual((victim / "important.txt").read_text(encoding="utf-8"), "user data\n")
            self.assertEqual(
                {path.name for path in destination.iterdir() if path.is_dir()},
                {"grill-requirements"},
            )

    def test_failure_during_late_swap_rolls_back_every_prior_skill(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "skills"
            skills = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
            install_skills.install_all(skills, {"codex": destination}, force=False)
            first = destination / skills[0].name
            (first / "pre-update-sentinel.txt").write_text("preserve\n", encoding="utf-8")
            original_swap = install_skills.swap_staged_skill
            calls = 0

            def fail_second_swap(staged: Path, target: Path, backup: Path) -> bool:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected late swap failure")
                return original_swap(staged, target, backup)

            with mock.patch.object(install_skills, "swap_staged_skill", side_effect=fail_second_swap):
                with self.assertRaisesRegex(OSError, "injected late swap failure"):
                    install_skills.install_all(skills, {"codex": destination}, force=True)

            self.assertEqual(
                (first / "pre-update-sentinel.txt").read_text(encoding="utf-8"),
                "preserve\n",
            )
            self.assertEqual(
                {path.name for path in destination.iterdir() if path.is_dir()},
                {skill.name for skill in skills},
            )

    def test_concurrent_destination_race_retains_previous_install_for_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "skills"
            skills = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
            install_skills.install_all(skills, {"codex": destination}, force=False)
            second = destination / skills[1].name
            (second / "pre-race-sentinel.txt").write_text("recover-me\n", encoding="utf-8")
            original_swap = install_skills.swap_staged_skill
            calls = 0

            def inject_destination_race(staged: Path, target: Path, backup: Path) -> bool:
                nonlocal calls
                calls += 1
                if calls == 2:
                    target.rename(backup)
                    target.mkdir()
                    raise OSError("injected concurrent destination")
                return original_swap(staged, target, backup)

            with mock.patch.object(
                install_skills, "swap_staged_skill", side_effect=inject_destination_race
            ):
                with self.assertRaisesRegex(OSError, "recovery data retained"):
                    install_skills.install_all(skills, {"codex": destination}, force=True)

            retained = list(destination.glob(f".vibeskills-*/{skills[1].name}.previous"))
            self.assertEqual(len(retained), 1)
            self.assertEqual(
                (retained[0] / "pre-race-sentinel.txt").read_text(encoding="utf-8"),
                "recover-me\n",
            )


if __name__ == "__main__":
    unittest.main()
