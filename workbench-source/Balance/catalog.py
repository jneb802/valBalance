"""Generate a new editable creature catalog; never overwrite reviewed settings."""
import argparse
import hashlib
import json
from pathlib import Path

import yaml

from balance import HERE, read
from progression import baselines

BIOMES = {'Black Forest': 'BlackForest', 'Mountain': 'Mountain', 'Meadows': 'Meadows',
          'Swamp': 'Swamp', 'Plains': 'Plains', 'Mistlands': 'Mistlands',
          'Ashlands': 'AshLands', 'Deep North': 'DeepNorth', 'Ocean': 'Ocean'}
VARIANTS = {
    'Skeleton_Swamps': 'Swamp',
    'FrozenKing_p2': 'DeepNorth', 'FrozenKing_p3': 'DeepNorth',
    'Skeleton_Hildir': 'BlackForest',
    'Fenring_Cultist_Hildir': 'Mountain',
    'GoblinBruteBros': 'Plains',
    'Charred_Melee_Dyrnwyn': 'AshLands', 'gd_king': 'BlackForest', 'Bonemass': 'Swamp',
    'Dragon': 'Mountain', 'GoblinKing': 'Plains', 'SeekerQueen': 'Mistlands',
    'Fader': 'AshLands', 'FrozenKing': 'DeepNorth', 'Eikthyr': 'Meadows',
}


def generate():
    roles = read(HERE / 'creature-roles.yaml')
    reviewed_ranges = baselines()
    creatures = {}
    for name, assignment in roles['creatures'].items():
        if name in roles.get('excluded_prefabs', {}):
            continue
        hazard = assignment['pool'] == 'hazard'
        enabled = assignment['pool'] in ('candidate', 'hazard')
        role = assignment['role']
        biome = BIOMES.get(assignment['group'], VARIANTS.get(name))
        if enabled and biome is None:
            raise ValueError('Missing biome membership: ' + name)
        entry = {'enabled': enabled, 'role': role or 'excluded', 'biomes': [biome] if biome else [],
                 'stars': None, 'waveLimits': assignment.get('wave_limits', {})}
        baseline = reviewed_ranges.get(name)
        if hazard and baseline is None:
            baseline = dict(minStars=0, maxStars=0, status='pending_review')
        if baseline is not None and (enabled or baseline['minStars'] != 0 or baseline['maxStars'] != 0):
            entry['stars'] = baseline
        if enabled:
            if baseline is None:
                raise ValueError('Missing approved Tier 1 baseline: ' + name)
            entry['notes'] = 'Approved Tier 1 baseline plus fixed stars per tier; see Balance/progression.yaml.'
            if hazard:
                label = 'Elder root' if name == 'TentaRoot' else 'Tentacle'
                entry['notes'] = label + ' hazard; approved Tier 1 baseline plus fixed stars per tier. Not selected for random waves.'
        else:
            entry['notes'] = assignment['group'] + '; excluded by the reviewed catalog.'
        creatures[name] = entry
    minibosses = ['Eikthyr', 'Troll', 'Skeleton_Hildir', 'Draugr_Elite', 'BlobElite', 'Abomination',
                  'Fenring', 'StoneGolem', 'Fenring_Cultist_Hildir', 'GoblinBrute', 'Lox', 'GoblinBruteBros',
                  'SeekerBrute', 'Gjall', 'DvergerMageFire', 'Morgen', 'FallenValkyrie', 'Charred_Melee_Dyrnwyn',
                  'JotunWarriorDualWield', 'Barka']
    bosses = ['gd_king', 'Bonemass', 'Dragon', 'GoblinKing', 'SeekerQueen', 'Fader', 'FrozenKing']
    # Mod-made Uber bosses come from Balance/uberbosses.json. They stay opt-in until their
    # star values and rooms are reviewed, so no Tier 1 baseline is required for them.
    for boss in json.loads((HERE / 'uberbosses.json').read_text())['bosses']:
        creatures[boss['id']] = {'enabled': False, 'role': 'boss', 'biomes': [VARIANTS[boss['source']]],
                                 'stars': {'minStars': 0, 'maxStars': 0, 'status': 'prototype'}, 'waveLimits': {},
                                 'notes': 'Opt-in ' + boss['name'] + '. Final star values and compatible rooms require review before enabling.'}
        bosses.append(boss['id'])
    baseline = HERE / read(HERE / 'progression.yaml')['baseline']
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
              (HERE / 'progression.yaml', HERE / 'creature-roles.yaml', baseline)}
    return {'schemaVersion': 2, 'notes': 'All enabled monsters are eligible at every tier. Tier 1 baselines plus 3 stars per tier. Source hashes: ' + str(hashes),
            'creatures': creatures, 'minibosses': minibosses, 'bosses': bosses,
            'layout': [{'kind': 'miniboss' if i in (3, 6, 9) else 'boss' if i == 10 else 'regular',
                        'standard': 8 if i in (3, 6, 9, 10) else 9, 'magic': 3, 'rare': 2} for i in range(1, 11)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = generate()
    with args.output.open('x') as stream:
        stream.write(yaml.safe_dump(data, sort_keys=False))
