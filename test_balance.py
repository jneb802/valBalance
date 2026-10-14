import tempfile
import unittest
from pathlib import Path

import yaml

from balance import DEFAULT_MODEL, plan


class BalanceModelTests(unittest.TestCase):
    def test_tier_and_rarity_are_separate(self):
        self.assertEqual(plan(1, "normal")["health_factor"], 1)
        self.assertAlmostEqual(plan(2, "rare")["health_factor"], 10.878)
        self.assertAlmostEqual(plan(3, "magic")["raw_damage_per_hit_factor"], 1.06 ** 2 * 1.04)
        self.assertIsNone(plan(2, "rare")["htd"])

    def test_edits_load_without_changing_reference(self):
        data = yaml.safe_load(DEFAULT_MODEL.read_text())
        data["adopted"]["tier"]["health_per_step"] = 1.2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.yaml"
            path.write_text(yaml.safe_dump(data))
            result = plan(2, "normal", path, DEFAULT_MODEL)
        self.assertAlmostEqual(result["health_factor"], 1.2)
        self.assertNotEqual(result["model_sha256"], plan(2, "normal")["model_sha256"])
        self.assertEqual(result["player_sha256"], plan(2, "normal")["model_sha256"])

    def test_invalid_inputs(self):
        for tier in (0, -1, 1.5, True, 101):
            with self.assertRaises(ValueError):
                plan(tier, "normal")
        with self.assertRaises(ValueError):
            plan(1, "unique")

    def test_unsafe_yaml_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.yaml"
            path.write_text("!!python/object:builtins.object {}")
            with self.assertRaises(ValueError):
                plan(1, "normal", path)
