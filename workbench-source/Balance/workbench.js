/* Source-based planning scenarios. No game or server writes. */
const BalanceEngine = (() => {
  const types = ['blunt','slash','pierce','fire','frost','lightning','poison','spirit'];
  const physical = types.slice(0,3);
  const immediate = ['blunt','slash','pierce','frost','lightning'];
  const sum = values => values.reduce((a,b)=>a+b,0);
  const zero = () => Object.fromEntries(types.map(t=>[t,0]));
  const armorDamage = (damage, armor) => armor <= 0 ? damage : damage > 2*armor ? damage-armor : damage*damage/(4*armor);
  function received(raw, player, armor) {
    const d={...zero(),...raw}, p=player.defense;
    const converted=sum(physical.map(t=>d[t]))*p.conversion;
    physical.forEach(t=>d[t]*=1-p.conversion);d.fire+=converted;
    const typed=sum(types.map(t=>d[t]*(1-p.resistance[t])*(player.native[t]??1)));
    return armorDamage(typed,armor)+(d.damage||0);
  }
  function hitCount(raw, player) {
    const p=player.defense, normal=received(raw,player,p.armor), low=received(raw,player,p.low_armor);
    if(normal<=0 && low<=0)return Infinity;
    let health=p.health,hits=0;
    if(health>health*p.threshold && normal>0){
      const above=Math.ceil((health-health*p.threshold)/normal-1e-12);
      hits+=above;health-=above*normal;
    }
    if(health<=1e-9)return hits;
    return low>0 ? hits+Math.ceil(health/low-1e-12) : Infinity;
  }
  function incoming(creature,stars,player){
    return creature.attacks.map(attack=>{
      const factor=attack.scales ? creature.scaling.damage_base*(1+stars*creature.scaling.damage_per_star) : 1;
      const damage=Object.fromEntries(Object.entries(attack.damage).map(([k,v])=>[k,v*factor]));
      return {name:attack.name,damage,raw:sum(Object.values(damage)),received:received(damage,player,player.defense.armor),htd:hitCount(damage,player),note:attack.note};
    });
  }
  function rng(seed){let a=seed>>>0;return ()=>{a+=0x6D2B79F5;let t=a;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}
  function weaponDamage(p){
    const fx=p.effects, d=Object.fromEntries(types.map(t=>[t,p.base[t]+(p.quality-1)*p.per_quality[t]]));
    const original=sum(Object.values(d));
    const names=['AddBluntDamage','AddSlashingDamage','AddPiercingDamage','AddFireDamage','AddFrostDamage','AddLightningDamage','AddPoisonDamage','AddSpiritDamage'];
    types.forEach((t,i)=>{d[t]+=original*(fx[names[i]]||0)/100;d[t]*=1+(fx[physical.includes(t)?'ModifyPhysicalDamage':'ModifyElementalDamage']||0)/100;});
    let coin=0;if(p.coins>0 && fx.CoinHoarder>0)coin=p.coins<=1000?p.coins*.000145:Math.log10(fx.CoinHoarder*p.coins)*6.258/150;
    const factor=1+(fx.ModifyDamage||0)/100+(fx.SpellSword||0)/100+coin;
    types.forEach(t=>d[t]*=factor);
    if(fx.NecroticFire>0){const pool=sum(physical.map(t=>d[t]));physical.forEach(t=>d[t]=0);d.fire+=pool*fx.NecroticFire;d.poison+=pool*fx.NecroticFire;}
    return d;
  }
  function strike(p,creature,random,multiplier,order){
    const base=weaponDamage(p),center=.4+.6*Math.min(100,p.skill)/100;
    const roll=Math.max(0,center-.15)+random()*(Math.min(1,center+.15)-Math.max(0,center-.15));
    const d=Object.fromEntries(types.map(t=>[t,base[t]*roll*multiplier]));
    const sls=t=>creature.scaling.damage_received[t[0].toUpperCase()+t.slice(1)]??1;
    if(order==='before')types.forEach(t=>d[t]*=sls(t));
    d.poison*=1+(p.effects.IncreaseAllPoisonDamageDone||0)/100;
    const share=d.poison*Math.min(1,(p.effects.PoisonToTrueDamage||0)/100);
    d.poison-=share;
    const target=types.filter(t=>t!=='poison').reduce((best,t)=>creature.native[t]>creature.native[best]?t:best,'blunt');
    d[target]+=share;
    if(random()<Math.min(1,(p.effects.ChanceDoubleDamage||0)/100))types.forEach(t=>d[t]*=2);
    if(order==='after')types.forEach(t=>d[t]*=sls(t));
    types.forEach(t=>d[t]*=creature.native[t]);
    return d;
  }
  function simulate(p,c,hp,order,seed){
    const random=rng(seed), dots={}, maxStamina=p.stamina.maximum;
    let health=hp,stamina=maxStamina,start=0,lastStart=-Infinity,stage=0,hits=0;
    const speed=1+(p.effects.ModifyAttackSpeed||0)/100;
    function tickUntil(stop){
      while(Object.keys(dots).length){
        const key=Object.keys(dots).reduce((a,b)=>dots[a].next<=dots[b].next?a:b),e=dots[key];
        if(e.next>stop)return null;
        if(e.next>=e.expires-1e-9){delete dots[key];continue;}
        const now=e.next;health-=e.tick;e.left=Math.max(0,e.left-e.tick);e.next+=e.interval;
        if(health<=0)return now;
      }
      return null;
    }
    function addDot(kind,amount,now){
      if(amount<=0)return;
      let old=dots[kind];if(old && now>=old.expires)old=null;
      let left=old?old.left:0;
      if(kind==='poison' && amount<left)return;
      left=kind==='poison'?amount:left+amount;
      const rule=p.dot[kind],interval=rule.interval,ttl=kind==='poison'?rule.base+(left*rule.per_damage)**rule.power:rule.ttl;
      const ticks=Math.floor(ttl/interval);if(kind!=='poison' && amount/ticks<.2 && (!old||!old.left))return;
      dots[kind]={left,tick:left/ticks,next:old?old.next:now,expires:now+ttl,interval};
    }
    while(hits<10000 && start<1800){
      if(stamina<p.stamina.cost){
        if(p.stamina.cost>maxStamina||p.stamina.regen<=0)return null;
        const ready=Math.max(start,lastStart+p.stamina.delay);
        const wait=maxStamina/p.stamina.regen*Math.log((2*maxStamina-stamina)/(2*maxStamina-p.stamina.cost));
        start=ready+wait;stamina=p.stamina.cost;stage=0;
      }
      let killed=tickUntil(start);if(killed!==null)return killed;
      const attack=p.stages[stage],time=start+attack.windup/speed;
      lastStart=start;stamina-=p.stamina.cost;
      killed=tickUntil(time);if(killed!==null)return killed;
      const d=strike(p,c,random,attack.multiplier,order);health-=sum(immediate.map(t=>d[t]));hits++;
      ['fire','poison','spirit'].forEach(t=>addDot(t,d[t],time));
      for(const proc of p.chains){if(random()<proc.chance)health-=proc.damage*c.native.lightning*(c.scaling.damage_received.Lightning??1);}
      if(health<=0)return time;
      killed=tickUntil(time);if(killed!==null)return killed;
      const duration=stage<p.stages.length-1 && attack.chain!==null ? attack.chain : attack.cycle;
      start+=duration/speed;stage=(stage+1)%p.stages.length;
    }
    return null;
  }
  function ttk(p,c,hp,order,trials=96){
    const values=[];for(let i=0;i<trials;i++){const t=simulate(p,c,hp,order,19+i*7919);if(t===null)return null;values.push(t);}
    values.sort((a,b)=>a-b);return values[Math.ceil(values.length/2)-1];
  }
  function metrics(c,range,players,order,trials=96){
    const health=range.map(s=>c.health*(c.scaling.health_base+s*c.scaling.health_per_star));
    const outcomes=players.map(p=>{
      const incomingHits=range.map(s=>incoming(c,s,p));
      const htd=incomingHits.map(h=>h.length?Math.min(...h.map(a=>a.htd)):null);
      return {id:p.id,ttk:health.map(h=>ttk(p,c,h,order,trials)),htd,attacks:incomingHits};
    });
    return {health,outcomes};
  }
  return {types,armorDamage,received,hitCount,incoming,weaponDamage,strike,simulate,ttk,metrics};
})();
if(typeof module!=='undefined')module.exports=BalanceEngine;
