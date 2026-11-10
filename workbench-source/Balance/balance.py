"""Offline tier targets and star fitting. Does not write encounter configs."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TYPES = ('damage', 'blunt', 'slash', 'pierce', 'fire', 'frost', 'lightning', 'poison', 'spirit')


def number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f'{name} must be finite and at least {minimum}')
    return value


def read(path):
    return yaml.load(Path(path).read_text(), Loader=yaml.CSafeLoader)


def targets(model, tier, role):
    if model['schema_version'] != 1:
        raise ValueError('Unsupported model schema')
    limits = model['tier']
    if isinstance(tier, bool) or not isinstance(tier, int) or not limits['minimum'] <= tier <= limits['maximum']:
        raise ValueError('Tier is outside the configured range')
    spec = model['roles'][role]
    counts = spec['modifiers']
    if (not isinstance(counts, list) or len(counts) != 2 or
            any(isinstance(n, bool) or not isinstance(n, int) for n in counts) or not 0 <= counts[0] <= counts[1]):
        raise ValueError('Modifier counts require ordered nonnegative integer bounds')
    if role == 'standard' and counts != [0, 0]:
        raise ValueError('Standard creatures must have zero intrinsic modifiers')
    result = {'tier': tier, 'role': role, 'modifiers': spec['modifiers']}
    for stat in ('health', 'damage'):
        base, factor = model['baseline'][stat], spec[stat]
        step = number(limits[stat + '_per_step'], stat + ' tier factor', 1)
        result[stat] = None if base is None or factor is None else (
            number(base, 'baseline ' + stat, 0.001) * number(factor, role + ' ' + stat, 0.001) * step ** (tier - 1))
    return result


def field(mapping, key, default=None):
    return next((v for k, v in (mapping or {}).items() if k.lower() == key.lower()), default)


def scaling(reference, prefab, native_boss, biome):
    if not isinstance(native_boss, bool):
        raise ValueError(f'{prefab}: native boss flag has not been verified')
    cfg = reference['settings']
    levels = reference['level_settings']
    biomes = field(levels, 'biomeConfiguration', {})
    if biome not in biomes:
        raise ValueError('Unknown biome in SLS snapshot: ' + biome)
    # Stat dictionaries are merged All -> specific biome -> creature. Boss
    # per-star defaults override biome values before creature overrides.
    layers = [biomes.get('All', {})]
    if biome != 'All':
        layers.append(biomes[biome])
    base = {'BaseHealth': 1, 'BaseDamage': 1}
    per = {'HealthPerLevel': cfg['EnemyHealthMultiplier'], 'DamagePerLevel': 0}
    received = {}
    for layer in layers:
        base.update(field(layer, 'CreatureBaseValueModifiers', {}) or {})
        per.update(field(layer, 'CreaturePerLevelValueModifiers', {}) or {})
        received.update(field(layer, 'DamageRecievedModifiers', {}) or {})
    if native_boss:
        per.update(HealthPerLevel=cfg['BossEnemyHealthMultiplier'], DamagePerLevel=cfg['BossEnemyDamageMultiplier'])
    creature = field(levels, 'creatureConfiguration', {}).get(prefab, {})
    base.update(field(creature, 'CreatureBaseValueModifiers', {}) or {})
    per.update(field(creature, 'CreaturePerLevelValueModifiers', {}) or {})
    received.update(field(creature, 'DamageRecievedModifiers', {}) or {})
    damage_per_star = per['DamagePerLevel'] or cfg['BossEnemyDamageMultiplier' if native_boss else 'EnemyDamageLevelMultiplier']
    return {
        'health_base': number(base['BaseHealth'], 'BaseHealth', 0.001),
        'health_per_star': number(per['HealthPerLevel'], 'HealthPerLevel'),
        'damage_base': number(base['BaseDamage'], 'BaseDamage', 0.001),
        'damage_per_star': number(damage_per_star, 'DamagePerLevel'),
        'damage_received': received,
        'required_modifiers': field(creature, 'RequiredModifiers', {}) or {},
        'biome': biome,
    }


def recorded_attacks(creature):
    result = {}
    for name, attack in creature['attacks'].items():
        raw = attack['base_payload']
        damage = {t: number(raw.get('m_' + t, 0), name + ':' + t) for t in TYPES}
        if sum(damage.values()) > 0:
            result[name] = damage
    if not result:
        raise ValueError('No damaging weapon payload; inspect effect_sources in the creature catalog')
    return result


def fit(model, reference, prefab, creature, tier, role, biome):
    excluded = read(HERE / 'creature-roles.yaml').get('excluded_prefabs', {})
    if prefab in excluded:
        raise ValueError(f'{prefab} is excluded from balancing: {excluded[prefab]}')
    target = targets(model, tier, role)
    if target['health'] is None or target['damage'] is None:
        raise ValueError(f'{role}: health or damage target is unset')
    scale = scaling(reference, prefab, creature['native_boss'], biome)
    base_health = number(creature['base_health'], 'prefab health', 0.001)
    if creature.get('current_prefab_health') != base_health:
        raise ValueError(f'{prefab}: historical health differs from the current prefab, or current health is unverified')
    if scale['health_base'] == 1 and scale['health_per_star'] == 0:
        raise ValueError('SLS zero-health-per-star fallback needs separate validation')
    attacks = recorded_attacks(creature)
    reference_attack = max(attacks, key=lambda a: sum(attacks[a].values()))
    damage = sum(attacks[reference_attack].values())
    settings = model['fitting']
    low, high = settings['minimum_stars'], settings['maximum_stars']
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (low, high)) or not 0 <= low <= high <= 10000:
        raise ValueError('Star search requires integer bounds within 0..10000')
    ht = number(settings['health_tolerance'], 'health tolerance')
    dt = number(settings['damage_tolerance'], 'damage tolerance')
    hw = number(settings['health_weight'], 'health weight', 0.001)
    dw = number(settings['damage_weight'], 'damage weight', 0.001)
    best = None
    accepted = []
    for stars in range(low, high + 1):
        health = base_health * (scale['health_base'] + stars * scale['health_per_star'])
        payload = damage * scale['damage_base'] * (1 + stars * scale['damage_per_star'])
        he, de = health / target['health'] - 1, payload / target['damage'] - 1
        score = hw * math.log(health / target['health']) ** 2 + dw * math.log(payload / target['damage']) ** 2
        row = {'stars': stars, 'health': health, 'damage': payload, 'health_error': he, 'damage_error': de, 'score': score}
        if best is None or score < best['score']:
            best = row
        if abs(he) <= ht + 1e-12 and abs(de) <= dt + 1e-12:
            accepted.append(row)
    # If feasible, choose within tolerance, even if an infeasible point has a lower score.
    selected = min(accepted, key=lambda r: r['score']) if accepted else best
    factor = scale['damage_base'] * (1 + selected['stars'] * scale['damage_per_star'])
    return {
        'prefab': prefab, 'target': target, 'scaling': scale,
        'status': 'recorded_payload_fit' if accepted else 'no_joint_star_range',
        'candidate': selected, 'acceptable_star_range': [accepted[0]['stars'], accepted[-1]['stars']] if accepted else None,
        'reference_attack': reference_attack,
        'attacks': {name: {t: v * factor for t, v in damage_types.items()} for name, damage_types in attacks.items()},
        'ttk': None, 'htd': None, 'ready_for_encounter': False,
        'unresolved': [
            'Uses full-health weapon payloads including attack multipliers; linked effects, hit counts, timing and conditional multipliers are not simulated.',
            'Role modifier selection, random/required SLS suppression and final modifier effects are not applied.',
            'Player offense, defense, recovery and current patch-order evidence are required for TTK/HTD.',
            'World health and difficulty factors are not included; this is the unit-world-factor comparison.',
            'Room compatibility and summons need separate validation.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['targets', 'fit'])
    parser.add_argument('--model', type=Path, default=HERE / 'model.yaml')
    parser.add_argument('--tier', type=int)
    parser.add_argument('--role', choices=['standard', 'magic', 'rare', 'miniboss', 'boss'])
    parser.add_argument('--creature')
    parser.add_argument('--biome', help='Physical room biome used by SLS, not the creature origin biome')
    args = parser.parse_args()
    model = read(args.model)
    try:
        if args.command == 'targets':
            output = [targets(model, tier, role)
                      for tier in ([args.tier] if args.tier is not None else range(model['tier']['minimum'], model['tier']['maximum'] + 1))
                      for role in ([args.role] if args.role else model['roles'])]
        else:
            if args.tier is None or not args.role or not args.creature or not args.biome:
                raise ValueError('fit requires --tier, --role, --creature and --biome')
            creatures = read(HERE / 'creatures.yaml')['creatures']
            output = fit(model, read(HERE / 'sls-reference.yaml'), args.creature, creatures[args.creature], args.tier, args.role, args.biome)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  (args.model, HERE / 'creatures.yaml', HERE / 'sls-reference.yaml', HERE / 'creature-roles.yaml')}
        print(json.dumps({'input_hashes': hashes, 'result': output}, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
