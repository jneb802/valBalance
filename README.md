# Shrine Balance

A local Python app for comparing player strength, creature roles, and wave composition. No dependencies beyond Python 3.9 or later. No game or server files are changed.

```sh
python3 tools/shrine_balance/app.py
```

Open http://127.0.0.1:8765. Use `--port 8766` if needed. Stop with Ctrl+C.

1. Enter player health, armor, resistances, effective immediate damage, and attack timings.
2. Set creature health, role, and representative incoming attack. Set a player damage override for creatures with different defenses.
3. Compare hits to kill (HTK), time to kill (TTK), hits to die (HTD), and time to die (TTD) against editable role targets. The suggested health interval satisfies both TTK and HTK targets; its lower bound is exclusive.
4. Set counts in each wave. Compare sequential clear time and constant-pack pressure.
5. Export JSON to keep or share a scenario. Import restores inputs, roles, and waves. Valid changes also save in browser storage.

## Defaults and provenance

The player defenses come from the Snuffiss analysis in the October 9, 2026 shrine-design session, based on the October 1 character snapshot. They include equipped Epic Loot armor and resistance totals, three best health foods, and no Crown. Health uses the intended modifier order; use 646.24 instead of 672.45 to examine the unresolved alternative order. No character account identifiers or raw saves are included.

The 500 effective immediate damage, 0.8-second attack interval, 0.4-second first-hit delay, 70% uptime, enemy timings, and contact percentages are **illustrative assumptions, not measurements of Snuffiss**. The earlier 791 mixed damage payload is intentionally not used. Creature health, raw damage, and wave counts are the preliminary Black Forest design, not live prefab defaults or a balanced recommendation. Shaman damage covers melee only; its poison and healing are excluded.

Role targets reproduce the user's proposed starting ranges. They are not measured industry averages. TTK targets apply to uninterrupted attack-start timing. Practical TTK is separately shown.

## Calculations and limits

- `HTK = ceil(creature health / effective immediate player hit)`.
- `Focused TTK = first-hit delay + (HTK - 1) * attack interval`.
- Practical TTK divides focused TTK by attack uptime.
- Incoming physical damage is reduced by physical resistance, then armor: `d - armor` if `d >= 2 * armor`, otherwise `d² / (4 * armor)`. Elemental input uses the entered elemental resistance and bypasses armor. This simplified split does not reproduce every damage type or mod interaction.
- Player HTD applies normal or low-health armor according to health before each hit. There is no block, parry, hit-ignore chance, or recovery. TTD is `(HTD - 1) * enemy interval`, starting at first impact.
- Sequential wave clear time sums practical creature TTK by count. It excludes area damage, travel, spawn delays, poison, and healing of enemies.
- Constant-pack damage per second sums `count * received hit / enemy interval * contact fraction`. The pack stays alive in this model. TTD integrates normal and low-health damage rates after subtracting user-entered recovery. If recovery prevents crossing either health segment, it reports that sustain holds. Burst can still kill.
- The clear/TTD ratio compares two coarse models with different timing conventions. It is not a win probability or difficulty grade.

Use effective damage measured against each creature. Do not convert random damage, poison, lifesteal, chain lightning, or avoidance into exact hit counts by averaging them. This first version intentionally provides a transparent deterministic baseline. Validate final events in the actual Season 8 mod set.

## Tests

```sh
python3 -m unittest discover -s tools/shrine_balance -p 'test_*.py' -v
```
