using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;

namespace ValheimEndgame;

public sealed class TabletEffects
{
    internal static readonly Dictionary<string, string> CountedTotems = new()
    {
        ["VE_SlowTotems"] = "movement", ["VE_AttackSlowTotems"] = "attack",
        ["VE_EitrTotems"] = "eitr", ["VE_HealthTotems"] = "health",
        ["VE_ProtectionTotems"] = "protection", ["VE_FrostTotems"] = "frost",
        ["VE_FireTotems"] = "flame", ["VE_FireballTotems"] = "fireball",
        ["VE_IceShardTotems"] = "iceshard", ["VE_MistileTotems"] = "mistile"
    };
    public Dictionary<string, int> TotemCounts { get; set; } = new();

    internal int TotemCount(bool selected, string kind)
    {
        if (!selected) return 0;
        // Encounters saved before count rolls have selected flags but no count mapping.
        int count = TotemCounts.TryGetValue(kind, out int saved) ? saved : 1;
        if (count < 1 || count > 4) throw new InvalidOperationException("Totem count must be between 1 and 4.");
        return count;
    }
    internal bool HasModifiers { get; set; }
    public double LootBonusPercent { get; set; }
    // Each modifier's share of LootBonusPercent, for player-facing explanations only.
    internal List<RewardContribution> RewardContributions { get; } = new();
    public Dictionary<string, float> PopulationByRole { get; set; } = new();
    public int ExtraBossesPerWave { get; set; }
    public bool BearTraps { get; set; }
    public bool Ballistae { get; set; }
    public bool Tentacles { get; set; }
    public bool BroodPods { get; set; }
    public bool Roots { get; set; }
    public bool ShamanShields { get; set; }
    public bool SlowTotems { get; set; }
    public bool AttackSlowTotems { get; set; }
    public bool EitrTotems { get; set; }
    public bool HealthTotems { get; set; }
    public bool ProtectionTotems { get; set; }
    public bool FrostTotems { get; set; }
    public bool FireTotems { get; set; }
    public bool FireballTotems { get; set; }
    public bool IceShardTotems { get; set; }
    public bool MistileTotems { get; set; }
    public float ProtectionReductionPercent { get; set; } = 20;
    public float TotemRadius { get; set; } = 12;
    public float MovementSlowPercent { get; set; } = 20;
    public float AttackSlowPercent { get; set; } = 20;
    public float EitrDrainPercent { get; set; } = 5;
    public float HealthDrainPercent { get; set; } = 5;
    public float FireDamage { get; set; } = 100;
    public float FrostDamage { get; set; } = 90;
    public float HazardDamagePerTierPercent { get; set; } = 10;
    public float FireballOrbDamage { get; set; } = 100;
    public float IceShardOrbDamage { get; set; } = 100;
    public float MistileOrbDamage { get; set; } = 100;
    public List<ForcedCreatureModifier> ForcedModifiers { get; set; } = new();
}

internal sealed class RewardContribution
{
    internal RewardContribution(string label, double percent) { Label = label; Percent = percent; }
    internal string Label { get; }
    internal double Percent { get; }
}

public sealed class ForcedCreatureModifier
{
    public string Name { get; set; } = "";
    public int Type { get; set; }
}

internal static class EpicLootIntegration
{
    private static readonly Dictionary<string, (string role, string label)> populationEffects = new()
    {
        ["VE_PopulationStandard"] = ("standard", "standard monsters"),
        ["VE_PopulationSupport"] = ("magic", "support monsters"),
        ["VE_PopulationElite"] = ("rare", "elite monsters"),
        ["VE_PopulationBosses"] = ("boss", "bosses and minibosses")
    };
    internal static string ModifierCategory(string effect)
    {
        if (populationEffects.ContainsKey(effect)) return "population";
        if (effect.StartsWith("VE_SLS_", StringComparison.Ordinal) || effect == "VE_ShamanShields") return "creatures";
        if (effect.EndsWith("Totems", StringComparison.Ordinal)) return "totems";
        return "hazards";
    }

