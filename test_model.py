import copy
import unittest

from model import DEFAULTS, analyze, hits_to_die, received


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.data = copy.deepcopy(DEFAULTS)

    def test_hit_breakpoint_and_first_hit_delay(self):
        self.data['player'].update(hit=300, interval=0.8, windup=0.4)
        self.data['enemies'][0]['health'] = 1200
        row = analyze(self.data)['enemies'][0]
        self.assertEqual(row['htk'], 4)
        self.assertAlmostEqual(row['ttk'], 2.8)
        self.data['enemies'][0]['health'] = 1201
        self.assertEqual(analyze(self.data)['enemies'][0]['htk'], 5)

    def test_conditional_armor_hit_sequence(self):
        p = {'health': 100, 'threshold': 75}
        self.assertEqual(hits_to_die(p, 30, 10), 8)
        self.assertEqual(hits_to_die(p, 100, 10), 1)
        self.assertIsNone(hits_to_die(p, 30, 0))

    def test_threshold_endpoints(self):
        self.assertEqual(hits_to_die({'health': 100, 'threshold': 100}, 100, 10), 10)
        self.assertEqual(hits_to_die({'health': 100, 'threshold': 0}, 30, 10), 4)

    def test_physical_curve_and_elemental_split(self):
        p = {'physical_resist': 50, 'elemental_resist': 25}
        self.assertAlmostEqual(received({'physical': 200, 'elemental': 40}, p, 100), 55)
        self.assertEqual(received({'physical': 600, 'elemental': 0}, p, 100), 200)
        self.assertEqual(received({'physical': 0, 'elemental': 0}, p, 0), 0)

    def test_full_resistance_and_sustain(self):
        self.data['player'].update(physical_resist=100, elemental_resist=100)
        output = analyze(self.data)
        self.assertIsNone(output['enemies'][0]['htd'])
        self.assertIsNone(output['waves'][0]['ttd'])
        self.assertIsNone(output['waves'][0]['ratio'])

    def test_empty_wave(self):
        for enemy in self.data['enemies']:
            enemy['counts'][0] = 0
        wave = analyze(self.data)['waves'][0]
        self.assertEqual(wave['clear'], 0)
        self.assertEqual(wave['pressure'], 0)
        self.assertIsNone(wave['ttd'])

    def test_conflicting_targets(self):
        self.data['roles']['Fodder'] = [20, 30, 1, 3, 8, None]
        self.assertFalse(analyze(self.data)['enemies'][0]['target_possible'])

    def test_invalid_inputs(self):
        for key, value in [('interval', 0), ('health', float('nan')), ('uptime', 101), ('hit', -5)]:
            with self.subTest(key=key):
                data = copy.deepcopy(DEFAULTS)
                data['player'][key] = value
                with self.assertRaises(ValueError):
                    analyze(data)
        self.data['enemies'][0]['counts'][0] = 1.5
        with self.assertRaises(ValueError):
            analyze(self.data)


if __name__ == '__main__':
    unittest.main()
