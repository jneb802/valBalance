/* Shared offline page controls; each editor owns its state and validation. */
const $ = id => document.getElementById(id), clone = x => JSON.parse(JSON.stringify(x));
function el(tag,text,cls) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function download(name,text,type) {const url=URL.createObjectURL(new Blob([text],{type})),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function saveDraft(key,state,status) {
 try {localStorage.setItem(key,JSON.stringify(state));status.textContent='Saved in this browser · '+new Date().toLocaleTimeString();}
 catch(error) {status.textContent='Storage unavailable. Use Export review.';}
}
function restoreDraft(key,initial,validate,status) {
 try {const saved=localStorage.getItem(key);return saved?validate(JSON.parse(saved)):clone(initial);}
 catch(error){status.textContent='Could not restore draft: '+error.message;return clone(initial);}
}
function bindReview({exportButton,importButton,file,status,filename,getState,accept}) {
 exportButton.onclick=()=>{try{download(filename,JSON.stringify({...getState(),exportedAt:new Date().toISOString()},null,2),'application/json');}catch(error){status.textContent=error.message;}};
 importButton.onclick=()=>file.click();
 file.onchange=async()=>{try{const f=file.files[0];if(!f)return;if(f.size>5000000)throw Error('Review exceeds 5 MB.');accept(JSON.parse(await f.text()));}catch(error){status.textContent=error.message;}finally{file.value='';}};
}
function csvDownload(filename,rows) {download(filename,rows.map(r=>r.map(x=>'"'+String(x).replaceAll('"','""')+'"').join(',')).join('\n'),'text/csv');}
const workbenchTabs=['creatures','scaling','loot','uberbosses'];
function selectWorkbenchTab(name) {
 for(const tab of workbenchTabs) {
  const selected=tab===name;$('panel-'+tab).hidden=!selected;$('tab-'+tab).setAttribute('aria-selected',String(selected));$('tab-'+tab).tabIndex=selected?0:-1;
 }
 location.hash=name;
 $('panel-'+name).dispatchEvent(new Event('workbench-tab-shown'));
}
for(const name of workbenchTabs) {
 $('tab-'+name).onclick=()=>selectWorkbenchTab(name);
 $('tab-'+name).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?workbenchTabs[0]:e.key==='End'?workbenchTabs.at(-1):workbenchTabs[(workbenchTabs.indexOf(name)+(e.key==='ArrowRight'?1:-1)+workbenchTabs.length)%workbenchTabs.length];selectWorkbenchTab(next);$('tab-'+next).focus();}};
}
selectWorkbenchTab(location.hash==='#chests'?'loot':workbenchTabs.includes(location.hash.slice(1))?location.hash.slice(1):'creatures');
