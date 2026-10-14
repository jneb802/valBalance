# Shrine balance model

Edit [configs/balance-model.yaml](../configs/balance-model.yaml) to tune the shared
design model. The `balance-model` command reads it directly using PyYAML's
`safe_load`. YAML comments explain the editable fields. JSON remains the combat
scenario and CLI output format.

## Status and baseline

Version 0.1.0 is a proposal, not a combat-validated replacement for current events.
The user accepted Black Forest's challenge level as shrine tier 1. Its existing
stars and SLS modifiers already include role differences. Do not multiply those
finished stats by rarity again. First establish a tier-1 normal baseline for each
creature, or solve backward from its intended role and measured results.

The `reference` section preserves PoE 1 wiki values reviewed on 2026-10-14.
The `adopted` section contains our editable Valheim proposal. Updating one does
not silently update the other. Source URLs live beside the reference values.
These are wiki-listed mechanics, not independently verified PoE code.

## Tier and rarity

PoE map progression combines monster-level growth and map bonuses. Across T1–T16,
the calculated per-step health gain ranges from about 10.30% to 12.45%; damage
from 5.89% to 6.21%. We propose constant 11% health and 6% raw damage increases
as a simplified starting curve. These are not exact PoE rates at every tier.

For tier `t`, relative to the same tier-1 normal creature:

```
health factor = health_per_step ** (t - 1) * rarity.health
raw hit factor = damage_per_step ** (t - 1) * rarity.damage_per_hit
```

Endgame PoE health factors combine innate and level-dependent rarity factors:
magic `2.48 * 1.75 = 4.34`; rare `4.90 * 2 = 9.80`.
The additional level factors remain constant from monster level 68 onward.
They are not applied again at each tier.

The listed damage modifiers also compensate for faster attacks:
magic `1.30 * 0.80 = 1.04` per hit and `1.20` attack speed;
rare `1.50 * 0.67 = 1.005` per hit and `1.33` attack speed.
Explicit modifiers add further effects. Faster animation does not necessarily
reduce AI delays or cooldowns. These speed factors are design references until
we establish their exact Valheim implementation and timing.

Normal enemies supply common packs. Magic enemies supply stronger support.
Rare enemies supply main wave threats. Rarity is independent of species and
tactical function: a Draugr can have any rarity. Unique final bosses, such as
the Troll and Abomination, require separate tuning; no automatic unique
multiplier is adopted here.

## Metrics and targets

- TTK: seconds for the player to kill a monster.
- HTK: player hits needed to kill a monster.
- HTD: monster hits needed to kill the player.
- TTD: seconds until the monster or pack kills the player.

The YAML reserves absolute tier-1 TTK and HTD bounds for each rarity. They remain
null until we calibrate them to the accepted event and exact player inputs.
We do not replace these missing targets with invented measurements. Existing
scenario role ranges remain scenario inputs; the new model does not override them.

With unchanged effective player damage, health ratios approximate TTK ratios.
Discrete hits, damage over time, resistances, stagger and movement can break that
relationship. HTD must be recalculated through player defenses, including health
state changes. Attack speed affects TTD even when HTD stays unchanged.
Creature counts, simultaneous attacks, poison, healing and support effects need
separate wave assessment. The tier formula is not a complete difficulty score.

## Use and tune

```sh
python3 -m pip install -r requirements.txt
python3 app.py balance-model --tier 2 --rarity rare \
  --player examples/snuffiss-weapon-source.json
```

This command reports factors, tier-1 target bounds, model version, model SHA-256,
and optional player-file SHA-256. It does not report synthetic TTK or HTD or
change combat scenarios. Use the existing `calibrate` command on resolved
creature stats and exact player inputs to measure those metrics.

For each comparison, save the planning output with the combat results and record
all additional scenario/config hashes. The player hash identifies only the supplied
file, not every defense input or installed game/mod binary. Missing player hashes
mean the planning output is not tied to a player snapshot.

When tuning, change adopted settings, increment `model_version`, and explain the
reason and evidence in the pull request. Re-run the same player scenarios, then
test combat in the maintained Season 8 environment. Preserve reference values
unless new source evidence corrects them. Event configs own wave composition,
stars and SLS choices; this model owns shared design factors and target bounds.
