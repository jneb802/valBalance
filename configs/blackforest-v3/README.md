# The Old Forest — first solo endgame test candidate

This candidate uses Snuffiss's equipped Q3 blood/lightning spear, Spears 100, Epic Loot effects and shardstones, no Crown, and three full-strength health foods. It uses the production 1.0.16 source snapshot. These are **modeled single-target results, not measured live combat times**.

## Selected creatures

| Creature | Role | Stars | Health | Required SLS modifiers | Median HTK | Median TTK | Player HTD |
|---|---|---:|---:|---|---:|---:|---:|
| Greydwarf | Fodder | 19 | 800 | None | 2 | 1.31 s | 327 |
| Greydwarf brute | Standard | 25 | 3,900 | Lightning, Frost | 6 | 5.15 s | 6 |
| Greydwarf shaman | Support | 20 | 1,260 | None | 3 | 2.27 s | 300, melee only |
| Bear (`Bjorn`) | Elite | 19 | 10,000 | Lightning | 16 | 15.34 s | 5, bite |
| Troll | Mini boss | 39 | 24,000 | None | 23 | 21.73 s | 4, heavy hit |

Controlled hits on Valnet client 02 verified **SLS scaling before Epic Loot poison conversion** for the recorded binaries. The same order survived a restart. The table now uses that order; the source profile retains both candidates for sensitivity analysis. All medians fit the selected role ranges. The sampled 10th–90th percentiles are: dwarf 0.34–1.34 s; brute 4.34–6.11 s; shaman 1.31–2.27 s; bear 13.80–16.69 s; troll 19.57–24.36 s. Random critical hits can kill fodder below the 0.5-second target floor.

The shaman falls from the withdrawn draft's 24 stars to 20. The other star choices still fit after recalculation; that does not validate the old placeholder model. Stars set health through `base HP * (1 + stars)`. Lightning and Frost increase incoming damage without adding health. Fodder melee is deliberately weak against this armor. Its role is obstruction and pressure on positioning. Shaman healing is its main threat; its poison attack is not represented by the melee HTD.

| Representative attack | Raw physical | Added lightning | Added frost | HP lost normally | HP lost below 75% health |
|---|---:|---:|---:|---:|---:|
| Greydwarf melee | 80.50 | 0 | 0 | 2.34 | 1.98 |
| Brute melee | 217.50 | 369.75 | 143.55 | 131.52 | 111.43 |
| Shaman melee | 84.00 | 0 | 0 | 2.55 | 2.16 |
| Bear bite | 316.25 | 442.75 | 0 | 165.49 | 140.21 |
| Troll heavy hit | 752.50 | 0 | 0 | 204.04 | 173.22 |

HTD uses 672.448 health, armor that changes at the recorded threshold, and typed resistances. It excludes block, parry, protective magic, healing, lifesteal, and random avoidance. It describes repeated successful hits of the specified attack, not every attack that creature has.

## Four packs

Use the existing `DynamicBoss` wave format with `levelIndex: 1`, normal mode, and the supplied catalog costs. Level 1 produces 100 challenge points in the recorded Season 8 config. It controls **numbers**, not these creatures' individual difficulty.

| Phase | Composition | Total |
|---|---|---:|
| 1 | 6 greydwarves, 2 support selections, 1 bear | 9 |
| 2 | 6 greydwarves, 2 support selections, 1 bear | 9 |
| 3 | 6 greydwarves, 2 support selections, 1 bear | 9 |
| 4 | Same pack plus 1 troll | 10 |

Each support selection is one brute or shaman. Both can select the same creature. The generator chooses its outline once, then reuses it across phases. Therefore, some runs have no shaman or no brute. Guaranteeing one of each needs a selection change or a different format with distinct categories; the supplied config does not claim that guarantee.

The default format has two 20% common slots, two 20% rare slots, one 20% elite slot, and one unique slot. At 100 points, common cost 6 yields three creatures per slot after the generator's ±10% amount variance and truncation. Rare/elite cost 20 yields one per slot after its minimum-one rule. Unique entries always yield one and appear only in the last phase. This is how the finale troll is enforced; `waveOverrides` alone cannot select a creature for a phase.

This is a repeated-pack event with a stronger finale, not the previously proposed bear-free opening. The first test should measure whether simultaneous bear and troll pressure is too high. Do not add isolated-target TTK values to claim a pack-clear time: chain damage, healing, movement, and shared stamina change it.

## Configuration files

1. Merge `SpawnableCreatures.fragment.yaml` into the existing `creatures` map.
2. Append the tribute entry from `WildShrines.fragment.yaml` to the existing `VF_wild_shrine_blue1` definition. Preserve its other tribute entries.
3. Preserve the recorded `DynamicBoss` format. No WaveStyles edit is required.
4. Exclude the five `EndForest*` aliases from unrelated challenge/wild levels that lack an explicit creature whitelist. Enabled catalog aliases are globally eligible; their names do not isolate them to this event.

These are merge fragments, **not complete replacement files**. Creature drops are disabled. The proposed entry cost is three `TrophyFrostTroll` items, whose prefab is in the production manifest. The current rare dust/essence/reagent reward bundle is retained as an economy placeholder, not a calibrated endgame payout. The wild-shrine schema has no boss-completion gate; possession of the tribute does not enforce progression.

Requires the spawn-managed Fortress PR19 implementation and its compatible SLS API. Fixed star bounds bypass ordinary random spawn caps. Required modifier maps do not disable additional random SLS modifiers. Extra health/resistance/damage modifiers can invalidate the table. High stars also affect creature size. Fortress already assigns spawned Humanoids to the Boss faction; this candidate does not require a separate faction mod.

## Reproduce the calculations

From the repository root:

```sh
python3 tools/shrine_balance/app.py calibrate \
  tools/shrine_balance/examples/blackforest-v3.json \
  --weapon tools/shrine_balance/examples/snuffiss-weapon-source.json
```

The checked-in `results.json` contains 2,000 seeded trials per creature under the observed order. `use_verified_patch_order` requires controlled-hit evidence with matching game version and SLS/Epic Loot hashes. Set it to false to compare both candidate orders. These checks do not certify other changes to the mod set; reobserve order after changing it. The model integrates the source animation landmarks into a nominal 0.961404-second successful attack cycle, with the first hit at 0.343993 seconds. It includes random skill damage, double damage, fire accumulation, poison replacement, initial chain hits, and source-form idle stamina recovery.

The explicit scenario assumes a dry, alert, unstaggered target, full player health, no dodge buff, full starting stamina per creature, and no incoming damage. It uses immediate first status/chain updates and continuous idle stamina recovery. Those are simulation scheduling choices; Unity frame timing and network delay remain unmeasured. It excludes chain returns, target healing, movement, stagger damage, and combat-induced health changes. The blood weapon's missing-health bonus means an injured player can kill faster. No exact live TTK is claimed.

## Validation status

32 Python tests and CLI execution pass. Configuration fields, category generation, costs, and final-phase unique behavior were checked against the PR19 source and the Season 8 snapshots. [Live patch-order evidence](../../live_probe/evidence/2026-10-09/README.md) covers two greydwarves and one troll on the aligned Valnet client. It confirms conversion and per-tick damage, not the full shrine encounter or attack cadence. No server files were changed. Production-context validation of the full event remains incomplete.

For live calibration, record spawned stars/modifiers, target HP, attack timestamps and damage types, stamina, player HP, real pack-clear duration, and deaths. Confirm the active patch order and the actual repeat cadence. Prioritize the shaman in the intended test run. Use its survival and healing in a second run to measure the cost of ignoring support.
