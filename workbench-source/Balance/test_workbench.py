"""Run with python3 -m unittest discover -s Balance -p test_workbench.py."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from apply_workbench_review import apply_review
from build_workbench import build_data, render_html
from import_players import import_folder
from balance import fit, read
import catalog
from progression import tier_ranges

HERE = Path(__file__).resolve().parent


class WorkbenchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = yaml.safe_load((HERE / 'workbench_players.yaml').read_text())['players']
        cls.data = build_data()
        cls.config = yaml.safe_load((HERE.parent / 'Config/creatures.yaml').read_text())

    def export(self, name='Example'):
        return dict(name=name, skillLevels={'Spears': 90}, playerItems=[
            dict(prefabName='SpearGold_BloodLightning', mQuality=3, mEquipped=True, mCustomdata={
                'MagicItemComponent': json.dumps(dict(Effects=[dict(EffectType='ModifyDamage', EffectValue=12)],
                                                      Sockets=[dict(Effect=dict(EffectType='ModifyDamage', EffectValue=8))]))}),
            dict(prefabName='HelmetDNHeavy', mQuality=2, mEquipped=True),
            dict(prefabName='Coins', mQuality=1, mStack=100)])

    def test_uber_combat_covers_every_boss_and_attack(self):
        combat = self.data['uberCombat']
        hits = (HERE / 'uberbosses-hits.js').read_text()
        for boss in self.data['uberBosses']['bosses']:
            entry = combat[boss['id']]
            self.assertGreater(entry['health'], 0)
            self.assertEqual(set(entry['native']), {'blunt', 'slash', 'pierce', 'fire', 'frost', 'lightning', 'poison', 'spirit'})
            self.assertGreater(entry['scaling']['health_per_star'], 0)
            self.assertEqual(entry['stars'], [self.config['creatures'][boss['id']]['stars']['minStars'], self.config['creatures'][boss['id']]['stars']['maxStars']])
            for attack in boss['attacks']:
                self.assertIn('\n  ' + attack['id'] + ': [', hits, msg='uberbosses-hits.js has no hit definition for ' + attack['id'])

    def test_import_errors_do_not_hide_valid_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.yaml').write_text(yaml.safe_dump(self.export()))
            (root / 'duplicate.yaml').write_text(yaml.safe_dump(self.export()))
            (root / 'broken.yaml').write_text('name: [')
            (root / 'unsupported.yaml').write_text('name: No inventory')
            players, errors = import_folder(root, self.templates)
            self.assertEqual([p['id'] for p in players], ['Example'])
            self.assertEqual(len(errors), 3)
            self.assertTrue(any('Duplicate character' in e['message'] for e in errors))
            profile = players[0]['choices'][0]['profile']
            self.assertEqual(profile['effects']['ModifyDamage'], 20)
            self.assertEqual(profile['skill'], 90)
            self.assertEqual(profile['coins'], 100)
            self.assertEqual(profile['defense']['armor'], 46)
            self.assertIsNone(profile['defense']['health'])
            self.assertIsNone(profile['stamina']['maximum'])
            self.assertNotIn('hostID', json.dumps(players))

    def test_refresh_and_no_active_weapon(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'example.yaml'
            export = self.export()
            export['playerItems'][0].pop('mEquipped')
            path.write_text(yaml.safe_dump(export))
            first, errors = import_folder(path.parent, self.templates)
            self.assertFalse(errors)
            self.assertEqual(first[0]['selectedWeapon'], '')
            export['skillLevels']['Spears'] = 80
            path.write_text(yaml.safe_dump(export))
            second, errors = import_folder(path.parent, self.templates)
            self.assertFalse(errors)
            self.assertNotEqual(first[0]['source']['sha256'], second[0]['source']['sha256'])
            self.assertEqual(first[0]['choices'][0]['key'], second[0]['choices'][0]['key'])
            self.assertEqual(second[0]['choices'][0]['profile']['skill'], 80)

    def review(self):
        return dict(schema=3, creatures={c['id']: dict(enabled=c['enabled'], tiers=copy.deepcopy(c['tiers']), notes='')
                                        for c in self.data['creatures']})

    def test_full_catalog_roundtrip_keeps_unconfigured_exclusions(self):
        self.assertEqual(len(self.data['creatures']), len([n for n in self.config['creatures'] if not n.startswith('VE_')]))
        self.assertEqual(apply_review(self.config, self.review()), self.config)
        review = self.review()
        review['creatures']['Troll']['tiers'] = tier_ranges(dict(minStars=11, maxStars=13))
        changed = apply_review(self.config, review)
        self.assertEqual(changed['creatures']['Troll']['stars']['minStars'], 11)
        self.assertEqual(tier_ranges(changed['creatures']['Troll']['stars'])['15'], [53, 55])
        self.assertEqual(changed['creatures']['Troll']['biomes'], self.config['creatures']['Troll']['biomes'])
        review['creatures']['Troll']['tiers']['15'] = [49, 51]
        with self.assertRaises(ValueError):
            apply_review(self.config, review)
        self.assertEqual(apply_review(self.config, self.review()), self.config)

    def test_shadowperson_cannot_return_through_catalog_regeneration(self):
        self.assertNotIn('ShadowPerson', self.config['creatures'])
        self.assertNotIn('ShadowPerson', [c['id'] for c in self.data['creatures']])
        roles = read(HERE / 'creature-roles.yaml')
        # Simulate an accidental re-addition to the old balance candidates.
        roles['creatures']['ShadowPerson'] = dict(role='magic', group='Deep North', pool='candidate')
        original_read = catalog.read
        with patch.object(catalog, 'read', side_effect=lambda path: roles if Path(path).name == 'creature-roles.yaml' else original_read(path)):
            generated = catalog.generate()
        self.assertNotIn('ShadowPerson', generated['creatures'])
        for config in [self.config, generated]:
            for group in ['minibosses', 'bosses']:
                self.assertNotIn('ShadowPerson', config[group])

    def test_explicit_fit_rejects_shadowperson(self):
        with self.assertRaisesRegex(ValueError, 'ShadowPerson is excluded from balancing'):
            fit(None, None, 'ShadowPerson', None, 1, 'magic', 'DeepNorth')

    def test_trollfrost_excluded_from_config_generation_and_review_import(self):
        self.assertNotIn('TrollFrost', self.config['creatures'])
        self.assertNotIn('TrollFrost', [c['id'] for c in self.data['creatures']])
        roles = read(HERE / 'creature-roles.yaml')
        roles['creatures']['TrollFrost'] = dict(role='rare', group='Deep North', pool='candidate')
        original_read = catalog.read
        with patch.object(catalog, 'read', side_effect=lambda path: roles if Path(path).name == 'creature-roles.yaml' else original_read(path)):
            generated = catalog.generate()
        self.assertNotIn('TrollFrost', generated['creatures'])
        for config in [self.config, generated]:
            for group in ['minibosses', 'bosses']:
                self.assertNotIn('TrollFrost', config[group])
        with self.assertRaisesRegex(ValueError, 'TrollFrost is excluded from balancing'):
            fit(None, None, 'TrollFrost', None, 1, 'rare', 'DeepNorth')
        review = self.review()
        review['creatures']['Troll']['tiers'] = tier_ranges(dict(minStars=11, maxStars=13))
        changed = apply_review(self.config, review)
        self.assertNotIn('TrollFrost', changed['creatures'])
        self.assertEqual(changed['creatures']['Troll']['stars']['minStars'], 11)
        self.assertEqual(changed['creatures']['Troll']['stars']['maxStars'], 13)

    def test_void_ghost_cannot_return_to_active_balancing(self):
        self.assertNotIn('Ghost_Void', self.config['creatures'])
        self.assertNotIn('Ghost_Void', [c['id'] for c in self.data['creatures']])
        roles = read(HERE / 'creature-roles.yaml')
        roles['creatures']['Ghost_Void'] = dict(role='magic', group='Deep North', pool='candidate')
        original_read = catalog.read
        with patch.object(catalog, 'read', side_effect=lambda path: roles if Path(path).name == 'creature-roles.yaml' else original_read(path)):
            generated = catalog.generate()
        self.assertNotIn('Ghost_Void', generated['creatures'])
        with self.assertRaisesRegex(ValueError, 'Ghost_Void is excluded from balancing'):
            fit(None, None, 'Ghost_Void', None, 1, 'magic', 'DeepNorth')
        review = self.review()
        review['creatures']['Ghost_Void'] = copy.deepcopy(review['creatures']['Troll'])
        self.assertEqual(apply_review(self.config, review), self.config)

    def test_global_roster_preserves_baselines_and_derives_every_tier(self):
        approved = json.loads((HERE / read(HERE / 'progression.yaml')['baseline']).read_text())
        generated = catalog.generate()
        for name, entry in self.config['creatures'].items():
            self.assertEqual(entry, generated['creatures'][name], name)
            if not entry['enabled']:
                continue
            self.assertIn(entry['role'], ['standard', 'magic', 'rare', 'miniboss', 'boss', 'hazard'])
            if entry['role'] in ['miniboss', 'boss']:
                self.assertIn(name, self.config['minibosses'] + self.config['bosses'])
            ranges = tier_ranges(entry['stars'])
            baseline = approved['creatures'][name]['tiers']['1']
            for tier in range(1, 16):
                self.assertEqual(ranges[str(tier)], [value + 3 * (tier - 1) for value in baseline], (name, tier))
        for role in ['standard', 'magic', 'rare']:
            self.assertTrue(any(c['enabled'] and c['role'] == role for c in self.config['creatures'].values()))

    def test_hazard_star_review_roundtrip(self):
        review = self.review()
        for name in ['staff_greenroots_tentaroot', 'TentaRoot', 'SeekerBrood']:
            row = next(c for c in self.data['creatures'] if c['id'] == name)
            self.assertTrue(row['enabled'])
            self.assertTrue(row['attacks'])
            review['creatures'][name]['tiers'] = tier_ranges(dict(minStars=7, maxStars=9))
        changed = apply_review(self.config, review)
        for name in ['staff_greenroots_tentaroot', 'TentaRoot', 'SeekerBrood']:
            self.assertEqual(tier_ranges(changed['creatures'][name]['stars'])['15'], [49, 51])
        for name in ['staff_greenroots_tentaroot', 'TentaRoot']:
            self.assertEqual(changed['creatures'][name]['role'], 'hazard')
            self.assertNotIn(name, changed['minibosses'] + changed['bosses'])

    def test_old_review_formats_are_rejected(self):
        review = self.review()
        for schema in [1, 2, None]:
            review['schema'] = schema
            with self.assertRaisesRegex(ValueError, 'schema-3'):
                apply_review(self.config, review)

    def test_current_review_keeps_wave_limits(self):
        changed = apply_review(self.config, self.review())
        for name in ['Morgen', 'FallenValkyrie']:
            self.assertEqual(changed['creatures'][name]['waveLimits'], {1: 1})

    def test_baseline_limits_leave_room_for_tier_fifteen(self):
        self.assertEqual(tier_ranges(dict(minStars=9958, maxStars=9958))['15'], [10000, 10000])
        for low, high in [(0, 9959), (-1, 1), (4, 3), (True, 1)]:
            with self.assertRaises(ValueError):
                tier_ranges(dict(minStars=low, maxStars=high))

    def test_review_cannot_restore_excluded_creature(self):
        review = self.review()
        review['creatures']['ShadowPerson'] = copy.deepcopy(review['creatures']['Troll'])
        self.assertEqual(apply_review(self.config, review), self.config)
        review['creatures']['UnknownCreature'] = review['creatures']['ShadowPerson']
        with self.assertRaisesRegex(ValueError, 'full current creature catalog'):
            apply_review(self.config, review)

    def test_scaling_tab_is_assembled_after_creature_ui(self):
        html = render_html(self.data)
        self.assertIn('id="tab-scaling"', html)
        self.assertIn('id="panel-scaling"', html)
        self.assertNotRegex(html, r'/\*(SCALING|LOOT|WORKBENCH)_[A-Z]+\*/|<!--(SCALING|LOOT)_PANEL-->')
        self.assertLess(html.index('function playerResult()'), html.index('function scalingUpdate()'))


if __name__ == '__main__':
    unittest.main()


class UberBossWorkbenchTest(unittest.TestCase):
    def test_uber_boss_values_are_embedded_and_every_settings_key_reaches_events_yaml(self):
        import apply_uberbosses
        data = build_data()
        self.assertEqual(data['uberBosses']['schema'], 1)
        self.assertEqual([b['id'] for b in data['uberBosses']['bosses']],
                         ['VE_UberEikthyr', 'VE_UberElder', 'VE_UberBonemass', 'VE_UberModer', 'VE_UberYagluth', 'VE_UberQueen', 'VE_UberFader'])
        events = yaml.safe_load((HERE.parent / 'Config/encounters.yaml').read_text())
        rendered = yaml.safe_load(apply_uberbosses.render(data['uberBosses']))
        for boss in data['uberBosses']['bosses']:
            section = apply_uberbosses.SECTIONS[boss['id']]
            self.assertEqual(rendered[section], boss['settings'], section)
            self.assertEqual(events[section], boss['settings'], section + ' in encounters.yaml differs; run apply_uberbosses.py')
            for attack in boss['attacks']:
                self.assertIn(attack['kind'], ('vanilla', 'replaced', 'new'))
                self.assertTrue(all(isinstance(v, (int, float)) for v in attack['fields'].values()), attack['id'])

    def test_merge_replaces_only_uber_sections(self):
        import apply_uberbosses
        text = 'schemaVersion: 6\nuberElder:\n  nestCount: 4\nuberModer:\n  drakeChance: 0.35\ntablets:\n  totemRadius: 12\n'
        merged = apply_uberbosses.merge(text, 'uberElder:\n  nestCount: 5\n')
        self.assertEqual(merged, 'schemaVersion: 6\nuberElder:\n  nestCount: 5\ntablets:\n  totemRadius: 12\n')
