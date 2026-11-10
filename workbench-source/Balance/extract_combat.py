"""Export creature combat fields from installed Unity bundles without starting Valheim."""
import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

import UnityPy
import yaml
from UnityPy.classes import PPtr

HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLES = Path.home() / ('Library/Application Support/Steam/steamapps/common/'
    'Valheim/Valheim.app/Contents/Resources/Data/StreamingAssets/SoftRef/Bundles')
TYPES = ('damage', 'blunt', 'slash', 'pierce', 'fire', 'frost', 'lightning', 'poison', 'spirit')
CHARACTERS = {'Humanoid', 'Character', 'Player'}
IGNORE = {'ZNetView', 'ZSyncTransform', 'ZSyncAnimation', 'CharacterDrop', 'FootStep',
    'LevelEffects', 'VisEquipment', 'LODGroup', 'LodFadeInOut', 'Ragdoll',
    'RandomAnimation', 'RandomSpeak', 'AudioMan', 'ZSFX', 'LightFlicker',
    'EffectFade', 'Billboard', 'ParticleDecal', 'Tail',
    'LookAt', 'Eye', 'LodLight', 'RandomFlyingBird', 'FloatingTerrain', 'AnimatorEffect'}
IGNORE.update({'PreBuildScriptableObject', 'MagicaCloth', 'MagicaCapsuleCollider',
    'CamShaker', 'LightLod', 'MeleeWeaponTrail', 'ParticleIntensityScaler', 'GlobalWind',
    'HoverText', 'MaterialVariation', 'PlayerClothWindShelter', 'UNRESOLVED_SCRIPT'})
CHARACTER_FIELDS = {'m_health', 'm_boss', 'm_damageModifiers', 'm_defaultItems',
    'm_randomWeapon', 'm_randomArmor', 'm_randomShield', 'm_randomSets', 'm_randomItems',
    'm_unarmedWeapon', 'm_deathEffects', 'm_hitEffects', 'm_critHitEffects',
    'm_perfectBlockStatusEffect', 'm_useAltStatusEffectScaling'}
SHARED_FIELDS = {'m_name', 'm_itemType', 'm_damages', 'm_damagesPerLevel', 'm_attack',
    'm_secondaryAttack', 'm_attackStatusEffect', 'm_attackStatusEffectChance',
    'm_spawnOnHit', 'm_spawnOnHitTerrain', 'm_dodgeable', 'm_blockable',
    'm_attackForce', 'm_backstabBonus', 'm_ammoType', 'm_skillType', 'm_tamedOnly',
    'm_hitEffect', 'm_hitTerrainEffect', 'm_startEffect', 'm_triggerEffect',
    'm_equipStatusEffect', 'm_setStatusEffect'}


class CatalogDumper(yaml.CSafeDumper):
    """Keep small value maps readable without expanding every damage type to a line."""


def represent_mapping(dumper, value):
    scalar = all(not isinstance(v, (dict, list)) for v in value.values())
    return dumper.represent_mapping('tag:yaml.org,2002:map', value, flow_style=scalar)


