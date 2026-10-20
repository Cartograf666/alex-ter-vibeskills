"""Keep the Claude plugin surface aligned with the portable toolkit."""

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AGENTS = {
    "vibeskills-scout": ("haiku", ["Read", "Grep", "Glob"]),
    "vibeskills-tester": ("haiku", ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]),
    "vibeskills-writer": ("sonnet", ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]),
    "vibeskills-verifier": ("haiku", ["Read", "Grep", "Glob", "Bash"]),
    "vibeskills-reviewer": ("opus", ["Read", "Grep", "Glob", "Bash"]),
}


class ClaudePluginTests(unittest.TestCase):
    def test_manifests_match_toolkit_version(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        plugin = json.loads(
            (ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(plugin["name"], "vibeskills")
        self.assertEqual(plugin["version"], version)
        self.assertEqual(marketplace["name"], "vibeskills")
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "vibeskills")
        self.assertEqual(entry["version"], version)
        self.assertEqual(entry["source"], "./")

    def test_all_six_skills_have_entrypoints(self):
        skills = [path for path in (ROOT / "skills").iterdir() if path.is_dir()]
        self.assertEqual(len(skills), 6)
        for skill in skills:
            with self.subTest(skill=skill.name):
                self.assertTrue((skill / "SKILL.md").is_file())

    def test_role_frontmatter_and_tool_boundaries(self):
        agents = sorted((ROOT / "agents").glob("*.md"))
        self.assertEqual({path.stem for path in agents}, set(EXPECTED_AGENTS))
        for path in agents:
            with self.subTest(agent=path.stem):
                lines = path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(lines[0], "---")
                self.assertIn("---", lines[1:], "missing frontmatter terminator")
                end = lines.index("---", 1)
                metadata = yaml.safe_load("\n".join(lines[1:end]))
                self.assertIsInstance(metadata, dict)
                self.assertEqual(metadata["name"], path.stem)
                self.assertIsInstance(metadata["description"], str)
                self.assertTrue(metadata["description"].strip())
                self.assertIsInstance(metadata["tools"], list)
                self.assertTrue(metadata["tools"])
                self.assertIn(metadata["model"], {"haiku", "sonnet", "opus"})
                model, tools = EXPECTED_AGENTS[path.stem]
                self.assertEqual(metadata["model"], model)
                self.assertEqual(metadata["tools"], tools)
                if path.stem in {
                    "vibeskills-scout", "vibeskills-verifier", "vibeskills-reviewer"
                }:
                    self.assertFalse(
                        {"Edit", "Write", "NotebookEdit"}.intersection(metadata["tools"])
                    )


if __name__ == "__main__":
    unittest.main()
