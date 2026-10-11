# Three-tier workshop — not deployable configs

No server files were changed. These are simulator inputs and outputs for discussion, not Fortress YAML or a deployment payload.

All three tiers use the same recorded Snuffiss build: quality-3 blood/lightning spear, Spears 100, recorded Epic Loot and shardstones, no Crown, 672.448 starting health, full-strength health food, and full stamina for each isolated target. Primary spear attacks only; no weapon swapping, blocking, protective magic, healing, lifesteal, dodging, movement, enemy healing, or stagger. Median results use 2,000 seeded trials per creature. Sizes are capped at 1.5x on production; geometry is not simulated.

The comparison deliberately freezes the October 9 game/mod calculation baseline and observed SLS-before-conversion order. Current production SLS 1.24.0 has a different binary and has not had equivalent controlled-hit validation. A read-only production check confirmed health per star 1, damage per star 0.25, and no health/damage overrides for these new creature prefabs. This does not validate current runtime patch order. No wave-clear times or win probabilities are claimed.

Creature data was extracted directly from the same archived production game bundle whose SHA-256 is in `creature-source-data.json`. It includes asset paths, health, native resistances, and typed weapon damage. `snuffiss-three-tiers.json` retains the original player inputs and adds the new targets; all use the original recorded SLS damage-received factors. Creature attacks use the primary physical damage only, excluding environmental chop/pickaxe damage. Draugr axe and bow both have 48 physical base damage. Golem representative attacks have 110. Oozer poison is a 115 base payload, not an immediate hit.

| Tier | Creature / role | Stars | HP | Required modifiers | Median HTK | Median TTK | HTD |
|---|---|---:|---:|---|---:|---:|---:|
| Black Forest | Greydwarf / fodder | 19 | 800 | None | 2 | 1.31 s | 327 |
| Black Forest | Brute / standard | 25 | 3,900 | Lightning, Frost | 6 | 5.15 s | 6 |
| Black Forest | Shaman / support | 20 | 1,260 | None | 3 | 2.27 s | 300, melee only |
| Black Forest | Bear / elite | 19 | 10,000 | Lightning | 16 | 15.34 s | 5, bite |
| Black Forest | Troll / finale | 39 | 24,000 | None | 23 | 21.73 s | 4, heavy |
| Swamp | Draugr / standard | 39 | 4,000 | Frost | 6 | 5.15 s | 4 |
| Swamp | Wraith / priority standard | 39 | 4,000 | None | 8 | 7.34 s | 5 |
| Swamp | Oozer / disruption | 9 | 1,500 | None | 3 | 2.27 s | Not modeled |
| Swamp | Abomination / finale | 20 | 16,800 | Frost | 28 | 29.34 s | 5, 80-base attack |
| Mountain | Ulv / fodder | 15 | 800 | None | 2 | 1.31 s | 15, bite |
| Mountain | Wolf / standard | 39 | 3,200 | None | 5 | 4.19 s | 4 |
| Mountain | Fenring / elite | 39 | 12,000 | None | 16 | 14.77 s | 3, leap |
| Mountain | Stone Golem / finale | 24 | 20,000 | None | 35 | 37.47 s | 4, 110-base attack |

HTD is repeated successful representative attacks against normal/low-health armor, without recovery or active defense. Oozer poison and spawned Blobs are not modeled: `base_physical: null` deliberately suppresses incoming damage/HTD rather than labeling the creature harmless. At nine stars, the nominal poison payload is 373.75 before player mitigation and damage-over-time scheduling. Its actual HTD requires poison application/refresh timing and the player's poison-specific defenses. Offense against the Oozer itself is modeled; its children are not.

## Proposed packs

These exact counts are workshop intentions; they have not been translated to Fortress wave-generation rules. Child spawns are additional.

| Wave | Black Forest baseline | Swamp proposal | Mountain proposal |
|---|---|---|---|
| 1 | 6 greydwarves + 2 brute/shaman selections + bear | 3 Draugr + Wraith + Oozer | 3 Ulvs + 2 Wolves + Fenring |
| 2 | Same baseline pack | 4 Draugr + Wraith + Oozer | 4 Ulvs + 2 Wolves + Fenring |
| 3 | Same baseline pack | 3 Draugr + 2 Wraiths + Oozer | 3 Ulvs + 3 Wolves + Fenring |
| 4 | Baseline pack + Troll | 2 Draugr + Wraith + Oozer + Abomination | 3 Ulvs + 2 Wolves + Stone Golem |

The original Black Forest support selections can repeat and reuse the generated outline. These proposed Swamp/Mountain wave counts are not proof that the existing DynamicBoss format produces them.

Swamp increases the number of consequential standard enemies and adds poison/support pressure. Its finale has a 35% longer modeled TTK than the Troll, but allows one more unblocked heavy hit. Mountain's fodder hurts substantially more than greydwarves, its Fenring allows fewer mistakes than the bear, and its finale TTK is 28% above the Abomination. Counts are lower to avoid increasing population, durability, and lethality together. These distinctions do not establish a measured ordering of whole-event difficulty.

The first rejected Abomination draft had 28,000 HP and a 51.34-second median TTK. The final proposal uses fewer stars because health alone does not predict kill time against its resistances. Similarly, Wraith remains a shorter priority fight rather than a long elite fight: more stars raise its damage too aggressively. Snuffiss's poison conversion is particularly important against poison-immune creatures; these numbers do not generalize to builds without it.

Before deployment, resolve Oozer child level/faction/shrine tracking, poison incoming damage, current SLS patch order, and actual pack-clear time. Validate the final creature rules and selection format separately. No new tribute or reward choices have been made.

## Reproduce

From the repository root, run each of `blackforest`, `swamp`, and `mountain`:

```sh
python3 app.py calibrate workshops/three-tiers/swamp.json --weapon workshops/three-tiers/snuffiss-three-tiers.json
```

Each `*-results.json` stores median and 10th/90th percentile HTK/TTK, health, raw damage, damage after defense, and HTD. The shared role ranges are the original broad guardrails; the proposals are deliberately not constrained to a universal percentage increase in all metrics.
