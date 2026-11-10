const labels = {Meadows:'Meadows',BlackForest:'Black Forest',Swamp:'Swamp',Mountain:'Mountain',Plains:'Plains',Mistlands:'Mistlands',AshLands:'Ashlands',DeepNorth:'Deep North',Unassigned:'Unassigned'};
const names = {Greydwarf_Elite:'Greydwarf Brute',Greydwarf_Shaman:'Greydwarf Shaman',Skeleton_Poison:'Rancid Remains',BlobElite:'Oozer',Hatchling:'Drake',Fenring_Cultist:'Cultist',Goblin:'Fuling',GoblinArcher:'Fuling Archer',GoblinShaman:'Fuling Shaman',GoblinBrute:'Fuling Berserker',BlobTar:'Growth',SeekerBrute:'Seeker Soldier',gd_king:'Elder',Dragon:'Moder',GoblinKing:'Yagluth',SeekerQueen:'Queen'};
Object.assign(names,{staff_greenroots_tentaroot:'Tentacle hazard',TentaRoot:'Elder root hazard',SeekerBrood:'Seeker brood / pod hatchling'});
$('role').append(el('option','hazard'));
const key = 've-balance-workbench-v3', cache = new Map();
let tier = 1, generation = 0, currentRows = [];
const initial = {schema:3,revision:DATA.revision,selectedPlayer:DATA.players[0]?.id || '',playerInputs:{},
 creatures:Object.fromEntries(DATA.creatures.map(c => [c.id,{enabled:c.enabled,tiers:clone(c.tiers),notes:c.review}]))};
