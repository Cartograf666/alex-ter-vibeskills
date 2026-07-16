from __future__ import annotations

import subprocess
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
APPROVE = ROOT / "scripts/approve_architecture.py"
VALIDATE = ROOT / "scripts/validate_architecture.py"
VALIDATE_BASELINE = ROOT / "scripts/validate_baseline.py"
SCHEMA = ROOT / "schemas/architecture.schema.json"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


class ArchitectureToolsTests(unittest.TestCase):
    def test_approval_hash_detects_manifest_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            manifest_path = temp / "architecture.yaml"
            manifest = yaml.safe_load((ROOT / "examples/architecture.yaml").read_text(encoding="utf-8"))
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            run("python3", str(APPROVE), str(manifest_path), "--approved-by", "owner@example.com", cwd=temp)
            run("python3", str(VALIDATE), str(manifest_path), "--schema", str(SCHEMA), cwd=temp)

            approved = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            approved["components"]["services"]["responsibilities"].append("unapproved new responsibility")
            manifest_path.write_text(yaml.safe_dump(approved, sort_keys=False), encoding="utf-8")
            result = run(
                "python3", str(VALIDATE), str(manifest_path), "--schema", str(SCHEMA),
                cwd=temp, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manifest payload changed", result.stderr)

    def test_approval_refuses_semantically_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            manifest_path = temp / "architecture.yaml"
            manifest = yaml.safe_load((ROOT / "examples/architecture.yaml").read_text(encoding="utf-8"))
            manifest["dependency_rules"][0]["to"] = "missing-component"
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            result = run(
                "python3", str(APPROVE), str(manifest_path), "--approved-by", "owner@example.com",
                cwd=temp, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to approve invalid", result.stderr)
            self.assertEqual(yaml.safe_load(manifest_path.read_text(encoding="utf-8"))["status"], "provisional")

    def test_baseline_rejects_forged_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            run("git", "init", "-b", "main", cwd=repo)
            run("git", "config", "user.name", "Test User", cwd=repo)
            run("git", "config", "user.email", "test@example.com", cwd=repo)
            (repo / "README.md").write_text("test\n", encoding="utf-8")
            run("git", "add", ".", cwd=repo)
            run("git", "commit", "-m", "Initial", cwd=repo)
            head = run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
            baseline = {
                "schema_version": 1, "generated_at": "2026-07-16T00:00:00Z", "source_revision": head,
                "known_violations": [{
                    "id": "ARCH-DEBT-1", "rule_id": "ARCH-NO_DB", "rule_version": 1,
                    "severity": "medium", "source": "controller", "target": "database",
                    "edge_kind": "data-access", "location": "src/controller.py:10",
                    "fingerprint": "0" * 64, "first_seen_revision": head,
                    "reason": "Legacy direct access", "policy": "baseline-only", "owner": None,
                    "review_after": None,
                }],
                "policy": {"allow_exact_baseline": True, "block_expansion": True, "block_new_instances": True},
            }
            baseline_path = repo / "baseline.yaml"
            baseline_path.write_text(yaml.safe_dump(baseline, sort_keys=False), encoding="utf-8")
            result = run(
                "python3", str(VALIDATE_BASELINE), str(baseline_path),
                "--schema", str(ROOT / "schemas/architecture-baseline.schema.json"),
                "--repository", str(repo), cwd=repo, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fingerprint does not match", result.stderr)

    def test_baseline_rejects_severity_increase_for_same_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            run("git", "init", "-b", "main", cwd=repo)
            run("git", "config", "user.name", "Test User", cwd=repo)
            run("git", "config", "user.email", "test@example.com", cwd=repo)
            (repo / "README.md").write_text("test\n", encoding="utf-8")
            run("git", "add", ".", cwd=repo)
            run("git", "commit", "-m", "Initial", cwd=repo)
            head = run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
            normalized = {
                "rule_id": "ARCH-NO_DB", "rule_version": 1, "source": "controller",
                "target": "database", "edge_kind": "data-access", "location": "src/controller.py:10",
            }
            fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            baseline_finding = {
                "id": "ARCH-DEBT-1", **normalized, "severity": "medium", "fingerprint": fingerprint,
                "first_seen_revision": head, "reason": "Legacy direct access", "policy": "baseline-only",
                "owner": None, "review_after": None,
            }
            baseline = {
                "schema_version": 1, "generated_at": "2026-07-16T00:00:00Z", "source_revision": head,
                "known_violations": [baseline_finding],
                "policy": {"allow_exact_baseline": True, "block_expansion": True, "block_new_instances": True},
            }
            current = [{**normalized, "severity": "critical"}]
            baseline_path, findings_path = repo / "baseline.yaml", repo / "findings.yaml"
            baseline_path.write_text(yaml.safe_dump(baseline, sort_keys=False), encoding="utf-8")
            findings_path.write_text(yaml.safe_dump(current, sort_keys=False), encoding="utf-8")
            result = run(
                "python3", str(VALIDATE_BASELINE), str(baseline_path), "--findings", str(findings_path),
                "--schema", str(ROOT / "schemas/architecture-baseline.schema.json"),
                "--repository", str(repo), cwd=repo, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("severity increased", result.stderr)


if __name__ == "__main__":
    unittest.main()
