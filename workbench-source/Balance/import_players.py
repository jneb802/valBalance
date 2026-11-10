"""Read local Enforcer exports. Never copy private export fields into the page."""
import copy
import datetime
import hashlib
import json
import math
from pathlib import Path

import yaml

ARMOR = {'HelmetDNHeavy': 44, 'ArmorDeepNorthHeavyChest': 44,
         'ArmorDeepNorthHeavylegs': 44, 'CapeDeepNorth': 12}
SKILLS = {'SpearGold_BloodLightning': 'Spears', 'VAGreatswordFader': 'Swords'}
UTILITY = {'Demister', 'LeatherBelt', 'TrinketBloodGoldHealth', 'BoltCharred'}


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError('Invalid ' + label)
    return value


def effects(items):
    totals = {}
    for item in items:
        data = item.get('mCustomdata', {})
        if not isinstance(data, dict):
            raise ValueError('mCustomdata must be a mapping')
        for key, value in data.items():
            if 'MagicItemComponent' not in key or not value:
                continue
            magic = json.loads(value)
            entries = magic.get('Effects', []) + [s['Effect'] for s in magic.get('Sockets', []) if s.get('Effect')]
            for effect in entries:
                name = effect['EffectType']
                totals[name] = totals.get(name, 0) + number(effect['EffectValue'], 'item effect', -10000)
    return totals


