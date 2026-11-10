/* Uber boss attacks as hits against a player profile. Reads the editable uberbosses.json attack fields and
   the combat data (health, resistances, SLS scaling) that build_workbench.py resolves for each boss. */
const UberHits = (() => {
 // One entry per attack id. Each part is one kind of hit the attack can land:
 //   damage: damage type -> attack field name (or a fixed number)
 //   hits: how many of that hit the attack produces: a number, a field name, or {duration, tick} for repeated contact
 //   scales: true for weapon hits, which SLS scales with stars; area and projectile damage is fixed
 //   note: what the count means when a player is unlikely to take every hit
 const PARTS = {
  Eikthyr_charge: [{label: 'Headbutt', damage: {lightning: 'lightning'}, hits: 1, scales: true}],
  Eikthyr_stomp: [{label: 'Stomp', damage: {lightning: 'lightning'}, hits: 1, scales: true}],
  VE_Eikthyr_DoubleAntler: [{label: 'Swing', damage: {pierce: 'pierce'}, hits: 2, scales: true, note: 'Left then right swing.'}],
  VE_Eikthyr_Charge: [
   {label: 'Hitbox tick', damage: {lightning: 'hitboxLightning', blunt: 'hitboxBlunt'}, hits: {duration: 'duration', tick: 'hitboxTick'}, note: 'One per tick while the player stays inside the charging hitbox.'},
   {label: 'Trail strike', damage: {lightning: 'trailLightning'}, hits: 1, note: 'One per trail strike the player stands in.'}],
  VE_Eikthyr_StompLine: [{label: 'Strike', damage: {lightning: 'lightning', blunt: 'blunt'}, hits: 'strikes', note: 'Strikes land along a line; a player is usually inside one or two.'}],
  VE_Eikthyr_Meteors: [{label: 'Ball', damage: {lightning: 'lightning', blunt: 'blunt'}, hits: 'ballsPerPlayer', note: 'Balls aimed at each player.'}],
  VE_Eikthyr_Vortex: [{label: 'Explosion', damage: {lightning: 'explosionLightning', blunt: 'explosionBlunt'}, hits: 1}],
  gd_king_punch: [{label: 'Punch', damage: {blunt: 'blunt'}, hits: 1, scales: true}],
  gd_king_shoot: [{label: 'Root shot', damage: {pierce: 'pierce'}, hits: 1, scales: true, note: 'One per projectile that connects.'}],
  gd_king_scream: [],
  VE_Elder_Shockwave: [
   {label: 'Stomp', damage: {blunt: 'blunt'}, hits: 1, scales: true},
   {label: 'Ring point', damage: {blunt: 'pointBlunt'}, hits: 'rings', note: 'One per ring that passes over the player.'}],
  VE_Elder_RootCast: [],
  VE_Elder_StaffRoots: [],
  VE_Elder_Curse: [],
  bonemass_attack_punch: [{label: 'Punch', damage: {blunt: 'blunt', poison: 'poison'}, hits: 1, scales: true}],
  bonemass_attack_aoe: [{label: 'Puke', damage: {poison: 'poison'}, hits: 1, scales: true}],
  VE_Bonemass_Throw: [],
  VE_Bonemass_CallHealers: [],
  dragon_bite: [{label: 'Bite', damage: {pierce: 'pierce'}, hits: 1, scales: true}],
  dragon_claw_left: [{label: 'Claw', damage: {slash: 'slash'}, hits: 1, scales: true}],
  dragon_spit_shotgun: [{label: 'Ice spit', damage: {pierce: 'pierce', frost: 'frost'}, hits: 1, scales: true, note: 'One per projectile that connects.'}],
  VE_Moder_Breath: [
   {label: 'Breath', damage: {frost: 'frost'}, hits: 1, scales: true},
   {label: 'Field tick', damage: {frost: 'fieldFrost'}, hits: {duration: 'fieldDuration', tick: 'fieldTick'}, note: 'One per tick while the player stays in the frost field.'}],
  VE_Moder_AirBreath: [
   {label: 'Breath', damage: {frost: 'frost'}, hits: 1, scales: true},
   {label: 'Field tick', damage: {frost: 'fieldFrost'}, hits: {duration: 'fieldDuration', tick: 'fieldTick'}, note: 'One per tick while the player stays in the frost field.'}],
  VE_Moder_Icicles: [{label: 'Shard', damage: {frost: 'frost', pierce: 'pierce'}, hits: 'shardsPerPlayer', note: 'Shards aimed at each player.'}],
  VE_FrostNova: [{label: 'Nova', damage: {frost: 'frost', blunt: 'blunt'}, hits: 1}],
  VE_FrostShockwave: [
   {label: 'Impact', damage: {blunt: 'impactBlunt', frost: 'impactFrost'}, hits: 1},
   {label: 'Ring point', damage: {blunt: 'pointBlunt', frost: 'pointFrost'}, hits: 'rings', note: 'One per ring that passes over the player.'}],
  GoblinKing_Meteors: [],
  GoblinKing_Taunt: [],
  VE_Yagluth_BeamSweep: [{label: 'Bolt', damage: {fire: 'fire', lightning: 'lightning'}, hits: 'bolts'}],
  VE_Yagluth_PalmSlam: [
   {label: 'Slam', damage: {fire: 'fire', lightning: 'lightning'}, hits: 1, scales: true},
   {label: 'Ring point', damage: {blunt: 'ringBlunt'}, hits: 'rings', note: 'One per ring that passes over the player; each applies the Enervation curse.'}],
  VE_GazeHead: [{label: 'Bolt', damage: {fire: 'boltFire', lightning: 'boltLightning'}, hits: 1, note: 'One every bolt interval while the head lives.'}],
  SeekerQueen_Slap: [{label: 'Slap', damage: {slash: 'slash'}, hits: 1, scales: true}],
  SeekerQueen_Bite: [{label: 'Bite', damage: {pierce: 'pierce', poison: 'poison'}, hits: 1, scales: true}],
  SeekerQueen_Rush: [{label: 'Rush', damage: {slash: 'slash'}, hits: 1, scales: true}],
  SeekerQueen_Call: [],
  SeekerQueen_Teleport: [],
  VE_Queen_Spit: [
   {label: 'Spit', damage: {blunt: 'blunt', poison: 'poison'}, hits: 1, scales: true},
   {label: 'Pool tick', damage: {poison: 'poolPoison'}, hits: {duration: 'poolDuration', tick: 'poolTick'}, note: 'One per tick while the player stands in the pool.'}],
  VE_Queen_Pierce: [
   {label: 'Pierce', damage: {pierce: 'pierce'}, hits: 1, scales: true},
   {label: 'Thorn', damage: {pierce: 'thornPierce'}, hits: 'thorns', note: 'Thorns burst around the target; a player is usually inside one or two.'}],
  VE_Undermine: [{label: 'Eruption', damage: {pierce: 'pierce', blunt: 'blunt'}, hits: 1}],
  VE_HiveNest: [],
  Fader_Bite: [{label: 'Bite', damage: {pierce: 'pierce'}, hits: 1, scales: true}],
  Fader_Claw_Left: [{label: 'Claw', damage: {pierce: 'pierce'}, hits: 1, scales: true}],
  Fader_Flamebreath: [{label: 'Breath', damage: {fire: 'fire'}, hits: 1, scales: true}],
  Fader_WallOfFire: [{label: 'Wall', damage: {pierce: 'pierce'}, hits: 1, scales: true}],
  Fader_Roar: [],
  VE_Fader_Fissures: [{label: 'Pillar', damage: {pierce: 'pierce'}, hits: 'fissures', scales: true, note: 'Each fissure raises a line of pillars; a player is usually caught by one pillar per fissure.'}],
  VE_Fader_MeteorStorm: [],
  VE_Fader_LavaSpin: [
   {label: 'Spin', damage: {pierce: 'pierce'}, hits: 1, scales: true},
   {label: 'Pool tick', damage: {fire: 'poolFire'}, hits: {duration: 'poolDuration', tick: 'poolTick'}, note: 'One per tick while the player stands in a lava pool.'}],
 };
 // Attacks with no direct damage of their own.
 const NO_DAMAGE = {
  gd_king_scream: 'Summons greydwarfs; no damage.', VE_Elder_RootCast: 'Summons roots; their own attacks deal the damage.', VE_Elder_StaffRoots: 'Summons roots; their own attacks deal the damage.',
  VE_Elder_Curse: 'Movement curse; no damage.', VE_Bonemass_Throw: 'Throws blobs and oozers; their own attacks deal the damage.', VE_Bonemass_CallHealers: 'Summons healers; no damage.',
  GoblinKing_Meteors: 'Vanilla meteor projectiles; their damage is not in uberbosses.json.', GoblinKing_Taunt: 'Taunt; no damage.', SeekerQueen_Call: 'Summons seekers; no damage.', SeekerQueen_Teleport: 'Burrow; no damage.',
  VE_HiveNest: 'Spawns larvae; no damage.', Fader_Roar: 'Summons charred; no damage.', VE_Fader_MeteorStorm: 'Vanilla meteor projectiles; their damage is not in uberbosses.json.',
 };
 function value(fields, ref) { return typeof ref === 'number' ? ref : Number(fields[ref] ?? 0); }
 function hitCount(fields, hits) {
  if (typeof hits === 'number') return hits;
  if (typeof hits === 'string') return Math.max(0, Math.round(value(fields, hits)));
  const tick = value(fields, hits.tick);
  return tick > 0 ? Math.max(1, Math.ceil(value(fields, hits.duration) / tick - 1e-9)) : 1;
 }
 // Base health comes from the editable boss settings; the vanilla boss value is the fallback.
 function baseHealth(boss, combat) { const h = Number(boss.settings && boss.settings.health); return Number.isFinite(h) && h > 0 ? h : combat.health; }
 function health(boss, combat, stars) { return baseHealth(boss, combat) * (combat.scaling.health_base + stars * combat.scaling.health_per_star); }
 function weaponFactor(combat, stars) { return combat.scaling.damage_base * (1 + stars * combat.scaling.damage_per_star); }
 // Every hit of one boss against one player profile at a star count.
 function rows(boss, combat, player, stars) {
  const result = [];
  for (const attack of boss.attacks) {
   const parts = PARTS[attack.id];
   if (parts === undefined) throw Error('No hit definition for Uber attack ' + attack.id);
   if (!parts.length) { result.push({attack, part: null, note: NO_DAMAGE[attack.id] || 'No direct damage.'}); continue; }
   for (const part of parts) {
    const factor = part.scales ? weaponFactor(combat, stars) : 1;
    const damage = Object.fromEntries(Object.entries(part.damage).map(([type, ref]) => [type, value(attack.fields, ref) * factor]));
    const hits = hitCount(attack.fields, part.hits);
    const editable = attack.kind !== 'vanilla';
    const raw = Object.values(damage).reduce((a, b) => a + b, 0);
    const received = BalanceEngine.received(damage, player, player.defense.armor);
    const htd = BalanceEngine.hitCount(damage, player);
    result.push({attack, part, damage, hits, raw, volley: raw * hits, received, htd, volleyKills: Number.isFinite(htd) && htd <= hits, note: part.note || '', editable});
   }
  }
  return result;
 }
 // Boss summary: health, the player's time to kill, and the attack that kills the player in the fewest hits.
 function summary(boss, combat, player, stars, trials) {
  const hp = health(boss, combat, stars);
  const creature = {native: combat.native, scaling: combat.scaling};
  const ttk = BalanceEngine.ttk(player, creature, hp, 'before', trials);
  const hitRows = rows(boss, combat, player, stars).filter(r => r.part);
  const deadliest = hitRows.reduce((best, r) => best === null || r.htd < best.htd ? r : best, null);
  return {health: hp, ttk, deadliest, rows: hitRows};
 }
 return {PARTS, NO_DAMAGE, hitCount, baseHealth, health, weaponFactor, rows, summary};
})();
if (typeof module !== 'undefined') module.exports = UberHits;
