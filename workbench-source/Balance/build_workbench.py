"""Build an offline HTML workshop. Does not modify game configuration."""
import hashlib
import json
import argparse
import datetime
from pathlib import Path

from balance import read, scaling, TYPES
from import_players import import_folder
from progression import tier_ranges
from loot_data import build_loot_data

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODIFIERS = {0: 1, 1: .5, 2: 1.5, 3: 0, 4: 0, 5: .25, 6: 2, 7: .75, 8: 1.25}


def payload(raw):
    return {t: raw.get('m_' + t, 0) for t in TYPES}


def attacks(creature, nodes):
    result = []
    for name, attack in creature['attacks'].items():
        damage = payload(attack['base_payload'])
        if sum(damage.values()) > 0:
            result.append(dict(name=name, damage=damage, scales=True,
                               note='One weapon hit/projectile; not the entire volley or damage per second.'))
    for source in creature['effect_sources']:
        node = nodes[source['node']]
        component = node['components'][source['component']]
        fields = component['fields']
        if component['class'] not in ('Aoe', 'MovementDamage') or not fields.get('m_Enabled', 1):
            continue
        if component['class'] == 'Aoe' and (fields.get('m_useAttackSettings') or not fields.get('m_hitCharacters', 1)):
            continue
        damage = payload(fields.get('m_damage', {}))
        if sum(damage.values()) <= 0:
            continue
        result.append(dict(name=node['name'] + ' / ' + component['class'], damage=damage,
                           scales=False, note='Own effect damage, per contact/tick. Does not use Attack.GetLevelDamageFactor. '
                           'Owner, geometry, repeats and additional SLS modifiers need live validation.',
                           interval=fields.get('m_hitInterval'), radius=fields.get('m_radius')))
    return result


def uber_combat(config, source, reference, bosses):
    """Health, resistances and star scaling for each Uber boss, inherited from the vanilla boss it clones.
    SLS keys creature overrides by prefab name, so the Uber prefab gets the All biome, boss and room biome layers only."""
    result = {}
    for boss in bosses:
        creature = source['creatures'][boss['source']]
        entry = config['creatures'][boss['id']]
        stars = entry.get('stars') or {}
        result[boss['id']] = dict(source=boss['source'], health=creature['base_health'],
                                  native={t: MODIFIERS[creature['native_damage_modifiers'].get('m_' + t, 0)] for t in TYPES if t != 'damage'},
                                  scaling=scaling(reference, boss['id'], creature['native_boss'], 'Mistlands'),
                                  stars=[stars.get('minStars', 0), stars.get('maxStars', 0)], biome=entry['biomes'][0] if entry['biomes'] else 'Unassigned')
    return result


