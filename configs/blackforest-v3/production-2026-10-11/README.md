# Production-based configuration candidate

Prepared from a read-only download of Praetoris production on October 11, 2026, then deployed that day at the user's explicit request. The server log reports Fortress 0.38.0 and StarLevelSystem 1.24.0.

## Deployment

Deployed directly through Fortress's server-sync hotreload path without restarting the server. Live source hashes still matched the audited baseline, and the pending scheduled release had no config-copy operations. No modpack or mod-list changes were made.

Original files are backed up on production at `/home/ubuntu/valbalance-deploy-20261011-1QAaxc/original/`. That directory's parent also contains the candidate files, deployment script, reload log, and final validation log.

The first atomic replacement did not trigger the LastWrite watcher; the script restored Levels.yaml and stopped. The successful retry explicitly updated each file timestamp after atomic replacement. Reload and server-to-client sync were confirmed for Levels, WildShrines, and SpawnableCreatures. The intermediate shrine reload warned that aliases were not yet in the catalog. A final shrine reload after the catalog update passed without Fortress warnings or errors.

Already-loaded shrines retain cached definitions until they unload and reload. No encounter was started as part of deployment. Combat balance validation remains outstanding.

Inspection of the deployed Fortress DLL found that its final schema uses `creatureRules`, `minStars`, `maxStars`, and `modifiers: {major: [...]}`. The earlier PR draft's `creatureOverrides`, `minimumStars`, `maximumStars`, and `slsModifiers` fields are not present. Both the parent fragment and this merged candidate now use the deployed schema. Modifier names and powers match production's SLS Modifiers.yaml: Lightning base 0.4/per-level 0.05; Frost base 0.4/per-level 0.01. The deployed SLS DLL contains the spawn-managed API.

The three YAML files in this directory are complete merged candidates, unlike the parent directory's fragments:

- `Levels.yaml`: add all five EndForest aliases to exclusions on all 36 existing challenge/arena levels.
- `WildShrines.yaml`: preserve all seven existing tribute events and exclude the aliases from each; add the 50-Resin challenge to the Black Forest and Plains shrines.
- `SpawnableCreatures.yaml`: preserve existing entries and add the five event aliases.

Parsed-data checks confirmed that existing event settings differ only by the added exclusions, all original creature entries and shrine metadata are preserved, and only the two new tribute events can select these aliases. Both new events retain identical encounter definitions. All generated files round-trip through YAML parsing.

Production's DynamicBoss format matches the candidate, and BaseChallengePoints is 100. No WaveStyles edit is needed. Future events without a creature whitelist must also exclude these aliases; there is no global event-private catalog flag.

Before deployment, verify these production source hashes still match. If they changed, merge again against the current files rather than overwrite newer edits.

| Source file | SHA-256 |
|---|---|
| Levels.yaml | b0487308beefdd91c3f6c8a366548825d61df6038ba3674e4a1261271be2736c |
| WildShrines.yaml | 962d6594f337b90f831d7035701fbff6754f1c2d291b343a63473c9eb452e829 |
| SpawnableCreatures.yaml | ae0010c58a5f73257389bd308d1e1dbc2aee9981305358b25ffe5f6ac7caa784 |
| WaveStyles.yaml | 204a353181d6bb452cd7b5530ef427a24de5482068c932673a1d24d5f0bd4dff |

Apply the exclusions in Levels.yaml and the merged WildShrines.yaml before adding the enabled catalog aliases. Test with freshly loaded shrines. Already-loaded shrine instances cache their old definitions, so file reload logs alone do not prove they use the new exclusions or events.

The production Fortress binary hash is `a130f1a738bdee26f653b4eac8aed1a0e1c8f40c35f1a85c74ca37ba4fdcb346`. The production SLS binary hash is `815d4a3b603b319b055bd8c76de4df7dc78b69e6ef5095459a0e14bd0d9515e6`.

This SLS binary differs from the October 9 controlled-hit evidence. The earlier combat predictions are not verified for this binary. Revalidate damage order and the full encounter on the deployed mod set before claiming calibrated production balance. Rewards remain placeholders.
