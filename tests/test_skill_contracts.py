from __future__ import annotations

import unittest
from pathlib import Path

from tests.eval_coverage import covers_adversarial


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class SkillContractTests(unittest.TestCase):
    """Guard the user-facing communication rules every skill must carry."""

    def skill_files(self) -> list[Path]:
        files = sorted(path / "SKILL.md" for path in SKILLS.iterdir() if path.is_dir())
        self.assertTrue(files, "no skills discovered")
        return files

    @covers_adversarial("EVAL-ARTIFACT-LANGUAGE-DRIFT")
    def test_every_skill_separates_user_language_from_artifact_contract(self) -> None:
        for skill_file in self.skill_files():
            text = skill_file.read_text(encoding="utf-8")
            with self.subTest(skill=skill_file.parent.name):
                self.assertIn("## Respond in the user's language", text)
                self.assertIn("Persisted artifacts are contracts, not chat.", text)
                self.assertIn(
                    "template headings, YAML keys, stable IDs, and status tokens exactly as specified",
                    text,
                )

    def test_every_skill_discloses_where_it_writes_files(self) -> None:
        for skill_file in self.skill_files():
            text = skill_file.read_text(encoding="utf-8")
            with self.subTest(skill=skill_file.parent.name):
                self.assertIn("## Summarize what you did", text)
                self.assertIn("where each created or updated file now lives", text)
                self.assertIn("never claim a file was written that was not", text)
                self.assertIn("This skill normally writes:", text)
                self.assertIn("`.ai/", text)


if __name__ == "__main__":
    unittest.main()
