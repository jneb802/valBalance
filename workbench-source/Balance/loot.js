/* Difficulty-based reward planning. Item selection mirrors the existing loot tables. */
(function(root) {
'use strict';
const copy = value => JSON.parse(JSON.stringify(value));
const categories = ['population','hazards','totems','creatures'];
const tabletRarities = ['None','Magic','Rare','Epic','Legendary','Mythic','Ancient'];
const setRarities = ['Legendary','Mythic','Ancient'];
const populationIds = ['VE_PopulationStandard','VE_PopulationSupport','VE_PopulationElite','VE_PopulationBosses'];
function setRewardRarity(tier) {
 if(!Number.isInteger(tier)||tier<1||tier>15)throw Error('Set rewards require tier 1–15.');
 return tier<=3?'Legendary':tier<=6?'Mythic':'Ancient';
}
function rewardName(item,tier) {
 return item.randomLegendarySetRune?setRewardRarity(tier)+' set runestone':item.id;
}
function rewardRows(analysis,tier) {
 const active=setRewardRarity(tier);
 return analysis.items.flatMap(row=>row.item.randomLegendarySetRune?setRarities.map(setRarity=>({
  ...row,label:setRarity+' set runestone',setRarity,
  ...(setRarity===active?{}:{probability:0,atLeastOne:0,expected:0,min:0,max:0})
 })):[{...row,label:row.item.id}]);
}
function setRewardOdds(analysis,tier) {
 const probability=analysis.items.filter(row=>row.item.randomLegendarySetRune).reduce((sum,row)=>sum+row.probability,0);
 const chance=1-Math.pow(1-probability,analysis.rolls);
 return setRarities.map(rarity=>rarity===setRewardRarity(tier)?chance:0);
}
const itemDefaults = {prefab:'',randomLegendarySetRune:false,enabled:true,minTier:1,maxTier:15,minQuantity:1,maxQuantity:1,tabletTier:0,tabletTheme:''};
function normalize(raw,context={}) {
 const c=copy(raw);
 // Convert saved drafts from the former equipment reward without changing their tuning.
 const renamed=new Map();
 for(const i of c.items){
  if(i.randomLegendarySetItem){i.randomLegendarySetRune=true;if(i.id==='random-legendary-set-item'){renamed.set(i.id,'random-legendary-set-runestone');i.id='random-legendary-set-runestone';}}
  delete i.randomLegendarySetItem;
  if(i.enchantment===null)delete i.enchantment;
 }
 for(const r of c.rarities)for(const e of r.entries)if(renamed.has(e.item))e.item=renamed.get(e.item);
 c.schemaVersion ??= 2;
 c.populationModifiers ??= copy(context.populationModifiers||{});
 c.items=c.items.map(i=>({...itemDefaults,...i}));
 c.rarities=c.rarities.map(r=>({...r,entries:r.entries.map(e=>({weight:1,...e}))}));
 return c;
}
function validate(c, context={}) {
 const errors=[],check=(ok,message)=>{if(!ok)errors.push(message);};
 const number=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
 const integer=(v,min,max)=>Number.isInteger(v)&&number(v,min,max);
 const text=v=>typeof v==='string'&&v.trim().length>0;
 const keys=(o,allowed,path)=>{for(const key of Object.keys(o))check(allowed.includes(key),path+': unknown field '+key);};
 if(!c||!Array.isArray(c.items)||!Array.isArray(c.rarities)||!c.rules)throw Error('Reward settings require items, rarities and rules.');
 keys(c,['schemaVersion','items','rarities','rules','populationModifiers'],'rewards');
 check(c.populationModifiers&&typeof c.populationModifiers==='object'&&!Array.isArray(c.populationModifiers),'populationModifiers must be a mapping.');
 if(c.populationModifiers)keys(c.populationModifiers,populationIds,'populationModifiers');
 for(const id of populationIds){
  const p=c.populationModifiers?.[id],bosses=id==='VE_PopulationBosses',allowed=tabletRarities.slice(bosses?3:1);
  check(p&&number(p.difficultyPer,0.01,500),id+': difficultyPer must be 0.01–500.');
  if(!p)continue;
  keys(p,['difficultyPer','ranges'],id);
  check(p.ranges&&typeof p.ranges==='object'&&!Array.isArray(p.ranges),id+': ranges must be a mapping.');
  if(p.ranges)keys(p.ranges,allowed,id+' ranges');
  for(const rarity of allowed){const range=p.ranges?.[rarity];check(range&&integer(range.min,1,bosses?20:500)&&integer(range.max,range.min,bosses?20:500),id+' '+rarity+': provide valid whole-number min/max values.');if(range)keys(range,['min','max'],id+' '+rarity);}
 }
 check(c.schemaVersion===2,'Use schemaVersion 2 for the difficulty-based plan.');
 check(c.items.length>0,'Add at least one item.');
 check(c.rarities.length>0,'Add at least one rarity table.');
 check(new Set(c.items.map(i=>i.id)).size===c.items.length,'Item IDs must be unique.');
 check(new Set(c.rarities.map(r=>r.id)).size===c.rarities.length,'Rarity IDs must be unique.');
 for(const i of c.items) {
  const p='Item '+i.id+': ';
  keys(i,['id',...Object.keys(itemDefaults)],p);
  check(text(i.id),p+'enter an ID.');
  check(typeof i.enabled==='boolean'&&typeof i.randomLegendarySetRune==='boolean',p+'enabled and random reward flags must be true or false.');
  check(typeof i.prefab==='string'&&(i.randomLegendarySetRune||text(i.prefab)),p+'enter a prefab or select a random set reward.');
  check(integer(i.minTier,1,15)&&integer(i.maxTier,i.minTier,15),p+'tier range must be 1–15.');
  check(integer(i.minQuantity,1,1000)&&integer(i.maxQuantity,i.minQuantity,1000),p+'quantity range must be 1–1000.');
  check(integer(i.tabletTier,0,15)&&typeof i.tabletTheme==='string',p+'tablet tier must be 0–15 and theme must be text.');
  if(i.randomLegendarySetRune)check(i.prefab===''&&i.minQuantity===1&&i.maxQuantity===1&&i.tabletTier===0&&i.tabletTheme==='',p+'random set runes require quantity 1 and no prefab or tablet settings.');
 }
 for(const r of c.rarities) {
  keys(r,['id','probability','entries'],'Rarity '+r.id);
  check(text(r.id)&&number(r.probability,0,1),'Rarity '+r.id+': probability must be between 0 and 100%.');
  check(Array.isArray(r.entries),'Rarity '+r.id+': entries must be a list.');
  if(!Array.isArray(r.entries))continue;
  check(new Set(r.entries.map(e=>e.item)).size===r.entries.length,'Rarity '+r.id+': item references must be unique.');
  for(const e of r.entries) {
   keys(e,['item','weight'],'Entry '+e.item);
   check(c.items.some(i=>i.id===e.item)&&number(e.weight,Number.MIN_VALUE,1000000),'Rarity '+r.id+': '+e.item+' needs an existing item and positive weight at most 1000000.');
  }
 }
 check(Math.abs(c.rarities.reduce((sum,r)=>sum+r.probability,0)-1)<0.000001,'Rarity probabilities must total 100%.');
 const r=c.rules;
 keys(r,['budgetPerRoll','maxRolls','tiers','categoryDifficulty','modifierDifficulty'],'rules');
 check(number(r.budgetPerRoll,0.01,1000000),'budgetPerRoll must be 0.01–1000000.');
 check(integer(r.maxRolls,1,10000),'maxRolls must be a whole number from 1–10000.');
 check(Array.isArray(r.tiers)&&r.tiers.length===15,'Provide exactly 15 tier rows.');
 if(Array.isArray(r.tiers))r.tiers.forEach((t,k)=>{keys(t,['difficulty','bonusPercent'],'Tier '+(k+1));check(number(t.difficulty,0,1000000)&&number(t.bonusPercent,0,1000),'Tier '+(k+1)+': difficulty must be 0–1000000 and bonusPercent 0–1000.');});
 for(const cat of categories)check(number(r.categoryDifficulty?.[cat],0,500),cat+' difficulty contribution must be 0–500%.');
 if(r.categoryDifficulty)keys(r.categoryDifficulty,categories,'categoryDifficulty');
 check(r.modifierDifficulty&&typeof r.modifierDifficulty==='object'&&!Array.isArray(r.modifierDifficulty),'modifierDifficulty must be a mapping.');
 for(const [id,v] of Object.entries(r.modifierDifficulty||{}))check(text(id)&&number(v,0,500),'Modifier '+id+' difficulty contribution must be 0–500%.');
 if(!errors.length)for(let tier=1;tier<=15;tier++)for(let k=0;k<c.rarities.length;k++)if(c.rarities[k].probability>0&&fallback(c,k,tier)<0)errors.push('Tier '+tier+': '+c.rarities[k].id+' has no eligible item or lower table.');
 if(errors.length)throw Error(errors.join('\n'));
 return c;
}
function category(id) {
 if(populationIds.includes(id))return 'population';
 if(id.startsWith('VE_SLS_')||id==='VE_ShamanShields')return 'creatures';
 if(id.endsWith('Totems'))return 'totems';
 return 'hazards';
}
function validateScenario(s, context={}) {
 if(s?.tabletRarity!==undefined&&!tabletRarities.includes(s.tabletRarity))throw Error('Choose a valid Epic Loot tablet rarity.');
 if(!s||!Number.isInteger(s.tier)||s.tier<1||s.tier>15||typeof s.completed!=='boolean'||typeof s.seed!=='string'||s.seed.length>200||!Array.isArray(s.effects)||s.effects.length>100)throw Error('Invalid scenario: use tier 1–15, completion state, a seed and up to 100 effects.');
 const seen=new Set(),forced=new Set();
 for(const e of s.effects) {
  if(typeof e.id!=='string'||seen.has(e.id)||!Number.isFinite(e.value)||e.value<0||e.value>500)throw Error('Each modifier needs a unique ID and strength 0–500.');
  seen.add(e.id);
  if(context.modifiers?.find(m=>m.id===e.id)?.ranges&&(!Number.isInteger(e.value)||e.value<1||e.value>4))throw Error('Totem counts must be whole numbers from 1 to 4.');
  if(e.id==='VE_PopulationBosses'&&(!Number.isInteger(e.value)||e.value>20))throw Error('Additional bosses/minibosses must be a whole number from 0–20 per eligible wave.');
  const sls=/^VE_SLS_[0-2]_([0-9A-F]+)$/.exec(e.id);
  if(sls) {if(sls[1].length%2||forced.has(sls[1]))throw Error('Conflicting or invalid Star Level System modifier.');forced.add(sls[1]);}
  else if(!context.modifiers?.some(m=>m.id===e.id))throw Error('Unknown tablet modifier: '+e.id);
 }
 return s;
}
function eligible(c,k,tier) {
 return c.rarities[k].entries.map(e=>({item:c.items.find(i=>i.id===e.item),weight:e.weight})).filter(e=>e.item?.enabled&&tier>=e.item.minTier&&tier<=e.item.maxTier);
}
function fallback(c,k,tier) {for(;k<c.rarities.length;k++)if(eligible(c,k,tier).length)return k;return -1;}
function bonus(c,s) {
 let total=0;
 const parts=s.effects.map(e=>{
  const cat=category(e.id),rate=c.rules.modifierDifficulty[e.id]??c.rules.categoryDifficulty[cat];
  // Population scales per difficultyPer of strength; totems scale per totem spawned each wave.
  const strength=cat==='population'?e.value/c.populationModifiers[e.id].difficultyPer:cat==='totems'?e.value:1;
  const value=rate*strength;total+=value;
  return {id:e.id,category:cat,rate,strength,value};
 });
 return {total,parts};
}
function analyze(c,s) {
 const b=bonus(c,s),r=c.rules,t=r.tiers[s.tier-1],difficulty=t.difficulty*(1+b.total/100),budget=difficulty*(1+t.bonusPercent/100);
 // Every partial roll counts as a whole roll. Rounding to 10 places first keeps 13.0000000001 at 13.
 const raw=budget/r.budgetPerRoll,rolls=s.completed?Math.min(r.maxRolls,Math.ceil(Number(raw.toFixed(10)))):0;
 const rarities=c.rarities.map(r=>({id:r.id,configured:r.probability,probability:0})),fallbacks=[];
 for(let k=0;k<c.rarities.length;k++) {
  if(!c.rarities[k].probability)continue;
  const target=fallback(c,k,s.tier);
  if(target<0)throw Error('No eligible reward table.');
  rarities[target].probability+=c.rarities[k].probability;
  if(target!==k)fallbacks.push({from:c.rarities[k].id,to:c.rarities[target].id,probability:c.rarities[k].probability});
 }
 const probabilities=new Map(c.items.map(i=>[i.id,0]));
 rarities.forEach((r,k)=>{
  const choices=eligible(c,k,s.tier),sum=choices.reduce((a,e)=>a+e.weight,0);
  for(const e of choices)probabilities.set(e.item.id,probabilities.get(e.item.id)+r.probability*e.weight/sum);
 });
 const chance=p=>1-Math.pow(1-p,rolls);
 return {bonus:b,baseDifficulty:t.difficulty,tierBonus:t.bonusPercent,difficulty,budget,raw,rolls,capped:s.completed&&raw>r.maxRolls,fallbacks,
  rarities:rarities.map(r=>({...r,atLeastOne:chance(r.probability)})),
  items:c.items.map(item=>{const probability=probabilities.get(item.id);return {item,probability,atLeastOne:chance(probability),expected:rolls*probability*(item.minQuantity+item.maxQuantity)/2,min:probability>=1?rolls*item.minQuantity:0,max:probability>0?rolls*item.maxQuantity:0};})};
}
function random(seed) {
 let n=2166136261;for(const c of String(seed))n=Math.imul(n^c.charCodeAt(0),16777619);
 return ()=>{n+=0x6D2B79F5;let t=n;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
}
function sample(c,s,count=3) {
 const result=analyze(c,s),rng=random(s.seed),examples=[];
 for(let n=0;n<count;n++) {
  const drops=[];
  for(let roll=0;roll<result.rolls;roll++) {
   let higher=0,k=c.rarities.findLastIndex(r=>r.probability>0);
   for(let j=0;j<c.rarities.length;j++) {
    const p=c.rarities[j].probability,check=p/(1-higher);
    if(p>0&&(check>=1||rng()<check)){k=j;break;}higher+=p;
   }
   k=fallback(c,k,s.tier);const choices=eligible(c,k,s.tier);
   let target=rng()*choices.reduce((a,e)=>a+e.weight,0),item=choices[choices.length-1].item;
   for(const e of choices){target-=e.weight;if(target<=0){item=e.item;break;}}
   drops.push({id:item.id,rarity:c.rarities[k].id,quantity:item.minQuantity+Math.floor(rng()*(item.maxQuantity-item.minQuantity+1))});
  }
  examples.push(drops);
 }
 return examples;
}
function generateModifiers(context,rarity,seed,config=context.config){
 if(!tabletRarities.includes(rarity))throw Error('Choose a valid Epic Loot tablet rarity.');
 if(rarity==='None')return [];
 const counts=context.effectCounts?.[rarity];
 if(!Array.isArray(counts)||!counts.length||counts.some(e=>!Array.isArray(e)||e.length!==2||!Number.isInteger(e[0])||e[0]<0||e[0]>100||!Number.isFinite(e[1])||e[1]<0))throw Error('Invalid modifier count distribution.');
 const weight=counts.reduce((sum,e)=>sum+e[1],0);if(weight<=0)throw Error('Modifier count weights must be positive.');
 const rng=random(seed);let target=rng()*weight,count=counts.at(-1)[0];
 for(const [n,w] of counts){target-=w;if(target<0){count=n;break;}}
 let pool=context.modifiers.filter(m=>!m.noRoll&&(category(m.id)!=='population'||config.populationModifiers[m.id].ranges[rarity]));
 const effects=[];
 while(effects.length<count&&pool.length){
  const chosen=pool[Math.floor(rng()*pool.length)],range=config.populationModifiers[chosen.id]?.ranges[rarity]||chosen.ranges?.[rarity];
  effects.push({id:chosen.id,value:range?range.min+Math.floor(rng()*(range.max-range.min+1)):chosen.value});
  const name=/^VE_SLS_[0-2]_([0-9A-F]+)$/.exec(chosen.id)?.[1];
  pool=pool.filter(m=>m.id!==chosen.id&&(!name||/^VE_SLS_[0-2]_([0-9A-F]+)$/.exec(m.id)?.[1]!==name));
 }
 if(effects.length<count)throw Error('Not enough compatible modifiers for this rarity.');
 validateScenario({tier:1,completed:true,seed:String(seed),effects,tabletRarity:rarity},context);
 return effects;
}
function review(raw, context) {
 if(raw?.kind!=='difficulty-loot'||raw.schema!==2)throw Error('Import a difficulty-loot review (schema 2). Older game/chest reviews use a different model.');
 const config=validate(normalize(raw.config,context),context),scenario=copy(raw.scenario);
 if(!raw.config.populationModifiers){
  const range=config.populationModifiers.VE_PopulationBosses.ranges[scenario.tabletRarity||'Legendary'];
  scenario.effects=scenario.effects.flatMap(effect=>effect.id!=='VE_PopulationBosses'?[effect]:range?[{...effect,value:range.min}]:[]);
 }
 validateScenario(scenario,context);
 return {kind:'difficulty-loot',schema:2,config,scenario,...(raw.configYaml===undefined?{}:{configYaml:raw.configYaml})};
}
const api={normalize,validate,category,validateScenario,eligible,fallback,bonus,analyze,sample,review,generateModifiers,tabletRarities,setRewardRarity,setRarities,rewardName,rewardRows,setRewardOdds};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.LootEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this);