CatalogDumper.add_representer(dict, represent_mapping)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Exporter:
    def __init__(self, bundles):
        self.env = UnityPy.Environment()
        self.sources = []
        for path in bundles:
            self.env.load_file(str(path))
            self.sources.append({'bundle': path.name, 'sha256': digest(path)})
        self.paths = {(o.deref().assets_file.name, o.path_id): p for p, o in self.env.container.items()}
        self.nodes = {}
        self.pending = deque()
        self.errors = []
        self.cache = {}
        self.status_by_name = {}
        for obj in self.env.objects:
            if obj.type.name == 'MonoBehaviour':
                # Scriptable status effects have no owning GameObject.
                data = self.tree(obj)
                if not data.get('m_GameObject', {}).get('m_PathID') and data.get('m_Name'):
                    self.status_by_name[data['m_Name']] = obj

    def tree(self, obj):
        key = (obj.assets_file.name, obj.path_id)
        if key not in self.cache:
            self.cache[key] = obj.read_typetree()
        return self.cache[key]

    def resolve(self, obj, ref, context):
        if not ref.get('m_PathID'):
            return None
        try:
            return PPtr(m_FileID=ref['m_FileID'], m_PathID=ref['m_PathID'],
                        assetsfile=obj.assets_file).deref()
        except Exception as error:
            self.errors.append({'context': context, 'reference': ref, 'error': str(error)})
            return None

    def classname(self, obj):
        script = self.resolve(obj, self.tree(obj)['m_Script'], 'script:' + str(obj.path_id))
        return script.read().m_ClassName if script else 'UNRESOLVED_SCRIPT'

    def components(self, obj):
        return [pair.component.deref() for pair in obj.read().m_Component
                if pair.component.type.name == 'MonoBehaviour']

    def key(self, obj):
        data = self.tree(obj)
        name = data.get('m_Name') or self.classname(obj)
        return name + '@' + str(obj.path_id)

    def enqueue(self, obj):
        key = self.key(obj)
        if key not in self.nodes:
            self.nodes[key] = None
            self.pending.append(obj)
        return key

    def convert(self, obj, value, context):
        if isinstance(value, dict):
            if set(value) == {'m_FileID', 'm_PathID'}:
                target = self.resolve(obj, value, context)
                if target is None:
                    return None
                if target.type.name in ('GameObject', 'MonoBehaviour'):
                    return {'ref': self.enqueue(target)}
                # Preserve other asset identity, but do not export mesh/audio/texture data.
                return {'asset_type': target.type.name, 'path_id': target.path_id}
            return {k: self.convert(obj, v, context + '.' + k) for k, v in value.items()}
        if isinstance(value, list):
            return [self.convert(obj, v, context + '[]') for v in value]
        return value

    def component(self, obj):
        cls = self.classname(obj)
        data = self.tree(obj)
        if cls in IGNORE:
            return None
        if cls in CHARACTERS:
            fields = {k: v for k, v in data.items() if k in CHARACTER_FIELDS}
        elif cls == 'ItemDrop':
            shared = data['m_itemData']['m_shared']
            fields = {k: v for k, v in shared.items() if k in SHARED_FIELDS or k.startswith('m_ai')}
            fields['prefab_quality'] = data['m_itemData']['m_quality']
            fields['prefab_world_level'] = data['m_itemData']['m_worldLevel']
        else:
            fields = {k: v for k, v in data.items()
                      if k not in ('m_GameObject', 'm_Script', 'm_Name', 'm_EditorClassIdentifier')}
        result = {'class': cls, 'fields': self.convert(obj, fields, cls)}
        # Projectile/Aoe use status-effect names rather than asset pointers.
        names = {v for k, v in fields.items()
                 if 'statusEffect' in k and isinstance(v, str) and v}
        result['named_status_effects'] = {
            name: self.enqueue(self.status_by_name[name]) for name in sorted(names)
            if name in self.status_by_name}
        missing = names - self.status_by_name.keys()
        for name in sorted(missing):
            self.errors.append({'context': cls + '.statusEffect', 'name': name})
        if not result['named_status_effects']:
            del result['named_status_effects']
        return result

    def drain(self):
        while self.pending:
            obj = self.pending.popleft()
            key = self.key(obj)
            data = self.tree(obj)
            node = {'name': data.get('m_Name', ''),
                    'asset': self.paths.get((obj.assets_file.name, obj.path_id)),
                    'components': []}
            if obj.type.name == 'GameObject':
                node['active'] = bool(data['m_IsActive'])
                for component in self.components(obj):
                    result = self.component(component)
                    if result:
                        node['components'].append(result)
                children = []
                for pair in obj.read().m_Component:
                    if pair.component.type.name != 'Transform':
                        continue
                    for child in pair.component.read().m_Children:
                        children.append(self.enqueue(child.read().m_GameObject.deref()))
                if children:
                    node['children'] = children
            else:
                result = self.component(obj)
                if result:
                    node['components'].append(result)
            self.nodes[key] = node

    def export(self):
        creatures = {}
        for path, obj in sorted(self.env.container.items(), key=lambda entry: entry[0]):
            obj = obj.deref()
            if obj.type.name != 'GameObject' or not path.endswith('.prefab'):
                continue
            chars = [(c, self.tree(c)) for c in self.components(obj)
                     if self.classname(c) in CHARACTERS]
            if not chars:
                continue
            component, char = chars[0]
            name = obj.read().m_Name
            if name == 'Player':
                continue
            row = {'asset': path, 'base_health': char['m_health'],
                   'current_prefab_health': char['m_health'],
                   'native_damage_modifiers': char['m_damageModifiers'],
                   'native_boss': bool(char.get('m_boss')), 'root': self.enqueue(obj), 'attacks': {}}
            sources = {k: v for k, v in char.items() if k in CHARACTER_FIELDS and
                       (k.endswith('Items') or k in ('m_randomWeapon', 'm_randomArmor',
                        'm_randomShield', 'm_randomSets', 'm_unarmedWeapon'))}
            def equipment(value, source):
                if isinstance(value, dict):
                    if set(value) == {'m_FileID', 'm_PathID'}:
                        target = self.resolve(component, value, name + '.' + source)
                        if target:
                            items = self.components(target) if target.type.name == 'GameObject' else [target]
                            for item in items:
                                fields = self.tree(item).get('m_itemData', {}).get('m_shared')
                                # Humanoid.EquipBestWeapon uses ItemData.IsWeapon.
                                # Decorative staves can contain unused attack defaults.
                                if not fields or fields['m_itemType'] not in (3, 4, 14, 15, 22):
                                    continue
                                item_name = target.read().m_Name
                                for mode in ('m_attack', 'm_secondaryAttack'):
                                    attack = fields[mode]
                                    if not attack['m_attackAnimation']:
                                        continue
                                    attack_name = item_name + ':' + mode.removeprefix('m_')
                                    damage = fields['m_damages']
                                    factor = attack['m_damageMultiplier']
                                    row['attacks'][attack_name] = {
                                        'equipment_source': source, 'item': self.enqueue(target),
                                        'mode': mode, 'animation': attack['m_attackAnimation'],
                                        'attack_type': attack['m_attackType'],
                                        'ai_attack_interval': fields['m_aiAttackInterval'],
                                        'projectiles': attack['m_projectiles'],
                                        'projectile_bursts': attack['m_projectileBursts'],
                                        'burst_interval': attack['m_burstInterval'],
                                        'base_damage': damage,
                                        'attack_multiplier': factor,
                                        'base_payload': {k: v * factor for k, v in damage.items()},
                                        'player_damage_total': sum(damage.get('m_' + t, 0) for t in TYPES) * factor,
                                        'projectile': self.convert(item, attack['m_attackProjectile'], attack_name),
                                        'status_effect': self.convert(item, fields['m_attackStatusEffect'], attack_name),
                                    }
                    else:
                        for k, v in value.items():
                            equipment(v, source + '.' + k)
                elif isinstance(value, list):
                    for i, v in enumerate(value):
                        equipment(v, source + '[' + str(i) + ']')
            for field, value in sources.items():
                equipment(value, field)
            row['attack_inventory'] = 'weapon_attacks' if row['attacks'] else 'no_animated_weapon_attacks'
            creatures[name] = row
        builtin_statuses = {}
        for name in ('Burning', 'Spirit', 'Poison', 'Frost', 'Lightning'):
            if name in self.status_by_name:
                builtin_statuses[name] = self.enqueue(self.status_by_name[name])
            else:
                self.errors.append({'context': 'Character elemental status', 'name': name})
        self.drain()
        # Keep child containers only when they lead to gameplay fields. References
        # to pure visual/audio objects retain names without exporting their hierarchy.
        keep = {key for key, node in self.nodes.items() if node['components']}
        while True:
            parents = {key for key, node in self.nodes.items()
                       if any(child in keep for child in node.get('children', []))}
            if parents <= keep:
                break
            keep.update(parents)
        def prune(value):
            if isinstance(value, dict):
                if set(value) == {'ref'} and value['ref'] not in keep:
                    return {'visual_asset': self.nodes[value['ref']]['name']}
                return {k: prune(v) for k, v in value.items()}
            if isinstance(value, list):
                return [prune(v) for v in value]
            return value
        self.nodes = {k: prune(v) for k, v in self.nodes.items() if k in keep}
        for node in self.nodes.values():
            if 'children' in node:
                node['children'] = [key for key in node['children'] if key in keep]
        roots = {row['root'] for row in creatures.values()}
        def references(value):
            if isinstance(value, dict):
                if set(value) == {'ref'}:
                    yield value['ref']
                else:
                    for v in value.values():
                        yield from references(v)
            elif isinstance(value, list):
                for v in value:
                    yield from references(v)
        for row in creatures.values():
            queue = [row['root']]
            visited = set()
            sources = []
            while queue:
                key = queue.pop()
                if key in visited or (key in roots and key != row['root']):
                    continue
                visited.add(key)
                node = self.nodes[key]
                queue.extend(node.get('children', []))
                queue.extend(references(node))
                for index, component in enumerate(node['components']):
                    fields = component['fields']
                    if component['class'] not in CHARACTERS | {'ItemDrop'} and (
                            any(isinstance(v, dict) and 'm_blunt' in v and 'Modifier' not in k
                                for k, v in fields.items())
                            or component['class'].startswith('SE_')):
                        sources.append({'node': key, 'component': index, 'class': component['class']})
                    queue.extend(component.get('named_status_effects', {}).values())
            row['effect_sources'] = sorted(sources, key=lambda s: (s['node'], s['component']))
            row['attack_inventory'] = ('weapon_attacks' if row['attacks'] else
                                      'effects_only' if sources else 'no_serialized_damage_source')
        return {'schema_version': 2, 'sources': self.sources,
                'scope': 'Serialized base values; no stars, SLS, difficulty, player defenses or random damage roll.',
                'damage_semantics': {
                    'base_payload': 'Item damage times attack multiplier, per hit/projectile at full attacker health. Not encounter DPS.',
                    'interval': 'ai_attack_interval is an AI cooldown, not measured animation duration or attack frequency.',
                    'projectile': 'Projectile.Setup replaces serialized damage when passed HitData; do not add both.',
                    'aoe': 'Aoe.Setup replaces damage only when m_useAttackSettings is enabled.',
                    'effects': 'Separate nodes preserve repeat intervals, lifetime, spawned objects and status fields; do not sum blindly.',
                    'dots': 'Fire, poison and spirit payloads are not necessarily immediate health loss.',
                    'coverage': 'All Character prefabs in supplied bundles. Includes excluded creatures for reference; does not alter spawn eligibility.',
                },
                'builtin_elemental_statuses': builtin_statuses,
                'creatures': dict(sorted(creatures.items())),
                'nodes': dict(sorted(self.nodes.items())), 'unresolved': self.errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundles', type=Path, default=DEFAULT_BUNDLES)
    parser.add_argument('--bundle', action='append', required=True,
                        help='Bundle name; repeat for its shared dependencies')
    parser.add_argument('--output', type=Path, default=HERE / 'creatures.yaml')
    args = parser.parse_args()
    exporter = Exporter([args.bundles / name for name in args.bundle])
    result = exporter.export()
    args.output.write_text(yaml.dump(result, Dumper=CatalogDumper,
                                    sort_keys=False, allow_unicode=True, width=110))
    print(json.dumps({'creatures': len(result['creatures']),
                      'attacks': sum(len(c['attacks']) for c in result['creatures'].values()),
                      'nodes': len(result['nodes']), 'unresolved': len(result['unresolved'])}))
    if result['unresolved']:
        raise SystemExit('Unresolved asset references; inspect output before using this catalog.')


if __name__ == '__main__':
    main()
