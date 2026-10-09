# Live damage-order probe

Temporary BepInEx test helper for a development character in a local proof world. It does not change the SLS or Epic Loot binaries. It must not be included in the production modpack.

Build against the game version under test:

```sh
dotnet build live_probe/ShrineDamageProbe.csproj \
  -p:GameAssembly=/path/to/assembly_valheim.dll
```

`GameInstall` and `GameManaged` can also be passed as MSBuild properties. The defaults point to a macOS Steam installation. Deploy only the resulting `ShrineDamageProbe.dll` to the leased test client's maintained profile. Back up its profile, metadata, and test character first.

Commands through valheimCLI:

```text
sb_order
sb_hit Greydwarf
sb_hit Troll
```

Wait at least 18 seconds between hit commands. `sb_order` records the actual game version, loaded SLS/Epic Loot SHA-256 hashes, and Harmony's sorted Character.Damage prefixes. It then installs observers around the two relevant patch methods, Character.Damage, RPC_Damage, and ApplyDamage. The observers log values without modifying the hit. The added Character.Damage observer has first priority; it does not add ordering constraints between the original patches. A second `sb_order` shows the resulting list.

`sb_hit` requires a local world. It temporarily unequips the development character's equipment, equips a disposable spear with only 52.5% poison conversion, and creates a test creature. It marks that creature spawn-managed through SLS, as the shrine integration does. It sets level 1 and 10,000 health, waits for initialization, then sends one HitData with 100 poison through Character.Damage. It logs each patch boundary and actual HP changes for 15 seconds. It then destroys the creature, removes the disposable weapon, and restores the previous equipment.

This isolates patch order. It is not a normal spear swing, attack-cadence test, random-proc test, or multiplayer-owner test. The damage types and HP losses are evidence; the test creature's artificial health is not a balance recommendation. Always inspect the cleanup line and exception window. Restore the saved character and original profile after testing, including generated files, then remove the helper and stop the client.