    internal static double RewardBonus(RewardCatalog rewards, string effect, double value)
    {
        double bonus = rewards.Rules.ModifierDifficulty.TryGetValue(effect, out double configured)
            ? configured : rewards.Rules.CategoryDifficulty[ModifierCategory(effect)];
        // Population scales per DifficultyPer of strength; totems scale per totem spawned each wave.
        return rewards.PopulationModifiers.TryGetValue(effect, out PopulationModifier population)
            ? bonus * value / population.DifficultyPer
            : ModifierCategory(effect) == "totems" ? bonus * value : bonus;
    }
    private static readonly Dictionary<string, string> registeredEffects = new();
    private static readonly Dictionary<string, string> effectTexts = new();
    internal static string RegisteredEffectNames => string.Join(", ", registeredEffects.Keys);
    private static readonly Dictionary<string, ForcedCreatureModifier> forcedEffects = new();
    private const string SlsAvailableRequirement = "warpalicious.ValheimEndgame.SlsAvailable";
    private static bool slsRequirementRegistered;
    private static readonly Dictionary<string, string> hazards = new()
    {
        ["BearTraps"] = "The room contains bear traps",
        ["Ballistae"] = "The room contains hostile ballistae",
        ["Tentacles"] = "The room contains hostile tentacles",
        ["BroodPods"] = "The room contains Seeker brood pods",
        ["Roots"] = "The room contains hostile Elder roots",
        ["ShamanShields"] = "Creatures spawn with a Fuling Shaman shield",
        ["SlowTotems"] = "Movement-slowing totems +{0}",
        ["AttackSlowTotems"] = "Attack-slowing totems +{0}",
        ["EitrTotems"] = "Eitr-draining totems +{0}",
        ["HealthTotems"] = "Health-draining totems +{0}",
        ["ProtectionTotems"] = "Protection totems +{0}",
        ["FrostTotems"] = "Frost-pulse totems +{0}",
        ["FireTotems"] = "Fire-pulse totems +{0}",
        ["FireballTotems"] = "Fireball totems +{0}",
        ["IceShardTotems"] = "Ice Shard totems +{0}",
        ["MistileTotems"] = "Mistile totems +{0}"
    };
    private static Type Api => Type.GetType("EpicLoot.API, EpicLoot", true)!;
    private static object? Call(string name, params object[] args) =>
        (Api.GetMethod(name, BindingFlags.Public | BindingFlags.Static) ?? throw new MissingMethodException("Epic Loot " + name)).Invoke(null, args);

    internal static int SetRewardRarity(int tier)
    {
        if (tier < 1 || tier > 15) throw new ArgumentOutOfRangeException(nameof(tier));
        // Epic Loot rarity ordinals: Legendary = 3, Mythic = 4, Ancient = 5.
        return tier <= 3 ? 3 : tier <= 6 ? 4 : 5;
    }

    // Resolving the sets costs one reflected call per registered legendary item. The
    // registrations change only when Epic Loot reloads its definitions with the world.
    private static ObjectDB? knownSetsFrom;
    private static readonly Dictionary<int, IReadOnlyList<string>> knownSets = new();

    internal static IReadOnlyList<string> RewardSets(int tier)
    {
        int rarity = SetRewardRarity(tier);
        if (!ReferenceEquals(knownSetsFrom, ObjectDB.instance))
        {
            knownSets.Clear();
            knownSetsFrom = ObjectDB.instance;
        }
        if (knownSets.TryGetValue(rarity, out IReadOnlyList<string> cached)) return cached;
        if (Call("GetApiVersion") is not int version || version < 4 ||
            Api.GetMethod("CreateMagicItem", new[] { typeof(string), typeof(string).MakeByRefType() }) == null)
            throw new InvalidOperationException("Set runestone rewards require Epic Loot 0.15.4 with API 4 or newer.");

        // API 4 lists eligible pieces but does not expose their set membership. Resolve it
        // from the registered definitions so custom sets work and uniques are excluded.
        Type helper = Type.GetType("EpicLoot.LegendarySystem.UniqueLegendaryHelper, EpicLoot", true)!;
        MethodInfo lookup = helper.GetMethod("TryGetLegendaryInfo")!;
        MethodInfo membership = helper.GetMethod("GetSetForLegendaryItem")!;
        HashSet<string> sets = new(StringComparer.Ordinal);
        foreach (string id in (IEnumerable<string>)Call("GetLegendaryIDs", rarity)!)
        {
            object[] arguments = { id, null! };
            if (lookup.Invoke(null, arguments) is true &&
                membership.Invoke(null, new[] { arguments[1] }) is string set && !string.IsNullOrWhiteSpace(set))
                sets.Add(set);
        }
        if (sets.Count == 0)
            throw new InvalidOperationException($"Epic Loot has no registered sets available at rarity {rarity} for the tier {tier} completion reward.");
        IReadOnlyList<string> result = Array.AsReadOnly(sets.OrderBy(set => set, StringComparer.Ordinal).ToArray());
        knownSets.Add(rarity, result);
        return result;
    }

