# Local Swamp test

Installed October 14 in the local mmcli `praetoris-season-8` profile only. Loaded Fortress 0.39.0 and SLS 1.25.1. No production deployment or mod update.

Offer **50 Guck** at the yellow Plains shrine. The existing **50 Resin** Black Forest event remains available.

Four waves: 4 Draugr, 2 Wraiths, and 1 Oozer each wave; the final wave also has 1 Abomination as the main boss. These are initial counts, excluding Oozer children. Stats match the workshop: Draugr 39 stars + Frost, Wraith 39 stars, Abomination 20 stars + Frost, Oozer 9 stars.

This is a supported approximation of the revised workshop schedule. The installed schema selects one wave format per event. Rules can vary stars/modifiers by wave, but cannot specify an arbitrary creature roster per wave. The local `CommonOnly` format was unused by all existing wild/challenge/arena events, so it is repurposed for this test. Its name is an enum identifier; its slot contents now include common, rare, elite, and unique categories. Do not merge this format blindly into another profile.

At the verified 100-point budget, common 40% with cost 9 produces 4 Draugr across the full random count range. Rare 40% with cost 18 produces 2 Wraiths. Elite 20% with cost 20 produces 1 Oozer under the minimum-one rule. Unique produces 1 Abomination in the last wave. The maximum is 8 initial creatures. All phase count modifiers are empty.

All existing local events explicitly exclude the four EndSwamp aliases; the new event exclusively selects them. Original creature entries and Black Forest rules are preserved. Rewards are copied placeholders from the Black Forest test.

Backups of Levels.yaml, WildShrines.yaml, WaveStyles.yaml, and SpawnableCreatures.yaml are outside the loaded profile at `/Users/benjmarston/.config/mmcli/swamp-local-z7ynm4pq/`. Leave the test installed for the user's local-world session. Connecting to production can overwrite synced configs.

These fragments are not full replacement files. When installing elsewhere, preserve existing events, verify CommonOnly is unused, and add exclusions to every unrelated event. A loaded shrine may require unloading and reloading to adopt the new tribute. The config install does not validate dungeon spawn placement, creature navigation, Oozer children, or actual encounter balance.
