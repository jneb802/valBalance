# Ten-tier Fortress configuration drafts

These are actual Fortress YAML merge fragments using `creatureRules`, `minStars`
and `maxStars`. They use the existing ten-tier star-only results without a new
balance pass. They have not been installed locally or deployed to production.

All ten entries target `VF_wild_shrine_yellow1`. Each costs 50 of its tribute:

| Tier | Event | Tribute |
|---|---|---|
| 1 | Black Forest | Resin |
| 2 | Swamp | Guck |
| 3 | Mountain | Crystal |
| 4 | Plains | BlackMetal |
| 5 | Mistlands bugs | SeekerMeat |
| 6 | Mistlands dvergr | Softtissue |
| 7 | Ashlands | CharredBone |
| 8 | Deep North | FreezeGland |
| 9 | Mixed elites | Amber |
| 10 | Mixed finale | Ruby |

Tributes for tiers 3–10 are provisional test selectors. Rewards retain the test
amounts (10 each DustRare, EssenceRare, ReagentRare); reward progression is not
balanced. The MWL interaction previously supported Resin/Guck only. Additional
selectors need MWL support before these can all be offered through that dungeon
interaction. Configuration alone does not extend its item handling.

## Files and merge requirements

- `SpawnableCreatures.fragment.yaml`: 41 namespaced aliases, drops disabled.
- `WildShrines.fragment.yaml`: ten tribute entries, exact stars, no required SLS affixes.
- `WaveStyles.fragment.yaml`: CommonOnly pack format plus the existing DynamicBoss format.
- `UnrelatedLevels.exclusions.yaml`: list to append to unrelated levels' `excludeSelectMonsters`.
- `index.yaml`: entry map, required budget, and source summary hash.

These are merge fragments, not replacement files. Update the yellow shrine's
matching tribute entries by name; preserve its localization and unrelated entries.
Do not append duplicate Resin/Guck entries. Merge the catalogue by alias name.
Before enabling the aliases, append the exclusion list to every unrelated normal
challenge and wild tribute definition that can select them. New entries already
whitelist only their own aliases. Aliases alone do not isolate creatures from
unrestricted events. Preserve existing exclusions when adding this list.

Wave-style names are enum values in the inspected Fortress source. CommonOnly is
shared configuration: audit all existing references before replacing its format.
If another event relies on the old format, resolve that conflict before installation.
DynamicBoss here reproduces the inspected existing format. No novel unsupported
wave-style name is invented.

## Wave count calculation

Requires `BaseChallengePoints = 100` and `MaxChallengePoints >= 100`.
`levelIndex` remains 1 for every event to keep its spawn budget fixed. Shrine tier
is expressed through its creature stars, not Fortress's challenge-point index.
Wild levels fall back to four phases; unique creatures spawn only in the last.

Fortress computes each segment as `points * percentage / 100 / spawnCost`,
applies ±10% randomness, truncates to an integer, then ensures at least one spawn.
CommonOnly uses 45/25/15 percent for common/rare/elite. With costs 10/10/10,
the ranges are 4.05–4.95, 2.25–2.75, and 1.35–1.65: exactly 4/2/1 enemies.
Mountain common cost 13 gives 3.115–3.808: three Ulvs. Unique count is forced to one.
Black Forest uses two common segments at 20%/cost6 (three each), two support
segments at 20%/cost20 (one each), and one elite. Support selections may repeat.
The generated outline is reused across phases. Phase caps include the finale boss.

Fortress terminology differs from our design: normal -> common, magic -> rare,
rare -> elite, and boss -> unique. Mixed-tier aliases use DeepNorth as their
catalogue selection biome so the chosen creatures pass the same-biome filter;
this does not change their native creature behavior or faction.

## Validation and remaining limits

Schema fields and wave arithmetic were checked against the local Fortress source.
Python tests check catalogue references, stars, whitelists, tribute uniqueness,
phase caps and spawn-count bounds. This is not a live game validation.
An empty modifier rule does not suppress random SLS modifiers. Runtime faction
handling, Dvergr hostility, Gjall room clearance, child spawns, and high-star
spell damage remain unresolved as documented in the workshop. These drafts
do not implement those behaviors or claim the events are ready for production.

Regenerate from the saved workshop results:

```sh
python3 configs/ten-tier/generate.py
```
