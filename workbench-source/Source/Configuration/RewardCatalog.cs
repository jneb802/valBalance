using System;
using System.Collections.Generic;
using System.Linq;

namespace ValheimEndgame;

public sealed class RewardCatalog
{
    public int SchemaVersion { get; set; } = 2;
    public List<RewardItem> Items { get; set; } = new();
    // Highest rarity first. Probabilities are overall probabilities, not conditional checks.
    public List<RewardRarity> Rarities { get; set; } = new();
    public RewardRules Rules { get; set; } = new();
    public Dictionary<string, PopulationModifier> PopulationModifiers { get; set; } = new();

    public static RewardCatalog Load(string yaml)
    {
        RewardCatalog result = Yaml.ConfigurationReader.Deserialize<RewardCatalog>(yaml);
        if (result == null) throw new ArgumentException("rewards.yaml must contain a reward catalog.");
        result.Validate();
        Require(result.PopulationModifiers.Count == 4, "populationModifiers", "requires the four tablet population effects");
        return result;
    }

    public void Validate()
    {
        Require(SchemaVersion == 2, "schemaVersion", "must be 2; replace the old base/wave roll settings with difficulty budgets");
        if (Items == null) throw new ArgumentException("rewards.yaml items must contain item definitions.");
        Require(Items.Count > 0 && Items.All(i => i != null), "items", "must contain item definitions");
        Require(Items.Select(i => i.Id).Distinct().Count() == Items.Count, "items", "IDs must be unique");
        foreach (RewardItem item in Items)
        {
            string path = "items." + item.Id;
            Require(!string.IsNullOrWhiteSpace(item.Id) && (item.RandomLegendarySetRune || !string.IsNullOrWhiteSpace(item.Prefab)), path, "requires id and prefab, or a random set reward");
            if (item.RandomLegendarySetRune)
                Require(item.Prefab == "" && item.MinQuantity == 1 && item.MaxQuantity == 1 &&
                    item.TabletTier == 0 && item.TabletTheme == "", path,
                    "random set rewards require quantity 1 and no prefab or tablet settings");
            Require(item.MinTier >= 1 && item.MaxTier <= 15 && item.MinTier <= item.MaxTier, path, "tier range must be within 1–15");
            Require(item.MinQuantity >= 1 && item.MaxQuantity >= item.MinQuantity && item.MaxQuantity <= 1000, path, "quantity range must be within 1–1000");
            Require(item.TabletTier >= 0 && item.TabletTier <= 15, path + ".tabletTier", "must be 0 (encounter tier) or 1–15");
            Require(item.TabletTheme != null, path + ".tabletTheme", "must be a theme name or an empty string");
        }
        if (Rarities == null) throw new ArgumentException("rewards.yaml rarities must contain ordered rarity tables.");
        Require(Rarities.Count > 0 && Rarities.All(r => r != null), "rarities", "must contain ordered rarity tables");
        Require(Rarities.Select(r => r.Id).Distinct().Count() == Rarities.Count, "rarities", "IDs must be unique");
        foreach (RewardRarity rarity in Rarities)
        {
            string path = "rarities." + rarity.Id;
            Require(!string.IsNullOrWhiteSpace(rarity.Id) && Finite(rarity.Probability) && rarity.Probability >= 0 && rarity.Probability <= 1, path, "requires an id and probability between 0 and 1");
            if (rarity.Entries == null) throw new ArgumentException("rewards.yaml " + path + ".entries must be a list.");
            Require(rarity.Entries.All(e => e != null), path + ".entries", "must be a list");
            Require(rarity.Entries.Select(e => e.Item).Distinct().Count() == rarity.Entries.Count, path, "item references must be unique");
            foreach (RewardWeight entry in rarity.Entries)
                Require(Items.Any(i => i.Id == entry.Item) && Finite(entry.Weight) && entry.Weight > 0 && entry.Weight <= 1000000, path + "." + entry.Item, "must reference an item with a positive weight no greater than 1000000");
        }
        Require(Math.Abs(Rarities.Sum(r => r.Probability) - 1) < 0.000001, "rarities", "overall probabilities must sum to 1");
        if (Rules == null) throw new ArgumentException("rewards.yaml rules are required.");
        Require(Finite(Rules.BudgetPerRoll) && Rules.BudgetPerRoll >= .01 && Rules.BudgetPerRoll <= 1000000 &&
            Rules.MaxRolls >= 1 && Rules.MaxRolls <= 10000, "rules", "budgetPerRoll must be 0.01–1000000 and maxRolls must be 1–10000");
        Require(Rules.Tiers != null && Rules.Tiers.Count == 15 && Rules.Tiers.All(t => t != null &&
            Finite(t.Difficulty) && t.Difficulty >= 0 && t.Difficulty <= 1000000 &&
            Finite(t.BonusPercent) && t.BonusPercent >= 0 && t.BonusPercent <= 1000), "rules.tiers", "requires 15 finite difficulty and bonus rows");
        if (Rules.CategoryDifficulty == null || Rules.ModifierDifficulty == null)
            throw new ArgumentException("rewards.yaml rules require categoryDifficulty and modifierDifficulty.");
        foreach (string category in new[] { "population", "hazards", "totems", "creatures" })
            Require(Rules.CategoryDifficulty.TryGetValue(category, out double bonus) && Finite(bonus) && bonus >= 0 && bonus <= 500, "rules.categoryDifficulty." + category, "must be between 0 and 500 percent");
        Require(Rules.ModifierDifficulty.All(p => !string.IsNullOrWhiteSpace(p.Key) && Finite(p.Value) && p.Value >= 0 && p.Value <= 500), "rules.modifierDifficulty", "requires named contributions between 0 and 500 percent");
        Require(PopulationModifiers != null, "populationModifiers", "must be a mapping");
        if (PopulationModifiers!.Count > 0)
        {
            string[] ids = { "VE_PopulationStandard", "VE_PopulationSupport", "VE_PopulationElite", "VE_PopulationBosses" };
            Require(PopulationModifiers.Count == ids.Length && ids.All(id => PopulationModifiers.TryGetValue(id, out PopulationModifier modifier) && modifier != null), "populationModifiers", "requires all four population effects");
            foreach (string id in ids) PopulationModifiers[id].Validate(id == "VE_PopulationBosses");
        }
        for (int tier = 1; tier <= 15; tier++)
            for (int index = 0; index < Rarities.Count; index++)
                if (Rarities[index].Probability > 0)
                    Require(Fallback(index, tier) >= 0, "rarities." + Rarities[index].Id, $"tier {tier} needs an eligible entry in this table or a lower rarity table");
    }

