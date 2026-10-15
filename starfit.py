"""Select integer stars by absolute health error; report damage separately."""
import math

from model import number


def closest_stars(base_health, target_health, health_per_star=1.0, max_stars=10000):
    number(base_health, "Base health", 0.001)
    number(target_health, "Target health", 0.001)
    number(health_per_star, "Health per star", 0.001)
    if isinstance(max_stars, bool) or not isinstance(max_stars, int) or not 0 <= max_stars <= 10000:
        raise ValueError("Maximum stars must be an integer from 0 to 10000")
    ideal = (target_health / base_health - 1) / health_per_star
    candidates = {max(0, min(max_stars, math.floor(ideal))),
                  max(0, min(max_stars, math.ceil(ideal)))}
    # Prefer fewer stars when health errors are equal.
    stars = min(candidates, key=lambda s: (abs(base_health * (1 + health_per_star * s) - target_health), s))
    health = base_health * (1 + health_per_star * stars)
    return {"stars": stars, "target_health": target_health, "health": health,
            "health_error_percent": 100 * (health / target_health - 1)}
