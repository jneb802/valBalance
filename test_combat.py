import json
import random
import unittest
from copy import deepcopy
from pathlib import Path

from combat import calibrate, distribution, simulate
from weapon import animation_landmarks


class CombatTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / 'examples'
        self.profile = json.loads((root / 'snuffiss-weapon-source.json').read_text())
        self.scenario = json.loads((root / 'blackforest-v3.json').read_text())
        self.target = self.profile['targets'][0]

    def run_combat(self, health, stamina=None):
        return simulate(self.profile, self.target, health, 'after_conversion', random.Random(1),
                        stamina or self.scenario['stamina'], False)

    def test_first_strike_starts_at_source_hit_event(self):
        result = self.run_combat(1)
        self.assertEqual(result['htk'], 1)
        self.assertEqual(result['ttk'], animation_landmarks(self.profile)['clip_hit_landmark_seconds'])

    def test_poison_is_ticked_not_counted_as_immediate(self):
        p = self.profile
        p['effects']['poison_conversion_percent'] = 0
        p['effects']['double_damage_chance_percent'] = 0
        p['effects']['added_damage_percent']['poison'] = 10000
        result = self.run_combat(1000)
        self.assertGreater(result['ttk'], animation_landmarks(p)['clip_hit_landmark_seconds'])

    def test_stamina_recovery_delays_long_fights(self):
        full = self.run_combat(5000)
        limited = deepcopy(self.scenario['stamina'])
        limited['initial'] = limited['cost_per_attack']
        empty = self.run_combat(5000, limited)
        self.assertGreater(empty['ttk'], full['ttk'])
        self.assertGreater(empty['stamina_wait_seconds'], 0)

    def test_dot_kill_between_attacks_does_not_count_an_extra_hit(self):
        # Fixed damage, fixed skill; a very long cycle allows a one-hit burn kill.
        p = self.profile
        p['effects']['double_damage_chance_percent'] = 0
        p['animation']['exit_transition'] = 10
        result = self.run_combat(600)
        self.assertEqual(result['htk'], 1)
        self.assertGreater(result['ttk'], animation_landmarks(p)['clip_hit_landmark_seconds'])

    def test_reproducible_distributions_keep_orders_separate(self):
        args = (self.profile, self.target, 800, self.scenario['stamina'], 50, 19)
        self.assertEqual(distribution(*args), distribution(*args))
        self.assertEqual(set(distribution(*args)), {'before_conversion', 'after_conversion'})

    def test_incoming_values_do_not_depend_on_offensive_random_rolls(self):
        self.scenario['trials'] = 5
        a = calibrate(self.profile, self.scenario)
        self.scenario['seed'] += 1
        b = calibrate(self.profile, self.scenario)
        self.assertEqual([r['htd'] for r in a['enemies']], [327, 6, 300, 5, 4])
        self.assertEqual([r['htd'] for r in a['enemies']], [r['htd'] for r in b['enemies']])

    def test_invalid_unsupported_inputs_fail(self):
        self.target['armor'] = 1
        with self.assertRaisesRegex(ValueError, 'zero monster armor'):
            self.run_combat(1000)
        with self.assertRaisesRegex(ValueError, 'trials'):
            distribution(self.profile, self.target, 800, self.scenario['stamina'], 0, 1)


if __name__ == '__main__':
    unittest.main()
