from __future__ import annotations

import importlib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class AdversarialEvalManifestTests(unittest.TestCase):
    def test_every_automated_case_references_a_discovered_test(self) -> None:
        manifest = yaml.safe_load(
            (ROOT / "evals/adversarial-cases.yaml").read_text(encoding="utf-8")
        )
        for case in manifest["cases"]:
            coverage = case["coverage"]
            with self.subTest(case=case["id"]):
                if coverage["mode"] == "manual":
                    self.assertIsNone(coverage["test"])
                    self.assertGreaterEqual(len(coverage["manual_reason"]), 10)
                    continue
                module_name, class_name, method_name = coverage["test"].rsplit(".", 2)
                test_class = getattr(importlib.import_module(module_name), class_name)
                method = getattr(test_class, method_name, None)
                self.assertTrue(callable(method))
                self.assertIn(case["id"], getattr(method, "adversarial_case_ids", frozenset()))


if __name__ == "__main__":
    unittest.main()
