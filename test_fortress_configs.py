import json
import unittest
from pathlib import Path

import yaml


class FortressDraftTests(unittest.TestCase):
    def test_references_and_stars_match_workshop(self):
        root = Path(__file__).parent
        config = root / 'configs/ten-tier'
        creatures = yaml.safe_load((config / 'SpawnableCreatures.fragment.yaml').read_text())['creatures']
        levels = yaml.safe_load((config / 'WildShrines.fragment.yaml').read_text())['wildShrines'][0]['wildShrineLevelsConfig']
        source = json.loads((root / 'workshops/star-only/summary.json').read_text())['creatures']
        expected = {f"VB10_T{r['tier']:02d}_{r['prefab']}": r['stars'] for r in source}
        self.assertEqual(len(levels), 10)
        self.assertEqual(len({x['tributeName'] for x in levels}), 10)
        self.assertEqual(set(creatures), set(expected))
        for entry in levels:
            level = entry['wildLevelDefinition']
            self.assertEqual(level['levelIndex'], 1)
            aliases = set(level['onlySelectMonsters'])
            self.assertEqual(aliases, {r['creatures'][0] for r in level['creatureRules']})
            for rule in level['creatureRules']:
                self.assertEqual(rule['minStars'], expected[rule['creatures'][0]])
                self.assertEqual(rule['maxStars'], rule['minStars'])
            self.assertEqual(sum(creatures[a]['spawnType'] == 'unique' for a in aliases), 1)
        exclusions = yaml.safe_load((config / 'UnrelatedLevels.exclusions.yaml').read_text())
        self.assertEqual(set(exclusions['excludeSelectMonsters']), set(creatures))

    def test_pack_count_bounds(self):
        for percentage, cost, count in [(45, 10, 4), (25, 10, 2), (15, 10, 1), (45, 13, 3), (20, 6, 3), (20, 20, 1)]:
            amount = percentage / cost
            self.assertEqual(max(1, int(amount * 0.9)), count)
            self.assertEqual(max(1, int(amount * 1.1)), count)
