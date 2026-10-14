# Star-only workshop

This is a health-first proposal, not a deployable Fortress configuration. No local
profile or production file is changed. Roles were approved in the design session.
The health anchors and resulting stars are new proposals; the accepted Black
Forest event itself has not been replaced.

## Selection rule

The accepted tier-1 Greydwarf has 800 health. Use that as the common normal-health
anchor across species. Magic targets are `800 * 4.34`; rare targets are
`800 * 9.8`. Apply the shared model's `1.11 ** (tier - 1)` health progression.
Unique bosses use the accepted 24,000-health Troll as a separate anchor with the
same tier progression, not an invented PoE unique multiplier.

Select the integer star count that minimizes absolute health error. Prefer the
lower count on a tie. The recorded Season 8 formulas are:

```
health = creature base health * (1 + stars)
raw damage = creature base damage * (1 + 0.25 * stars)
```

This normalizes health across different creatures. It does not preserve their
base-health ratios or guarantee matching TTK. Species resistances still apply.
Damage is not part of the optimization: stars cannot independently fit health,
damage and attack speed. The summary's damage reference compares each creature
with its own nearest tier-1 health fit, then applies 6% damage growth per tier.
It is a diagnostic, not an adopted absolute damage or HTD target. The proposed
rarity damage and speed factors are not added through hidden stat overrides.

## Results against recorded Snuffiss inputs

Median TTK comes from 2,000 seeded trials per creature. HTD is repeated successful
representative hits without blocking, healing or avoidance. Raw damage below is
physical damage from the selected attack, not every attack the creature can use.

| Tier | Creature | Rarity | Stars | Target HP | Actual HP | Raw hit | TTK seconds | HTD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Greydwarf | Normal | 19 | 800 | 800 | 80.5 | 1.31 | 327 |
| 1 | Brute | Magic | 22 | 3,472 | 3,450 | 195 | 4.34 | 56 |
| 1 | Shaman | Magic | 57 | 3,472 | 3,480 | 213.5 | 4.34 | 47* |
| 1 | Bear | Rare | 15 | 7,840 | 8,000 | 261.25 | 12.84 | 31 |
| 1 | Troll | Unique | 39 | 24,000 | 24,000 | 752.5 | 21.73 | 4 |
| 2 | Draugr | Normal | 8 | 888 | 900 | 144 | 1.31 | 102 |
| 2 | Wraith | Magic | 38 | 3,853.92 | 3,900 | 630 | 7.34 | 6 |
| 2 | Oozer | Rare | 57 | 8,702.4 | 8,700 | Unknown | 10.92 | Unknown |
| 2 | Abomination | Unique | 32 | 26,640 | 26,400 | 720 | 48.34 | 5 |
| 3 | Ulv | Normal | 19 | 985.68 | 1,000 | 460 | 1.31 | 10 |
| 3 | Wolf | Magic | 52 | 4,277.85 | 4,240 | 980 | 5.15 | 3 |
| 3 | Fenring | Rare | 31 | 9,659.66 | 9,600 | 831.25 | 12.34 | 4 |
| 3 | Stone Golem | Unique | 36 | 29,570.4 | 29,600 | 1,100 | 59.77 | 2 |

*Shaman HTD describes melee only. Its poison and healing are not simulated.
Oozer has a nominal 1,753.75 raw poison payload at 57 stars, not an immediate hit.
Incoming poison timing/refresh, poison defenses, and child spawns remain unresolved.

Every health fit is within 2.1%. This is not proof that TTK or HTD targets are met.
The shared model still has no calibrated absolute TTK/HTD bounds. Removing required
Lightning/Frost modifiers makes the Black Forest Brute and Bear substantially less
dangerous than the accepted event. The Abomination and Golem take much longer to
kill than the Troll despite small tier increments. This pass identifies where
later tuning must address damage or effective durability separately.

## Four-wave proposals

Hold these counts steady while evaluating star changes. These are workshop counts,
not proof of Fortress's generated selection behavior. Child spawns are additional.

| Event | Waves 1, 2 and 3, each | Wave 4 |
|---|---|---|
| Black Forest | 6 Greydwarves + 2 Brute/Shaman selections + 1 Bear | Same pack + 1 Troll |
| Swamp | 4 Draugr + 2 Wraiths + 1 Oozer | Same pack + 1 Abomination |
| Mountain | 3 Ulvs + 2 Wolves + 1 Fenring | Same pack + 1 Stone Golem |

Black Forest support selections may repeat. Swamp retains the agreed Oozer in
every wave and Abomination only in the finale. Mountain counts are provisional.
No overall wave-clear time or difficulty ordering is claimed.

## Reproduce and limits

```sh
python3 -m pip install -r requirements.txt
python3 workshops/star-only/run.py
```

Edit `design.yaml` for anchors, assignments and proposed wave counts. Edit
`configs/balance-model.yaml` for shared tier and rarity settings. The generator
reads both, writes scenario/results files, and records their input hashes in
`summary.json`. Stars are actual star counts, not internal level (stars + 1).

`player.json`, `creature-source-data.json` and the scenario template preserve inputs
from the earlier three-tier workshop on `config/local-swamp-test` at commit
136b939. Creature data includes original source provenance. The player uses the
recorded Q3 blood/lightning spear, Spears 100, Epic Loot/shardstones, 672.448 HP,
and no Crown. Per-target resistance and existing SLS damage-received settings
remain; "star-only" means no additional required offensive SLS modifiers.

The simulator uses the frozen October 9 patch-order evidence and nominal source
animation timing. Current runtime, AI attack timing, random SLS modifiers, rarity
attack-speed changes, poison threats, Shaman healing, and Oozer child behavior
are not validated by this run. Each isolated fight starts at full stamina. These
results are not a full-wave simulation. Do not deploy this workshop unchanged.
