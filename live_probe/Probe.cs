using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

[BepInPlugin("odin.shrine.damageprobe", "ShrineDamageProbe", "0.1.0")]
public class ShrineDamageProbe : BaseUnityPlugin
{
    private static ManualLogSource Log;
    private static readonly Harmony Hooks = new Harmony("odin.shrine.damageprobe");
    private static Character Target;
    private static string Case;
    private bool installed;
    private bool busy;

    private void Awake()
    {
        Log = Logger;
        new Terminal.ConsoleCommand("sb_order", "Dump sorted Character.Damage prefixes; install read-only observers", args => Install());
        new Terminal.ConsoleCommand("sb_hit", "Controlled local test: sb_hit Greydwarf|Troll", args =>
        {
            if (busy || args.Length != 2 || (args[1] != "Greydwarf" && args[1] != "Troll"))
                throw new ArgumentException("Use sb_hit Greydwarf or sb_hit Troll, one at a time");
            if (Player.m_localPlayer == null || ZNet.instance == null || !ZNet.instance.IsServer())
                throw new InvalidOperationException("Controlled test requires a local proof world");
            Install();
            StartCoroutine(Run(args[1]));
        });
    }

    private void Install()
    {
        Log.LogInfo("VERSION game=" + global::Version.GetVersionString());
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies().Where(a => a.GetName().Name == "EpicLoot" || a.GetName().Name == "StarLevelSystem"))
        {
            using (System.Security.Cryptography.SHA256 hash = System.Security.Cryptography.SHA256.Create())
                Log.LogInfo($"ASSEMBLY name={assembly.GetName().Name} sha256={BitConverter.ToString(hash.ComputeHash(System.IO.File.ReadAllBytes(assembly.Location))).Replace("-", "").ToLowerInvariant()}");
        }
        MethodInfo original = AccessTools.Method(typeof(Character), "Damage", new[] { typeof(HitData) });
        Patches info = Harmony.GetPatchInfo(original);
        foreach (MethodInfo method in PatchProcessor.GetSortedPatchMethods(original, info.Prefixes.ToArray()))
        {
            Patch patch = info.Prefixes.First(p => p.PatchMethod == method);
            Log.LogInfo($"ORDER owner={patch.owner} priority={patch.priority} index={patch.index} method={method.DeclaringType.FullName}.{method.Name} before={string.Join(",", patch.before)} after={string.Join(",", patch.after)}");
        }
        if (installed) return;
        foreach (Patch patch in info.Prefixes.Where(p => p.PatchMethod.Name == "EarlyPreDamagePatch" || p.PatchMethod.DeclaringType.Name == "CharacterDamageModificationApply"))
        {
            Hooks.Patch(patch.PatchMethod, new HarmonyMethod(typeof(ShrineDamageProbe), nameof(EnterPatch)), new HarmonyMethod(typeof(ShrineDamageProbe), nameof(ExitPatch)));
            Log.LogInfo("OBSERVING " + patch.PatchMethod.DeclaringType.FullName + "." + patch.PatchMethod.Name);
        }
        Hooks.Patch(AccessTools.Method(typeof(Character), "RPC_Damage"),
            new HarmonyMethod(typeof(ShrineDamageProbe), nameof(EnterDamage)), new HarmonyMethod(typeof(ShrineDamageProbe), nameof(ExitDamage)));
        Hooks.Patch(AccessTools.Method(typeof(Character), "ApplyDamage"),
            new HarmonyMethod(typeof(ShrineDamageProbe), nameof(EnterDamage)), new HarmonyMethod(typeof(ShrineDamageProbe), nameof(ExitDamage)));
        Hooks.Patch(original,
            new HarmonyMethod(typeof(ShrineDamageProbe), nameof(EnterDamage)) { priority = Priority.First },
            new HarmonyMethod(typeof(ShrineDamageProbe), nameof(ExitDamage)));
        installed = true;
    }

    private static string Damage(HitData hit) => $"blunt={hit.m_damage.m_blunt:R} slash={hit.m_damage.m_slash:R} pierce={hit.m_damage.m_pierce:R} fire={hit.m_damage.m_fire:R} frost={hit.m_damage.m_frost:R} lightning={hit.m_damage.m_lightning:R} poison={hit.m_damage.m_poison:R} spirit={hit.m_damage.m_spirit:R}";
    private static void EnterPatch(MethodBase __originalMethod, object[] __args) => PatchLog("ENTER", __originalMethod, __args);
    private static void ExitPatch(MethodBase __originalMethod, object[] __args) => PatchLog("EXIT", __originalMethod, __args);
    private static void PatchLog(string stage, MethodBase method, object[] args)
    {
        if (Target == null || !args.Any(a => ReferenceEquals(a, Target))) return;
        HitData hit = args.OfType<HitData>().FirstOrDefault();
        if (hit != null) Log.LogInfo($"TRACE case={Case} t={Time.time:R} {stage} {method.DeclaringType.Name}.{method.Name} {Damage(hit)}");
    }
    private static void EnterDamage(Character __instance, MethodBase __originalMethod, object[] __args) => HealthLog("ENTER", __instance, __originalMethod, __args);
    private static void ExitDamage(Character __instance, MethodBase __originalMethod, object[] __args) => HealthLog("EXIT", __instance, __originalMethod, __args);
    private static void HealthLog(string stage, Character character, MethodBase method, object[] args)
    {
        if (character != Target || Target == null) return;
        HitData hit = args.OfType<HitData>().FirstOrDefault();
        if (hit != null) Log.LogInfo($"TRACE case={Case} t={Time.time:R} {stage} {method.Name} hp={character.GetHealth():R} {Damage(hit)}");
    }

    private IEnumerator Run(string prefab)
    {
        busy = true;
        Player player = Player.m_localPlayer;
        List<ItemDrop.ItemData> equipped = player.GetInventory().GetAllItems().Where(i => i.m_equipped).ToList();
        ItemDrop.ItemData weapon = null;
        GameObject spawned = null;
        try
        {
            foreach (ItemDrop.ItemData item in equipped) player.UnequipItem(item, false);
            weapon = ObjectDB.instance.GetItemPrefab("SpearGold_BloodLightning").GetComponent<ItemDrop>().m_itemData.Clone();
            weapon.m_dropPrefab = ObjectDB.instance.GetItemPrefab("SpearGold_BloodLightning");
            Assembly epic = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "EpicLoot");
            Type magicType = epic.GetType("EpicLoot.MagicItem", true);
            object magic = Activator.CreateInstance(magicType);
            IList effects = (IList)magicType.GetField("Effects").GetValue(magic);
            effects.Add(Activator.CreateInstance(epic.GetType("EpicLoot.MagicItemEffect", true), "PoisonToTrueDamage", 52.5f));
            epic.GetType("EpicLoot.ItemDataExtensions", true).GetMethod("SaveMagicItem").Invoke(null, new[] { weapon, magic });
            if (!player.GetInventory().AddItem(weapon)) throw new InvalidOperationException("No inventory room");
            player.EquipItem(weapon, false);
            spawned = Instantiate(ZNetScene.instance.GetPrefab(prefab), player.transform.position + player.transform.forward * 5, Quaternion.identity);
            Target = spawned.GetComponent<Character>();
            spawned.GetComponent<ZNetView>().ClaimOwnership();
            Assembly sls = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "StarLevelSystem");
            Type api = sls.GetTypes().First(t => t.Name == "APIReciever");
            if (!(bool)api.GetMethod("SetCreatureSpawnManaged").Invoke(null, new object[] { Target, true }))
                throw new InvalidOperationException("SLS did not accept spawn-managed test creature");
            BaseAI ai = spawned.GetComponent<BaseAI>();
            if (ai != null) ai.enabled = false;
            Target.SetLevel(1);
            Target.SetMaxHealth(10000);
            Target.SetHealth(10000);
            yield return new WaitForSeconds(2);
            if (Target == null || spawned.GetComponent<CapsuleCollider>() == null)
                throw new InvalidOperationException("Test creature disappeared before the hit");
            Target.SetHealth(10000);
            IDictionary modifiers = (IDictionary)api.GetMethod("GetAllDamageRecievedModifiers").Invoke(null, new object[] { Target });
            Log.LogInfo("TARGET received modifiers=" + string.Join(",", modifiers.Keys.Cast<object>().Select(k => k + ":" + modifiers[k])));
            Case = prefab + "-" + Time.frameCount;
            HitData hit = new HitData();
            hit.m_damage.m_poison = 100;
            hit.m_skill = Skills.SkillType.Spears;
            hit.m_point = Target.GetCenterPoint();
            hit.m_backstabBonus = 1;
            hit.SetAttacker(player);
            Log.LogInfo($"START case={Case} owner={spawned.GetComponent<ZNetView>().IsOwner()} level={Target.GetLevel()} hp={Target.GetHealth():R} {Damage(hit)}");
            Target.Damage(hit);
            yield return new WaitForSeconds(15);
            Log.LogInfo($"END case={Case} hp={Target.GetHealth():R}");
        }
        finally
        {
            Target = null;
            if (spawned != null) ZNetScene.instance.Destroy(spawned);
            if (weapon != null)
            {
                player.UnequipItem(weapon, false);
                player.GetInventory().RemoveItem(weapon);
            }
            foreach (ItemDrop.ItemData item in equipped) player.EquipItem(item, false);
            busy = false;
            Log.LogInfo("CLEANUP restored equipment and removed probe creature/item");
        }
    }
}
