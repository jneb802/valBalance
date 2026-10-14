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
    rows = []
    for event, definition in design["events"].items():
        tier = definition["tier"]
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
            damage_reference = None if physical is None else physical * (1 + design["damage_per_star"] * baseline["stars"]) * model["adopted"]["tier"]["damage_per_step"] ** (tier - 1)
            row = {"event": event, "tier": tier, "prefab": prefab, "rarity": rarity,
                   "base_health": base, **fit, "same_creature_tier1_stars": baseline["stars"],
                   "tier_damage_reference": damage_reference}
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
        for suffix, value in (("scenario", scenario), ("results", result)):
            (HERE / f"{event}-{suffix}.json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (DEFAULT_MODEL, HERE / "design.yaml", profile_path, HERE / "scenario-template.json")}
    report = {"model_version": model["model_version"], "input_sha256": hashes,
              "selection": "Nearest health; lower stars on ties. Damage and timing are diagnostics, not optimized.",
              "creatures": rows}
    (HERE / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
