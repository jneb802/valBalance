(function() {
'use strict';
const E=LootEngine,Y=LootYaml,context=DATA.loot,baseline=E.validate(E.normalize(context.config),context),key='ve-difficulty-loot-v2';
const initial={kind:'difficulty-loot',schema:2,config:clone(baseline),configYaml:context.configYaml,scenario:{tier:1,completed:true,seed:'endgame-1',effects:[],tabletRarity:'Legendary'}};
let draft=restoreDraft(key,initial,v=>Y.review(v,context),$('loot-error')),latest=null;
const yamlKey='ve-difficulty-loot-yaml-v2';
let yamlTimer;
function saveYamlText(){try{localStorage.setItem(yamlKey,$('loot-yaml').value);}catch(error){$('loot-save-status').textContent='Storage unavailable. Export your review.';}}
const percent=n=>(n*100).toFixed(2)+'%',decimal=n=>Number(n.toFixed(4)).toLocaleString();
function button(text,action){const b=el('button',text);b.type='button';b.onclick=action;return b;}
function field(label,value,change,options={}) {
 const wrap=el('label',label),input=el('input');input.type=options.type||'number';
 input.setAttribute('aria-label',label);
 if(input.type==='checkbox')input.checked=value;else input.value=value;
 for(const k of ['min','max','step','placeholder'])if(options[k]!==undefined)input[k]=options[k];
 if(input.type==='number'&&!options.step)input.step='any';
 input.onchange=()=>change(input.type==='checkbox'?input.checked:input.type==='number'?(input.value===''?NaN:Number(input.value)):input.value);
 wrap.append(input);return wrap;
}
function select(label,value,values,change) {
 const wrap=el('label',label),input=el('select');input.setAttribute('aria-label',label);
 for(const v of values){const o=el('option',typeof v==='object'?v.label:String(v));o.value=typeof v==='object'?v.value:v;input.append(o);}
 input.value=value;input.onchange=()=>change(input.value);wrap.append(input);return wrap;
}
function table(headers,rows) {
 const wrap=el('div',undefined,'tablewrap'),t=el('table'),head=el('thead'),tr=el('tr'),body=el('tbody');
 headers.forEach(h=>tr.append(el('th',h)));head.append(tr);
 for(const cells of rows){const row=el('tr');for(const c of cells){const td=el('td');if(c instanceof Node)td.append(c);else td.textContent=c;row.append(td);}body.append(row);}
 t.append(head,body);wrap.append(t);return wrap;
}
function resultsReady(ready) {
 for(const id of ['loot-results','loot-odds']){$(id).classList.toggle('loot-results-paused',!ready);$(id).inert=!ready;}
 ['loot-export','loot-reroll','loot-preview','loot-csv','loot-yaml-download','loot-generate-modifiers'].forEach(id=>{if($(id))$(id).disabled=!ready;});
}
function update(persist=true) {
 if(persist)saveYamlText();
 try {
  const original=$('loot-yaml').value;
  const text=(original.includes('randomLegendarySetItem')||original.includes('enchantment'))?Y.upgradeSetRewards(original,context):original;
  if(text!==original){$('loot-yaml').value=text;saveYamlText();}
  const config=Y.parse(text,context);
  E.review({...draft,config},context);
  draft.config=config;draft.configYaml=text;
  $('loot-yaml-error').textContent='';$('loot-yaml').setAttribute('aria-invalid','false');
  $('loot-yaml-status').textContent='Valid YAML · results updated';
  $('loot-error').textContent='';resultsReady(true);
  if(persist)saveDraft(key,draft,$('loot-save-status'));
  renderResults();
 }catch(error){
  $('loot-yaml-error').textContent=error.message;$('loot-yaml').setAttribute('aria-invalid','true');
  $('loot-yaml-status').textContent='Results show the last valid configuration. Fix the YAML to update them.';
  latest=null;$('loot-error').textContent=error.message;resultsReady(false);
  $('loot-live-summary').textContent=error.message.split('\n')[0];
  $('loot-save-status').textContent='Fix the YAML to update results or export';
 }
}
function tierControl(s) {
 const wrap=el('div',undefined,'loot-tier-control'),label=el('label','Encounter tier'),control=el('div',undefined,'loot-tier-stepper'),input=el('input'),arrows=el('div',undefined,'loot-tier-arrows');
 label.htmlFor='loot-tier';input.id='loot-tier';input.type='number';input.min=1;input.max=15;input.step=1;input.value=s.tier;
 const up=button('▲',()=>change(s.tier+1)),down=button('▼',()=>change(s.tier-1));
 up.setAttribute('aria-label','Increase encounter tier');down.setAttribute('aria-label','Decrease encounter tier');
 function refresh(){input.value=s.tier;up.disabled=s.tier===15;down.disabled=s.tier===1;}
 function change(value){if(!Number.isInteger(value)||value<1||value>15){refresh();$('loot-error').textContent='Encounter tier must be a whole number from 1 to 15.';return;}s.tier=value;refresh();update();}
 input.oninput=()=>{if(input.value!==''&&input.checkValidity())change(Number(input.value));};
 input.onchange=()=>change(input.value===''?NaN:Number(input.value));
 arrows.append(up,down);control.append(input,arrows);wrap.append(label,control);refresh();return wrap;
}
function renderScenario() {
 const s=draft.scenario,area=$('loot-scenario');area.replaceChildren();
 area.append(tierControl(s),
  select('Outcome',s.completed?'completed':'failed',[{value:'completed',label:'Completed'},{value:'failed',label:'Failed / aborted'}],v=>{s.completed=v==='completed';update();}),
  field('Random seed',s.seed,v=>{s.seed=v;update();},{type:'text'}));
 const generator=$('loot-modifier-generator');generator.replaceChildren();
 generator.append(select('Tablet rarity',s.tabletRarity||'Legendary',E.tabletRarities,v=>{s.tabletRarity=v;if(v==='None'){s.effects=[];renderScenario();$('loot-modifier-status').textContent='Unenchanted tablet. Removed all modifiers.';}update();}));
 const generate=button('Generate random modifiers',()=>{
  try{
   s.tabletRarity=generator.querySelector('select').value;
   s.effects=E.generateModifiers(context,s.tabletRarity,String(crypto.getRandomValues(new Uint32Array(1))[0]),draft.config);
   renderScenario();update();$('loot-modifier-status').textContent='Generated '+s.effects.length+' '+s.tabletRarity+' tablet modifiers. Replaced the previous selection.';
  }catch(error){$('loot-error').textContent=error.message;}
 });generate.id='loot-generate-modifiers';generator.append(generate);
 $('loot-modifier-status').textContent='';
 $('loot-selected-modifiers').replaceChildren(...s.effects.map(e=>el('span',context.modifiers.find(m=>m.id===e.id)?.label||e.id,'badge')));
 const effects=$('loot-effects');effects.replaceChildren();
 const options=[...context.modifiers,...s.effects.filter(e=>!context.modifiers.some(m=>m.id===e.id)).map(e=>({id:e.id,label:e.id,value:e.value}))];
 for(const m of options) {
  const row=el('div',undefined,'loot-effect'),active=s.effects.find(e=>e.id===m.id);
  row.append(field(m.label,!!active,on=>{if(on)s.effects.push({id:m.id,value:draft.config.populationModifiers[m.id]?.ranges[s.tabletRarity||'Legendary']?.min??m.value});else s.effects=s.effects.filter(e=>e.id!==m.id);renderScenario();update();},{type:'checkbox'}));
  row.append(el('small',m.id+' · '+E.category(m.id)));
  if(m.noRoll)row.append(el('small','Excluded from random generation; available for existing tablets.'));
  const contribution=el('small');contribution.dataset.modifierId=m.id;row.append(contribution);
  if(active&&E.category(m.id)==='population'){
   const bosses=m.id==='VE_PopulationBosses';
   row.append(field(m.label+(bosses?' (extra per eligible wave)':' strength (%)'),active.value,v=>{active.value=v;update();},{min:0,max:bosses?20:500,step:1}));
  }
  if(active&&m.ranges)row.append(field('Totems per wave (maximum four)',active.value,v=>{active.value=v;update();},{min:1,max:4,step:1}));
  effects.append(row);
 }
}
function renderSettings() {$('loot-yaml').value=draft.configYaml;}
function itemDescription(i,tier) {
 if(i.randomLegendarySetRune)return E.setRewardRarity(tier)+' set runestone · Legendary T1–3, Mythic T4–6, Ancient T7–15 · set selected in game';
 const parts=[i.prefab];
 if(/^ve_tablet_tier\d+$/i.test(i.prefab))parts.push('Tier '+(i.tabletTier||tier)+' · '+(i.tabletTheme||'random enabled theme'));
 return parts.join(' · ');
}
function renderResults() {
 const s=draft.scenario,c=draft.config,b=E.analyze(c,s);latest=b;
 $('loot-live-summary').textContent='Tier '+s.tier+' · '+decimal(b.rolls)+' reward rolls · '+decimal(b.bonus.total)+'% modifier difficulty';
 $('loot-modifier-summary').textContent='· '+s.effects.length+' selected · +'+decimal(b.bonus.total)+'% difficulty';
 for(const node of document.querySelectorAll('[data-modifier-id]')){const id=node.dataset.modifierId,active=b.bonus.parts.find(p=>p.id===id),rate=c.rules.modifierDifficulty[id]??c.rules.categoryDifficulty[E.category(id)],population=c.populationModifiers[id];node.textContent=active?'Adds '+decimal(active.value)+'% difficulty':decimal(rate)+'% difficulty'+(population?' per +'+decimal(population.difficultyPer)+(id==='VE_PopulationBosses'?' bosses/minibosses per eligible wave':'% creatures'):E.category(id)==='totems'?' per totem':' when selected');}
 const rollInfo=$('loot-roll-info');
 $('loot-metrics').replaceChildren(...[['Reward rolls',decimal(b.rolls)],['Adjusted difficulty',decimal(b.difficulty)],['Reward budget',decimal(b.budget)]].map(([label,value],index)=>{const box=el('div',undefined,'loot-metric'),title=el('div',undefined,'loot-metric-title');title.append(el('span',label));if(index===0)title.append(rollInfo);box.append(title,el('b',value));return box;}));
 $('loot-roll-summary').textContent=s.completed?b.rolls+' reward rolls. Tier reward bonus: '+decimal(b.tierBonus)+'%.'+(b.capped?' Roll cap reached.':''):'Failed / aborted run: no rewards. Difficulty and budget show the encounter before failure.';
 $('loot-formula').textContent=`Tier difficulty ${decimal(b.baseDifficulty)} × (1 + ${decimal(b.bonus.total)}% modifier difficulty) = ${decimal(b.difficulty)}.\nAdjusted difficulty × (1 + ${decimal(b.tierBonus)}% tier bonus) = ${decimal(b.budget)} budget.\nBudget ÷ ${decimal(c.rules.budgetPerRoll)} cost per roll = ${decimal(b.raw)}, rounded up to ${b.rolls} reward rolls. Maximum ${c.rules.maxRolls}.\nFailed runs give zero rolls.`;
 $('loot-bonuses').replaceChildren(...b.bonus.parts.map(p=>el('small',p.id+': '+decimal(p.rate)+'% × '+decimal(p.strength)+' = '+decimal(p.value)+'% ')));
 $('loot-fallback').textContent=b.fallbacks.map(f=>percent(f.probability)+' moves from '+f.from+' to '+f.to+'.').join(' ');
 const exampleArea=$('loot-examples');exampleArea.replaceChildren();
 E.sample(c,s).forEach((drops,index)=>{
  const card=el('div',undefined,'loot-example');card.append(el('h3','Example '+(index+1)+' · '+drops.length+' rolls'));
  if(!drops.length)card.append(el('p','No rewards.'));
  const grouped=new Map();for(const drop of drops){const key=JSON.stringify([drop.id,drop.rarity]);const old=grouped.get(key)||{...drop,quantity:0,rolls:0};old.quantity+=drop.quantity;old.rolls++;grouped.set(key,old);}
  for(const drop of grouped.values()){const item=c.items.find(i=>i.id===drop.id),row=el('div',drop.quantity+' × '+E.rewardName(item,s.tier),'loot-drop');row.append(el('small',drop.rarity+' table · '+drop.rolls+' selection'+(drop.rolls===1?'':'s')),el('small',itemDescription(item,s.tier)));card.append(row);}
  exampleArea.append(card);
 });
 $('loot-rarity-results').replaceChildren(table(['Table','Configured chance','Effective / roll','At least one / run'],b.rarities.map(r=>[r.id,percent(r.configured),percent(r.probability),percent(r.atLeastOne)])));
 $('loot-item-results').replaceChildren(table(['Item','Chance / roll','At least one / run','Average quantity / run','Possible min–max / run'],E.rewardRows(b,s.tier).map(i=>{const name=el('span',i.label);if(!i.item.enabled)name.append(el('small','Disabled'));else if(i.setRarity&&i.setRarity!==E.setRewardRarity(s.tier))name.append(el('small','Outside set rarity tiers'));else if(s.tier<i.item.minTier||s.tier>i.item.maxTier)name.append(el('small','Outside tier range'));else if(!i.probability)name.append(el('small','No active table chance'));return [name,percent(i.probability),percent(i.atLeastOne),decimal(i.expected),i.min+'–'+i.max];})));
 const tiers=Array.from({length:15},(_,k)=>E.analyze(c,{...s,tier:k+1})),max=Math.max(1,...tiers.map(t=>t.rolls));
 const quantities=table(['Tier',...E.rewardRows(b,s.tier).map(i=>i.label)],tiers.map((t,k)=>[k+1,...E.rewardRows(t,k+1).map(i=>decimal(i.expected))]));
 quantities.classList.add('loot-quantity-matrix');quantities.tabIndex=0;quantities.setAttribute('role','region');quantities.setAttribute('aria-label','Average item quantities by tier; scroll horizontally for more items');
 quantities.querySelector('table').setAttribute('aria-label','Average quantity of each item per run, for tiers 1 through 15');
 $('loot-quantity-results').replaceChildren(quantities);
 $('loot-tier-results').replaceChildren(table(['Tier','Base difficulty','With modifiers','Tier bonus','Budget','Reward rolls',...c.rarities.map(r=>r.id+' table ≥1 / run'),...E.setRarities.map(r=>r+' set ≥1 / run')],tiers.map((t,k)=>{const bar=el('div',undefined,'loot-tier-bar'),fill=el('div');fill.style.width=(100*t.rolls/max)+'%';bar.append(fill,el('span',decimal(t.rolls)+(t.capped?' (cap)':'')));return [k+1,decimal(t.baseDifficulty),decimal(t.difficulty),decimal(t.tierBonus)+'%',decimal(t.budget),bar,...t.rarities.map(r=>percent(r.atLeastOne)),...E.setRewardOdds(t,k+1).map(percent)];})));
}
bindReview({exportButton:$('loot-export'),importButton:$('loot-import'),file:$('loot-file'),status:$('loot-error'),filename:'valheim-endgame-loot-review.json',getState:()=>({...Y.review(draft,context),inputHashes:context.hashes}),accept:raw=>{draft=Y.review(raw,context);renderScenario();renderSettings();update();}});
$('loot-csv').onclick=()=>{if(!latest)return;csvDownload('loot-tier-'+draft.scenario.tier+'.csv',[['Item','Tier','Completed','Reward rolls','Probability per roll','At least one per run','Average quantity per run','Minimum','Maximum'],...E.rewardRows(latest,draft.scenario.tier).map(i=>[i.label,draft.scenario.tier,draft.scenario.completed,latest.rolls,i.probability,i.atLeastOne,i.expected,i.min,i.max])]);};
$('loot-reset').onclick=()=>{if(confirm('Reset all reward settings to the embedded configuration? Scenarios stay.')){draft.config=clone(baseline);draft.configYaml=context.configYaml;renderSettings();update();}};
$('loot-reroll').onclick=()=>{draft.scenario.seed=String(Date.now())+'-'+crypto.getRandomValues(new Uint32Array(1))[0];renderScenario();update();};
$('loot-add-sls').onclick=()=>{const id=$('loot-sls-id').value.trim(),candidate=clone(draft.scenario);candidate.effects.push({id,value:1});try{if(!id.startsWith('VE_SLS_'))throw Error('Enter an exact Star Level System effect ID.');E.validateScenario(candidate,context);draft.scenario=candidate;$('loot-sls-id').value='';renderScenario();update();}catch(error){$('loot-error').textContent=error.message;}};
$('loot-yaml').oninput=()=>{clearTimeout(yamlTimer);saveYamlText();resultsReady(false);latest=null;$('loot-yaml-status').textContent='Checking YAML…';$('loot-live-summary').textContent='Checking YAML…';yamlTimer=setTimeout(()=>update(),250);};
$('loot-yaml-download').onclick=()=>download('rewards.yaml',draft.configYaml,'application/yaml');
$('loot-close-dialog').onclick=()=>$('loot-dialog').close();
const rollInfo=$('loot-roll-info'),rollInfoButton=$('loot-roll-info-button'),rollTooltip=$('loot-roll-tooltip');
function showRollTooltip(show){rollTooltip.hidden=!show;rollInfoButton.setAttribute('aria-expanded',String(show));}
rollInfo.onmouseenter=()=>showRollTooltip(true);
rollInfo.onmouseleave=()=>{if(!rollInfo.contains(document.activeElement))showRollTooltip(false);};
rollInfo.addEventListener('focusin',()=>showRollTooltip(true));
rollInfo.addEventListener('focusout',event=>{if(!rollInfo.contains(event.relatedTarget))showRollTooltip(false);});
rollInfoButton.onclick=()=>showRollTooltip(true);
document.addEventListener('keydown',event=>{if(event.key==='Escape')showRollTooltip(false);});
document.addEventListener('pointerdown',event=>{if(!rollInfo.contains(event.target))showRollTooltip(false);});
$('loot-jump-settings').onclick=()=>$('loot-settings').scrollIntoView({behavior:'smooth'});
$('loot-jump-results').onclick=()=>$('loot-results').scrollIntoView({behavior:'smooth'});
$('loot-preview').onclick=()=>{
 $('loot-dialog-title').textContent='Proposed reward changes';const body=$('loot-dialog-body');body.replaceChildren();
 const changes=[];
 function diff(a,b,path){if(JSON.stringify(a)===JSON.stringify(b))return;if(a&&b&&typeof a==='object'&&typeof b==='object'&&!Array.isArray(a)&&!Array.isArray(b)){for(const k of new Set([...Object.keys(a),...Object.keys(b)]))diff(a[k],b[k],path?path+'.'+k:k);}else changes.push(path+'\n  Current: '+JSON.stringify(a)+'\n  Proposed: '+JSON.stringify(b));}
 diff(baseline,draft.config,'');body.append(el('pre',changes.join('\n\n')||'No changes from the starting plan.','loot-json'),el('p','Download rewards.yaml or export a review to keep these settings. Deploying the YAML is a separate step.'));$('loot-dialog').showModal();
};
// One-time migration preserves the original drafts while transferring compatible inputs.
try{
 if(!localStorage.getItem(key)&&!localStorage.getItem(yamlKey)){
  const oldReview=JSON.parse(localStorage.getItem('ve-loot-workbench-v1')||'null');
  const text=localStorage.getItem('ve-loot-yaml-v1-'+context.legacyHash)||oldReview?.configYaml;
  if(text){
   const area=$('loot-migration');
   area.append(button('Download earlier reward YAML',()=>download('earlier-rewards.yaml',text,'application/yaml')));
   try{
    const old=jsyaml.load(text,{schema:jsyaml.JSON_SCHEMA,maxDepth:30});
    const normalized=E.normalize(old),embedded=E.normalize(context.legacyConfig);
    const changed=JSON.stringify([normalized.items,normalized.rarities])!==JSON.stringify([embedded.items,embedded.rarities]);
    if(changed){
     const config=E.validate(E.normalize({...context.config,items:old.items,rarities:old.rarities}),context);
     draft.config=config;
     draft.configYaml=jsyaml.dump(config,{lineWidth:100,noRefs:true});
     area.prepend(el('span','Carried over your earlier item tables. Difficulty rules use the new starting plan. '));
    }else area.prepend(el('span','Using the new starting plan. Earlier reward YAML is preserved. '));
   }catch(error){area.prepend(el('span','Earlier item tables could not be migrated. Your earlier YAML is preserved for download. '));}
  }
  const scalingText=localStorage.getItem('ve-roll-scaling-yaml-v1');
  if(scalingText){
   try{
    const scaling=jsyaml.load(scalingText,{schema:jsyaml.JSON_SCHEMA,maxDepth:30}),candidate=clone(draft.config);
    if(!Array.isArray(scaling.tiers)||scaling.tiers.length<1||scaling.tiers.length>15)throw Error('Invalid tier rows');
    candidate.rules.budgetPerRoll=scaling.budgetPerRoll;
    scaling.tiers.forEach((t,k)=>{candidate.rules.tiers[k]=t;});
    draft.config=E.validate(candidate,context);draft.configYaml=jsyaml.dump(draft.config,{lineWidth:100,noRefs:true});
    $('loot-migration').append(el('span',' Carried over tier difficulty and bonus inputs from your scaling draft.'));
   }catch(error){$('loot-migration').append(el('span',' Earlier scaling inputs could not be migrated. '),button('Download earlier scaling YAML',()=>download('earlier-scaling-plan.yaml',scalingText,'application/yaml')));}
  }
  saveDraft(key,draft,$('loot-save-status'));
 }
}catch(error){/* Local storage may be unavailable; keep the embedded plan. */}
renderScenario();renderSettings();
try{const text=localStorage.getItem(yamlKey);if(text!==null)$('loot-yaml').value=text;}catch(error){/* Review export remains available without browser storage. */}
// Upgrade only the former default bonus series, preserving raw YAML and custom plans.
try{
 const text=$('loot-yaml').value,c=Y.parse(text,context);
 if(c.rules.tiers.every((t,k)=>t.bonusPercent===k*10)){
  const revised=text.replace(/(^[ \t]*(?:-[ \t]*\{[^}\n]*?)?bonusPercent:[ \t]*)(\d+)(?=[,}\s]|$)/gm,(_,prefix,value)=>prefix+Number(value)/5);
  const check=Y.parse(revised,context);
  if(check.rules.tiers.every((t,k)=>t.bonusPercent===k*2)){
   $('loot-yaml').value=revised;draft.config=check;draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));
   $('loot-migration').append(el('span',' Updated the default tier bonus to +2 percentage points per tier.'));
  }
 }
}catch(error){/* Unfinished YAML stays untouched. */}
// Replace the original illustrative curve only when all difficulty rows still match it.
try{
 const text=$('loot-yaml').value,c=Y.parse(text,context),previous=[100,140,195,270,378,529,741,1037,1452,2033,2846,3984,5578,7809,10933];
 if(c.rules.tiers.every((t,k)=>t.difficulty===previous[k])){
  let index=0;
  const revised=text.replace(/(^[ \t]*(?:-[ \t]*\{[^}\n]*?)?difficulty:[ \t]*)(\d+)(?=[,}\s]|$)/gm,(_,prefix)=>prefix+Number((100*1.05**index++).toFixed(4)))
   .replace('# Tiers 1–4 are our examples. Tiers 5–15 provisionally grow difficulty by ~40%.','# Base difficulty = 100 × 1.05^(tier - 1), rounded to four decimal places.');
  const check=Y.parse(revised,context);
  if(check.rules.tiers.every((t,k)=>t.difficulty===Number((100*1.05**k).toFixed(4)))){
   $('loot-yaml').value=revised;draft.config=check;draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));
   $('loot-migration').append(el('span',' Updated base difficulty to +5% per tier.'));
  }
 }
}catch(error){/* Preserve unfinished YAML and custom difficulty curves. */}
// Keep a failed restore message visible until the next user edit.
try{
 if(!localStorage.getItem('ve-loot-set-rewards-v3')){
  const revised=Y.upgradeSetRewards($('loot-yaml').value,context);
  if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));$('loot-migration').append(el('span',' Updated the legendary reward to a random set runestone.'));}
  localStorage.setItem('ve-loot-set-rewards-v3','done');
 }
}catch(error){$('loot-migration').append(el('span',' Could not update earlier reward choices: '+error.message));}
try{
 if(!localStorage.getItem('ve-loot-remove-firewalker-v1')){
  const revised=Y.removeFirewalker($('loot-yaml').value,context);
  if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));$('loot-migration').append(el('span',' Removed Firewalker stone from the reward plan.'));}
  localStorage.setItem('ve-loot-remove-firewalker-v1','done');
 }
}catch(error){$('loot-migration').append(el('span',' Could not remove Firewalker stone from the earlier draft: '+error.message));}
try{
 const revised=Y.expandModifierDifficulty($('loot-yaml').value,context,draft.scenario.effects);
 if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));$('loot-migration').append(el('span',' Listed every tablet modifier individually; existing values were preserved.'));}
}catch(error){/* Preserve unfinished YAML; the existing validation message explains it. */}
try{
 const revised=Y.exposePopulationModifiers($('loot-yaml').value,context);
 if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));$('loot-migration').append(el('span',' Added population ranges and difficultyPer settings. Boss modifiers now use extra counts per eligible wave.'));}
}catch(error){/* Keep unfinished YAML for the user to correct. */}
try{
 if(!localStorage.getItem('ve-loot-add-ancient-shard-v1')){
  const revised=Y.addAncientMaterial($('loot-yaml').value,context,'ShardAncient');
  if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));$('loot-migration').append(el('span',' Added Ancient Shard to common rewards from tier 6.'));}
  localStorage.setItem('ve-loot-add-ancient-shard-v1','done');
 }
}catch(error){$('loot-migration').append(el('span',' Could not add Ancient Shard: '+error.message));}
try{
 if(!localStorage.getItem('ve-loot-reward-unlocks-v1')){
  const revised=Y.repairRewardUnlocks($('loot-yaml').value,context);
  if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));$('loot-migration').append(el('span',' Ancient Runestone (RunestoneAncient) is available from tier 6; Legendary Chisel from tier 4.'));}
  localStorage.setItem('ve-loot-reward-unlocks-v1','done');
 }
}catch(error){$('loot-migration').append(el('span',' Could not update reward unlocks: '+error.message));}
try{
 if(!localStorage.getItem('ve-loot-tiered-sets-v1')){
  const revised=Y.upgradeSetRewards($('loot-yaml').value,context,true);
  if(revised!==$('loot-yaml').value){$('loot-yaml').value=revised;draft.config=Y.parse(revised,context);draft.configYaml=revised;saveYamlText();saveDraft(key,draft,$('loot-save-status'));}
  $('loot-migration').append(el('span',' Set rewards: Legendary at tiers 1–3, Mythic at tiers 4–6, Ancient at tiers 7–15.'));
  localStorage.setItem('ve-loot-tiered-sets-v1','done');
 }
}catch(error){$('loot-migration').append(el('span',' Could not update set reward tiers: '+error.message));}
const restoreError=$('loot-error').textContent;update(false);if(restoreError)$('loot-error').textContent=restoreError;
window.lootWorkbench={get state(){return draft;},get result(){return latest;},context};
})();
