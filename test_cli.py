import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


APP = Path(__file__).with_name('app.py')


class CommandLineTests(unittest.TestCase):
    def run_app(self, *args):
        return subprocess.run([sys.executable, str(APP), *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def test_example_to_report_and_json(self):
        with tempfile.TemporaryDirectory() as folder:
            scenario = Path(folder) / 'scenario.json'
            self.assertEqual(self.run_app('example', scenario).returncode, 0)
            unresolved = self.run_app('analyze', scenario)
            self.assertEqual(unresolved.returncode, 2)
            self.assertIn('Unresolved player hit', unresolved.stderr)
            data = json.loads(scenario.read_text())
            # Synthetic test fixture only; these are not shipped player offense defaults.
            data['player'].update(hit=500, interval=0.8, windup=0.4, uptime=70)
            scenario.write_text(json.dumps(data))
            report = self.run_app('analyze', scenario)
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertIn('Greydwarf [Fodder]', report.stdout)
            self.assertIn('Troll pack — 12 enemies', report.stdout)
            output = Path(folder) / 'results.json'
            result = self.run_app('analyze', scenario, '--json', '--output', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            parsed = json.loads(output.read_text())
            self.assertEqual(parsed['enemies'][0]['htk'], 3)
            self.assertEqual(len(parsed['waves']), 4)
            self.assertEqual(self.run_app('example', scenario).returncode, 2)

    def test_invalid_scenario_is_actionable(self):
        with tempfile.TemporaryDirectory() as folder:
            scenario = Path(folder) / 'bad.json'
            scenario.write_text('{"version": 99}')
            result = self.run_app('analyze', scenario)
            self.assertEqual(result.returncode, 2)
            self.assertIn('version 1', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_real_weapon_audit_and_withdrawn_scenarios(self):
        examples = APP.parent / 'examples'
        response = self.run_app('weapon', examples / 'snuffiss-weapon-source.json')
        self.assertEqual(response.returncode, 0, response.stderr)
        result = json.loads(response.stdout)
        self.assertEqual(result['weapon'], 'SpearGold_BloodLightning')
        self.assertIsNone(result['ttk'])
        self.assertIn('player to kill monster', result['metric_definitions']['ttk'])
        for name in ('blackforest-stars-v1.json', 'blackforest-modifiers-v2.json'):
            response = self.run_app('analyze', examples / name)
            self.assertEqual(response.returncode, 2)
            self.assertIn('No placeholder damage or timing', response.stderr)


if __name__ == '__main__':
    unittest.main()
