"""Deterministic planning calculations, not a Valheim combat simulator."""
import math


DEFAULTS = {
    "version": 1,
    "player": {"health": 672.45, "armor": 186.36, "low_armor": 219.96,
               "threshold": 75, "physical_resist": 48.12, "elemental_resist": 38.728,
               "hit": 500, "interval": 0.8, "windup": 0.4, "uptime": 70,
               "healing": 0},
    "roles": {
        "Fodder": [0.5, 2, 1, 3, 8, None],
        "Standard": [3, 8, 4, 8, 4, 7],
        "Elite": [10, 25, 10, 25, 3, 5],
        "Mini boss": [20, 60, None, None, 2, 4],
        "Main boss": [60, 180, None, None, 2, 4]},
    "enemies": [
        {"name": "Greydwarf", "role": "Fodder", "health": 1200, "hit": 0, "physical": 224, "elemental": 0, "interval": 3, "contact": 40, "counts": [6, 6, 8, 8]},
        {"name": "Brute", "role": "Standard", "health": 4800, "hit": 0, "physical": 480, "elemental": 0, "interval": 4, "contact": 40, "counts": [2, 1, 2, 1]},
        {"name": "Shaman (melee only)", "role": "Standard", "health": 1800, "hit": 0, "physical": 112, "elemental": 0, "interval": 4, "contact": 30, "counts": [1, 1, 1, 1]},
        {"name": "Bear (bite)", "role": "Elite", "health": 12000, "hit": 0, "physical": 660, "elemental": 0, "interval": 3, "contact": 50, "counts": [0, 1, 1, 1]},
        {"name": "Troll (heavy hit)", "role": "Mini boss", "health": 30000, "hit": 0, "physical": 1050, "elemental": 0, "interval": 5, "contact": 50, "counts": [0, 0, 0, 1]}],
    "waves": ["First pack", "Bear pack", "Reinforced pack", "Troll pack"]}


def number(value, label, minimum=0, maximum=1e9):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def validate(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Expected a version 1 scenario")
    p = data["player"]
    if not isinstance(p, dict):
        raise ValueError("Player must be an object")
    for key in DEFAULTS["player"]:
        number(p[key], f"Player {key}", 0.001 if key in ("health", "hit", "interval", "uptime") else 0,
               100 if key in ("threshold", "physical_resist", "elemental_resist", "uptime") else 1e9)
    if not isinstance(data["waves"], list) or not 1 <= len(data["waves"]) <= 20:
        raise ValueError("Use 1–20 waves")
    if any(not isinstance(w, str) or not w.strip() or len(w) > 100 for w in data["waves"]):
        raise ValueError("Wave names must contain 1–100 characters")
    if not isinstance(data["roles"], dict) or not 1 <= len(data["roles"]) <= 20:
        raise ValueError("Use 1–20 roles")
    for role, limits in data["roles"].items():
        if not isinstance(role, str) or not role.strip() or not isinstance(limits, list) or len(limits) != 6:
            raise ValueError("Each role needs six limits: TTK min/max, HTK min/max, HTD min/max")
        for i in range(0, 6, 2):
            lo, hi = limits[i:i+2]
            for v in (lo, hi):
                if v is not None:
                    number(v, f"{role} limit")
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f"{role}: minimum exceeds maximum")
    if not isinstance(data["enemies"], list) or not 1 <= len(data["enemies"]) <= 100:
        raise ValueError("Use 1–100 enemies")
    for e in data["enemies"]:
        if not isinstance(e, dict):
            raise ValueError("Each enemy must be an object")
        if not isinstance(e["name"], str) or not e["name"].strip() or len(e["name"]) > 100:
            raise ValueError("Enemy names must contain 1–100 characters")
        if e["role"] not in data["roles"]:
            raise ValueError("Unknown enemy role")
        for key in ("health", "hit", "physical", "elemental", "interval", "contact"):
            number(e[key], f"{e['name']} {key}", 0.001 if key in ("health", "interval") else 0,
                   100 if key == "contact" else 1e9)
        if not isinstance(e["counts"], list) or len(e["counts"]) != len(data["waves"]):
            raise ValueError("Each enemy needs one count per wave")
        for count in e["counts"]:
            number(count, "Enemy count", 0, 1000)
            if int(count) != count:
                raise ValueError("Enemy counts must be whole numbers")


