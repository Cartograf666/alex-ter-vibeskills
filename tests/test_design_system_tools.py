from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
APPROVE = ROOT / "scripts/approve_design_system.py"
VALIDATE = ROOT / "scripts/validate_design_system.py"
SCHEMA = ROOT / "schemas/design-system.schema.json"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


class DesignSystemToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        run("git", "init", "-b", "main", cwd=self.repo)
        (self.repo / "tokens.css").write_text(":root { --color-text: #111; }\n", encoding="utf-8")
        (self.repo / "components").mkdir()
        (self.repo / "components" / "README.md").write_text("# Components\n", encoding="utf-8")
        manifest = yaml.safe_load((ROOT / "examples/design-system.yaml").read_text(encoding="utf-8"))
        manifest["tokens"]["source_paths"] = ["tokens.css"]
        manifest["components"]["registry_paths"] = ["components"]
        manifest["components"]["documentation_paths"] = ["components/README.md"]
        self.manifest_path = self.repo / "design-system.yaml"
        self.manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def validate(self, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run(
            "python3", str(VALIDATE), str(self.manifest_path), "--schema", str(SCHEMA),
            "--repository", str(self.repo), cwd=self.repo, check=check,
        )

    def test_provisional_manifest_is_valid(self) -> None:
        self.assertIn("Valid design-system manifest", self.validate().stdout)

    def test_approval_hash_detects_manifest_change(self) -> None:
        run(
            "python3", str(APPROVE), str(self.manifest_path),
            "--approved-by", "owner@example.com", "--repository", str(self.repo), cwd=self.repo,
        )
        self.validate()
        manifest = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
        manifest["visual_direction"]["traits"] = ["unapproved"]
        self.manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest payload changed", result.stderr)

    def test_approved_manifest_rejects_missing_token_source(self) -> None:
        run(
            "python3", str(APPROVE), str(self.manifest_path),
            "--approved-by", "owner@example.com", "--repository", str(self.repo), cwd=self.repo,
        )
        (self.repo / "tokens.css").unlink()
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references missing paths", result.stderr)

    def test_approval_detects_token_content_change(self) -> None:
        run(
            "python3", str(APPROVE), str(self.manifest_path),
            "--approved-by", "owner@example.com", "--repository", str(self.repo), cwd=self.repo,
        )
        (self.repo / "tokens.css").write_text(":root { --color-text: transparent; }\n", encoding="utf-8")
        result = self.validate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact contents changed", result.stderr)


if __name__ == "__main__":
    unittest.main()
