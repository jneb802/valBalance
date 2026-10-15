"""Rebuild star-only proposals and sampled combat reports from repository inputs."""
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from balance import DEFAULT_MODEL, plan
from combat import calibrate
from starfit import closest_stars

HERE = Path(__file__).resolve().parent


def main():
    design = yaml.safe_load((HERE / "design.yaml").read_text())
    if design["health_per_star"] != 1 or design["damage_per_star"] != 0.25:
        raise ValueError("Combat calibration currently requires health/star 1 and damage/star 0.25")
    model = yaml.safe_load(DEFAULT_MODEL.read_text())
    profile_path = HERE / "player.json"
    profile = json.loads(profile_path.read_text())
    template = json.loads((HERE / "scenario-template.json").read_text())
    targets = {target["name"]: target for target in profile["targets"]}
    local_sources = json.loads((HERE / "additional-creature-source-data.json").read_text())["creatures"]
    rows = []
    waves = []
    curve = []
    for event, definition in design["events"].items():
        tier = definition["tier"]
        health_growth = model["adopted"]["tier"]["health_per_step"] ** (tier - 1)
        curve.append({"tier": tier, "event": event, "health_factor": health_growth,
                      "damage_factor": model["adopted"]["tier"]["damage_per_step"] ** (tier - 1),
                      "normal_hp": design["normal_tier1_health"] * health_growth,
                      "magic_hp": design["normal_tier1_health"] * health_growth * model["adopted"]["rarity"]["magic"]["health"],
                      "rare_hp": design["normal_tier1_health"] * health_growth * model["adopted"]["rarity"]["rare"]["health"],
                      "boss_hp": design["boss_tier1_health"] * health_growth})
        scenario = json.loads(json.dumps(template))
        scenario["enemies"] = []
        event_rows = []
        for prefab, creature in definition["creatures"].items():
            rarity = creature["rarity"]
            if rarity == "unique":
                health1 = design["boss_tier1_health"]
            else:
                health1 = design["normal_tier1_health"] * plan(1, rarity)["health_factor"]
            target_health = health1 * model["adopted"]["tier"]["health_per_step"] ** (tier - 1)
            base = targets[prefab]["base_health"]
            fit = closest_stars(base, target_health, design["health_per_star"], design["maximum_stars"])
            baseline = closest_stars(base, health1, design["health_per_star"], design["maximum_stars"])
            physical = creature["base_physical"]
            attack = local_sources.get(prefab, {}).get("attacks", {}).get(creature.get("attack"))
            if attack is not None and physical is not None:
                extracted_physical = sum(attack[k] for k in ("m_blunt", "m_slash", "m_pierce"))
                if extracted_physical != physical or any(attack[k] for k in ("m_damage", "m_fire", "m_frost", "m_lightning", "m_poison", "m_spirit")):
                    raise ValueError(f"{prefab}: representative attack does not match extracted pure physical damage")
            damage_reference = None if physical is None else physical * (1 + design["damage_per_star"] * baseline["stars"]) * model["adopted"]["tier"]["damage_per_step"] ** (tier - 1)
            row = {"event": event, "tier": tier, "prefab": prefab, "rarity": rarity,
                   "base_health": base, **fit, "same_creature_tier1_stars": baseline["stars"],
                   "tier_damage_reference": damage_reference}
            row["attack"] = creature.get("attack")
            row["scaled_attack_payload"] = None if attack is None else {
                k: v * (1 + design["damage_per_star"] * fit["stars"])
                for k, v in attack.items() if v and k not in ("m_chop", "m_pickaxe", "m_nonPlayer")}
            if "base_poison_payload" in creature:
                row["raw_poison_payload"] = creature["base_poison_payload"] * (1 + design["damage_per_star"] * fit["stars"])
            event_rows.append(row)
            scenario["enemies"].append({"prefab": prefab, "role": rarity, "stars": fit["stars"],
                                        "base_physical": physical, "sls_modifiers": []})
        result = calibrate(profile, scenario)
        for row, outcome in zip(event_rows, result["enemies"]):
            order = result["selected_patch_orders"][0]
            row.update(raw_physical=outcome["raw_physical"], received=outcome["received_normal"],
                       htd=outcome["htd"], ttk=outcome["offense"][order]["ttk"]["p50"],
                       htk=outcome["offense"][order]["htk"]["p50"])
            ref = row["tier_damage_reference"]
            row["tier_damage_error_percent"] = None if ref is None else 100 * (row["raw_physical"] / ref - 1)
        rows.extend(event_rows)
        health_by_prefab = {r["prefab"]: r["health"] for r in event_rows}
        for wave in range(1, 5):
            counts = dict(definition["waves"]["regular"])
            if wave == 4:
                for prefab, count in definition["waves"]["finale_addition"].items():
                    counts[prefab] = counts.get(prefab, 0) + count
            minimum = maximum = 0
            for prefab, count in counts.items():
                possible = [health_by_prefab[p] for p in definition["support_pool"]] if prefab == "magic_support_selections" else [health_by_prefab[prefab]]
                minimum += min(possible) * count
                maximum += max(possible) * count
            waves.append({"event": event, "wave": wave, "counts": counts,
                          "total_creatures_excluding_children": sum(counts.values()),
                          "total_hp_min": minimum, "total_hp_max": maximum})
        for suffix, value in (("scenario", scenario), ("results", result)):
            (HERE / f"{event}-{suffix}.json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (DEFAULT_MODEL, HERE / "design.yaml", profile_path, HERE / "scenario-template.json", HERE / "additional-creature-source-data.json")}
    report = {"model_version": model["model_version"], "input_sha256": hashes,
              "selection": "Nearest health; lower stars on ties. Damage and timing are diagnostics, not optimized.",
              "tier_curve": curve, "waves": waves, "creatures": rows}
    (HERE / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    lines = ["# Ten-tier calculated workshop", "", "Generated by `python3 workshops/star-only/run.py`. See README.md for assumptions and limits.", "",
             "## Target curve", "", "| Tier | Event | Health factor | Damage factor | Normal HP | Magic HP | Rare HP | Boss HP |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in curve:
        lines.append(f"| {row['tier']} | {row['event']} | {row['health_factor']:.4f} | {row['damage_factor']:.4f} | {row['normal_hp']:.2f} | {row['magic_hp']:.2f} | {row['rare_hp']:.2f} | {row['boss_hp']:.2f} |")
    lines += ["", "## Nearest-health stars and combat diagnostics", "", "Raw hit is the selected pure physical attack only. Unknown does not mean harmless. TTK is median seconds; no healing, geometry or weak spots.", "",
              "| Tier | Prefab | Rarity | Base HP | Stars | Target HP | Actual HP | HP error | Raw hit | TTK | HTD |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        raw = 'Unknown' if row['raw_physical'] is None else f"{row['raw_physical']:.2f}"
        htd = 'Unknown' if row['htd'] is None else str(row['htd'])
        lines.append(f"| {row['tier']} | {row['prefab']} | {row['rarity']} | {row['base_health']:g} | {row['stars']} | {row['target_health']:.2f} | {row['health']:g} | {row['health_error_percent']:+.2f}% | {raw} | {row['ttk']:.2f} | {htd} |")
    lines += ["", "## Wave totals", "", "Four waves per event. HP sums are not wave TTK; children and summons are excluded.", "",
              "| Event | Wave | Counts | Total creatures | Total HP range |", "|---|---:|---|---:|---:|"]
    for row in waves:
        counts = ', '.join(f'{count} {name}' for name, count in row['counts'].items())
        lines.append(f"| {row['event']} | {row['wave']} | {counts} | {row['total_creatures_excluding_children']} | {row['total_hp_min']:g}–{row['total_hp_max']:g} |")
    (HERE / "RESULTS.md").write_text('\n'.join(lines) + '\n')
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