    internal static ItemDrop.ItemData CreateSetRune(int tier)
    {
        IReadOnlyList<string> sets = RewardSets(tier);
        string set = sets[UnityEngine.Random.Range(0, sets.Count)];
        string request = Yaml.JsonWriter.Serialize(new
        {
            Runestone = true, Rarity = SetRewardRarity(tier), SetID = set, Effects = Array.Empty<object>()
        });
        object[] arguments = { request, "" };
        if (Call("CreateMagicItem", arguments) is not ItemDrop.ItemData item)
            throw new InvalidOperationException("Epic Loot could not create the completion set runestone: " + arguments[1]);
        item.m_stack = 1;
        return item;
    }

    internal static void Register()
    {
        if (!slsRequirementRegistered)
        {
            Func<ItemDrop.ItemData, object, string, bool, bool, bool, bool> requirement =
                (item, magicItem, effectType, lootRoll, augmentRoll, runeRoll) =>
                    forcedEffects.TryGetValue(effectType, out ForcedCreatureModifier modifier) &&
                    SlsIntegration.IsAvailable(modifier);
            if (Call("RegisterMagicEffectRequirement", SlsAvailableRequirement, requirement) is not true)
                throw new InvalidOperationException("Epic Loot could not register the tablet SLS availability requirement.");
            slsRequirementRegistered = true;
        }
        TabletBalance balance = Plugin.Instance?.Catalog?.Tablets ?? new TabletBalance();
        RewardCatalog rewards = Plugin.Instance?.Catalog?.Rewards ?? ConfigurationLoader.LoadRewardDefaults();
        Dictionary<string, (string text, string description, float value)> effects = new();
        foreach (KeyValuePair<string, (string role, string label)> population in populationEffects)
            effects.Add(population.Key, (population.Value.role == "boss"
                    ? "More " + population.Value.label + " +{0}"
                    : "More " + population.Value.label + " +{0}%",
                population.Value.role == "boss"
                    ? "Adds {0} bosses or minibosses per wave, shared across existing boss and miniboss entries. Waves without bosses or minibosses are unchanged."
                    : "Increases the number of " + population.Value.label + " in each wave by {0}%. Each creature entry rounds up to a whole creature. Waves without this role are unchanged.",
                1));
        foreach (KeyValuePair<string, string> hazard in hazards)
            effects.Add("VE_" + hazard.Key, (hazard.Value, TabletEffectDescriptions.Hazard(hazard.Key, balance), 1));
        foreach (ForcedCreatureModifier modifier in SlsIntegration.AvailableModifiers())
        {
            string id = "VE_SLS_" + modifier.Type + "_" + BitConverter.ToString(Encoding.UTF8.GetBytes(modifier.Name)).Replace("-", "");
            forcedEffects[id] = modifier;
            effects[id] = ("All monsters have " + modifier.Name, TabletEffectDescriptions.Creature(modifier.Name), 1);
        }
        foreach (KeyValuePair<string, (string text, string description, float value)> pair in effects)
        {
            effectTexts[pair.Key] = pair.Value.text;
            string[] exclusive = forcedEffects.TryGetValue(pair.Key, out ForcedCreatureModifier forced)
                ? forcedEffects.Where(other => other.Key != pair.Key && other.Value.Name == forced.Name).Select(other => other.Key).ToArray()
                : Array.Empty<string>();
            object range = new { MinValue = pair.Value.value, MaxValue = pair.Value.value, Increment = 1 };
            PopulationModifier? population = rewards.PopulationModifiers.TryGetValue(pair.Key, out PopulationModifier configured) ? configured : null;
            Dictionary<string, object> ranges = population != null
                ? population.Ranges.ToDictionary(entry => entry.Key, entry => (object)new { MinValue = entry.Value.Min, MaxValue = entry.Value.Max, Increment = 1 })
                : TabletEffects.CountedTotems.ContainsKey(pair.Key)
                    ? PopulationModifier.Rarities.Select((rarity, index) => new { rarity, maximum = Math.Min(index + 1, 4) })
                        .ToDictionary(entry => entry.rarity, entry => (object)new { MinValue = 1, MaxValue = entry.maximum, Increment = 1 })
                    : PopulationModifier.Rarities.ToDictionary(rarity => rarity, _ => range);
            string json = Yaml.JsonWriter.Serialize(new
            {
                Type = pair.Key, DisplayText = pair.Value.text,
                Description = pair.Value.description + TabletEffectDescriptions.Reward(pair.Key, rewards), SelectionWeight = 1,
                CanBeAugmented = true, CanBeDisenchanted = false, CanBeRunified = false,
                // Check the active SLS list when Epic Loot selects effects, without rewriting definitions on sync.
                Requirements = new
                {
                    NoRoll = forced?.Name is "Lootbags" or "Alert" or "Big" or "BossSummoner", ExclusiveSelf = true,
                    ExclusiveEffectTypes = exclusive, AllowedItemTypes = new[] { "Tablet" },
                    AllowedRarities = ranges.Keys.ToArray(),
                    ExternalRequirements = forced != null ? new[] { SlsAvailableRequirement } : Array.Empty<string>()
                },
                ValuesPerRarity = ranges
            });
            if (registeredEffects.TryGetValue(pair.Key, out string existing))
            {
                if (Call("UpdateMagicEffect", existing, json) is not true)
                    throw new InvalidOperationException("Epic Loot could not update " + pair.Key);
            }
            else
            {
                if (Call("AddMagicEffect", json) is not string key || key.Length == 0)
                    throw new InvalidOperationException("Epic Loot rejected " + pair.Key);
                registeredEffects.Add(pair.Key, key);
            }
        }
    }

