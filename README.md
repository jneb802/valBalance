# Shrine Balance

A Python calculation model and command-line app for comparing player strength, creature roles, and wave composition. No dependencies beyond Python 3.9 or later. No game or server files are changed.

```sh
python3 tools/shrine_balance/app.py example /tmp/forest-scenario.json
python3 tools/shrine_balance/app.py analyze /tmp/forest-scenario.json
python3 tools/shrine_balance/app.py analyze /tmp/forest-scenario.json --json --output /tmp/forest-results.json
```

1. Generate the example JSON and edit player health, armor, resistances, effective immediate damage, and attack timings.
2. Set creature health, role, and representative incoming attack. Set `hit` to override player damage for creatures with different defenses; zero uses the player default.
3. Compare hits to kill (HTK), time to kill (TTK), hits to die (HTD), and time to die (TTD) against editable role targets. The suggested health interval satisfies both TTK and HTK targets; its lower bound is exclusive.
4. Set counts in each wave. Compare sequential clear time and constant-pack pressure.
5. Keep separate scenario JSON files to compare builds and event variants. Use `--json` for further analysis in Python. Output files must not already exist.

The reusable entry point is `model.analyze(scenario)`. It validates input and returns `enemies` and `waves` result lists. It has no file, browser, network, or server dependencies.

## Input schema

- `version`: `1`.
- `player`: health, normal `armor`, `low_armor`, low-health `threshold` percent, `physical_resist` and `elemental_resist` percentages, effective immediate `hit`, attack `interval` seconds, first-hit `windup` seconds, attack `uptime` percent, and sustained `healing` HP/second.
- `roles`: role names mapped to six limits: `[TTK min, TTK max, HTK min, HTK max, player HTD min, player HTD max]`. Use `null` for an unrestricted limit.
- `enemies`: name, role, health, effective player hit override, raw physical and elemental damage for one representative attack, enemy attack interval, contact percentage, and counts in wave order.
- `waves`: wave names, in the same order as each enemy's `counts` array.

Contact percentage is the fraction of enemy attack opportunities that reach the player after movement and active defense. It affects wave pressure only. Uptime is the fraction of combat time available for player attacks. It affects practical TTK and wave clear time, not focused HTK/TTK.

Optional `stars`, `base_health`, `base_physical`, and `base_elemental` inputs enable the nominal Season 8 star calculation. When `stars` is present, it overrides the supplied health and damage fields using `health = base_health * (1 + stars)` and `damage = base_damage * (1 + 0.25 * stars)`. Base elemental damage defaults to zero. This mode does not include custom per-creature stat overrides or SLS modifiers. The report includes resolved health, stars, and raw damage.

`examples/blackforest-stars-v1.json` is the first star-only design. All creatures meet their durability targets under the illustrative offense assumptions. Brutes and bears do not meet damage targets. Exact wave counts remain a design target, not a guarantee from the Fortress PR schema.

## Defaults and provenance

The player defenses come from the Snuffiss analysis in the October 9, 2026 shrine-design session, based on the October 1 character snapshot. They include equipped Epic Loot armor and resistance totals, three best health foods, and no Crown. Health uses the intended modifier order; use 646.24 instead of 672.45 to examine the unresolved alternative order. No character account identifiers or raw saves are included.

The 500 effective immediate damage, 0.8-second attack interval, 0.4-second first-hit delay, 70% uptime, enemy timings, and contact percentages are **illustrative assumptions, not measurements of Snuffiss**. The earlier 791 mixed damage payload is intentionally not used. Creature health, raw damage, and wave counts are the preliminary Black Forest design, not live prefab defaults or a balanced recommendation. Shaman damage covers melee only; its poison and healing are excluded.

Role targets reproduce the user's proposed starting ranges. They are not measured industry averages. TTK targets apply to uninterrupted attack-start timing. Practical TTK is separately shown.

## Calculations and limits

- `HTK = ceil(creature health / effective immediate player hit)`.
- `Focused TTK = first-hit delay + (HTK - 1) * attack interval`.
- Practical TTK divides focused TTK by attack uptime.
- Incoming damage uses resistance per type, then armor on the combined damage: `d - armor` if `d >= 2 * armor`, otherwise `d² / (4 * armor)`. This corrects the first version's elemental armor bypass. Generic elemental input must represent immediate damage, not a fire or poison payload.
- Player HTD applies normal or low-health armor according to health before each hit. There is no block, parry, hit-ignore chance, or recovery. TTD is `(HTD - 1) * enemy interval`, starting at first impact.
- Sequential wave clear time sums practical creature TTK by count. It excludes area damage, travel, spawn delays, poison, and healing of enemies.
- Constant-pack damage per second sums `count * received hit / enemy interval * contact fraction`. The pack stays alive in this model. TTD integrates normal and low-health damage rates after subtracting user-entered recovery. If recovery prevents crossing either health segment, it reports that sustain holds. Burst can still kill.
- The clear/TTD ratio compares two coarse models with different timing conventions. It is not a win probability or difficulty grade.

Use effective damage measured against each creature. Do not convert random damage, poison, lifesteal, chain lightning, or avoidance into exact hit counts by averaging them. This first version intentionally provides a transparent deterministic baseline. Validate final events in the actual Season 8 mod set.

## SLS damage modifiers

An enemy can specify `sls_modifiers: ["Lightning", "Frost"]`. The scenario must supply `sls_modifier_powers`, mapping each chosen name to `[basePower, perlevelPower]`. Season 8 snapshot values are Lightning `[0.4, 0.05]` and Frost `[0.4, 0.01]`. Each adds `original attack * (basePower + perlevelPower * (stars + 1))`. Both use the same original attack total; they do not multiply each other.

Player `lightning_resist` and `frost_resist` override the generic elemental resistance. Optional `lightning_multiplier` and `frost_multiplier` represent native resistance multipliers after Epic Loot resistance; both default to 1. The Snuffiss modifier example uses 57.728% lightning resistance and a 0.5 native frost multiplier from his chest armor.

Only these two immediate damage modifiers are supported. Other modifiers are rejected rather than silently approximated. Fire and poison need damage-over-time modeling; ElementalChaos needs random type selection. Brutal changes attack animation speed, and Fast changes movement, so neither has a direct damage-per-hit bonus.

## Tests

```sh
python3 -m unittest discover -s tools/shrine_balance -p 'test_*.py' -v
```
