"""Read versioned design factors without changing combat inputs."""
import hashlib
from pathlib import Path

import yaml

from model import number


DEFAULT_MODEL = Path(__file__).resolve().parent / "configs" / "balance-model.yaml"


def plan(tier, rarity, path=DEFAULT_MODEL, player_path=None):
    """Return planning factors relative to the same tier-1 normal creature."""
    if isinstance(tier, bool) or not isinstance(tier, int) or not 1 <= tier <= 100:
        raise ValueError("Tier must be a whole number from 1 to 100")
    raw = Path(path).read_bytes()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid balance model YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Balance model must be a YAML mapping")
    if data["schema_version"] != 1:
        raise ValueError("Expected balance model schema 1")
    adopted = data["adopted"]
    if adopted["baseline"]["tier"] != 1:
        raise ValueError("This model requires a tier-1 baseline")
    if rarity not in ("normal", "magic", "rare"):
        raise ValueError("Choose normal, magic, or rare; unique bosses require separate tuning")
    selected = adopted["rarity"][rarity]
    health_step = number(adopted["tier"]["health_per_step"], "Health step", 1, 10)
    damage_step = number(adopted["tier"]["damage_per_step"], "Damage step", 1, 10)
    health = number(selected["health"], "Rarity health", 0.001, 1000)
    damage = number(selected["damage_per_hit"], "Rarity damage", 0.001, 1000)
    speed = number(selected["attack_speed"], "Rarity attack speed", 0.001, 1000)
    targets = adopted["targets"][rarity]
    for metric in ("ttk_seconds", "htd_hits"):
        bounds = targets[metric]
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError(f"{metric} needs minimum and maximum")
        for bound in bounds:
            if bound is not None:
                number(bound, metric)
        if all(bound is not None for bound in bounds) and bounds[0] > bounds[1]:
            raise ValueError(f"{metric} minimum exceeds maximum")
    return {
        "model_version": data["model_version"],
        "model_sha256": hashlib.sha256(raw).hexdigest(),
        "player_sha256": hashlib.sha256(Path(player_path).read_bytes()).hexdigest() if player_path else None,
        "status": data["status"],
        "tier": tier,
        "rarity": rarity,
        "relative_to": "Same creature at tier 1, normal rarity, before explicit modifiers",
        "health_factor": health_step ** (tier - 1) * health,
        "raw_damage_per_hit_factor": damage_step ** (tier - 1) * damage,
        "attack_speed_factor": speed,
        "tier_1_targets": targets,
        "ttk": None,
        "htd": None,
        "limits": "Planning factors only. Resolve creature stats, defenses, modifiers and attack timing through combat calibration. Do not multiply already-tuned event stats again."
    }
