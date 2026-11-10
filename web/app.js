const $ = id => document.getElementById(id);
const node = (tag, text) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
let data, players=[], selected='', generation=0;
const inputs=new Map(), stars=new Map(), overrides={};
const fields=['health_base','health_per_star','damage_base','damage_per_star'];
function playerControls(){
 const area=$('players');area.replaceChildren();
 const menu=node('select');menu.id='character';menu.setAttribute('aria-label','Character');
 for(const p of players){const option=node('option',p.id);option.value=p.id;menu.append(option);}menu.value=selected;
 menu.onchange=()=>{selected=menu.value;playerControls();render();};area.append(node('label','Character '),menu);
 const p=players.find(p=>p.id===selected);if(!p)return;
 const values=inputs.get(selected)||{};inputs.set(selected,values);
 const weapon=node('select');weapon.id='weapon';weapon.setAttribute('aria-label','Weapon');
 const prompt=node('option','Select weapon');prompt.value='';weapon.append(prompt);
 for(const c of p.choices){const o=node('option',c.label);o.value=c.key;weapon.append(o);}weapon.value=values.weapon??p.selectedWeapon;
 weapon.onchange=()=>{values.weapon=weapon.value;render();};area.append(weapon);
 for(const field of ['health','stamina']){const label=node('label','Maximum '+field+' '),n=node('input');n.type='number';n.min='.01';n.step='any';n.id=field;n.value=values[field]??'';n.onchange=()=>{values[field]=Number(n.value);render();};label.append(n);area.append(label);}
}
function profile(){
 const p=players.find(p=>p.id===selected);if(!p)return {missing:['Load an Enforcer character export.']};
 const v=inputs.get(selected)||{},missing=p.missing.slice();
 const choice=p.choices.find(c=>c.key===(v.weapon??p.selectedWeapon));
 if(!choice)missing.push('Select a verified weapon.');
 for(const f of ['health','stamina'])if(!Number.isFinite(v[f])||v[f]<=0)missing.push('Enter maximum '+f+' from the game.');
 if(missing.length)return {missing};
 const result=structuredClone(choice.profile);result.defense.health=v.health;result.stamina.maximum=v.stamina;
 return {missing:[],value:result};
}
async function load(request){
 try{
  const response=await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
  if(!response.ok)throw Error('Import failed. Use YAML files up to 5 MB each, at most 20 per request.');
  const result=await response.json();
  for(const p of result.players){const previous=players.findIndex(x=>x.id.toLowerCase()===p.id.toLowerCase());if(previous>=0){inputs.delete(players[previous].id);players[previous]=p;}else players.push(p);}
  if(!selected&&players.length)selected=players[0].id;
  $('errors').textContent=result.errors.map(e=>e.file+': '+e.message).join(' · ');playerControls();render();
 }catch(e){$('errors').textContent=e.message;}
}
function display(value){return value===null?'Limit':!Number.isFinite(value)?'∞':Number.isInteger(value)?String(value):value.toFixed(1);}
async function render(){
 const stamp=++generation,q=$('search').value.toLowerCase(),list=data.creatures.filter(c=>c.id.toLowerCase().includes(q));
 $('count').textContent=`${list.length} visible / ${data.creatures.length} extracted creatures`;
 const p=profile();$('status').textContent=p.missing.join(' ')||'Calculating…';$('rows').replaceChildren();
 for(const c of list){
  if(stamp!==generation)return;
  const tr=node('tr'),s=stars.get(c.id)||0;tr.dataset.id=c.id;
  const name=node('td',c.id);name.append(node('small',c.biome+' · '+c.role));tr.append(name);
  const cell=node('td'),step=node('div');step.className='stepper';
  const minus=node('button','−'),input=node('input'),plus=node('button','+');input.type='number';input.min=0;input.max=10000;input.step=1;input.value=s;input.setAttribute('aria-label',c.id+' stars');
  const change=value=>{if(!Number.isInteger(value)||value<0||value>10000){$('status').textContent='Stars must be a whole number from 0 to 10000.';input.value=s;return;}stars.set(c.id,value);render();};
  minus.disabled=s===0;plus.disabled=s===10000;minus.setAttribute('aria-label','Decrease '+c.id+' stars');plus.setAttribute('aria-label','Increase '+c.id+' stars');minus.onclick=()=>change(s-1);plus.onclick=()=>change(s+1);input.onchange=()=>change(input.value===''?NaN:Number(input.value));step.append(minus,input,plus);cell.append(step);tr.append(cell);
  tr.append(node('td',fields.map(f=>c.scaling[f]).join(' / ')));
  const resolved=structuredClone(c);Object.assign(resolved.scaling,overrides);
  const hp=c.health*(resolved.scaling.health_base+s*resolved.scaling.health_per_star);tr.append(node('td',display(hp)));
  const ttk=node('td',p.missing.length?'Missing inputs':'…'),htd=node('td',p.missing.length?'Missing inputs':'…');tr.append(ttk,htd);$('rows').append(tr);
  if(!p.missing.length){await new Promise(r=>setTimeout(r,0));if(stamp!==generation)return;const m=BalanceEngine.metrics(resolved,[s,s],[p.value],'before').outcomes[0];ttk.textContent=display(m.ttk[0]);htd.textContent=m.htd[0]===null?'No recorded attack':display(m.htd[0]);}
 }
 if(stamp===generation&&!p.missing.length)$('status').textContent='Ready · 96 repeatable trials per value · SLS before physical conversion';
}
async function start(){
 data=await (await fetch('data.json')).json();
 for(const f of fields){const label=node('label',f.replaceAll('_',' ')+' '),n=node('input');n.type='number';n.min=f.endsWith('base')?'.001':'0';n.step='any';n.id=f;n.placeholder='Per creature';n.onchange=()=>{const v=Number(n.value);if(n.value==='')delete overrides[f];else if(Number.isFinite(v)&&v>=Number(n.min)&&v<=10000)overrides[f]=v;else {n.value=overrides[f]??'';$('status').textContent='Scaling must be within the allowed nonnegative range (base must be positive).';return;}render();};label.append(n);const defaults=[...new Set(data.creatures.map(c=>c.scaling[f]))].sort((a,b)=>a-b);label.append(node('small','Recorded defaults: '+defaults.join(', ')));$('scaling').append(label);}
 $('resetScaling').onclick=()=>{for(const f of fields){delete overrides[f];$(f).value='';}render();};
 $('resetStars').onclick=()=>{stars.clear();render();};$('search').oninput=render;
 $('uploads').onchange=async()=>{const files=Array.from($('uploads').files);if(files.length>20||files.some(f=>f.size>5000000)){$('errors').textContent='Use at most 20 files, up to 5 MB each.';return;}await load({files:await Promise.all(files.map(async f=>({name:f.name,text:await f.text()})))});$('uploads').value='';};
 $('loadPaths').onclick=()=>load({paths:$('paths').value.split('\n').map(x=>x.trim()).filter(Boolean)});
 window.valbalance={get data(){return data;},profile,stars,overrides};render();
}
start().catch(e=>{$('status').textContent='Cannot start workbench: '+e.message;});
