"""Build planning inputs and the modifier IDs available in the mod."""
import hashlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def build_loot_data(root=ROOT):
    source = (root / 'Source/Integrations/EpicLootIntegration.cs').read_text()
    plan = (root / 'Config/rewards.yaml').read_text()
    rewards = yaml.safe_load(plan)
    populations = re.findall(r'\["(VE_Population\w+)"\] = \("([^"]+)", "([^"]+)"\)', source)
    hazard_source = source.split('Dictionary<string, string> hazards = new()', 1)[1].split('};', 1)[0]
    hazards = re.findall(r'\["([^"]+)"\] = "([^"]+)"', hazard_source)
    if len(populations) != 4 or not hazards:
        raise ValueError('Tablet modifier source changed; update the loot data extractor.')
    population_modifiers = rewards['populationModifiers']
    modifiers = [dict(id=key, label='More ' + label, value=population_modifiers[key]['ranges']['Legendary']['min'])
                 for key, role, label in populations]
    counted = set(re.findall(r'\["(VE_\w+Totems)"\] = "[a-z]+"', source.split('CountedTotems = new()', 1)[1].split('};', 1)[0]))
    count_ranges = {rarity: dict(min=1, max=min(index + 1, 4))
                    for index, rarity in enumerate(['Magic', 'Rare', 'Epic', 'Legendary', 'Mythic', 'Ancient'])}
    modifiers += [dict(id='VE_' + key, label=label.replace('{0}', '1–4'), value=1,
                      ranges=count_ranges if 'VE_' + key in counted else None) for key, label in hazards]
    sls = yaml.safe_load((root / 'Balance/sls-reference.yaml').read_text())['modifiers']
    for index, group in enumerate(['majorModifiers', 'minorModifiers', 'bossModifiers']):
        for name in sls[group]:
            modifiers.append(dict(id=f'VE_SLS_{index}_{name.encode("utf-8").hex().upper()}',
                                  label=f'All monsters have {name} ({group.removesuffix("Modifiers")})',
                                  value=1, noRoll=name in ('Lootbags', 'Alert', 'Big', 'BossSummoner')))
    paths = ['Config/rewards.yaml', 'Config/encounters.yaml', 'Config/creatures.yaml', 'Source/Configuration/RewardCatalog.cs',
             'Source/Encounters/RewardItems.cs', 'Source/Integrations/EpicLootIntegration.cs']
    hashes = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
    return dict(config=yaml.safe_load(plan), configYaml=plan,
                legacyHash=hashes['Config/rewards.yaml'],
                legacyConfig=yaml.safe_load((root / 'Config/rewards.yaml').read_text()),
                hashes=hashes, modifiers=modifiers, populationModifiers=population_modifiers,
                effectCounts=yaml.safe_load((root / 'Balance/tablet-rolls.yaml').read_text()))