    internal List<(RewardItem item, double weight)> Eligible(int rarity, int tier) => Rarities[rarity].Entries
        .Select(e => (item: Items.Single(i => i.Id == e.Item), weight: e.Weight))
        .Where(e => e.item.Enabled && tier >= e.item.MinTier && tier <= e.item.MaxTier).ToList();

    internal int Fallback(int rarity, int tier)
    {
        for (int index = rarity; index < Rarities.Count; index++) if (Eligible(index, tier).Count > 0) return index;
        return -1;
    }

    public Dictionary<string, double> EffectiveProbabilities(int tier)
    {
        Dictionary<string, double> result = Rarities.ToDictionary(r => r.Id, _ => 0d);
        for (int index = 0; index < Rarities.Count; index++)
            if (Rarities[index].Probability > 0) result[Rarities[Fallback(index, tier)].Id] += Rarities[index].Probability;
        return result;
    }

    internal RewardRollBudget Budget(int tier, double modifierDifficulty)
    {
        if (tier < 1 || tier > 15 || !Finite(modifierDifficulty) || modifierDifficulty < 0)
            throw new ArgumentException("Reward rolls require tier 1–15 and finite nonnegative modifier difficulty.");
        RewardTier settings = Rules.Tiers[tier - 1];
        double budget = settings.Difficulty * (1 + modifierDifficulty / 100) * (1 + settings.BonusPercent / 100);
        // Every partial roll counts as a whole roll. Rounding to 10 places first keeps 13.0000000001 at 13.
        double uncapped = Math.Round(budget / Rules.BudgetPerRoll, 10, MidpointRounding.AwayFromZero);
        return new RewardRollBudget(settings.Difficulty, settings.BonusPercent, modifierDifficulty, budget, Rules.BudgetPerRoll,
            Rules.MaxRolls, uncapped > Rules.MaxRolls, (int)Math.Min(Rules.MaxRolls, Math.Ceiling(uncapped)));
    }

