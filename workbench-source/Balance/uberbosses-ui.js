/* Uber bosses tab: edits Balance/uberbosses.json, the source of truth for Uber boss balance. */
(function uberBosses() {
 const KEY='ve-uberbosses-v1', status=$('uber-save-status'), error=$('uber-error');
 const LABELS={interval:['Interval','s'],rangeMin:['Range min','m'],rangeMax:['Range max','m'],blunt:['Blunt'],pierce:['Pierce'],slash:['Slash'],fire:['Fire'],frost:['Frost'],lightning:['Lightning'],poison:['Poison'],
  radius:['Radius','m'],force:['Knockback'],duration:['Duration','s'],speed:['Speed','m/s'],hitboxLightning:['Hitbox lightning'],hitboxBlunt:['Hitbox blunt'],hitboxTick:['Hitbox tick','s'],hitboxForce:['Hitbox knockback'],hitboxWidth:['Hitbox width','m'],hitboxLength:['Hitbox length','m'],
  trailSpacing:['Trail spacing','m'],trailLightning:['Trail lightning'],trailRadius:['Trail radius','m'],strikes:['Strikes'],spacing:['Spacing','m'],strikeDelay:['Delay per strike','s'],ballsPerPlayer:['Balls per player'],spread:['Spread','m'],warning:['Warning','s'],ballDelay:['Delay per ball','s'],
  hold:['Hold','s'],explosionLightning:['Explosion lightning'],explosionBlunt:['Explosion blunt'],explosionRadius:['Explosion radius','m'],explosionForce:['Explosion knockback'],rings:['Rings'],ringSpacing:['Ring spacing','m'],ringDelay:['Delay per ring','s'],pointBlunt:['Point blunt'],pointFrost:['Point frost'],pointRadius:['Point radius','m'],pointForce:['Point knockback'],
  launchMin:['Launch min'],launchMax:['Launch max'],roots:['Roots'],maxAlive:['Max alive'],blobs:['Blobs'],oozers:['Oozers'],ringRadius:['Ring radius','m'],fieldFrost:['Field frost per tick'],fieldTick:['Field tick','s'],fieldDuration:['Field duration','s'],fieldForce:['Field knockback'],fieldWidth:['Field width','m'],fieldLength:['Field length','m'],
  shardsPerPlayer:['Shards per player'],shardDelay:['Delay per shard','s'],impactBlunt:['Impact blunt'],impactFrost:['Impact frost'],impactRadius:['Impact radius','m'],bolts:['Bolts'],boltInterval:['Bolt interval','s'],turnRate:['Turn rate','°/s'],ringBlunt:['Ring blunt'],ringForce:['Ring knockback'],
  health:['Health'],keepDistance:['Keep distance','m'],boltFire:['Bolt fire'],boltLightning:['Bolt lightning'],boltForce:['Bolt knockback'],poolPoison:['Pool poison per tick'],poolTick:['Pool tick','s'],poolDuration:['Pool duration','s'],poolRadius:['Pool radius','m'],
  thorns:['Thorns'],thornSpread:['Thorn spread','m'],thornWarning:['Thorn warning','s'],thornPierce:['Thorn pierce'],thornRadius:['Thorn radius','m'],thornForce:['Thorn knockback'],slowSeconds:['Slow','s'],slowPercent:['Slow','%'],fissures:['Fissures'],pillarsMin:['Pillars per fissure, min'],pillarsMax:['Pillars per fissure, max'],pools:['Pools'],poolFire:['Pool fire per tick']};
 const KINDS={vanilla:'Vanilla',replaced:'Replaced',new:'New'};
 const initial=DATA.uberBosses;
 function validate(raw) {
  if(!raw||raw.schema!==1||!Array.isArray(raw.bosses))throw Error('Not an uberbosses.json file (schema 1).');
  const state=clone(initial);
  for(const boss of state.bosses) {
   const source=raw.bosses.find(b=>b.id===boss.id);if(!source)continue;
   for(const key of Object.keys(boss.settings))if(source.settings&&key in source.settings)boss.settings[key]=source.settings[key];
   for(const attack of boss.attacks) {
    const sourceAttack=(source.attacks||[]).find(a=>a.id===attack.id);if(!sourceAttack||attack.kind==='vanilla')continue;
    for(const key of Object.keys(attack.fields))if(sourceAttack.fields&&typeof sourceAttack.fields[key]==='number')attack.fields[key]=sourceAttack.fields[key];
   }
  }
  return state;
 }
 let state=restoreDraft(KEY,initial,validate,status);
 const bossSelect=$('uber-boss');
 for(const boss of initial.bosses)bossSelect.append(Object.assign(el('option',boss.name),{value:boss.id}));
 bossSelect.onchange=render;$('uber-kind').onchange=render;
 const playerSelect=$('uber-player'),starsInput=$('uber-stars');
 for(const player of DATA.players)playerSelect.append(Object.assign(el('option',player.id),{value:player.id}));
 playerSelect.value=DATA.players.some(p=>p.id==='Snuffiss')?'Snuffiss':(DATA.players[0]?.id||'');
 starsInput.value=Math.min(...Object.values(DATA.uberCombat).map(c=>c.stars[0]));
 playerSelect.onchange=render;starsInput.onchange=render;
 const summaryCache=new Map();
 function player(){const p=DATA.players.find(p=>p.id===playerSelect.value);return p&&!p.imported?p:null;}
 function stars(){const v=Math.round(Number(starsInput.value));return Number.isFinite(v)&&v>=0?v:0;}
 const num=v=>Number.isFinite(v)?(Math.abs(v)>=100?Math.round(v).toLocaleString():(Math.round(v*10)/10).toLocaleString()):'∞';
 function damageText(damage){return Object.entries(damage).filter(([,v])=>v>0).map(([t,v])=>num(v)+' '+t).join(' + ')||'0';}
 function cell(value,onChange,wide){
  const input=el('input','',wide?'uber-cell uber-cell-wide':'uber-cell');input.type='number';input.step='any';input.min='0';input.value=value;
  input.onchange=()=>{const v=Number(input.value);if(!Number.isFinite(v)||v<0){input.value=value;return;}onChange(v);saveDraft(KEY,state,status);render();};
  return input;
 }
 function renderThreat(boss){
  const profile=player(),summary=$('uber-summary'),hits=$('uber-hits'),note=$('uber-player-note');summary.replaceChildren();hits.replaceChildren();
  if(!profile){note.textContent='Select a saved player profile. Imported exports need the Creature balance tab inputs.';$('uber-threat-status').textContent='';return;}
  note.textContent=profile.weapon+' · '+profile.defense.health.toFixed(0)+' HP · '+profile.defense.armor.toFixed(0)+' armor';
  const s=stars();
  for(const each of state.bosses){
   const combat=DATA.uberCombat[each.id],key=JSON.stringify([each.id,s,profile.id,each.settings.health,each.attacks]);
   if(!summaryCache.has(key))summaryCache.set(key,UberHits.summary(each,combat,profile,s,96));
   const m=summaryCache.get(key),row=el('tr');if(each.id===boss.id)row.className='changed';
   const d=m.deadliest,name=el('td',each.name);name.append(el('small','Vanilla '+combat.source+' has '+num(combat.health)));row.append(name);
   const base=el('td',undefined,'num');base.append(cell(UberHits.baseHealth(each,combat),v=>{each.settings.health=v;},true));row.append(base);
   [num(m.health),m.ttk===null?'Limit':m.ttk.toFixed(1)+' s',d?d.attack.name+' · '+d.part.label:'—',d?num(d.received):'—',d?num(d.htd):'—'].forEach(v=>row.append(el('td',v,'num')));
   summary.append(row);
  }
  for(const r of UberHits.rows(boss,DATA.uberCombat[boss.id],profile,s)){
   const row=el('tr'),name=el('td',r.attack.name);name.append(el('small',KINDS[r.attack.kind]+' · '+r.attack.id));row.append(name);
   if(!r.part){const empty=el('td',r.note,'muted');empty.colSpan=7;row.append(empty);hits.append(row);continue;}
   const hit=el('td',r.part.label);if(r.note)hit.append(el('small',r.note));row.append(hit);
   const damage=el('td',undefined,'num');
   for(const [type,ref] of Object.entries(r.part.damage)){
    const line=el('div');
    if(r.editable&&typeof ref==='string')line.append(cell(r.attack.fields[ref],v=>{r.attack.fields[ref]=v;}),el('span',' '+type,'uber-types'));
    else line.append(el('span',num(r.damage[type])+' '+type,'uber-types'));
    damage.append(line);
   }
   if(Object.keys(r.part.damage).length>1)damage.append(el('small',num(r.raw)+' total'));row.append(damage);
   const count=el('td',undefined,'num'),h=r.part.hits;
   if(r.editable&&typeof h==='string')count.append(cell(r.attack.fields[h],v=>{r.attack.fields[h]=Math.round(v);}));
   else if(r.editable&&typeof h==='object'){count.append(el('span',num(r.hits)+' ticks'));const line=el('div');line.append(cell(r.attack.fields[h.duration],v=>{r.attack.fields[h.duration]=v;}),el('span',' s / ','uber-types'),cell(r.attack.fields[h.tick],v=>{r.attack.fields[h.tick]=v;}),el('span',' s tick','uber-types'));count.append(line);}
   else count.textContent=num(r.hits);
   row.append(count);
   [num(r.volley),num(r.received),num(r.htd)].forEach(v=>row.append(el('td',v,'num')));
   row.append(el('td',r.volleyKills?'Yes':'No',r.volleyKills?'uber-kill':'muted'));hits.append(row);
  }
  $('uber-threat-status').textContent='Stars '+s+' · room biome Mistlands · SLS before conversion';
 }
 function label(key){const l=LABELS[key]||[key.replace(/([A-Z])/g,' $1').replace(/^./,c=>c.toUpperCase())];return l[1]?l[0]+' ('+l[1]+')':l[0];}
 function settingLabel(key){return key.replace(/([A-Z])/g,' $1').replace(/^./,c=>c.toUpperCase());}
 function numberInput(value,onChange,step) {
  const input=el('input');input.type='number';input.step=step||'any';input.value=value;input.className='uber-input';
  input.onchange=()=>{const v=Number(input.value);if(!Number.isFinite(v)){input.value=value;return;}onChange(v);saveDraft(KEY,state,status);renderThreat(state.bosses.find(b=>b.id===bossSelect.value)||state.bosses[0]);};
  return input;
 }
 function listInput(values,onChange) {
  const input=el('input');input.type='text';input.value=values.join(', ');input.className='uber-input uber-list';
  input.onchange=()=>{const parsed=input.value.split(',').map(s=>Number(s.trim())).filter(Number.isFinite);if(!parsed.length){input.value=values.join(', ');return;}onChange(parsed);saveDraft(KEY,state,status);};
  return input;
 }
 function render() {
  error.textContent='';
  const boss=state.bosses.find(b=>b.id===bossSelect.value)||state.bosses[0];
  const settings=$('uber-settings');settings.replaceChildren(el('h2','Encounter settings · '+boss.name));
  const grid=el('div',undefined,'uber-grid');
  for(const [key,value] of Object.entries(boss.settings)) {
   const field=el('label',undefined,'uber-field');field.append(el('span',settingLabel(key)));
   field.append(Array.isArray(value)?listInput(value,v=>{boss.settings[key]=v;}):numberInput(value,v=>{boss.settings[key]=v;}));grid.append(field);
  }
  settings.append(grid,el('p','These values are written to Config/encounters.yaml by apply_uberbosses.py.','muted'));
  const container=$('uber-attacks');container.replaceChildren();
  const showAll=$('uber-kind').value==='all';let shown=0;
  for(const attack of boss.attacks) {
   if(!showAll&&attack.kind==='vanilla')continue;shown++;
   const panel=el('div',undefined,'panel uber-attack');
   const head=el('div',undefined,'actions');head.append(el('h3',attack.name),el('span',KINDS[attack.kind]+' · '+attack.id,'right muted'));panel.append(head);
   const fields=el('div',undefined,'uber-grid');
   for(const [key,value] of Object.entries(attack.fields)) {
    const field=el('label',undefined,'uber-field');field.append(el('span',label(key)));
    if(attack.kind==='vanilla'){const fixed=el('output',String(value),'uber-fixed');field.append(fixed);}
    else field.append(numberInput(value,v=>{attack.fields[key]=v;}));
    fields.append(field);
   }
   panel.append(fields);
   if(attack.kind==='vanilla')panel.append(el('p','Vanilla weapon, unchanged by the mod. Shown so the whole kit can be read together.','muted'));
   container.append(panel);
  }
  $('uber-count').textContent=shown+' of '+boss.attacks.length+' attacks';
  renderThreat(boss);
 }
 bindReview({exportButton:$('uber-export'),importButton:$('uber-import'),file:$('uber-file'),status:error,filename:'uberbosses.json',
  getState:()=>({schema:1,note:initial.note,bosses:state.bosses}),accept:raw=>{state=validate(raw);saveDraft(KEY,state,status);render();}});
 $('uber-reset').onclick=()=>{state=clone(initial);saveDraft(KEY,state,status);render();};
 $('uber-csv').onclick=()=>{const rows=[['Boss','Attack','Kind','Field','Value']];for(const boss of state.bosses){for(const [k,v] of Object.entries(boss.settings))rows.push([boss.name,'(settings)','setting',k,Array.isArray(v)?v.join(' '):v]);for(const a of boss.attacks)for(const [k,v] of Object.entries(a.fields))rows.push([boss.name,a.name,a.kind,k,v]);}csvDownload('uberbosses.csv',rows);};
 render();
})();
