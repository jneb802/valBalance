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


if __name__ == '__main__':
    unittest.main()