    internal static void Refresh()
    {
        knownSets.Clear();
        if (registeredEffects.Count > 0) Register();
    }

    internal sealed class MagicData
    {
        public int Rarity { get; set; }
        public List<MagicEffect> Effects { get; set; } = new();
    }

    /// <summary>The item's Epic Loot rarity ordinal (Magic 0 to Ancient 5), or -1 when it is not enchanted.</summary>
    internal static int Rarity(ItemDrop.ItemData item)
    {
        string? json = Call("GetMagicItemJson", item) as string;
        if (string.IsNullOrWhiteSpace(json)) return -1;
        int rarity = Yaml.CompatibleReader.Deserialize<MagicData>(json!).Rarity;
        if (rarity < 0 || rarity > 5) throw new InvalidOperationException("Invalid tablet rarity.");
        return rarity;
    }
    internal sealed class MagicEffect
    {
        public string EffectType { get; set; } = "";
        public float EffectValue { get; set; }
    }
    private static string EffectLabel(string effect, float value) => effectTexts.TryGetValue(effect, out string text)
        ? string.Format(System.Globalization.CultureInfo.InvariantCulture, text, value.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture))
        : effect;

    internal static TabletEffects Read(ItemDrop.ItemData item)
    {
        TabletBalance balance = Plugin.Instance!.Catalog!.Tablets;
        TabletEffects result = new()
        {
            ProtectionReductionPercent = balance.ProtectionReductionPercent,
            TotemRadius = balance.TotemRadius, MovementSlowPercent = balance.MovementSlowPercent,
            AttackSlowPercent = balance.AttackSlowPercent, EitrDrainPercent = balance.EitrDrainPercent,
            HealthDrainPercent = balance.HealthDrainPercent,
            FireDamage = balance.FireDamage, FrostDamage = balance.FrostDamage,
            HazardDamagePerTierPercent = balance.HazardDamagePerTierPercent,
            FireballOrbDamage = balance.FireballOrbDamage, IceShardOrbDamage = balance.IceShardOrbDamage, MistileOrbDamage = balance.MistileOrbDamage
        };
        string? json = Call("GetMagicItemJson", item) as string;
        if (string.IsNullOrWhiteSpace(json)) return result;
        MagicData data = Yaml.CompatibleReader.Deserialize<MagicData>(json!);
        result.HasModifiers = data.Effects.Count > 0;
        HashSet<string> seen = new();
        foreach (MagicEffect effect in data.Effects)
        {
            if (!seen.Add(effect.EffectType) || float.IsNaN(effect.EffectValue) || float.IsInfinity(effect.EffectValue) ||
                effect.EffectValue < 0 || effect.EffectValue > 500) throw new InvalidOperationException("Invalid tablet magic effect.");
            RewardCatalog rewards = Plugin.Instance!.Catalog!.Rewards!;
            bool population = populationEffects.TryGetValue(effect.EffectType, out (string role, string label) populationInfo);
            double bonus = RewardBonus(rewards, effect.EffectType, effect.EffectValue);
            result.LootBonusPercent += bonus;
            result.RewardContributions.Add(new RewardContribution(EffectLabel(effect.EffectType, effect.EffectValue), bonus));
            if (population)
            {
                if (populationInfo.role == "boss")
                {
                    if (effect.EffectValue != Math.Floor(effect.EffectValue) ||
                        effect.EffectValue > rewards.PopulationModifiers[effect.EffectType].Ranges.Values.Max(range => range.Max))
                        throw new InvalidOperationException("This tablet uses an unsupported boss count. Create a new tablet with current effects.");
                    result.ExtraBossesPerWave = (int)effect.EffectValue;
                }
                else result.PopulationByRole[populationInfo.role] = 1 + effect.EffectValue / 100;
                continue;
            }
            if (forcedEffects.TryGetValue(effect.EffectType, out ForcedCreatureModifier forced))
            {
                if (result.ForcedModifiers.Any(existing => existing.Name == forced.Name))
                    throw new InvalidOperationException("Conflicting tablet SLS modifier " + forced.Name + ". Create a new tablet with current effects.");
                result.ForcedModifiers.Add(new ForcedCreatureModifier { Name = forced.Name, Type = forced.Type });
            }
            else if (effect.EffectType.StartsWith("VE_", StringComparison.Ordinal) && hazards.ContainsKey(effect.EffectType.Substring(3)))
            {
                if (TabletEffects.CountedTotems.TryGetValue(effect.EffectType, out string kind))
                {
                    if (effect.EffectValue != Math.Floor(effect.EffectValue) || effect.EffectValue < 1 || effect.EffectValue > 4)
                        throw new InvalidOperationException("Totem modifiers require a whole spawn count from 1 to 4.");
                    result.TotemCounts[kind] = (int)effect.EffectValue;
                }
                typeof(TabletEffects).GetProperty(effect.EffectType.Substring(3))!.SetValue(result, true);
            }
            else throw new InvalidOperationException("Unsupported tablet effect " + effect.EffectType + ". Create a new tablet with current effects.");
        }
        return result;
    }
}