let state = clone(initial);
function validState(candidate) {
 if (!candidate || candidate.schema!==3 || !candidate.creatures) throw Error('Expected a schema-3 workbench review JSON file.');
 const records=Object.entries(candidate.creatures).filter(([id])=>!Object.hasOwn(DATA.excludedPrefabs || {},id));
 if (!records.length || records.length!==DATA.creatures.length) throw Error('Review does not contain the current full creature catalog.');
 const merged = clone(initial);
 for (const [id,r] of records) {
  if (!Object.hasOwn(merged.creatures,id)) throw Error('Unknown creature: '+id);
  if (typeof r.enabled !== 'boolean' || typeof r.notes !== 'string' || r.notes.length > 10000 || !r.tiers || Object.keys(r.tiers).length !== 15) throw Error('Invalid review for '+id);
  for (let t=1;t<=15;t++) {const a=r.tiers[t];if (!Array.isArray(a) || a.length!==2 || a.some(v=>!Number.isInteger(v)||v<0||v>10000) || a[0]>a[1]) throw Error('Invalid stars for '+id+' tier '+t);}
  merged.creatures[id]=clone(r);
  if(DATA.creatures.find(c=>c.id===id).role==='hazard')merged.creatures[id].enabled=true;
  if(r.tiers[1][1]>9958)throw Error('Tier 1 maximum must be at most 9958: '+id);
  for(let t=1;t<=15;t++) {
   const expected=r.tiers[1].map(v=>v+3*(t-1));
   if(JSON.stringify(r.tiers[t])!==JSON.stringify(expected))throw Error('Higher tiers must follow Tier 1 plus 3 stars per tier: '+id);
   merged.creatures[id].tiers[t]=expected;
  }
 }
 if (typeof candidate.selectedPlayer==='string') merged.selectedPlayer=candidate.selectedPlayer;
 if (candidate.playerInputs && typeof candidate.playerInputs==='object' && !Array.isArray(candidate.playerInputs)) merged.playerInputs=clone(candidate.playerInputs);
 return merged;
}
state=restoreDraft(key,initial,validState,$('status'));
if (!DATA.players.some(p=>p.id===state.selectedPlayer)) state.selectedPlayer=DATA.players[0]?.id || '';
function save() {
 saveDraft(key,state,$('saveStatus'));
}
function rangeText(a,seconds=false) {if(a.some(x=>x===null))return seconds?'Limit':'—';if(a.some(x=>!Number.isFinite(x)))return '∞';const v=a.slice().sort((a,b)=>a-b).map(x=>seconds?x.toFixed(1):Math.round(x).toLocaleString());return(v[0]===v[1]?v[0]:v.join('–'))+(seconds?' s':'');}
function selected() {return DATA.players.find(p=>p.id===state.selectedPlayer);}
function playerResult() {
 const p=selected();if(!p)return {missing:['No player loaded. Place exports in Balance/player-imports and run the import command.']};
 if(!p.imported)return {profile:p,missing:[]};
 const inputs=state.playerInputs[p.id] || {}, weapon=inputs.weapon ?? p.selectedWeapon;
 const choice=p.choices.find(c=>c.key===weapon), missing=p.missing.slice();
 if(!choice)missing.push('Select a supported weapon from this export.');
 for(const field of ['health','stamina'])if(!Number.isFinite(inputs[field])||inputs[field]<=0)missing.push('Enter current maximum '+field+' from the game.');
 if(missing.length)return {missing};
 const profile=clone(choice.profile);profile.defense.health=inputs.health;profile.stamina.maximum=inputs.stamina;
 return {profile,missing:[]};
}
function getMetric(c,range) {
 const result=playerResult();
 if(result.missing.length)return {health:range.map(s=>c.health*(c.scaling.health_base+s*c.scaling.health_per_star)),outcomes:[],missing:result.missing};
 const k=JSON.stringify([c.id,range,result.profile]);
 if(!cache.has(k))cache.set(k,BalanceEngine.metrics(c,range,[result.profile],'before'));
 return cache.get(k);
}
function playerControls() {
 const area=$('players');area.replaceChildren();
 const select=el('select');select.id='playerSelect';select.setAttribute('aria-label','Player');
 for(const p of DATA.players){const o=el('option',p.id);o.value=p.id;select.append(o);}select.value=state.selectedPlayer;
 select.onchange=()=>{state.selectedPlayer=select.value;save();playerControls();render();};area.append(el('label','Player '),select);
 const p=selected();if(!p)return;
 if(p.imported) {
  const inputs=state.playerInputs[p.id] ||= {};
  const weapon=el('select');weapon.id='weaponSelect';weapon.setAttribute('aria-label','Comparison weapon');
  const prompt=el('option','Select comparison weapon');prompt.value='';weapon.append(prompt);
  for(const c of p.choices){const o=el('option',c.label+(c.equipped?' · equipped':''));o.value=c.key;weapon.append(o);}
  weapon.value=inputs.weapon ?? p.selectedWeapon;weapon.onchange=()=>{inputs.weapon=weapon.value;cache.clear();save();render();};area.append(weapon);
  for(const field of ['health','stamina']) {
   const label=el('label','Maximum '+field+' '),input=el('input');input.type='number';input.min='.01';input.step='any';input.id='player-'+field;input.style.width='110px';input.value=inputs[field] ?? '';
   input.onchange=()=>{inputs[field]=input.value===''?null:Number(input.value);cache.clear();save();render();};label.append(input);area.append(label);
  }
  area.append(el('small','Source: '+p.source.file+' · modified '+p.source.modified+' · imported '+DATA.builtAt));
  area.append(el('small','Health and stamina require game values. Weapon damage and timing use verified source references. Native resistance scenario: fire/frost meads 0.5, poison mead 0.25, spirit 0; Epic Loot resistance cap 50%; rested stamina regeneration. See Player inputs & assumptions.'));
 } else area.append(el('small',p.weapon+' · saved reference scenario · '+p.defense.health.toFixed(1)+' HP · '+p.defense.armor.toFixed(1)+' armor'));
}
function filtered() {
 const q=$('search').value.trim().toLowerCase();
 return DATA.creatures.filter(c=>($('showExcluded').checked||state.creatures[c.id].enabled)&&($('biome').value==='All'||c.biome===$('biome').value)&&($('role').value==='All'||c.role===$('role').value)&&(!q||(c.id+' '+(names[c.id]||'')).toLowerCase().includes(q)));
}
function changeRange(c,range) {
 if(tier!==1)return;
 if(range.some(v=>!Number.isInteger(v)||v<0||v>9958)||range[0]>range[1]){$('status').textContent='Use whole Tier 1 stars from 0 to 9958. Minimum cannot exceed maximum.';return;}
 for(let t=1;t<=15;t++)state.creatures[c.id].tiers[t]=range.map(v=>v+3*(t-1));save();render();
}
async function render() {
 const stamp=++generation,list=filtered();currentRows=list;$('rows').replaceChildren();
 const excluded=DATA.creatures.filter(c=>!state.creatures[c.id].enabled).length;
 $('count').textContent=list.length+' visible / '+DATA.creatures.length+' total · '+excluded+' excluded';
 $('tierNote').textContent='Edit Tier 1. Each higher tier adds 3 stars to both bounds. Imported older reviews use only their Tier 1 ranges.';
 $('reset').disabled=tier!==1;
 document.querySelectorAll('#tiers button').forEach(b=>b.classList.toggle('selected',Number(b.textContent)===tier));
 $('status').textContent='Calculating…';const pending=[];
 for(const c of list) {
  const r=state.creatures[c.id],stars=r.tiers[tier],tr=el('tr');tr.dataset.id=c.id;
  tr.className=!r.enabled?'disabled':JSON.stringify(stars)!==JSON.stringify(c.tiers[tier])?'changed':'';
  const nameCell=el('td'),name=el('button',names[c.id]||c.id,'name');name.onclick=()=>details(c);
  nameCell.append(name,el('small',(labels[c.biome]||c.biome)+' · '+c.role+' · '+(r.enabled?'Included':'Excluded')));if(!c.configuredTiers.includes(tier))nameCell.append(el('small','No configured range at this tier · draft starts at 0'));tr.append(nameCell);
  const control=el('td'),stepper=el('div',undefined,'stepper'),minus=el('button','−'),plus=el('button','+');
  minus.setAttribute('aria-label','Decrease '+c.id+' stars');plus.setAttribute('aria-label','Increase '+c.id+' stars');minus.disabled=tier!==1||stars[0]===0;plus.disabled=tier!==1||stars[1]===9958;
  minus.onclick=()=>{const d=Math.min(Number($('step').value),stars[0]);changeRange(c,stars.map(x=>x-d));};plus.onclick=()=>{const d=Math.min(Number($('step').value),9958-stars[1]);changeRange(c,stars.map(x=>x+d));};stepper.append(minus);
  stars.forEach((value,index)=>{if(index)stepper.append(el('span','–'));const input=el('input');input.type='number';input.min=0;input.max=tier===1?9958:10000;input.value=value;input.readOnly=tier!==1;input.setAttribute('aria-label',c.id+(index?' maximum':' minimum')+' stars');input.onchange=()=>{const a=stars.slice();a[index]=input.value===''?NaN:Number(input.value);changeRange(c,a);};stepper.append(input);});stepper.append(plus);control.append(stepper);
  control.append(el('small',tier===1?'Tier 1 baseline':'Derived from Tier 1 + '+(3*(tier-1))+' stars'));tr.append(control);
  const cells=Array.from({length:3},()=>el('td','…','num'));cells.forEach(td=>tr.append(td));
  const review=el('td'),button=el('button',r.notes?'Notes':'Add note');button.onclick=()=>details(c);review.append(button);tr.append(review);$('rows').append(tr);pending.push({c,stars,cells});
 }
 for(const {c,stars,cells} of pending) {
  await new Promise(resolve=>setTimeout(resolve,0));if(stamp!==generation)return;
  const m=getMetric(c,stars);cells[0].textContent=rangeText(m.health);
  if(m.outcomes.length){cells[1].textContent=rangeText(m.outcomes[0].ttk,true);cells[2].textContent=rangeText(m.outcomes[0].htd);}
  else {cells[1].textContent='Missing inputs';cells[2].textContent='Missing inputs';}
 }
 if(stamp===generation){const missing=playerResult().missing;$('status').textContent=missing.length?missing.join(' '):'Ready · planning estimates · 96 repeatable simulations per endpoint · SLS before conversion';}
}
function details(c) {
 const r=state.creatures[c.id],m=getMetric(c,r.tiers[tier]),body=$('detailBody');$('detailTitle').textContent=(names[c.id]||c.id)+' · Tier '+tier;body.replaceChildren();
 body.append(el('p','Prefab: '+c.id+' · Base health: '+c.health));if(c.warning)body.append(el('p',c.warning,'pending'));
 if(c.role==='hazard')body.append(el('p','Hazard star settings apply when the tablet enables this hazard. These creatures are not selected for random waves.'));
 else {const toggle=el('label'),check=el('input');check.type='checkbox';check.checked=r.enabled;check.onchange=()=>{r.enabled=check.checked;save();render();};toggle.append(check,document.createTextNode(' Include in all tiers'));body.append(toggle);}
 const notes=el('textarea');notes.value=r.notes;notes.setAttribute('aria-label','Review notes for '+c.id);notes.onchange=()=>{r.notes=notes.value;save();render();};body.append(el('p','Review notes'),notes);
 body.append(el('h2','Effective star scaling'),el('p','Health = base health × (health base + stars × health per star). Weapon attack damage = payload × (damage base + stars × damage per star). Independent area damage uses its own payload.'),el('pre',JSON.stringify({effective:c.scaling,nativeBoss:c.nativeBoss,creatureOverrides:c.scalingOverrides},null,2)));
 body.append(el('p','These are the resolved SLS values after biome, boss and creature overrides. Physical room biome: Mistlands. Incoming damage modifiers and required creature modifiers are included in the values above.'));
 if(m.outcomes.length) {
  const table=el('table'),head=el('tr');['Attack','Stars','Raw damage','Received','Hits to die'].forEach(t=>head.append(el('th',t)));table.append(head);
  for(let endpoint=0;endpoint<2;endpoint++){if(endpoint&&r.tiers[tier][0]===r.tiers[tier][1])continue;for(const a of m.outcomes[0].attacks[endpoint]){const row=el('tr');[a.name,r.tiers[tier][endpoint],a.raw.toFixed(1),a.received.toFixed(1),a.htd].forEach(v=>row.append(el('td',v)));table.append(row);}}
  body.append(el('p','The table result uses the attack with the lowest hits to die. Area contacts remain separate.'),table);
 } else body.append(el('p',m.missing.join(' '),'error'));
 body.append(el('h2','All tier ranges'),el('pre',JSON.stringify(r.tiers,null,2)),el('h2','Attack source inputs'),el('pre',JSON.stringify(c.attacks,null,2)));$('detail').showModal();
}
bindReview({exportButton:$('export'),importButton:$('import'),file:$('file'),status:$('status'),filename:'valheim-endgame-balance-review.json',getState:()=>({...state,inputHashes:DATA.hashes}),accept:candidate=>{state=validState(candidate);if(!DATA.players.some(p=>p.id===state.selectedPlayer))state.selectedPlayer=DATA.players[0]?.id||'';cache.clear();save();playerControls();render();}});
$('csv').onclick=()=>{const lines=[['Tier','Player','Biome','Prefab','Role','Included','Min stars','Max stars','Health','TTK seconds','HTD','Notes']];for(const c of currentRows){const r=state.creatures[c.id],m=getMetric(c,r.tiers[tier]),o=m.outcomes[0];lines.push([tier,state.selectedPlayer,c.biome,c.id,c.role,r.enabled,...r.tiers[tier],rangeText(m.health),o?rangeText(o.ttk,true):'Missing inputs',o?rangeText(o.htd):'Missing inputs',r.notes]);}csvDownload('tier-'+tier+'-balance.csv',lines);};
$('reset').onclick=()=>{if(tier!==1||!confirm('Reset all Tier 1 baselines and their derived ranges? Notes, exclusions and player inputs stay.'))return;for(const c of DATA.creatures)state.creatures[c.id].tiers=clone(c.tiers);save();render();};
$('assumptions').onclick=()=>{
 $('detailTitle').textContent='Player inputs & calculation limits';const body=$('detailBody');body.replaceChildren();
 for(const text of [
  'These are planning estimates. Time to kill uses 96 repeatable trials with primary attacks, no misses, stagger, backstab, movement, healing or temporary buffs. Nominal animation timing and stamina pauses are included. The simulation ends after 30 minutes or 10,000 attacks.',
  'Hits to die starts at full health. It excludes blocking, dodge, healing and protective shields. Each damage-over-time payload finishes between hits. This is not sustained survival time. Volleys, summons and repeated environmental contacts are not combined into one hit.',
  'SLS uses the recorded production configuration from 2026-10-17 and physical room biome Mistlands. World difficulty factors are 1. Random modifiers and tablet enchantments are excluded. SLS before physical conversion is the selected patch order assumption; live patch order has not been revalidated.',
  'Imported equipment supplies item quality, skills, Epic Loot effects, coins and verified Deep North armor values. Only the spear and greatsword in the saved source references have verified weapon payload and animation inputs. Unknown armor or weapons require source verification before results are available.',
  'Imported maximum health and maximum stamina are entered from the game. Assumptions: rested stamina regeneration, fire/frost meads 0.5, poison mead 0.25, spirit immunity 0, resistance cap 50%, low-health armor threshold 75%. These are visible model scenarios, not facts from the export.',
  'Place raw exports in Balance/player-imports. Run python3 Balance/build_workbench.py --imports. Reopen workbench.local.html to refresh players. Browser drafts keep creature edits, player selection and health/stamina entries. Update runtime values when food changes.',
  'Export review saves all tiers, notes and inclusion state. Preview a config update with python3 Balance/apply_workbench_review.py REVIEW.json. Add --write to apply it locally. Review the config diff and validate in game before deployment.'
 ])body.append(el('p',text));
 const p=selected();if(p)body.append(el('h2',p.id),el('pre',JSON.stringify({source:p.source,missing:playerResult().missing,inputs:playerResult().profile},null,2)));
 body.append(el('h2','Global progression and SLS defaults'),el('pre',JSON.stringify({progression:DATA.progression,settings:DATA.scalingRules},null,2)),el('h2','Source fingerprints'),el('pre',JSON.stringify(DATA.hashes,null,2)));$('detail').showModal();
};
$('closeDetail').onclick=()=>$('detail').close();
for(let i=DATA.progression.minimum_tier;i<=DATA.progression.maximum_tier;i++){const button=el('button',String(i));button.setAttribute('aria-label','Tier '+i);button.onclick=()=>{tier=i;render();};$('tiers').append(button);}
Object.entries(labels).forEach(([value,label])=>{const option=el('option',label);option.value=value;$('biome').append(option);});$('biome').value='All';$('showExcluded').checked=true;
['biome','role','showExcluded'].forEach(id=>$(id).onchange=render);$('search').oninput=render;
for(const error of DATA.importErrors){const row=el('p',error.file+': '+error.message,'error');$('importErrors').append(row);}
playerControls();window.workbench={DATA,get state(){return state;},get tier(){return tier;},validState,metrics:getMetric,playerResult};render();
