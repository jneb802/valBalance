import json
import unittest
from pathlib import Path

import yaml

from starfit import closest_stars


class TierWorkshopTests(unittest.TestCase):
    def test_all_tiers_have_four_waves_and_nearest_health_fits(self):
        root = Path(__file__).parent / 'workshops' / 'star-only'
        summary = json.loads((root / 'summary.json').read_text())
        design = yaml.safe_load((root / 'design.yaml').read_text())
        self.assertEqual(sorted(e['tier'] for e in design['events'].values()), list(range(1, 11)))
        self.assertEqual(len(summary['waves']), 40)
        self.assertEqual(len(summary['creatures']), 41)
        for row in summary['creatures']:
            self.assertEqual(row['stars'], closest_stars(row['base_health'], row['target_health'])['stars'])
        for event, definition in design['events'].items():
            waves = [w for w in summary['waves'] if w['event'] == event]
            self.assertEqual([w['wave'] for w in waves], [1, 2, 3, 4])
            for boss in definition['waves']['finale_addition']:
                self.assertTrue(all(boss not in w['counts'] for w in waves[:3]))
                self.assertIn(boss, waves[3]['counts'])