def received(e, p, armor):
    physical = e["physical"] * (1 - p["physical_resist"] / 100)
    # Valheim armor curve for the physical portion; element input is immediate only.
    physical = physical - armor if physical >= 2 * armor else physical * physical / (4 * armor)
    return physical + e["elemental"] * (1 - p["elemental_resist"] / 100)


def hits_to_die(p, normal, low):
    """Exact count for constant hits within each health state, no recovery or avoidance."""
    health = p["health"]
    boundary = health * p["threshold"] / 100
    hits = 0
    if health > boundary:
        if normal <= 0:
            return None
        hits = math.ceil((health - boundary) / normal)
        health -= hits * normal
        if health <= 1e-9:
            return hits
    if low <= 0:
        return None
    return hits + math.ceil(health / low)


def rating(value, lo, hi):
    if value is None:
        return "No kill"
    if lo is not None and value < lo:
        return "Below target"
    if hi is not None and value > hi:
        return "Above target"
    return "In range" if lo is not None or hi is not None else "Unspecified"


def analyze(data):
    validate(data)
    p = data["player"]
    rows = []
    for e in data["enemies"]:
        hit = e["hit"] or p["hit"]
        htk = math.ceil(e["health"] / hit)
        focused = p["windup"] + (htk - 1) * p["interval"]
        practical = focused / (p["uptime"] / 100)
        normal = received(e, p, p["armor"])
        low = received(e, p, p["low_armor"])
        htd = hits_to_die(p, normal, low)
        ttd = None if htd is None else (htd - 1) * e["interval"]
        limits = data["roles"][e["role"]]
        # Intersection of hit-count and attack-start TTK targets, converted to health.
        minimum_hits = max(1, math.ceil(limits[2] or 1))
        maximum_hits = math.floor(limits[3]) if limits[3] is not None else None
        if limits[0] is not None:
            minimum_hits = max(minimum_hits, math.ceil((limits[0] - p["windup"]) / p["interval"] + 1))
        if limits[1] is not None:
            time_max = math.floor((limits[1] - p["windup"]) / p["interval"] + 1)
            maximum_hits = time_max if maximum_hits is None else min(maximum_hits, time_max)
        possible = maximum_hits is None or maximum_hits >= minimum_hits
        rows.append({"name": e["name"], "htk": htk, "ttk": focused, "practical": practical,
                     "damage": normal, "low_damage": low, "htd": htd, "ttd": ttd,
                     "ttk_rating": rating(focused, *limits[:2]), "htk_rating": rating(htk, *limits[2:4]),
                     "htd_rating": rating(htd, *limits[4:]),
                     "health_min_exclusive": (minimum_hits - 1) * hit if possible else None,
                     "health_max": maximum_hits * hit if possible and maximum_hits is not None else None,
                     "target_possible": possible})
    waves = []
    for index, name in enumerate(data["waves"]):
        counts = [e["counts"][index] for e in data["enemies"]]
        pressure = sum(c * r["damage"] / e["interval"] * e["contact"] / 100
                       for c, r, e in zip(counts, rows, data["enemies"]))
        low_pressure = sum(c * r["low_damage"] / e["interval"] * e["contact"] / 100
                           for c, r, e in zip(counts, rows, data["enemies"]))
        first_net, low_net = pressure - p["healing"], low_pressure - p["healing"]
        upper_hp = p["health"] * (1 - p["threshold"] / 100)
        lower_hp = p["health"] - upper_hp
        ttd = None if (upper_hp > 0 and first_net <= 0) or (lower_hp > 0 and low_net <= 0) else (
            (upper_hp / first_net if upper_hp else 0) + (lower_hp / low_net if lower_hp else 0))
        clear = sum(c * r["practical"] for c, r in zip(counts, rows))
        waves.append({"name": name, "count": sum(counts), "clear": clear, "pressure": pressure,
                      "low_pressure": low_pressure, "ttd": ttd,
                      "ratio": clear / ttd if ttd else None})
    return {"enemies": rows, "waves": waves}
