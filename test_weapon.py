import copy
import json
from pathlib import Path
import unittest

from weapon import audit, coin_bonus, evaluate_events, strike, weapon_damage


class WeaponTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((Path(__file__).parent / 'examples/snuffiss-weapon-source.json').read_text())

    def test_quality_and_equipped_effects(self):
        damage = weapon_damage(self.profile, self.profile['context'])
        self.assertAlmostEqual(damage['pierce'], 281.9553629249)
        self.assertAlmostEqual(damage['lightning'], 77.5377248044)
        self.assertAlmostEqual(damage['poison'], 355.8981568520)
        self.assertEqual(self.profile['effects']['double_damage_chance_percent'], 19.5)

    def test_conversion_does_not_count_fire_as_immediate(self):
        p = self.profile
        result = strike(p, p['targets'][0], p['context'], 1, False, 'after_conversion')
        self.assertEqual(result['converted_to'], 'fire')
        self.assertAlmostEqual(result['immediate_damage'], 359.4930877293)
        self.assertGreater(result['fire_payload'], 370)
        self.assertGreater(result['poison_payload'], 126)

    def test_troll_conversion_and_double_damage(self):
        p = self.profile
        normal = strike(p, p['targets'][-1], p['context'], 1, False, 'after_conversion')
        double = strike(p, p['targets'][-1], p['context'], 1, True, 'after_conversion')
        self.assertEqual(normal['converted_to'], 'pierce')
        self.assertAlmostEqual(double['immediate_damage'], 2 * normal['immediate_damage'])

    def test_health_and_dodge_state_are_explicit(self):
        p = self.profile
        context = copy.deepcopy(p['context'])
        context['health'] -= 100
        full = weapon_damage(p, p['context'])['pierce']
        hurt = weapon_damage(p, context)['pierce']
        self.assertAlmostEqual(hurt / full, 1.2, places=6)
        context['dodge_buff_active'] = True
        self.assertGreater(weapon_damage(p, context)['pierce'], hurt)

    def test_audit_refuses_to_invent_cadence_or_kill_metrics(self):
        result = audit(self.profile)
        self.assertIsNone(result['ttk'])
        self.assertIsNone(result['htk'])
        self.assertIsNone(result['timing']['attack_interval_seconds'])
        self.assertAlmostEqual(result['timing']['clip_hit_landmark_seconds'], 0.343992782)
        self.assertTrue(result['unresolved'])

    def test_damage_events_count_strikes_not_dot_ticks(self):
        result = evaluate_events({'monster_health': 100, 'attack_start': 1, 'events': [
            {'time': 1.3, 'kind': 'weapon_hit', 'amount': 60},
            {'time': 1.4, 'kind': 'proc', 'amount': 10},
            {'time': 2.4, 'kind': 'dot', 'amount': 30}]})
        self.assertEqual(result['htk'], 1)
        self.assertAlmostEqual(result['ttk'], 1.4)
        self.assertEqual(result['killing_event'], 'dot')

    def test_nonlethal_and_invalid_trace(self):
        trace = {'monster_health': 100, 'attack_start': 0, 'events': [{'time': 1, 'kind': 'weapon_hit', 'amount': 60}]}
        self.assertIsNone(evaluate_events(trace)['ttk'])
        trace['events'].append({'time': 0, 'kind': 'dot', 'amount': 40})
        with self.assertRaises(ValueError):
            evaluate_events(trace)

    def test_coin_formula_boundaries(self):
        self.assertEqual(coin_bonus(12, 0), 0)
        self.assertAlmostEqual(coin_bonus(12, 1000), 0.145)
        self.assertAlmostEqual(coin_bonus(12, 3221), 0.1913768146)


if __name__ == '__main__':
    unittest.main()