def import_folder(folder, templates):
    players, errors, names = [], [], set()
    weapons = {p['weapon']: p for p in templates}
    paths = sorted(set(folder.glob('*.yaml')) | set(folder.glob('*.yml')))
    for path in paths:
        try:
            if path.stat().st_size > 5_000_000:
                raise ValueError('Export exceeds 5 MB')
            raw = path.read_bytes()
            data = yaml.safe_load(raw)
            if not isinstance(data, dict) or not isinstance(data.get('name'), str) or not data['name'].strip():
                raise ValueError('Expected an Enforcer export with name, playerItems and skillLevels')
            name = data['name'].strip()
            if name.casefold() in names:
                raise ValueError('Duplicate character ' + name + '; keep one export per character')
            items, skills = data.get('playerItems'), data.get('skillLevels')
            if not isinstance(items, list) or not isinstance(skills, dict):
                raise ValueError('playerItems must be a list and skillLevels must be a mapping')
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get('prefabName'), str):
                    raise ValueError('Each playerItems entry needs prefabName')
                number(item.get('mQuality'), 'item quality', 1)
                if int(item['mQuality']) != item['mQuality']:
                    raise ValueError('Item quality must be a whole number')
                # Enforcer omits fields with their default value (false).
                item.setdefault('mEquipped', False)
                if not isinstance(item['mEquipped'], bool):
                    raise ValueError('Each item needs a boolean mEquipped')
            # Validate effects even on carried items, before accepting this character.
            effects(items)
            choices = []
            for weapon in items:
                prefab = weapon['prefabName']
                if prefab not in weapons:
                    continue
                source = weapons[prefab]
                skill = skills.get(SKILLS[prefab])
                if skill is None:
                    raise ValueError('Missing skill ' + SKILLS[prefab])
                number(skill, SKILLS[prefab])
                if skill > 100:
                    raise ValueError('Skill exceeds 100; this calculator supports 0–100')
                equipped = [i for i in items if i['mEquipped'] and i['prefabName'] not in weapons] + [weapon]
                fx = effects(equipped)
                armor, raw_armor = 0, 0
                for item in equipped:
                    if item['prefabName'] not in ARMOR:
                        continue
                    base = ARMOR[item['prefabName']] + 2 * (item['mQuality'] - 1)
                    raw_armor += base
                    armor += base * (1 + effects([item]).get('ModifyArmor', 0) / 100)
                profile = copy.deepcopy(source)
                profile.update(id=name, quality=weapon['mQuality'], skill=skill, effects=fx,
                               snapshot_sha256=hashlib.sha256(raw).hexdigest(),
                               source='Local Enforcer import; weapon payload and animation inputs use the verified source reference. Runtime health and stamina require game values.',
                               weapon_selection='Equipped weapon' if weapon['mEquipped'] else 'Carried weapon; explicit selection required',
                               coins=sum(i.get('mStack', 1) for i in items if i['prefabName'] == 'Coins'))
                profile['defense'].update(armor=armor, low_armor=armor + raw_armor * fx.get('ModifyArmorLowHealth', 0) / 100,
                                          conversion=fx.get('PhysToFire', 0) / 100)
                typed = {'blunt': 'Blunt', 'slash': 'Slashing', 'pierce': 'Piercing', 'fire': 'Fire',
                         'frost': 'Frost', 'lightning': 'Lightning', 'poison': 'Poison', 'spirit': 'Spirit'}
                profile['defense']['resistance'] = {
                    kind: min(.5, max(0, (fx.get('Add' + label + 'ResistancePercentage', 0) +
                                         fx.get('AddPhysicalResistancePercentage' if kind in ('blunt', 'slash', 'pierce') else 'AddElementalResistancePercentage', 0)) / 100))
                    for kind, label in typed.items()}
                # Runtime food health and stamina are not present in Enforcer exports.
                profile['defense']['health'] = None
                profile['defense']['threshold'] = .75 if fx.get('ModifyArmorLowHealth', 0) else 0
                base_cost = source['stamina']['cost'] / (1 - .33 * source['skill'] / 100) / (1 - source['effects'].get('ModifyAttackStaminaUse', 0) / 100)
                profile['stamina'] = dict(maximum=None, cost=base_cost * (1 - .33 * skill / 100) * (1 - fx.get('ModifyAttackStaminaUse', 0) / 100),
                                          regen=6 * (2 + fx.get('ModifyStaminaRegen', 0) / 100), delay=1)
                profile['chains'] = ([dict(chance=.25, damage=75), dict(chance=.15, damage=75 * fx.get('ChainLightning', 0) / 100)]
                                     if prefab == 'SpearGold_BloodLightning' else [])
                identity = json.dumps([prefab, weapon['mQuality'], weapon.get('mGridpos'), weapon.get('mCustomdata')], sort_keys=True)
                choices.append(dict(key=hashlib.sha256(identity.encode()).hexdigest()[:16], label=f'{prefab} · quality {weapon["mQuality"]}',
                                    equipped=weapon['mEquipped'], profile=profile))
            missing = []
            if not choices:
                missing.append('No weapon with verified damage and animation inputs. Supported weapons: ' + ', '.join(weapons))
            unknown = [i['prefabName'] for i in items if i['mEquipped'] and
                       i['prefabName'].startswith(('Armor', 'Helmet', 'Cape')) and i['prefabName'] not in ARMOR]
            if unknown:
                missing.append('Armor needs verification: ' + ', '.join(unknown))
            unsupported = [i['prefabName'] for i in items if i['mEquipped'] and
                           i['prefabName'] not in ARMOR and i['prefabName'] not in weapons and i['prefabName'] not in UTILITY]
            if unsupported:
                missing.append('Equipped item stats need verification: ' + ', '.join(unsupported))
            active = [c for c in choices if c['equipped']]
            players.append(dict(id=name, imported=True, choices=choices,
                                selectedWeapon=active[0]['key'] if len(active) == 1 else '', missing=missing,
                                source=dict(file=path.name, sha256=hashlib.sha256(raw).hexdigest(),
                                            modified=datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat())))
            names.add(name.casefold())
        except (ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
            # Parser exceptions can include source lines containing private data.
            message = str(error) if isinstance(error, ValueError) and not isinstance(error, yaml.YAMLError) else 'Malformed or unsupported export structure'
            if isinstance(error, json.JSONDecodeError):
                message = 'Malformed Epic Loot item data'
            errors.append(dict(file=path.name, message=message))
    return players, errors
