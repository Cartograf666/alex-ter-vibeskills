from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


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

            second = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("--force", second.stderr)

            forced = subprocess.run([*command, "--force"], text=True, capture_output=True)
            self.assertEqual(forced.returncode, 0, forced.stderr)


if __name__ == "__main__":
    unittest.main()
