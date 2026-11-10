using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using UnityEngine;

namespace ValheimEndgame;

internal static class RewardItems
{
    // Reward prefabs are proven against the item database, which does not change while a
    // world is loaded, and the rules come from a catalog that is replaced only on reload.
    private static ObjectDB? checkedDatabase;
    private static ConditionalWeakTable<RewardCatalog, HashSet<int>> checkedTiers = new();

    /// <summary>Every rewarded player of an Uber fight receives the boss's trophy and a set runestone instead of a next-tier tablet.</summary>
    internal static void ValidateUber(RewardCatalog catalog, string boss)
    {
        Validate(catalog, Tablet.UberTier);
        UberBossDefinition definition = UberBossCatalog.Find(boss) ?? throw new InvalidOperationException("Unknown Uber boss: " + boss);
        if (ObjectDB.instance.GetItemPrefab(definition.Trophy)?.GetComponent<ItemDrop>() == null)
            throw new InvalidOperationException("The Uber trophy prefab is unavailable: " + definition.Trophy);
        EpicLootIntegration.RewardSets(Tablet.UberTier);
    }

    internal static void Validate(RewardCatalog catalog, int tier)
    {
        if (!ReferenceEquals(checkedDatabase, ObjectDB.instance))
        {
            checkedDatabase = ObjectDB.instance;
            checkedTiers = new ConditionalWeakTable<RewardCatalog, HashSet<int>>();
        }
        HashSet<int> tiers = checkedTiers.GetOrCreateValue(catalog);
        if (tiers.Contains(tier)) return;
        catalog.Validate();
        foreach (RewardItem entry in catalog.Items.Where(i => i.Enabled && tier >= i.MinTier && tier <= i.MaxTier))
        {
            if (entry.RandomLegendarySetRune)
            {
                EpicLootIntegration.RewardSets(tier);
                continue;
            }
            if (TabletItem.IsUberPrefab(entry.Prefab))
                throw new InvalidOperationException($"rewards.yaml items.{entry.Id}: Uber tablets come from the Dungeon Master, not the reward pool.");
            GameObject prefab = Prefab(entry, tier);
            if (prefab == null) throw new InvalidOperationException($"rewards.yaml items.{entry.Id}: item prefab {entry.Prefab} is unavailable.");
            ItemDrop? drop = prefab.GetComponent<ItemDrop>();
            if (drop == null) throw new InvalidOperationException($"rewards.yaml items.{entry.Id}: item prefab {entry.Prefab} is unavailable.");
            if (entry.MaxQuantity > drop.m_itemData.m_shared.m_maxStackSize)
                throw new InvalidOperationException($"rewards.yaml items.{entry.Id}: each roll must fit one stack.");
            if (Tablet.TierFromPrefab(prefab.name) > 0 && entry.TabletTheme.Length > 0 && !RoomAssets.HasTheme(entry.TabletTheme))
                throw new InvalidOperationException($"rewards.yaml items.{entry.Id}: tablet theme {entry.TabletTheme} has no enabled rooms.");
        }
        tiers.Add(tier);
    }

    internal static GameObject Prefab(RewardItem item, int tier) => ObjectDB.instance.GetItemPrefab(
        Tablet.TierFromPrefab(item.Prefab) > 0 ? TabletItem.PrefabName(item.TabletTier == 0 ? tier : item.TabletTier) : item.Prefab);

    /// <summary>One member's guaranteed rewards, normal rolls, and event additions. Uber bosses grant a trophy and set rune instead of a tablet.</summary>
    internal static Inventory Roll(RewardCatalog catalog, int tier, double bonus, ZDO? record = null,
        List<EventSnapshot>? events = null, string? uberBoss = null)
    {
        List<ItemDrop.ItemData> items = new();
        if (uberBoss == null)
        {
            Validate(catalog, tier);
            items.Add(NewTablet(ObjectDB.instance.GetItemPrefab(TabletItem.PrefabName(Math.Min(tier + 1, 15))), ""));
        }
        else
        {
            ValidateUber(catalog, uberBoss);
            GameObject trophy = ObjectDB.instance.GetItemPrefab(UberBossCatalog.Find(uberBoss)!.Trophy);
            ItemDrop.ItemData item = trophy.GetComponent<ItemDrop>().m_itemData.Clone();
            item.m_dropPrefab = trophy;
            item.m_stack = 1;
            items.Add(item);
            items.Add(EpicLootIntegration.CreateSetRune(tier));
        }
        int rolls = catalog.Rolls(tier, bonus);
        AppendRolls(catalog, tier, rolls, items);
        if (record != null && events != null) EncounterEvents.AddRewards(record, events, tier, items);
        Inventory inventory = new("Encounter rewards", null, 8, Math.Max(8, (items.Count + 7) / 8));
        foreach (ItemDrop.ItemData item in items)
            if (!inventory.AddItem(item)) throw new InvalidOperationException("Reward roll exceeded the reward inventory capacity.");
        return inventory;
    }

    internal static void AppendRolls(RewardCatalog catalog, int tier, int rolls, List<ItemDrop.ItemData> items)
    {
        Validate(catalog, tier);
        for (int roll = 0; roll < rolls; roll++)
        {
            int rarity = SelectRarity(catalog);
            List<(RewardItem item, double weight)> choices = catalog.Eligible(catalog.Fallback(rarity, tier), tier);
            double target = UnityEngine.Random.value * choices.Sum(c => c.weight);
            RewardItem entry = choices.Last().item;
            foreach ((RewardItem item, double weight) choice in choices)
            {
                target -= choice.weight;
                if (target <= 0) { entry = choice.item; break; }
            }
            ItemDrop.ItemData item;
            GameObject? prefab = entry.RandomLegendarySetRune ? null : Prefab(entry, tier);
            if (prefab == null)
                item = EpicLootIntegration.CreateSetRune(tier);
            else if (Tablet.TierFromPrefab(prefab.name) > 0)
                item = NewTablet(prefab, entry.TabletTheme);
            else
            {
                item = prefab.GetComponent<ItemDrop>().m_itemData.Clone();
                item.m_dropPrefab = prefab;
                item.m_stack = UnityEngine.Random.Range(entry.MinQuantity, entry.MaxQuantity + 1);
            }
            items.Add(item);
        }
    }

    // A new tablet: the configured theme or a random one, and all attempts.
    private static ItemDrop.ItemData NewTablet(GameObject prefab, string theme)
    {
        ItemDrop.ItemData item = prefab.GetComponent<ItemDrop>().m_itemData.Clone();
        item.m_dropPrefab = prefab;
        item.m_stack = 1;
        Tablet tablet = Tablet.Read(item) ?? throw new InvalidOperationException("Invalid tablet prefab: " + prefab.name);
        tablet.Theme = theme.Length > 0 ? theme : RoomAssets.RollTheme();
        tablet.Attempts = Tablet.DefaultAttempts;
        tablet.Save();
        return item;
    }

    private static int SelectRarity(RewardCatalog catalog)
    {
        double higher = 0;
        for (int index = 0; index < catalog.Rarities.Count; index++)
        {
            double probability = catalog.Rarities[index].Probability;
            double check = probability / (1 - higher);
            if (probability > 0 && (check >= 1 || UnityEngine.Random.value < check)) return index;
            higher += probability;
        }
        return catalog.Rarities.FindLastIndex(r => r.Probability > 0);
    }

}
