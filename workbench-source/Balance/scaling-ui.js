/* Creature scaling charts: selected player TTK and HTD against stars for chosen creatures. */
const scalingColors = ['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
const scalingKey = 've-balance-scaling-v1', scalingNs = 'http://www.w3.org/2000/svg';
const scalingMetrics = [{key:'ttk',plot:'scaling-ttk',name:'Time to kill'},{key:'htd',plot:'scaling-htd',name:'Hits to die'}];
const scalingTierRange = [DATA.progression.minimum_tier, DATA.progression.maximum_tier];
let scaling = {selected:{},axis:'absolute',tier:scalingTierRange[0]}, scalingSeries = new Map(), scalingGeneration = 0, scalingCharts = [];
try {
 const saved=JSON.parse(localStorage.getItem(scalingKey)||'null');
 if(saved) {
  const slots=Object.entries(saved.selected||{}).filter(([id,slot])=>Object.hasOwn(state.creatures,id)&&Number.isInteger(slot)&&slot>=0&&slot<scalingColors.length);
  if(new Set(slots.map(s=>s[1])).size===slots.length)scaling.selected=Object.fromEntries(slots);
  if(['absolute','relative'].includes(saved.axis))scaling.axis=saved.axis;
  if(Number.isInteger(saved.tier)&&saved.tier>=scalingTierRange[0]&&saved.tier<=scalingTierRange[1])scaling.tier=saved.tier;
 }
} catch(error) {}
function saveScaling() {try{localStorage.setItem(scalingKey,JSON.stringify(scaling));}catch(error){}}
function svgEl(tag,attrs,text) {const n=document.createElementNS(scalingNs,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
function scalingName(id) {return names[id]||id;}
function scalingText(key,v) {return v===null?(key==='ttk'?'Limit':'—'):!Number.isFinite(v)?'∞':key==='ttk'?v.toFixed(1)+' s':Math.round(v).toLocaleString();}
function scalingNice(v) {if(!(v>0))return 1;const p=10**Math.floor(Math.log10(v)),f=v/p;return (f<=1?1:f<=2?2:f<=5?5:10)*p;}
// Every star from Tier 1 minimum to Tier 15 maximum, thinned past 120 points; tier bounds are always kept.
function scalingStars(c) {
 const tiers=state.creatures[c.id].tiers,low=tiers[scalingTierRange[0]][0],high=tiers[scalingTierRange[1]][1];
 const step=Math.max(1,Math.ceil((high-low)/120)),stars=new Set(Object.values(tiers).flat());
 for(let s=low;s<high;s+=step)stars.add(s);
 return {low,stars:[...stars].sort((a,b)=>a-b)};
}
function scalingTiersAt(id,star) {
 const t=Object.entries(state.creatures[id].tiers).filter(([,r])=>r[0]<=star&&star<=r[1]).map(([t])=>Number(t));
 return !t.length?'':t.length===1?'T'+t[0]:'T'+t[0]+'–T'+t.at(-1);
}
function scalingPlayer() {
 const select=$('scaling-player');select.replaceChildren();
 for(const p of DATA.players){const o=el('option',p.id);o.value=p.id;select.append(o);}
 select.value=state.selectedPlayer;
}
function scalingPicker() {
 const list=$('scaling-list'),q=$('scaling-search').value.trim().toLowerCase(),full=Object.keys(scaling.selected).length>=scalingColors.length;
 list.replaceChildren();
 $('scaling-limit').textContent=Object.keys(scaling.selected).length+' of '+scalingColors.length+' selected'+(full?' · remove one to add another':'');
 for(const biome of Object.keys(labels)) {
  if($('scaling-biome').value!=='All'&&$('scaling-biome').value!==biome)continue;
  const creatures=DATA.creatures.filter(c=>c.biome===biome&&(!q||(c.id+' '+(names[c.id]||'')).toLowerCase().includes(q)));
  if(!creatures.length)continue;
  list.append(el('h3',labels[biome]));
  for(const c of creatures) {
   const label=el('label'),check=el('input'),on=Object.hasOwn(scaling.selected,c.id);
   check.type='checkbox';check.checked=on;check.disabled=!on&&full;check.onchange=()=>scalingToggle(c.id,check.checked);
   const swatch=el('span',undefined,'scaling-swatch');if(on)swatch.style.background=scalingColors[scaling.selected[c.id]];
   label.append(check,swatch,el('span',scalingName(c.id)),el('small',c.role+(state.creatures[c.id].enabled?'':' · excluded'),'right'));list.append(label);
  }
 }
}
function scalingLegend() {
 const legend=$('scaling-legend');legend.replaceChildren();
 for(const [id,slot] of Object.entries(scaling.selected)) {
  const button=el('button'),swatch=el('span',undefined,'scaling-swatch');swatch.style.background=scalingColors[slot];
  button.append(swatch,el('span',scalingName(id)),el('span','×','muted'));button.setAttribute('aria-label','Remove '+scalingName(id));button.onclick=()=>scalingToggle(id,false);legend.append(button);
 }
}
function scalingToggle(id,on) {
 if(on){const used=new Set(Object.values(scaling.selected)),slot=scalingColors.findIndex((_,i)=>!used.has(i));if(slot<0)return;scaling.selected[id]=slot;}
 else delete scaling.selected[id];
 saveScaling();scalingPicker();scalingLegend();scalingUpdate();
}
async function scalingUpdate() {
 const stamp=++scalingGeneration,ids=Object.keys(scaling.selected),missing=playerResult().missing;
 scalingSeries=new Map();scalingDraw();
 if(missing.length){$('scaling-status').textContent=missing.join(' ')+' Set these on the Creature balance tab.';return;}
 if(!ids.length){$('scaling-status').textContent='Select creatures to chart.';return;}
 for(const [index,id] of ids.entries()) {
  const c=DATA.creatures.find(x=>x.id===id),{low,stars}=scalingStars(c),points=[];
  for(let i=0;i<stars.length;i++) {
   if(i%4===0){$('scaling-status').textContent='Calculating '+scalingName(id)+' · '+(index+1)+' of '+ids.length+'…';await new Promise(resolve=>setTimeout(resolve,0));if(stamp!==scalingGeneration)return;}
   const o=getMetric(c,[stars[i]]).outcomes[0];
   points.push({star:stars[i],x:scaling.axis==='absolute'?stars[i]:stars[i]-low,ttk:o.ttk[0],htd:o.htd[0]});
  }
  scalingSeries.set(id,{id,points});scalingDraw();
 }
 $('scaling-status').textContent='Ready · '+state.selectedPlayer+' · planning estimates';
}
function scalingDraw() {
 scalingCharts=scalingMetrics.map(scalingChart).filter(Boolean);
 const rows=$('scaling-rows');rows.replaceChildren();
 for(const s of scalingSeries.values())for(const p of s.points){const tr=el('tr');[scalingName(s.id),p.star,scalingTiersAt(s.id,p.star),scalingText('ttk',p.ttk),scalingText('htd',p.htd)].forEach((v,i)=>tr.append(el('td',v,i===1||i>2?'num':undefined)));rows.append(tr);}
}
function scalingChart(metric) {
 const box=$(metric.plot),series=[...scalingSeries.values()];box.replaceChildren();
 const values=series.flatMap(s=>s.points.map(p=>p[metric.key])).filter(Number.isFinite);
 if(!values.length){box.append(el('div',series.length?'No finite values for the selected creatures.':'Select creatures to chart.','scaling-empty'));return null;}
 const width=box.clientWidth,height=box.clientHeight,labelled=series.length<=4,m={l:52,r:labelled?Math.min(130,width/4):16,t:10,b:34};
 const xs=series.flatMap(s=>s.points.map(p=>p.x)),xMin=Math.min(...xs),xMax=Math.max(...xs),max=Math.max(...values);
 const yStep=scalingNice(max/5),yMax=Math.ceil(max/yStep)*yStep||1,plotW=width-m.l-m.r;
 const sx=v=>m.l+(xMax===xMin?.5:(v-xMin)/(xMax-xMin))*plotW,sy=v=>height-m.b-v/yMax*(height-m.t-m.b);
 const svg=svgEl('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':metric.name+' by stars for '+series.map(s=>scalingName(s.id)).join(', ')});
 for(let i=0;i*yStep<=yMax+1e-9;i++){const v=i*yStep;svg.append(svgEl('line',{class:'grid',x1:m.l,x2:width-m.r,y1:sy(v),y2:sy(v)}),svgEl('text',{x:m.l-6,y:sy(v)+4,'text-anchor':'end'},String(+v.toFixed(2))));}
 const xStep=Math.max(1,scalingNice((xMax-xMin)/Math.max(3,Math.floor(plotW/70))));
 for(let v=Math.ceil(xMin/xStep)*xStep;v<=xMax;v+=xStep)svg.append(svgEl('text',{x:sx(v),y:height-m.b+15,'text-anchor':'middle'},String(v)));
 svg.append(svgEl('text',{x:m.l+plotW/2,y:height-4,'text-anchor':'middle'},scaling.axis==='absolute'?'Stars':'Stars above Tier 1 minimum'));
 const ends=[];
 for(const s of series) {
  const color=scalingColors[scaling.selected[s.id]];let d='',open=false;
  for(const p of s.points){const v=p[metric.key];if(Number.isFinite(v)){d+=(open?'L':'M')+sx(p.x).toFixed(1)+' '+sy(v).toFixed(1);open=true;}else open=false;}
  svg.append(svgEl('path',{d,fill:'none',stroke:color,'stroke-width':2,'stroke-linejoin':'round'}));
  for(const star of new Set(state.creatures[s.id].tiers[scaling.tier])){const p=s.points.find(q=>q.star===star);if(p&&Number.isFinite(p[metric.key]))svg.append(svgEl('circle',{cx:sx(p.x),cy:sy(p[metric.key]),r:4,fill:color,style:'stroke:var(--surface);stroke-width:2'}));}
  const last=s.points.findLast(p=>Number.isFinite(p[metric.key]));if(last)ends.push({x:sx(last.x)+6,y:sy(last[metric.key])+4,name:scalingName(s.id)});
 }
 if(labelled){ends.sort((a,b)=>a.y-b.y);ends.forEach((e,i)=>{if(i&&e.y-ends[i-1].y<13)e.y=ends[i-1].y+13;svg.append(svgEl('text',{class:'label',x:e.x,y:e.y},e.name));});}
 const cross=svgEl('line',{class:'cross',y1:m.t,y2:height-m.b,visibility:'hidden'}),hit=svgEl('rect',{x:m.l,y:m.t,width:Math.max(0,plotW),height:height-m.t-m.b,fill:'transparent'});
 svg.append(cross,hit);const tip=el('div',undefined,'scaling-tip');tip.hidden=true;box.append(svg,tip);
 const chart={
  show(x,withTip) {
   if(x<xMin||x>xMax){chart.hide();return;}
   cross.setAttribute('x1',sx(x));cross.setAttribute('x2',sx(x));cross.setAttribute('visibility','visible');tip.hidden=!withTip;if(!withTip)return;
   tip.replaceChildren(el('strong',scaling.axis==='absolute'?x+' stars':'+'+x+' stars above Tier 1'));
   for(const s of series) {
    const p=s.points.reduce((best,q)=>Math.abs(q.x-x)<Math.abs(best.x-x)?q:best);if(x<s.points[0].x||x>s.points.at(-1).x)continue;
    const row=el('div'),swatch=el('span',undefined,'scaling-swatch');swatch.style.background=scalingColors[scaling.selected[s.id]];
    row.append(swatch,el('span',scalingName(s.id)+' · '+p.star+'★ '+scalingTiersAt(s.id,p.star)),el('b',scalingText(metric.key,p[metric.key])));tip.append(row);
   }
   const left=sx(x)+12;tip.style.left=(left+tip.offsetWidth>width?sx(x)-12-tip.offsetWidth:left)+'px';tip.style.top=m.t+'px';
  },
  hide(){cross.setAttribute('visibility','hidden');tip.hidden=true;}
 };
 hit.onpointermove=e=>{const r=svg.getBoundingClientRect(),px=(e.clientX-r.left)*width/r.width,x=Math.round(xMin+(px-m.l)/plotW*(xMax-xMin));scalingCharts.forEach(c=>c.show(x,c===chart));};
 hit.onpointerleave=()=>scalingCharts.forEach(c=>c.hide());
 return chart;
}
function scalingShown() {scalingPlayer();scalingPicker();scalingLegend();scalingUpdate();}
for(let t=scalingTierRange[0];t<=scalingTierRange[1];t++){const o=el('option','Tier '+t);o.value=t;$('scaling-tier').append(o);}
Object.entries(labels).forEach(([value,label])=>{const o=el('option',label);o.value=value;$('scaling-biome').append(o);});
$('scaling-tier').value=scaling.tier;$('scaling-axis').value=scaling.axis;
$('scaling-tier').onchange=()=>{scaling.tier=Number($('scaling-tier').value);saveScaling();scalingDraw();};
$('scaling-axis').onchange=()=>{scaling.axis=$('scaling-axis').value;saveScaling();scalingUpdate();};
$('scaling-player').onchange=()=>{state.selectedPlayer=$('scaling-player').value;save();playerControls();render();scalingUpdate();};
$('scaling-search').oninput=scalingPicker;$('scaling-biome').onchange=scalingPicker;
$('scaling-clear').onclick=()=>{scaling.selected={};saveScaling();scalingPicker();scalingLegend();scalingUpdate();};
$('scaling-csv').onclick=()=>{const lines=[['Player','Prefab','Stars','Tiers','TTK seconds','HTD']];for(const s of scalingSeries.values())for(const p of s.points)lines.push([state.selectedPlayer,s.id,p.star,scalingTiersAt(s.id,p.star),scalingText('ttk',p.ttk),scalingText('htd',p.htd)]);csvDownload('creature-scaling.csv',lines);};
$('panel-scaling').addEventListener('workbench-tab-shown',scalingShown);
let scalingResize;window.addEventListener('resize',()=>{clearTimeout(scalingResize);scalingResize=setTimeout(()=>{if(!$('panel-scaling').hidden)scalingDraw();},150);});
if(!$('panel-scaling').hidden)scalingShown();
