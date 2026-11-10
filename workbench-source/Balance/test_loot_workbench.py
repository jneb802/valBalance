"""Offline loot workbench contract tests. Requires Node.js on PATH (or NODE)."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

from loot_data import build_loot_data

HERE = Path(__file__).resolve().parent
NODE = os.environ.get('NODE', 'node')


class LootWorkbenchTest(unittest.TestCase):
    def setUp(self):
        self.context = build_loot_data()
        self.config = self.context['config']
        self.scenario = dict(tier=1, completed=True, seed='test', effects=[])

    def run_engine(self, expression, config=None, scenario=None):
        script = """
const fs=require('fs'), E=require(process.argv[1]), input=JSON.parse(fs.readFileSync(0,'utf8'));
const Y=require(process.argv[2]);
const context=input.context, c=E.normalize(input.config), s=input.scenario;
try { E.validate(c, context); E.validateScenario(s, context);
process.stdout.write(JSON.stringify((()=>{EXPRESSION})())); }
catch(error) { process.stdout.write(JSON.stringify({error:error.message})); }
""".replace('EXPRESSION', expression)
        result = subprocess.run([NODE, '-e', script, str(HERE / 'loot.js'), str(HERE / 'loot-yaml.js')], input=json.dumps(dict(
            context=self.context, config=config if config is not None else self.config,
            scenario=scenario if scenario is not None else self.scenario)), text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_baseline_odds_and_quantity(self):
        result = self.run_engine('return E.analyze(c,s);')
        self.assertEqual(result['rolls'], 10)
        self.assertAlmostEqual(result['rarities'][0]['atLeastOne'], 1 - .99**10)
        self.assertAlmostEqual(result['rarities'][1]['atLeastOne'], 1 - .91**10)
        coins = next(i for i in result['items'] if i['item']['id'] == 'coins')
        self.assertAlmostEqual(coins['expected'], 10 * (.9 * 2.5 / 6.75) * 125)

    def test_unlocks_redistribute_weights(self):
        result = self.run_engine('return E.analyze(c,{...s,tier:6});')
        items = {i['item']['id']: i for i in result['items']}
        self.assertAlmostEqual(items['legendary-chisel']['probability'], .01 / 2.25)
        self.assertAlmostEqual(items['mythic-chisel']['probability'], .01 * .25 / 2.25)
        self.assertEqual(items['ancient-chisel']['probability'], 0)

    def test_population_strength_overrides_fractional_rolls_and_cap(self):
        # Pin the totem rate so this test does not depend on the shipped tuning.
        self.config['rules']['modifierDifficulty']['VE_SlowTotems'] = 2
        self.scenario['effects'] = [dict(id='VE_PopulationStandard', value=100), dict(id='VE_SlowTotems', value=1)]
        result = self.run_engine('return E.analyze(c,s);')
        self.assertEqual(result['bonus']['total'], 10)
        # Floating-point budgets land just above 11; rounding to 10 places keeps them at 11 rolls, not 12.
        self.assertAlmostEqual(result['raw'], 11)
        self.assertEqual(result['rolls'], 11)
        self.config['rules']['modifierDifficulty']['VE_PopulationStandard'] = 500
        self.config['rules']['maxRolls'] = 64
        result = self.run_engine('return E.analyze(c,s);')
        self.assertEqual(result['rolls'], 64)
        self.assertTrue(result['capped'])

    def test_fallback_and_disabled_items(self):
        for item in self.config['items']:
            if item['id'] != 'coins':
                item['enabled'] = False
        result = self.run_engine('return E.analyze(c,s);')
        self.assertEqual(result['rarities'][-1]['probability'], 1)
        self.assertEqual(len(result['fallbacks']), 2)
        self.config['items'][0]['enabled'] = False
        self.assertIn('no eligible item', self.run_engine('return true;')['error'])

    def test_failed_run_and_repeatable_examples(self):
        self.assertTrue(self.run_engine('return JSON.stringify(E.sample(c,s))===JSON.stringify(E.sample(c,s));'))
        self.scenario['completed'] = False
        result = self.run_engine('return {analysis:E.analyze(c,s),sample:E.sample(c,s)};')
        self.assertEqual(result['analysis']['rolls'], 0)
        self.assertTrue(all(i['expected'] == i['atLeastOne'] == 0 for i in result['analysis']['items']))
        self.assertEqual(result['sample'], [[], [], []])

    def test_samples_follow_distribution_and_quantity_limits(self):
        result = self.run_engine('return E.sample(c,s,10000).flat();')
        coins = [drop for drop in result if drop['id'] == 'coins']
        self.assertEqual(len(result), 100000)
        self.assertAlmostEqual(len(coins) / len(result), .9 * 2.5 / 6.75, delta=.004)
        self.assertTrue(all(50 <= drop['quantity'] <= 200 for drop in coins))

    def test_item_probability_combines_multiple_tables(self):
        self.config['rarities'][0]['entries'] = [dict(item='coins', weight=1)]
        result = self.run_engine('return E.analyze(c,s);')
        self.assertAlmostEqual(result['items'][0]['probability'], .01 + .9 * 2.5 / 6.75)

    def test_invalid_probability_tier_count_and_quantity(self):
        for mutate, message in [
            (lambda c: c['rarities'][0].update(probability=.5), 'total 100%'),
            (lambda c: c['rules']['tiers'].pop(), '15 tier rows'),
            (lambda c: c['rules'].update(budgetPerRoll=0), 'budgetPerRoll'),
            (lambda c: c['rules'].update(baseRolls=1), 'unknown field'),
            (lambda c: c['items'][0].update(minQuantity=0), 'quantity range'),
            (lambda c: c['items'][0].update(enchantment=dict(rarity='Rare', power=1)), 'unknown field enchantment'),
        ]:
            config = copy.deepcopy(self.config)
            mutate(config)
            self.assertIn(message, self.run_engine('return true;', config)['error'])

    def test_modifier_duplicates_unknown_ids_and_conflicts(self):
        for effects in [[dict(id='unknown', value=1)],
                        [dict(id='VE_BearTraps', value=1)] * 2,
                        [dict(id='VE_SLS_0_4142', value=1), dict(id='VE_SLS_1_4142', value=1)]]:
            self.scenario['effects'] = effects
            self.assertIn('error', self.run_engine('return true;'))

    def test_review_roundtrip_and_old_model_rejection(self):
        result = self.run_engine("return Y.review({kind:'difficulty-loot',schema:2,config:c,scenario:s},context);")
        self.assertEqual(result['config'], self.run_engine('return c;'))
        self.assertIn('different model', self.run_engine("return E.review({kind:'loot',schema:1,config:c,scenario:s},context);")['error'])

    def test_yaml_comments_and_inline_maps_match_runtime_settings(self):
        self.assertEqual(self.run_engine('return Y.parse(context.configYaml,context);'),
                         self.run_engine('return c;'))
        result = self.run_engine("return Y.review({kind:'difficulty-loot',schema:2,config:c,scenario:s},context);")
        self.assertEqual(result['configYaml'], self.context['configYaml'])

    def test_yaml_rejects_duplicate_keys_and_circular_aliases(self):
        self.assertIn('duplicated mapping key', self.run_engine("return Y.parse('rules: {}\\nrules: {}',context);")['error'])
        self.assertIn('circular aliases', self.run_engine("return Y.parse('items: &items [*items]',context);")['error'])

    def test_yaml_review_preserves_text_and_rejects_conflicting_settings(self):
        before = self.context['configYaml']
        text = before.replace('budgetPerRoll: 10', 'budgetPerRoll: 4') + '\n# Keep my note\n'
        self.config['rules']['budgetPerRoll'] = 4
        expression = "return Y.review({kind:'difficulty-loot',schema:2,config:c,configYaml:" + json.dumps(text) + ",scenario:s},context);"
        result = self.run_engine(expression)
        self.assertEqual(result['config']['rules']['budgetPerRoll'], 4)
        self.assertEqual(result['configYaml'], text)
        self.config['rules']['budgetPerRoll'] = 5
        self.assertIn('does not match', self.run_engine(expression)['error'])

    def test_partial_rolls_round_up(self):
        self.config['rules']['tiers'][1]['difficulty'] = 140
        self.config['rules']['tiers'][1]['bonusPercent'] = 10
        self.scenario['tier'] = 2
        result = self.run_engine('return E.analyze(c,s);')
        self.assertAlmostEqual(result['raw'], 15.4)
        self.assertEqual(result['rolls'], 16)
        for item in result['items']:
            p = item['probability']
            self.assertAlmostEqual(item['atLeastOne'], 1 - (1-p)**16)
            self.assertEqual(item['max'], 16 * item['item']['maxQuantity'] if p else 0)
        rolls = self.run_engine('return E.sample(c,s,100).map(d=>d.length);')
        self.assertEqual(set(rolls), {16})
        self.config['rules']['budgetPerRoll'] = 7
        self.config['rules']['tiers'][1]['difficulty'] = 70
        self.config['rules']['tiers'][1]['bonusPercent'] = 0
        self.assertEqual(self.run_engine('return E.analyze(c,s);')['rolls'], 10)

    def test_tier_bonus_and_modifiers_compose_once(self):
        self.config['rules']['modifierDifficulty']['VE_SlowTotems'] = 25
        self.config['rules']['tiers'][1]['difficulty'] = 140
        self.config['rules']['tiers'][1]['bonusPercent'] = 10
        self.scenario.update(tier=2, effects=[dict(id='VE_SlowTotems', value=1)])
        result = self.run_engine('return E.analyze(c,s);')
        self.assertEqual(result['difficulty'], 175)
        self.assertAlmostEqual(result['budget'], 192.5)
        self.assertEqual(result['rolls'], 20)
        self.config['rules']['modifierDifficulty']['VE_SlowTotems'] = 0
        self.assertEqual(self.run_engine('return E.analyze(c,s);')['rolls'], 16)

    def test_totem_bonus_scales_per_totem(self):
        self.config['rules']['modifierDifficulty']['VE_SlowTotems'] = 5
        for count in (1, 3):
            self.scenario['effects'] = [dict(id='VE_SlowTotems', value=count)]
            self.assertEqual(self.run_engine('return E.bonus(c,s).total;'), 5 * count)

    def test_zero_and_guaranteed_item_ranges(self):
        self.config['rules']['tiers'][1]['difficulty'] = 140
        self.config['rules']['tiers'][1]['bonusPercent'] = 10
        self.config['rarities'] = [dict(id='common', probability=1, entries=[dict(item='coins', weight=1)])]
        self.scenario['tier'] = 2
        item = self.run_engine('return E.analyze(c,s).items[0];')
        self.assertEqual(item['min'], 800)
        self.assertEqual(item['max'], 3200)
        self.assertEqual(item['atLeastOne'], 1)
        self.config['rules']['tiers'][1]['difficulty'] = 0
        result = self.run_engine('return {a:E.analyze(c,s),d:E.sample(c,s)};')
        self.assertEqual(result['a']['items'][0]['min'], 0)
        self.assertEqual(result['a']['items'][0]['max'], 0)
        self.assertEqual(result['a']['items'][0]['atLeastOne'], 0)
        self.assertEqual(result['d'], [[], [], []])

    def test_default_bonus_increases_by_two_percentage_points(self):
        self.assertEqual([t['bonusPercent'] for t in self.config['rules']['tiers']], list(range(0, 30, 2)))
        result = self.run_engine('return E.analyze(c,{...s,tier:2});')
        self.assertAlmostEqual(result['raw'], 10.71)
        self.assertEqual(result['rolls'], 11)
        self.assertEqual(result['baseDifficulty'], 105)

    def test_default_difficulty_grows_five_percent_per_tier(self):
        self.assertEqual([t['difficulty'] for t in self.config['rules']['tiers']],
                         [round(100 * 1.05**k, 4) for k in range(15)])

    def test_random_set_runestone_and_ancient_runestone_unlocks(self):
        result = self.run_engine('return [3,4,5,6].map(tier=>E.analyze(c,{...s,tier}).items);')
        by_tier = [{i['item']['id']: i for i in items} for items in result]
        self.assertGreater(by_tier[0]['random-legendary-set-runestone']['probability'], 0)
        self.assertGreater(by_tier[1]['random-legendary-set-runestone']['probability'], 0)
        self.assertEqual(by_tier[0]['legendary-chisel']['probability'], 0)
        self.assertGreater(by_tier[1]['legendary-chisel']['probability'], 0)
        self.assertEqual(by_tier[2]['RunestoneAncient']['probability'], 0)
        self.assertGreater(by_tier[3]['RunestoneAncient']['probability'], 0)
        self.assertEqual(by_tier[2]['ShardAncient']['probability'], 0)
        self.assertAlmostEqual(by_tier[3]['ShardAncient']['probability'], .9 / 8.75)
        drops = self.run_engine('return E.sample(c,{...s,tier:6},3000).flat().filter(d=>d.id==="random-legendary-set-runestone");')
        self.assertGreater(len(drops), 0)
        self.assertTrue(all(d['quantity'] == 1 for d in drops))

    def test_random_set_runestone_validation(self):
        for patch in [dict(prefab='ShieldIronTower'), dict(maxQuantity=2), dict(tabletTier=4),
                      dict(enchantment=dict(rarity='Legendary', power=1))]:
            c = copy.deepcopy(self.config)
            next(i for i in c['items'] if i['id'] == 'random-legendary-set-runestone').update(patch)
            self.assertIn('error', self.run_engine('return c;', c))

    def test_set_rewards_cover_all_tiers_with_staggered_rarity(self):
        result = self.run_engine('''return Array.from({length:15},(_,i)=>{
const tier=i+1,item=E.analyze(c,{...s,tier}).items.find(i=>i.item.randomLegendarySetRune);
return {rarity:E.setRewardRarity(tier),probability:item.probability,min:item.item.minQuantity,max:item.item.maxQuantity};
});''')
        self.assertEqual([r['rarity'] for r in result], ['Legendary'] * 3 + ['Mythic'] * 3 + ['Ancient'] * 9)
        self.assertTrue(all(r['probability'] > 0 and r['min'] == r['max'] == 1 for r in result))

    def test_tiered_set_migration_preserves_other_saved_settings(self):
        for flow in [0, -1]:
            result = self.run_engine('''
const yaml=require(process.argv[1].replace('loot.js','vendor/js-yaml-4.3.0.min.js'));
const old=JSON.parse(JSON.stringify(c)),item=old.items.find(i=>i.randomLegendarySetRune);
item.minTier=4;item.maxTier=10;old.rules.budgetPerRoll=17;
old.rarities[0].entries.find(e=>e.item===item.id).weight=3;
const raw='# Keep my tuning\\n'+yaml.dump(old,{flowLevel:FLOW});
const revised=Y.upgradeSetRewards(raw,context,true),next=Y.parse(revised,context);
return {min:next.items.find(i=>i.randomLegendarySetRune).minTier,max:next.items.find(i=>i.randomLegendarySetRune).maxTier,
budget:next.rules.budgetPerRoll,weight:next.rarities[0].entries.find(e=>e.item===item.id).weight,
comment:revised.startsWith('# Keep my tuning'),repeat:Y.upgradeSetRewards(revised,context,true)===revised};
'''.replace('FLOW', str(flow)))
            self.assertEqual(result, dict(min=1, max=15, budget=17, weight=3, comment=True, repeat=True))

    def test_display_separates_set_rarities_without_changing_reward_odds(self):
        result = self.run_engine('''return Array.from({length:15},(_,k)=>{
const tier=k+1,a=E.analyze(c,{...s,tier}),rows=E.rewardRows(a,tier);
const original=a.items.find(r=>r.item.randomLegendarySetRune),sets=rows.filter(r=>r.setRarity);
return {sets:sets.map(r=>({label:r.label,probability:r.probability,expected:r.expected,atLeastOne:r.atLeastOne})),
original,odds:E.setRewardOdds(a,tier),name:E.rewardName(original.item,tier),
total:rows.reduce((sum,r)=>sum+r.expected,0),originalTotal:a.items.reduce((sum,r)=>sum+r.expected,0)};
});''')
        for tier, row in enumerate(result, 1):
            active = 0 if tier <= 3 else 1 if tier <= 6 else 2
            self.assertEqual([s['label'] for s in row['sets']],
                             ['Legendary set runestone', 'Mythic set runestone', 'Ancient set runestone'])
            self.assertEqual(row['name'], row['sets'][active]['label'])
            self.assertAlmostEqual(row['total'], row['originalTotal'])
            for index, reward in enumerate(row['sets']):
                for key in ['probability', 'expected', 'atLeastOne']:
                    self.assertAlmostEqual(reward[key], row['original'][key] if index == active else 0)
                self.assertAlmostEqual(row['odds'][index], row['original']['atLeastOne'] if index == active else 0)

    def test_set_display_shows_zero_payouts_for_failed_runs(self):
        result = self.run_engine('''return [1,4,7,15].map(tier=>{
const a=E.analyze(c,{...s,tier,completed:false});
return {rows:E.rewardRows(a,tier).filter(r=>r.setRarity),odds:E.setRewardOdds(a,tier)};
});''')
        for tier in result:
            self.assertEqual(tier['odds'], [0, 0, 0])
            for row in tier['rows']:
                self.assertEqual([row[key] for key in ['expected', 'atLeastOne', 'min', 'max']], [0, 0, 0, 0])

    def test_set_odds_combine_multiple_set_reward_entries(self):
        result = self.run_engine('''
const second={...c.items.find(i=>i.randomLegendarySetRune),id:'another-set-reward'};
c.items.push(second);c.rarities[0].entries.push({item:second.id,weight:2});
const a=E.analyze(c,{...s,tier:7}),p=a.items.filter(r=>r.item.randomLegendarySetRune).reduce((sum,r)=>sum+r.probability,0);
return {odds:E.setRewardOdds(a,7),expected:1-Math.pow(1-p,a.rolls)};
''')
        self.assertEqual(result['odds'][:2], [0, 0])
        self.assertGreater(result['odds'][2], 0)
        self.assertAlmostEqual(result['odds'][2], result['expected'])

    def test_equipment_draft_becomes_set_runestone_without_losing_tuning(self):
        for flow in [0, -1]:
            expression = '''
const yaml=require(VENDOR),old=JSON.parse(JSON.stringify(c));
const item=old.items.find(i=>i.randomLegendarySetRune);
item.randomLegendarySetRune=false;item.randomLegendarySetItem=true;item.id='random-legendary-set-item';item.minTier=7;
old.rules.budgetPerRoll=17;
old.rarities.forEach(r=>r.entries.forEach(e=>{if(e.item==='random-legendary-set-runestone'){e.item=item.id;e.weight=3;}}));
const raw='# My tuning\\n'+yaml.dump(old,{flowLevel:FLOW});
const revised=Y.upgradeSetRewards(raw,context),next=Y.parse(revised,context);
const review=Y.review({kind:'difficulty-loot',schema:2,config:old,configYaml:raw,scenario:s},context);
return {rune:next.items.find(i=>i.id==='random-legendary-set-runestone').randomLegendarySetRune,
tier:next.items.find(i=>i.randomLegendarySetRune).minTier,budget:next.rules.budgetPerRoll,
weight:next.rarities[0].entries.find(e=>e.item==='random-legendary-set-runestone').weight,
removed:!revised.includes('randomLegendarySetItem'),reviewClean:!review.configYaml.includes('randomLegendarySetItem'),
comment:revised.startsWith('# My tuning'),repeat:Y.upgradeSetRewards(revised,context)===revised};
'''.replace('VENDOR', json.dumps(str(HERE / 'vendor/js-yaml-4.3.0.min.js'))).replace('FLOW', str(flow))
            self.assertEqual(self.run_engine(expression), dict(rune=True, tier=7, budget=17, weight=3,
                removed=True, reviewClean=True, comment=True, repeat=True))

    def test_null_enchantment_fields_are_removed_from_saved_reviews(self):
        for flow in [0, -1]:
            expression = '''
const yaml=require(VENDOR),old=JSON.parse(JSON.stringify(c));
old.items.forEach(i=>i.enchantment=null);old.rules.budgetPerRoll=17;
const raw='# My settings\\n'+yaml.dump(old,{flowLevel:FLOW});
const revised=Y.upgradeSetRewards(raw,context),next=Y.parse(revised,context);
const review=Y.review({kind:'difficulty-loot',schema:2,config:old,configYaml:raw,scenario:s},context);
return {removed:!revised.includes('enchantment'),reviewClean:!review.configYaml.includes('enchantment'),
fieldsClean:next.items.every(i=>!Object.hasOwn(i,'enchantment')),budget:next.rules.budgetPerRoll,
comment:revised.startsWith('# My settings'),repeat:Y.upgradeSetRewards(revised,context)===revised};
'''.replace('VENDOR', json.dumps(str(HERE / 'vendor/js-yaml-4.3.0.min.js'))).replace('FLOW', str(flow))
            self.assertEqual(self.run_engine(expression), dict(removed=True, reviewClean=True,
                fieldsClean=True, budget=17, comment=True, repeat=True))

    def test_ancient_shard_addition_preserves_saved_yaml(self):
        expression = '''
const yaml=require(VENDOR),old=JSON.parse(JSON.stringify(c));
old.items=old.items.filter(i=>i.id!=='ShardAncient');
old.rarities.forEach(r=>r.entries=r.entries.filter(e=>e.item!=='ShardAncient'));
old.rules.budgetPerRoll=17;
const text='# Keep custom settings\\n'+yaml.dump(old,{flowLevel:FLOW});
const revised=Y.addAncientMaterial(text,context,'ShardAncient'),next=Y.parse(revised,context);
return {budget:next.rules.budgetPerRoll,item:next.items.find(i=>i.id==='ShardAncient').minTier,
 weight:next.rarities.find(r=>r.id==='common').entries.find(e=>e.item==='ShardAncient').weight,
 repeat:Y.addAncientMaterial(revised,context,'ShardAncient')===revised,comment:revised.startsWith('# Keep custom settings')};
'''.replace('VENDOR', json.dumps(str(HERE / 'vendor/js-yaml-4.3.0.min.js')))
        for flow in [0, -1]:
            self.assertEqual(self.run_engine(expression.replace('FLOW', str(flow))),
                             dict(budget=17, item=6, weight=1, repeat=True, comment=True))

    def test_saved_runestone_repair_and_chisel_unlock(self):
        expression = '''
const yaml=require(VENDOR),old=JSON.parse(JSON.stringify(c));
old.rules.budgetPerRoll=17;old.items.find(i=>i.id==='legendary-chisel').minTier=1;
if(MISSING)old.items=old.items.filter(i=>i.prefab!=='RunestoneAncient');
else old.items.find(i=>i.prefab==='RunestoneAncient').enabled=false;
old.rarities.forEach(r=>r.entries=r.entries.filter(e=>e.item!=='RunestoneAncient'));
const text='# Keep reward edits\\n'+yaml.dump(old,{flowLevel:FLOW});
const revised=Y.repairRewardUnlocks(text,context),next=Y.parse(revised,context);
return {budget:next.rules.budgetPerRoll,rune:next.items.find(i=>i.prefab==='RunestoneAncient').minTier,
 enabled:next.items.find(i=>i.prefab==='RunestoneAncient').enabled,chisel:next.items.find(i=>i.id==='legendary-chisel').minTier,
 weight:next.rarities.find(r=>r.id==='common').entries.find(e=>e.item==='RunestoneAncient').weight,
 repeat:Y.repairRewardUnlocks(revised,context)===revised,comment:revised.startsWith('# Keep reward edits')};
'''.replace('VENDOR', json.dumps(str(HERE / 'vendor/js-yaml-4.3.0.min.js')))
        for flow in [0, -1]:
            for missing in ['true', 'false']:
                self.assertEqual(self.run_engine(expression.replace('FLOW', str(flow)).replace('MISSING', missing)),
                                 dict(budget=17, rune=6, enabled=True, chisel=4, weight=1, repeat=True, comment=True))

    def test_random_tablet_modifier_counts_and_exclusions(self):
        result = self.run_engine('''
return E.tabletRarities.filter(rarity=>rarity!=='None').map((rarity,index)=>{
 const counts={};
 for(let n=0;n<1000;n++){
  const effects=E.generateModifiers(context,rarity,rarity+n);
  E.validateScenario({...s,effects,tabletRarity:rarity},context);
  if(effects.some(e=>['_4C6F6F7462616773','_416C657274','_426967','_426F737353756D6D6F6E6572'].some(suffix=>e.id.endsWith(suffix))))throw Error('Excluded modifier rolled');
  for(const effect of effects){
   const population=c.populationModifiers[effect.id],modifier=context.modifiers.find(m=>m.id===effect.id),range=population?.ranges[rarity]||modifier.ranges?.[rarity];
   if(population&&(!range||!Number.isInteger(effect.value)||effect.value<range.min||effect.value>range.max))throw Error('Wrong population range');
   if(modifier.ranges&&(!Number.isInteger(effect.value)||effect.value<range.min||effect.value>range.max))throw Error('Wrong totem count');
   if(!range&&effect.value!==modifier.value)throw Error('Wrong strength');
  }
  counts[effects.length]=(counts[effects.length]||0)+1;
 }
 return {minimum:index+1,counts};
});''')
        for row in result:
            minimum = row['minimum']
            self.assertEqual(set(row['counts']), {str(minimum), str(minimum+1), str(minimum+2)})
            self.assertAlmostEqual(row['counts'][str(minimum)] / 1000, .8, delta=.05)

    def test_random_modifiers_repeat_and_survive_reviews(self):
        result = self.run_engine('''
const effects=E.generateModifiers(context,'Ancient','test-seed');
const scenario={...s,effects,tabletRarity:'Ancient'};
return {same:JSON.stringify(effects)===JSON.stringify(E.generateModifiers(context,'Ancient','test-seed')),
 review:Y.review({kind:'difficulty-loot',schema:2,config:c,scenario},context).scenario};''')
        self.assertTrue(result['same'])
        self.assertEqual(result['review']['tabletRarity'], 'Ancient')
        self.assertIn('valid Epic Loot', self.run_engine("return E.generateModifiers(context,'Wrong','seed');")['error'])

    def test_population_divisors_and_custom_roll_ranges(self):
        self.scenario['effects'] = [dict(id='VE_PopulationStandard', value=10), dict(id='VE_PopulationBosses', value=3)]
        self.config['populationModifiers']['VE_PopulationStandard']['difficultyPer'] = 5
        self.config['populationModifiers']['VE_PopulationBosses']['difficultyPer'] = 2
        result = self.run_engine('return E.analyze(c,s);')
        self.assertEqual(result['bonus']['total'], 19)
        self.assertAlmostEqual(result['raw'], 11.9)
        self.assertEqual(result['rolls'], 12)
        result = self.run_engine('''
c.populationModifiers.VE_PopulationStandard.ranges.Magic={min:8,max:8};
let count=0;
for(let n=0;n<1000;n++)for(const e of E.generateModifiers(context,'Magic','custom'+n,c)){
 if(e.id==='VE_PopulationBosses')throw Error('Boss effect on Magic');
 if(e.id==='VE_PopulationStandard'){if(e.value!==8)throw Error('Ignored custom range');count++;}
}
return count;
''')
        self.assertGreater(result, 0)

    def test_population_config_rejects_invalid_ranges_and_divisors(self):
        for field, value in [('difficultyPer', 0), ('difficultyPer', -1), ('ranges', {'Magic': dict(min=1, max=2)})]:
            config = copy.deepcopy(self.config)
            config['populationModifiers']['VE_PopulationBosses'][field] = value
            self.assertIn('error', self.run_engine('return true;', config))
        config = copy.deepcopy(self.config)
        config['populationModifiers']['VE_PopulationStandard']['ranges']['Magic'] = dict(min=10, max=5)
        self.assertIn('error', self.run_engine('return true;', config))

    def test_saved_population_settings_upgrade_preserves_rewards(self):
        result = self.run_engine('''
const yaml=require(VENDOR),old=JSON.parse(JSON.stringify(c));delete old.populationModifiers;
old.rules.budgetPerRoll=17;
const text='# Keep custom rewards\\n'+yaml.dump(old);
const revised=Y.exposePopulationModifiers(text,context),config=Y.parse(revised,context);
const review=Y.review({kind:'difficulty-loot',schema:2,config:old,configYaml:text,
 scenario:{...s,tabletRarity:'Legendary',effects:[{id:'VE_PopulationBosses',value:100}]}},context);
return {budget:config.rules.budgetPerRoll,comment:revised.startsWith('# Keep custom rewards'),
 same:Y.exposePopulationModifiers(revised,context)===revised,bosses:review.scenario.effects[0].value};
'''.replace('VENDOR', json.dumps(str(HERE / 'vendor/js-yaml-4.3.0.min.js'))))
        self.assertEqual(result, dict(budget=17, comment=True, same=True, bosses=2))

    def test_individual_modifier_values_cover_pool_and_preserve_existing_rates(self):
        self.assertTrue(all(m['id'] in self.config['rules']['modifierDifficulty'] for m in self.context['modifiers']))
        self.config['rules']['modifierDifficulty'] = {'VE_BearTraps': 0, 'custom-effect': 17}
        self.config['rules']['categoryDifficulty']['totems'] = 12
        expression = '''
const yaml=require(VENDOR),text='# Keep note\\n'+yaml.dump(c,{flowLevel:FLOW});
const revised=Y.expandModifierDifficulty(text,context),next=Y.parse(revised,context);
return {traps:next.rules.modifierDifficulty.VE_BearTraps,totem:next.rules.modifierDifficulty.VE_SlowTotems,
 custom:next.rules.modifierDifficulty['custom-effect'],complete:context.modifiers.every(m=>Object.hasOwn(next.rules.modifierDifficulty,m.id)),
 unchanged:context.modifiers.every(m=>E.bonus(c,{...s,effects:[{id:m.id,value:m.value}]}).total===E.bonus(next,{...s,effects:[{id:m.id,value:m.value}]}).total),
 repeat:Y.expandModifierDifficulty(revised,context)===revised,comment:revised.startsWith('# Keep note')};
'''.replace('VENDOR', json.dumps(str(HERE / 'vendor/js-yaml-4.3.0.min.js')))
        for flow in [0, -1]:
            self.assertEqual(self.run_engine(expression.replace('FLOW', str(flow))),
                             dict(traps=0, totem=12, custom=17, complete=True, unchanged=True, repeat=True, comment=True))

    def test_totem_roll_counts_follow_rarity_and_cap_at_four(self):
        result = self.run_engine('''
context.modifiers=context.modifiers.filter(m=>m.id==='VE_SlowTotems');
const result={};
for(const rarity of E.tabletRarities.filter(r=>r!=='None')){
 context.effectCounts[rarity]=[[1,1]];
 result[rarity]=[...new Set(Array.from({length:100},(_,seed)=>E.generateModifiers(context,rarity,String(seed),c)[0].value))].sort();
}
return result;
''')
        for rarity, maximum in zip(['Magic', 'Rare', 'Epic', 'Legendary', 'Mythic', 'Ancient'], [1, 2, 3, 4, 4, 4]):
            self.assertEqual(result[rarity], list(range(1, maximum + 1)), rarity)

    def test_totem_scenario_rejects_fractional_or_excessive_counts(self):
        for count in [0, 1.5, 5]:
            scenario = dict(self.scenario, effects=[dict(id='VE_SlowTotems', value=count)])
            result = self.run_engine('return E.validateScenario(s,context);', scenario=scenario)
            self.assertIn('Totem counts', result['error'])

    def test_approved_tier_fifteen_reference(self):
        self.scenario.update(tier=15, effects=[dict(id='VE_BearTraps', value=1)])
        self.config['rules']['modifierDifficulty']['VE_BearTraps'] = 63.6
        result = self.run_engine('return E.analyze(c,s);')
        self.assertAlmostEqual(result['raw'], 41.4613600256)
        self.assertEqual(result['rolls'], 42)
        # Approved expectations were set at 41.4613600256 rolls; rounding up to 42 scales them evenly.
        scale = 42 / 41.4613600256
        items = {entry['item']['id']: entry for entry in result['items']}
        self.assertAlmostEqual(items['coins']['expected'], 1332.6865722514285 * scale)
        self.assertAlmostEqual(items['ReagentAncient']['expected'], 28.786029960630863 * scale)
        self.assertAlmostEqual(items['ShardAncient']['expected'], 6.396895546806857 * scale)
        self.assertAlmostEqual(items['RunestoneAncient']['expected'], 4.264597031204572 * scale)
        self.assertEqual(items['RunestoneAncient']['item']['maxQuantity'], 1)



if __name__ == '__main__':
    unittest.main()