public sealed class TabletBalance
{
    public float ProtectionReductionPercent { get; set; } = 20;
    public float TotemRadius { get; set; } = 12;
    public float MovementSlowPercent { get; set; } = 20;
    public float AttackSlowPercent { get; set; } = 20;
    public float EitrDrainPercent { get; set; } = 5;
    public float HealthDrainPercent { get; set; } = 5;
    public float FireDamage { get; set; } = 100;
    public float FrostDamage { get; set; } = 90;
    public float HazardDamagePerTierPercent { get; set; } = 10;
    public float FireballOrbDamage { get; set; } = 100;
    public float IceShardOrbDamage { get; set; } = 100;
    public float MistileOrbDamage { get; set; } = 100;
}

public sealed class PopulationModifier
{
    internal static readonly string[] Rarities = { "Magic", "Rare", "Epic", "Legendary", "Mythic", "Ancient" };
    public double DifficultyPer { get; set; }
    public Dictionary<string, PopulationRange> Ranges { get; set; } = new();

    internal void Validate(bool bosses)
    {
        string[] allowed = bosses ? Rarities.Skip(2).ToArray() : Rarities;
        if (double.IsNaN(DifficultyPer) || double.IsInfinity(DifficultyPer) || DifficultyPer < .01 || DifficultyPer > 500 ||
            Ranges == null || Ranges.Count != allowed.Length || allowed.Any(rarity => !Ranges.ContainsKey(rarity)) ||
            Ranges.Values.Any(range => range == null || range.Min < 1 || range.Max < range.Min || range.Max > (bosses ? 20 : 500)))
            throw new ArgumentException("Population modifiers require a positive difficultyPer and whole-number ranges for each allowed rarity; boss counts are limited to 20 per wave.");
    }
}

public sealed class PopulationRange
{
    public int Min { get; set; }
    public int Max { get; set; }
}
