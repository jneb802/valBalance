"""Preview a workbench review as a creature config diff. Use --write to apply."""
import argparse
import copy
import difflib
import json
from pathlib import Path

import yaml
from progression import tier_ranges


def apply_review(config, review):
    if not isinstance(review, dict) or review.get('schema') != 3:
        raise ValueError('Expected a schema-3 workbench review JSON file')
    records = review.get('creatures')
    excluded = yaml.safe_load((Path(__file__).resolve().parent / 'creature-roles.yaml').read_text()).get('excluded_prefabs', {})
    # Mod-made Uber bosses are balanced on their own workbench tab, not in creature reviews.
    catalog = {name for name in config['creatures'] if not name.startswith('VE_')}
    if not isinstance(records, dict) or set(records) - set(excluded) - {n for n in records if n.startswith('VE_')} != catalog:
        raise ValueError('Review must contain the full current creature catalog')
    result = copy.deepcopy(config)
    for name, entry in records.items():
        if name in excluded or name.startswith('VE_'):
            continue
        if not isinstance(entry.get('enabled'), bool) or not isinstance(entry.get('tiers'), dict) or set(entry['tiers']) != {str(t) for t in range(1, 16)}:
            raise ValueError('Invalid inclusion state or tier list: ' + name)
        result['creatures'][name]['enabled'] = True if result['creatures'][name]['role'] == 'hazard' else entry['enabled']
        for tier, values in entry['tiers'].items():
            if not isinstance(values, list) or len(values) != 2 or any(type(v) is not int or not 0 <= v <= 10000 for v in values) or values[0] > values[1]:
                raise ValueError('Invalid star range: ' + name + ' tier ' + tier)
        low, high = entry['tiers']['1']
        expected = tier_ranges(dict(minStars=low, maxStars=high))
        if entry['tiers'] != expected:
            raise ValueError('Higher tiers must follow the Tier 1 baseline plus 3 stars per tier: ' + name)
        target = result['creatures'][name]
        if not entry['enabled'] and target.get('stars') is None and low == high == 0:
            continue
        target['stars'] = dict(target.get('stars') or {}, minStars=low, maxStars=high)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parent.parent / 'Config/creatures.yaml')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    before = args.config.read_text()
    try:
        review = json.loads(args.review.read_text())
        result = apply_review(yaml.safe_load(before), review)
    except (ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        parser.exit(2, 'Review was not applied: ' + str(error) + '\n')
    after = yaml.safe_dump(result, sort_keys=False)
    print(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=str(args.config), tofile='review')), end='')
    if args.write:
        args.config.write_text(after)
        print('Applied locally. Review the diff and validate before deployment.')
    else:
        print('Preview only. Add --write to update the local config.')
