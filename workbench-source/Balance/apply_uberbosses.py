"""Write the Uber boss encounter settings from Balance/uberbosses.json into Config/encounters.yaml.

The attack numbers in the same file are baked into the bundle by Unity/Editor~/UberBossAuthoring.cs;
this script only owns the uber* sections of encounters.yaml. Run from the repository:

    python3 Balance/apply_uberbosses.py            # rewrite Config/encounters.yaml
    python3 Balance/apply_uberbosses.py --check    # exit 1 when encounters.yaml is out of date
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SECTIONS = {
    'VE_UberEikthyr': 'uberEikthyr', 'VE_UberElder': 'uberElder', 'VE_UberBonemass': 'uberBonemass', 'VE_UberModer': 'uberModer',
    'VE_UberYagluth': 'uberYagluth', 'VE_UberQueen': 'uberQueen', 'VE_UberFader': 'uberFader',
}


def load(path=HERE / 'uberbosses.json'):
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or not isinstance(data.get('bosses'), list):
        raise ValueError('uberbosses.json must use schema 1 with a bosses list.')
    return data


def scalar(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return '[' + ', '.join(scalar(v) for v in value) + ']'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render(data):
    lines = []
    for boss in data['bosses']:
        section = SECTIONS.get(boss['id'])
        if section is None:
            raise ValueError('Unknown Uber boss in uberbosses.json: ' + boss['id'])
        lines.append(section + ':')
        for key, value in boss['settings'].items():
            lines.append('  ' + key + ': ' + scalar(value))
    return '\n'.join(lines) + '\n'


def merge(events_text, block):
    """Replace every existing uber* top-level section with the rendered block, keeping the rest."""
    pattern = re.compile(r'^uber[A-Za-z]+:\n(?:  .*\n)*', re.M)
    matches = list(pattern.finditer(events_text))
    if not matches:
        raise ValueError('Config/encounters.yaml has no uber* sections to replace.')
    start, end = matches[0].start(), matches[-1].end()
    between = events_text[start:end]
    if pattern.sub('', between).strip():
        raise ValueError('Non-Uber content sits between the uber* sections; move it before editing.')
    return events_text[:start] + block + events_text[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report whether Config/encounters.yaml matches uberbosses.json')
    args = parser.parse_args()
    events = ROOT / 'Config/encounters.yaml'
    updated = merge(events.read_text(), render(load()))
    if args.check:
        if updated != events.read_text():
            print('Config/encounters.yaml is out of date with Balance/uberbosses.json. Run apply_uberbosses.py.')
            sys.exit(1)
        print('Config/encounters.yaml matches Balance/uberbosses.json.')
        return
    events.write_text(updated)
    print('Wrote Uber boss settings into Config/encounters.yaml.')


if __name__ == '__main__':
    main()