    internal int Rolls(int tier, double modifierDifficulty) => Budget(tier, modifierDifficulty).Rolls;

    // Each roll first selects a rarity, then one eligible item from that rarity by weight.
    internal List<RewardOdds> Odds(int tier)
    {
        Dictionary<string, double> probabilities = EffectiveProbabilities(tier);
        List<RewardOdds> result = new();
        for (int index = 0; index < Rarities.Count; index++)
        {
            double probability = probabilities[Rarities[index].Id];
            if (probability <= 0) continue;
            List<(RewardItem item, double weight)> choices = Eligible(index, tier);
            double total = choices.Sum(c => c.weight);
            result.Add(new RewardOdds(Rarities[index].Id, probability,
                choices.Select(c => (c.item, probability * c.weight / total)).ToList()));
        }
        return result;
    }

    internal double AtLeastOne(int tier, double modifierDifficulty, double probability) =>
        1 - Math.Pow(1 - probability, Rolls(tier, modifierDifficulty));

    private static bool Finite(double n) => !double.IsNaN(n) && !double.IsInfinity(n);
    private static void Require(bool valid, string path, string correction)
    { if (!valid) throw new ArgumentException("rewards.yaml " + path + ": " + correction + "."); }
}

internal sealed class RewardRollBudget
{
    internal RewardRollBudget(double tierDifficulty, double tierBonusPercent, double modifierPercent, double budget,
        double costPerRoll, int maxRolls, bool capped, int rolls)
    {
        TierDifficulty = tierDifficulty; TierBonusPercent = tierBonusPercent; ModifierPercent = modifierPercent;
        Budget = budget; CostPerRoll = costPerRoll; MaxRolls = maxRolls; Capped = capped; Rolls = rolls;
    }

    internal double TierDifficulty { get; }
    internal double TierBonusPercent { get; }
    internal double ModifierPercent { get; }
    internal double Budget { get; }
    internal double CostPerRoll { get; }
    internal int MaxRolls { get; }
    internal bool Capped { get; }
    internal int Rolls { get; }
}

internal sealed class RewardOdds
{
    internal RewardOdds(string rarity, double probability, List<(RewardItem item, double probability)> items)
    { Rarity = rarity; Probability = probability; Items = items; }

    internal string Rarity { get; }
    internal double Probability { get; }
    internal List<(RewardItem item, double probability)> Items { get; }
}

public sealed class RewardItem
{
    public string Id { get; set; } = "";
    public string Prefab { get; set; } = "";
    // Keep the YAML key; encounter tier selects Legendary, Mythic, or Ancient rarity.
    public bool RandomLegendarySetRune { get; set; }
    public bool Enabled { get; set; } = true;
    public int MinTier { get; set; } = 1;
    public int MaxTier { get; set; } = 15;
    public int MinQuantity { get; set; } = 1;
    public int MaxQuantity { get; set; } = 1;
    public int TabletTier { get; set; }
    public string TabletTheme { get; set; } = "";
}

public sealed class RewardWeight
{
    public string Item { get; set; } = "";
    public double Weight { get; set; } = 1;
}

public sealed class RewardRarity
{
    public string Id { get; set; } = "";
    public double Probability { get; set; }
    public List<RewardWeight> Entries { get; set; } = new();
}

public sealed class RewardRules
{
    public double BudgetPerRoll { get; set; } = 10;
    public int MaxRolls { get; set; } = 10000;
    public List<RewardTier> Tiers { get; set; } = new();
    public Dictionary<string, double> CategoryDifficulty { get; set; } = new();
    public Dictionary<string, double> ModifierDifficulty { get; set; } = new();
}

public sealed class RewardTier
{
    public double Difficulty { get; set; }
    public double BonusPercent { get; set; }
}
