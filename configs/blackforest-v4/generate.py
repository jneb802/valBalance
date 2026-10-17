"""Fit stars to role HTD and generate an explicit, isolated Tier 1 candidate.

Run from any directory. Does not write to a game profile or server.
"""
import json
from copy import deepcopy
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TYPES = ('blunt', 'slash', 'pierce', 'fire', 'frost', 'lightning', 'poison', 'spirit')


def received(damage, player, native, armor):
    damage = deepcopy(damage)
    converted = sum(damage.get(t, 0) for t in TYPES[:3]) * player['conversion']
    for kind in TYPES[:3]:
        damage[kind] = damage.get(kind, 0) * (1 - player['conversion'])
    damage['fire'] = damage.get('fire', 0) + converted
    typed = sum(damage.get(t, 0) * (1 - player['resistance'][t]) * native.get(t, 1)
                for t in TYPES)
    reduced = typed - armor if typed > 2 * armor else typed * typed / (4 * armor)
    return reduced + damage.get('damage', 0)


def htd(damage, player, native):
    health = player['health']
    for hits in range(1, 100001):
        armor = player['low_armor'] if health <= player['health'] * player['threshold'] else player['armor']
        loss = received(damage, player, native, armor)
        if loss <= 0:
            return None
        health -= loss
        if health <= 1e-9:
            return hits
    raise ValueError('HTD exceeds calculation limit')


def generate():
    design = yaml.safe_load((HERE / 'design.yaml').read_text())
    defense = yaml.safe_load((HERE / 'players.yaml').read_text())
    sources = json.loads((HERE / 'creature-source.json').read_text())
    baseline = design['baseline']
    players, native = defense['players'], defense['native']
    reference = players[baseline['reference_player']]
    rows, catalogue, rules, aliases = [], {}, [], {}
    for key, spec in design['creatures'].items():
        source = sources[spec['prefab']]
        attacks = {
            name: {t: values.get('m_' + t, 0) for t in (*TYPES, 'damage')}
            for name, values in source['attacks'].items()
        }
        attacks = {name: damage for name, damage in attacks.items() if sum(damage.values()) > 0}
        if not attacks:
            raise ValueError(f'{key}: no direct attack data')
        target = baseline['target_htd'][spec['role']]
        for stars in range(baseline['maximum_stars'] + 1):
            scaled = {a: {t: v * (1 + baseline['damage_per_star'] * stars) for t, v in d.items()}
                      for a, d in attacks.items()}
            hit_counts = {a: htd(d, reference, native) for a, d in scaled.items()}
            valid = {a: h for a, h in hit_counts.items() if h is not None}
            if valid and min(valid.values()) <= target:
                break
        else:
            raise ValueError(f'{key}: target cannot be reached')
        attack = min(valid, key=lambda a: (valid[a], -received(scaled[a], reference, native, reference['armor'])))
        alias = 'VB16_T01_' + key
        aliases[key] = alias
        catalogue[alias] = dict(prefabName=spec['prefab'], spawnCost=100,
                               spawnType={'standard': 'common', 'magic': 'rare', 'rare': 'elite',
                                          'miniboss': 'unique', 'boss': 'unique'}[spec['role']],
                               biome='BlackForest', enabled=True, dropsEnabled=False)
        rules.append(dict(creatures=[alias], minStars=stars, maxStars=stars))
        rows.append(dict(name=key, prefab=spec['prefab'], role=spec['role'], stars=stars,
                         health=source['base_health'] * (1 + baseline['health_per_star'] * stars),
                         reference_attack=attack, target_htd=target,
                         attacks={a: dict(raw_damage=sum(d.values()), damage=d,
                                          htd={p: htd(d, values, native) for p, values in players.items()})
                                  for a, d in scaled.items()}))
    phases = []
    wave_rows = []
    for number, wave in enumerate(design['waves'], 1):
        assert all(isinstance(n, int) and 0 < n <= 32767 for n in wave['creatures'].values())
        phases.append([dict(creature=aliases[name], amount=count) for name, count in wave['creatures'].items()])
        wave_rows.append(dict(number=number, **wave, count=sum(wave['creatures'].values())))
    assert len(phases) == 16
    assert all(w['count'] == 14 for w in wave_rows)
    assert [next((n for n in w['creatures'] if design['creatures'][n]['role'] in ('miniboss', 'boss')), None)
            for w in wave_rows if w['number'] % 4 == 0] == ['Troll', 'RancidChampion', 'Brenna', 'Elder']
    entry = dict(tributeName=design['tribute']['prefab'], tributeAmount=design['tribute']['amount'],
                 rewards=dict(DustRare=10, EssenceRare=10, ReagentRare=10), hardMode=False, siegeMode=False,
                 wildshrineWaveStartLocalization='Tier 1: the forest and its dead awaken. Sixteen waves.',
                 wildshrineWaveEndLocalization='Tier 1 complete. The Elder has fallen.',
                 wildLevelDefinition=dict(levelIndex=1, biome='BlackForest', waveFormat='DynamicBoss',
                     numPhases=16, maxCreaturesPerPhaseOverride=14,
                     levelWarningLocalization='Minibosses in waves 4, 8, and 12. The Elder in wave 16.',
                     onlySelectMonsters=list(catalogue), commonSpawnModifiers={}, rareSpawnModifiers={},
                     eliteSpawnModifiers={}, creatureRules=rules, explicitPhases=phases))
    documents = {
        'WildShrines.fragment.yaml': {'wildShrines': [dict(definitionForWildShrine=design['shrine'], wildShrineLevelsConfig=[entry])]},
        'SpawnableCreatures.fragment.yaml': {'creatures': catalogue},
        'UnrelatedLevels.exclusions.yaml': {'excludeSelectMonsters': list(catalogue)},
        'results.yaml': dict(status=design['status'], total_creatures=sum(w['count'] for w in wave_rows),
                             assumptions=design['assumptions'], creatures=rows, waves=wave_rows),
    }
    for name, document in documents.items():
        (HERE / name).write_text('# Generated by generate.py. Requires Fortress explicit-wild-phases support.\n' +
                                 yaml.safe_dump(document, sort_keys=False))
    return documents


if __name__ == '__main__':
    generate()
