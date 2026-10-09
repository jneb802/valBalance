# Observed SLS/Epic Loot damage order

**SLS damage-received scaling runs before Epic Loot poison conversion** on the tested Valnet client 02 baseline. Both prefixes have Harmony priority 400 and no explicit before/after constraints. SLS registers at index 1; Epic Loot's early prefix registers at index 3. The order was the same on two client starts, including after removal of identical duplicate DLLs.

Environment: Valheim Linux client `l-1.0.16`; Season 8 8.0.39 client mod set; shared DLLs and SLS/Epic Loot combat configuration matched to deployed production. The original Valnet 02 profile was 8.0.34 and was backed up before temporary alignment. The probe printed hashes from the actual loaded assemblies:

- SLS: `c0ecc08ea9a17bc62311b6dee98ca03a0325c32bec5bec36bd096975605c3b6f`
- Epic Loot: `802790e0cbd8a6f951627619a488b84e6a406e8770e2687b2fff8b63d2adf9ea`
- Linux client game assembly: `68f3baa9454653e5d3cdde49ad8932d36c13716caaa15b352aa3fb530ad63d9c`

## Controlled hits

The local `TestingWorld` tests used a development character, a disposable weapon with only 52.5% poison conversion, 100 incoming poison, and spawn-managed level-1 targets with artificial 10,000 HP. No random critical or chain effects were equipped. The observer logged actual patch entry/exit and actual HP changes.

| Stage | Greydwarf, repeated twice | Troll |
|---|---|---|
| Input | 100 poison | 100 poison |
| After SLS | 150 poison | 150 poison |
| After conversion | 78.75 fire + 71.25 poison | 78.75 pierce + 71.25 poison |
| Immediate HP loss | 0 | 118.125 |
| Fire ticks | 5 × 31.5 | None |
| Poison ticks | 7 × 5.9375 | 10 × approximately 7.9166665 |
| Observed total HP loss | 199.0625 | 197.295 |

The troll's cumulative HP differs from a float64 sum by approximately 0.0033 due to float32 HP updates. The regression test permits 0.005 aggregate rounding error and checks individual typed damage separately.

`controlled-hits.log` preserves the probe lines. `controlled-hits.json` contains the extracted fixture. `restart-order.log` preserves the first process's version/hash/order observations. The second process also logs its order before each hit. The first helper attempt failed when its unmanaged creature disappeared; it was corrected to use the shrine's spawn-managed API before collecting these three complete hit traces.

## Proven scope and remaining limits

The trace confirms the local attacking-client patch order, conversion type, native resistance, per-tick damage, and actual HP changes for these controlled hits. Character.Damage executes on the attacking client; RPC_Damage executes on the target owner. In this local test they are the same process. Remote ownership, dedicated multiplayer, full spear swings, random chains, and shrine waves were not tested.

The observed status ticks were about 1.02 seconds apart, with the first tick on the following status update. The encounter simulator still uses nominal one-second DoT scheduling and immediate first updates. These traces therefore do not certify its exact TTK. Its attack cadence and stamina scheduling also remain nominal. The `events` command can evaluate authoritative HP-change traces directly when measured timing is required.

There were no warnings or errors between the first controlled hit and the last cleanup. Startup did emit Linux shader errors, content/config warnings, and eight PieceManager snapshot exceptions in `ZDOMan.AddIfPortal` before the tests. Those concern asset/piece initialization and did not interrupt the traced damage sequence. This is scoped damage-path evidence, not a clean bill of health for the full mod set.

The default scenario now uses the observed order. Changing the recorded game version or SLS/Epic Loot hash rejects that evidence. Other mod changes can also alter ordering despite matching these two hashes; rerun the probe after changing the mod set. No ordering constraint was added to SLS or Epic Loot.
