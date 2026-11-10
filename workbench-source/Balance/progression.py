"""Generate star ranges from the approved Tier 1 review."""
import json
from balance import HERE, read


def baselines():
    settings = read(HERE / 'progression.yaml')
    review = json.loads((HERE / settings['baseline']).read_text())
    result = {}
    for name, entry in review['creatures'].items():
        low, high = entry['tiers']['1']
        tier_ranges(dict(minStars=low, maxStars=high))
        status = 'user_reviewed' if entry['enabled'] or low or high else 'pending_review'
        result[name] = dict(minStars=low, maxStars=high, status=status)
    return result


def tier_ranges(stars):
    settings = read(HERE / 'progression.yaml')
    if (settings['minimum_tier'], settings['maximum_tier'], settings['stars_per_tier']) != (1, 15, 3):
        raise ValueError('Runtime progression requires tiers 1–15 and +3 stars per tier')
    if stars is None:
        stars = dict(minStars=0, maxStars=0)
    low, high = stars['minStars'], stars['maxStars']
    if type(low) is not int or type(high) is not int or not 0 <= low <= high <= 9958:
        raise ValueError('Tier 1 stars must be whole numbers from 0 to 9958')
    return {str(tier): [low + 3 * (tier - 1), high + 3 * (tier - 1)] for tier in range(1, 16)}
