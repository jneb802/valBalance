import json
import unittest
from copy import deepcopy
from pathlib import Path

from weapon import TYPES, strike, verified_patch_order


class LiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent
        self.profile = json.loads((root / 'examples/snuffiss-weapon-source.json').read_text())
        self.evidence = json.loads((root / 'live_probe/evidence/2026-10-09/controlled-hits.json').read_text())

    def test_observed_damage_matches_source_calculation(self):
        profile = deepcopy(self.profile)
        profile['weapon']['base_damage'] = {t: 100 if t == 'poison' else 0 for t in TYPES}
        profile['weapon']['per_quality'] = dict.fromkeys(TYPES, 0)
        profile['effects']['added_damage_percent'] = dict.fromkeys(TYPES, 0)
        profile['effects']['modify_damage_percent'] = 0
        profile['coins'] = 0
        for case in self.evidence['cases']:
            target = next(t for t in profile['targets'] if t['name'] == case['prefab'])
            result = strike(profile, target, profile['context'], 1, False, verified_patch_order(profile))
            self.assertEqual(case['after_sls']['poison'], 150)
            self.assertEqual(case['after_conversion']['poison'], 71.25)
            converted_type = result['converted_to']
            self.assertEqual(case['after_conversion'][converted_type], 78.75)
            immediate = case['applied_events'][0]['damage']
            self.assertAlmostEqual(sum(immediate.values()), result['immediate_damage'])
            poison_ticks = [e['damage']['poison'] for e in case['applied_events'] if e['damage']['poison']]
            ttl = 1 + result['poison_payload'] ** .5
            self.assertAlmostEqual(poison_ticks[0], result['poison_payload'] / int(ttl), places=5)
            fire_ticks = [e['damage']['fire'] for e in case['applied_events'] if e['damage']['fire']]
            if fire_ticks:
                self.assertAlmostEqual(fire_ticks[0], result['fire_payload'] / 5)
            # Unity accumulates HP in float32, while the Python model uses float64.
            total = sum(sum(e['damage'].values()) for e in case['applied_events'])
            self.assertAlmostEqual(total, case['observed_hp_loss'], delta=.005)

    def test_changed_binary_or_version_requires_new_evidence(self):
        self.assertEqual(verified_patch_order(self.profile), 'before_conversion')
        for key in ('sls_assembly_sha256', 'epicloot_assembly_sha256'):
            changed = deepcopy(self.profile)
            changed['sources'][key] = 'different-binary'
            with self.assertRaisesRegex(ValueError, 'does not match'):
                verified_patch_order(changed)
        self.profile['game_version'] = 'different-version'
        with self.assertRaisesRegex(ValueError, 'different game version'):
            verified_patch_order(self.profile)

    def test_patch_list_alone_is_not_controlled_hit_evidence(self):
        self.profile['observed_patch_order']['validation'] = 'patch-list-only'
        with self.assertRaisesRegex(ValueError, 'controlled-hit'):
            verified_patch_order(self.profile)


if __name__ == '__main__':
    unittest.main()