def build_data(imports=False):
    config = read(ROOT / 'Config/creatures.yaml')
    source = read(HERE / 'creatures.yaml')
    reference = read(HERE / 'sls-reference.yaml')
    review = json.loads((HERE / 'review-2026-10-17.json').read_text())
    profiles = read(HERE / 'workbench_players.yaml')
    excluded = read(HERE / 'creature-roles.yaml').get('excluded_prefabs', {})
    dot = {}
    for kind, name in [('fire', 'Burning'), ('spirit', 'Spirit'), ('poison', 'Poison')]:
        node = source['nodes'][source['builtin_elemental_statuses'][name]]
        fields = node['components'][0]['fields']
        dot[kind] = dict(interval=fields['m_damageInterval'], ttl=fields['m_ttl'])
        if kind == 'poison':
            dot[kind].update(base=fields['m_baseTTL'], per_damage=fields['m_TTLPerDamage'], power=fields['m_TTLPower'])
    for player in profiles['players']:
        player['dot'] = dot
    result = []
    for name, entry in config['creatures'].items():
        if name not in source['creatures']:
            continue  # Mod-made creatures such as the Uber bosses have their own tab.
        creature = source['creatures'][name]
        scale = scaling(reference, name, creature['native_boss'], 'Mistlands')
        tiers = tier_ranges(entry.get('stars'))
        result.append(dict(id=name, role=entry['role'], biome=entry['biomes'][0] if entry['biomes'] else 'Unassigned', health=creature['base_health'],
                           native={t: MODIFIERS[creature['native_damage_modifiers'].get('m_' + t, 0)] for t in TYPES if t != 'damage'},
                           scaling=scale, nativeBoss=creature['native_boss'],
                           scalingOverrides=reference['level_settings'].get('creatureConfiguration', {}).get(name, {}),
                           attacks=attacks(creature, source['nodes']), tiers=tiers,
                           enabled=entry['enabled'], configuredTiers=list(range(1, 16)) if entry.get('stars') else [],
                           review=review['creatures'].get(name, {}).get('notes', ''),
                           warning='Phase-specific invulnerability: standalone target simulation may not represent this phase.' if name == 'FrozenKing_p2' else ''))
    inputs = ['creatures.yaml', 'sls-reference.yaml', 'model.yaml', 'review-2026-10-17.json', 'workbench_players.yaml', 'creature-roles.yaml', 'progression.yaml', 'uberbosses.json']
    hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in inputs}
    hashes['Config/creatures.yaml'] = hashlib.sha256((ROOT / 'Config/creatures.yaml').read_bytes()).hexdigest()
    revision = hashlib.sha256(json.dumps({k: v for k, v in hashes.items() if k != 'workbench_players.yaml'}, sort_keys=True).encode()).hexdigest()[:16]
    imported, errors = import_folder(HERE / 'player-imports', profiles['players']) if imports else ([], [])
    if imports:
        for player in imported:
            for choice in player['choices']:
                choice['profile']['dot'] = dot
    uber = json.loads((HERE / 'uberbosses.json').read_text())
    return dict(schema=2, revision=revision, hashes=hashes, loot=build_loot_data(), creatures=result, uberBosses=uber,
                uberCombat=uber_combat(config, source, reference, uber['bosses']), players=imported if imports else profiles['players'],
                importErrors=errors, imports=imports, excludedPrefabs=excluded, builtAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                progression=read(HERE / 'progression.yaml'), scalingRules=dict(defaults=reference['settings'],
                    biomeLayers={name: reference['level_settings']['biomeConfiguration'].get(name, {}) for name in ['All', 'Mistlands']}),
                provenance=profiles['provenance'],
                dot=dot,
                tier_note='Edit each monster’s Tier 1 baseline. Tiers 2–15 add 3 stars to both bounds per tier.')


def render_html(data):
    template = (HERE / 'workbench.template.html').read_text()
    engine = (HERE / 'workbench.js').read_text()
    encoded = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')
    output = template.replace('/*WORKBENCH_DATA*/', 'const DATA = ' + encoded + ';').replace('/*WORKBENCH_ENGINE*/', engine).replace('/*WORKBENCH_UI*/', (HERE / 'workbench-ui.js').read_text())
    for marker, filename in [('/*WORKBENCH_COMMON*/', 'workbench-common.js'), ('/*LOOT_ENGINE*/', 'loot.js'),
                             ('/*WORKBENCH_STYLE*/', 'workbench.css'),
                             ('/*LOOT_YAML*/', 'loot-yaml.js'),
                             ('/*LOOT_UI*/', 'loot-ui.js'), ('/*LOOT_STYLE*/', 'loot.css'),
                             ('<!--LOOT_PANEL-->', 'loot.template.html'),
                             ('/*SCALING_UI*/', 'scaling-ui.js'), ('/*SCALING_STYLE*/', 'scaling.css'),
                             ('<!--SCALING_PANEL-->', 'scaling.template.html'),
                             ('/*UBER_HITS*/', 'uberbosses-hits.js'), ('/*UBER_UI*/', 'uberbosses-ui.js'), ('/*UBER_STYLE*/', 'uberbosses.css'),
                             ('<!--UBER_PANEL-->', 'uberbosses.template.html')]:
        output = output.replace(marker, (HERE / filename).read_text())
    vendor = (HERE / 'vendor/js-yaml-4.3.0.min.js').read_text().split('//# sourceMappingURL=')[0]
    license_text = (HERE / 'vendor/js-yaml.LICENSE').read_text()
    return output.replace('/*YAML_VENDOR*/', '/* js-yaml 4.3.0\n' + license_text + '\n*/\n' + vendor)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--imports', action='store_true', help='Read local player-imports and write workbench.local.html')
    args = parser.parse_args()
    data = build_data(args.imports)
    name = 'workbench.local.html' if args.imports else 'workbench.html'
    (HERE / name).write_text(render_html(data))
    print(f'Built {name}: {len(data["creatures"])} creatures; {len(data["players"])} players; {len(data["importErrors"])} import errors; revision {data["revision"]}')
