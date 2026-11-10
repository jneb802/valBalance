/* Validated YAML and portable reviews for the difficulty-based planner. */
(function(root) {
'use strict';
const node=typeof module!=='undefined'&&module.exports;
const yaml=node?require('./vendor/js-yaml-4.3.0.min.js'):root.jsyaml;
const engine=node?require('./loot.js'):root.LootEngine;
function parse(text,context) {
 if(typeof text!=='string'||text.length>1000000)throw Error('Reward YAML must be text no larger than 1 MB.');
 const data=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30});
 let count=0;const path=new Set();
 function check(value) {
  if(++count>100000)throw Error('Reward YAML contains too many values.');
  if(!value||typeof value!=='object')return;
  if(path.has(value))throw Error('Reward YAML cannot contain circular aliases.');
  path.add(value);for(const child of Object.values(value))check(child);path.delete(value);
 }
 check(data);
 if(!data||Array.isArray(data)||typeof data!=='object')throw Error('Enter a reward configuration with rules, items and rarities.');
 if(!Array.isArray(data.items)||!Array.isArray(data.rarities)||!data.rules)throw Error('Reward YAML requires rules, items and rarities.');
 return engine.validate(engine.normalize(data,context),context);
}
function canonical(value) {
 if(Array.isArray(value))return value.map(canonical);
 if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])]));
 return value;
}
function equal(a,b){return JSON.stringify(canonical(a))===JSON.stringify(canonical(b));}
function review(raw,context) {
 const result=engine.review(raw,context);
 if(raw.configYaml!==undefined) {
  const parsed=parse(raw.configYaml,context);
  if(!equal(parsed,result.config))throw Error('The review YAML does not match its reward settings. Export the review again.');
  if((raw.configYaml.includes('randomLegendarySetItem')||raw.configYaml.includes('enchantment')))result.configYaml=upgradeSetRewards(raw.configYaml,context);
 }else result.configYaml=context.configYaml&&equal(result.config,engine.normalize(context.config,context))?context.configYaml:yaml.dump(result.config,{lineWidth:100,noRefs:true,schema:yaml.JSON_SCHEMA});
 return result;
}
function upgradeSetRewards(text,context,unlockAllTiers=false){
 parse(text,context);
 const nodes=[],stack=[];
 const data=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30,listener:(event,state)=>{
  if(event==='open')stack.push(state.position);
  else{const start=stack.pop();if(state.kind==='mapping')nodes.push({start,end:state.position,value:state.result});}
 }});
 const changed=new Set();
 for(const i of data.items)if(i.enchantment===null){delete i.enchantment;changed.add(i);}
 for(const i of data.items)if(Object.hasOwn(i,'randomLegendarySetItem')){
  if(i.randomLegendarySetItem){
   i.randomLegendarySetRune=true;
   if(i.id==='random-legendary-set-item'){
    i.id='random-legendary-set-runestone';
    for(const r of data.rarities)for(const e of r.entries)if(e.item==='random-legendary-set-item'){e.item=i.id;changed.add(e);}
   }
  }
  delete i.randomLegendarySetItem;changed.add(i);
 }
 for(const i of data.items)if(i.prefab==='RunestoneAncient'&&(i.minTier??1)<6){i.minTier=6;changed.add(i);}
 if(unlockAllTiers)for(const i of data.items)if(i.randomLegendarySetRune&&((i.minTier??1)!==1||(i.maxTier??15)!==15)){
  i.minTier=1;i.maxTier=15;changed.add(i);
 }
 if(!changed.size)return text;
 const expected=engine.validate(engine.normalize(data,context),context),edits=new Map();
 for(const n of nodes)if(changed.has(n.value))edits.set(n.start,n);
 for(const n of [...edits.values()].sort((a,b)=>b.start-a.start)){
  const source=text.slice(n.start,n.end),trailing=source.match(/\s*$/)[0];
  text=text.slice(0,n.start)+yaml.dump(n.value,{flowLevel:0,lineWidth:-1,noRefs:true}).trimEnd()+trailing+text.slice(n.end);
 }
 if(!equal(parse(text,context),expected))throw Error('Update the set runestone entries manually in the YAML.');
 return text;
}
function removeFirewalker(text,context){
 parse(text,context);
 const nodes=[],stack=[];
 const data=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30,listener:(event,state)=>{
  if(event==='open')stack.push(state.position);
  else{const start=stack.pop();if(state.kind==='sequence')nodes.push({start,end:state.position,value:state.result});}
 }});
 const ids=new Set(data.items.filter(i=>i.id==='firewalker-stone'||i.prefab==='Firewalker_Epic_ShardStone').map(i=>i.id));
 if(!ids.size)return text;
 const changed=new Set();
 function remove(list,predicate){for(let k=list.length-1;k>=0;k--)if(predicate(list[k])){list.splice(k,1);changed.add(list);}}
 remove(data.items,i=>ids.has(i.id));for(const r of data.rarities)remove(r.entries,e=>ids.has(e.item));
 const expected=engine.validate(engine.normalize(data,context),context),edits=new Map();
 for(const n of nodes)if(changed.has(n.value))edits.set(n.start,n);
 for(const n of [...edits.values()].sort((a,b)=>b.start-a.start)){
  const source=text.slice(n.start,n.end),leading=source.match(/^\s*/)[0],trailing=source.match(/\s*$/)[0];
  const flow=source.trimStart().startsWith('['),position=n.start+leading.length,indent=' '.repeat(position-text.lastIndexOf('\n',position-1)-1);
  const replacement=yaml.dump(n.value,{flowLevel:flow?0:-1,lineWidth:-1,noRefs:true}).trimEnd();
  text=text.slice(0,n.start)+leading+(flow?replacement:replacement.replaceAll('\n','\n'+indent))+trailing+text.slice(n.end);
 }
 if(!equal(parse(text,context),expected))throw Error('Remove the Firewalker item and its table references in the YAML.');
 return text;
}
function expandModifierDifficulty(text,context,effects=[]){
 const c=parse(text,context),labels=new Map(context.modifiers.map(m=>[m.id,m.label+(m.noRoll?' (excluded from random generation)':'')]));
 for(const e of effects)if(!labels.has(e.id))labels.set(e.id,e.id);
 let changed=false;
 for(const id of labels.keys())if(!Object.hasOwn(c.rules.modifierDifficulty,id)){c.rules.modifierDifficulty[id]=c.rules.categoryDifficulty[engine.category(id)];changed=true;}
 if(!changed)return text;
 const nodes=[],stack=[];
 const raw=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30,listener:(event,state)=>{
  if(event==='open')stack.push(state.position);
  else{const start=stack.pop();if(state.kind==='mapping')nodes.push({start,end:state.position,value:state.result});}
 }});
 const node=nodes.find(n=>n.value===raw.rules.modifierDifficulty);
 if(!node)throw Error('Could not locate modifierDifficulty in the YAML.');
 const source=text.slice(node.start,node.end),leading=source.match(/^\s*/)[0],trailing=source.match(/\s*$/)[0];
 const rows=Object.entries(c.rules.modifierDifficulty).map(([id,value])=>'    '+yaml.dump(id).trim()+': '+value+',  # '+(labels.get(id)||'Custom modifier').replace(/[\r\n]/g,' '));
 const revised=text.slice(0,node.start)+leading+'{\n'+rows.join('\n')+'\n  }'+trailing+text.slice(node.end);
 if(!equal(parse(revised,context),c))throw Error('Could not expand modifierDifficulty without changing other settings.');
 return revised;
}
function exposePopulationModifiers(text,context){
 const c=parse(text,context),raw=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30});
 if(Object.hasOwn(raw,'populationModifiers'))return text;
 const block=yaml.dump({populationModifiers:c.populationModifiers},{lineWidth:100,noRefs:true,flowLevel:4});
 const revised=text.replace(/^\s*#.*$/gm,'').trimStart().startsWith('{')?yaml.dump({...raw,populationModifiers:c.populationModifiers},{lineWidth:100,noRefs:true}):text.trimEnd()+'\n\n# Population roll ranges and reward difficulty divisors.\n'+block;
 if(!equal(parse(revised,context),c))throw Error('Could not expose population modifier settings.');
 return revised;
}
function addAncientMaterial(text,context,prefab){
 parse(text,context);
 const nodes=[],stack=[];
 const raw=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30,listener:(event,state)=>{
  if(event==='open')stack.push(state.position);
  else{const start=stack.pop();if(state.kind==='sequence')nodes.push({start,end:state.position,value:state.result});}
 }});
 const common=raw.rarities.find(r=>r.id==='common');if(!common)throw Error('Add '+prefab+' to your chosen reward table; this plan has no common table.');
 let item=raw.items.find(i=>i.prefab===prefab);
 const additions=[];
 if(!item){
  if(raw.items.some(i=>i.id===prefab))throw Error('Item ID '+prefab+' is already used by another prefab.');
  item={id:prefab,prefab,minTier:6,minQuantity:1,maxQuantity:2};additions.push({list:raw.items,item});
 }
 if(!raw.rarities.some(r=>r.entries.some(e=>e.item===item.id)))additions.push({list:common.entries,item:{item:item.id,weight:1}});
 const edits=additions.map(addition=>({...nodes.find(n=>n.value===addition.list),item:addition.item}));
 for(const edit of edits.sort((a,b)=>b.start-a.start)){
  const source=text.slice(edit.start,edit.end),leading=source.match(/^\s*/)[0],trailing=source.match(/\s*$/)[0],body=source.trim();
  const value=yaml.dump(edit.item,{flowLevel:0,lineWidth:-1}).trimEnd();
  const position=edit.start+leading.length,indent=' '.repeat(position-text.lastIndexOf('\n',position-1)-1);
  const revised=body.startsWith('[')?body.slice(0,-1)+(body.slice(1,-1).trim()?', ':'')+value+']':body+'\n'+indent+'- '+value;
  text=text.slice(0,edit.start)+leading+revised+trailing+text.slice(edit.end);
 }
 for(const addition of additions)addition.list.push(addition.item);
 if(!equal(parse(text,context),engine.normalize(raw,context)))throw Error('Could not add '+prefab+' without changing other settings.');
 return text;
}
function repairRewardUnlocks(text,context){
 text=addAncientMaterial(text,context,'RunestoneAncient');
 const nodes=[],stack=[];
 const raw=yaml.load(text,{schema:yaml.JSON_SCHEMA,maxDepth:30,listener:(event,state)=>{
  if(event==='open')stack.push(state.position);
  else{const start=stack.pop();if(state.kind==='mapping')nodes.push({start,end:state.position,value:state.result});}
 }});
 const changed=new Set();
 for(const item of raw.items){
  const tier={RunestoneAncient:6,ShardSlotChiselLegendary:4}[item.prefab];if(!tier)continue;
  if((item.minTier??1)!==tier){item.minTier=tier;changed.add(item);}
  if((item.maxTier??15)<tier){item.maxTier=tier;changed.add(item);}
  if(item.prefab==='RunestoneAncient'&&item.enabled===false){item.enabled=true;changed.add(item);}
 }
 for(const node of nodes.filter(n=>changed.has(n.value)).sort((a,b)=>b.start-a.start)){
  const source=text.slice(node.start,node.end),leading=source.match(/^\s*/)[0],trailing=source.match(/\s*$/)[0];
  text=text.slice(0,node.start)+leading+yaml.dump(node.value,{flowLevel:0,lineWidth:-1}).trimEnd()+trailing+text.slice(node.end);
 }
 if(!equal(parse(text,context),engine.normalize(raw,context)))throw Error('Could not update reward unlock tiers without changing other settings.');
 return text;
}
const api={parse,review,upgradeSetRewards,removeFirewalker,expandModifierDifficulty,exposePopulationModifiers,addAncientMaterial,repairRewardUnlocks};
if(node)module.exports=api;else root.LootYaml=api;
})(typeof globalThis!=='undefined'?globalThis:this);
