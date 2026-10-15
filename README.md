# valBalance

A Python calculation model and command-line app for comparing player strength, creature roles, and wave composition. Requires Python 3.9 or later and PyYAML. No game or server files are changed.

Install dependencies with `python3 -m pip install -r requirements.txt`.

Shared tier and rarity settings live in [configs/balance-model.yaml](configs/balance-model.yaml).
Player defenses use six sections: health value, armor value, conversion, Epic Loot resistance, base-game resistance, and recovery. Use [Klov's defensive-layer reference](configs/player-defense-klov.yaml) as the editable YAML template. It records calculation assumptions and unresolved inputs; it is reference data, not a CLI input file.
See [the balance model guide](docs/balance-model.md) for sources, formulas, tuning,
and validation status. Inspect planning factors with
`python3 app.py balance-model --tier 2 --rarity rare`.

```sh
python3 app.py weapon examples/snuffiss-weapon-source.json
python3 app.py calibrate examples/blackforest-v3.json --weapon examples/snuffiss-weapon-source.json
python3 app.py example /tmp/forest-scenario.json
# Enter verified scalar inputs before running the simpler constant-hit model:
python3 app.py analyze /tmp/forest-scenario.json
python3 app.py analyze /tmp/forest-scenario.json --json --output /tmp/forest-results.json
```

## Metric names

- TTK: seconds for the player to kill a monster.
- HTK: player hits needed to kill a monster.
- HTD: monster hits needed to kill the player.
- TTD: seconds until the monster or pack kills the player.

## Actual player inputs

`weapon.py` accepts weapon base damage by type, per-quality increases, quality, skill, equipped damage effects, socket effect totals, coin count, current/max health, dodge-buff state, target native resistance, target SLS damage-received multipliers, target armor, skill roll, and double-damage outcome. It separates immediate damage from fire, poison, and spirit payloads. It never turns an averaged payload into a hit count.

`examples/snuffiss-weapon-source.json` contains data extracted from the production **1.0.16** asset bundle and assembly, the deployed Epic Loot assembly, the Season 8 config snapshot, and Snuffiss's saved equipped gear. It records source hashes. The local installed 1.0.17 assets were not used as the authoritative source.

The file contains primary spear attack animation events, speed changes, attack-state transitions, hit pause, poison/fire timing rules, and native/Epic Loot proc inputs. `weapon` reports exact per-strike outcomes for the supplied states and random rolls, plus unresolved inputs. It does **not** yet simulate the full fight. It returns `null` for TTK/HTK rather than inventing a repeated-attack interval or treating delayed damage as immediate.

`calibrate` runs the separate nominal single-target scenario model in `combat.py`. It includes timed fire/poison refresh, skill and double-damage rolls, initial chain hits, and stamina depletion/recovery. It integrates source animation events into a nominal cycle. The current scenario selects SLS-before-conversion using [controlled Valnet evidence](live_probe/evidence/2026-10-09/README.md); the alternative remains available for sensitivity analysis. The selected evidence must match the profile's game version and SLS/Epic Loot binary hashes. It does not establish order for other mod sets or report exact live timing. The full-health/no-dodge-buff context is an explicit test case, not the character's current live state. Targets use their base native resistances and the recorded SLS poison multiplier; wetness, stagger, backstab, and random defensive modifiers require separate encounter states.

The [Black Forest v3 candidate](configs/blackforest-v3/README.md) contains the resulting star/modifier choices, role targets, reproducible sampled results, and YAML merge fragments. It uses six greydwarves, two brute/shaman selections, and one bear per pack; a unique troll joins the final pack. The full simulation assumptions and remaining live-validation requirements are recorded beside the config. No production files are changed by this app.

`events` calculates exact HTK/TTK from a supplied sequence of **applied health changes**. Input fields are `monster_health`, `attack_start`, and time-ordered `events`, each with `time`, `kind` (`weapon_hit`, `dot`, `proc`, or `heal`), and nonnegative `amount`. Dot/proc events can kill the monster without adding to HTK. This path accepts authoritative event data; it does not synthesize missing events.

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

The prior Black Forest star and modifier scenarios are retained as **withdrawn calibration drafts**. Their offensive inputs are now null, and `analyze` rejects them until verified inputs are supplied. Use v3 for the current source-based test candidate. Its catalog costs and existing wave format determine the pack counts; its two support selections can repeat.

## Defaults and provenance

The player defenses come from the Snuffiss analysis in the October 9, 2026 shrine-design session, based on the October 1 character snapshot. They include equipped Epic Loot armor and resistance totals, three best health foods, and no Crown. Health uses the intended modifier order; use 646.24 instead of 672.45 to examine the unresolved alternative order. No character account identifiers or raw saves are included.

There is **no default player hit damage, interval, first-hit delay, or attack uptime**. The previous values were placeholders, not measurements, and have been removed from all shipped scenarios. Synthetic values remain only in tests. Enemy timing and contact values in the old draft are also unverified; do not use them for calibrated TTD/wave predictions. Creature health, raw damage, and wave counts in those drafts are proposals, not validated recommendations.

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
python3 -m unittest discover -s . -p 'test_*.py' -v
```
