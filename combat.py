"""Repeatable, source-based single-target scenarios, not a Unity runtime emulator."""
import math
import random
from copy import deepcopy

from weapon import animation_landmarks, finite, skill_range, strike, verified_patch_order
from model import received, hits_to_die, rating


def simulate(profile, target, health, order, rng, stamina, proc_hits=True):
    """Nominal animation timing; immediate first DoT update; dry, alert target.

    Continuous idle stamina recovery integrates Player.UpdateStats. No recovery
    occurs inside the attack. Each chain proc hits this isolated target once.
    These scheduling assumptions are explicit, not measured live timings.
    """
    finite(health, 'Monster health', 0.001)
    if target['armor'] != 0:
        raise ValueError('Proc simulation currently requires zero monster armor')
    timing = animation_landmarks(profile)
    windup = timing['clip_hit_landmark_seconds']
    cycle = timing['nominal_successful_cycle_seconds']
    maximum = finite(stamina['maximum'], 'Maximum stamina', 0.001)
    available = finite(stamina['initial'], 'Initial stamina', 0, maximum)
    cost = finite(stamina['cost_per_attack'], 'Attack stamina cost', 0.001, maximum)
    regen = finite(stamina['base_regen'], 'Stamina regeneration', 0.001)
    multiplier = finite(stamina['regen_multiplier'], 'Stamina regeneration multiplier', 0.001)
    delay = finite(stamina['regen_delay'], 'Stamina regeneration delay')
    # Player prefab time multiplier is 1 in this scenario.
    if stamina['regen_time_multiplier'] != 1:
        raise ValueError('Only source stamina time multiplier 1 is supported')
    lo, hi = skill_range(profile['skill'])
    effects = {}
    time, next_start, last_start, hits = 0.0, 0.0, -math.inf, 0
    idle_seconds = 0.0

    def add_dot(kind, payload, now):
        if payload <= 0:
            return
        rules = profile['dot_rules'][kind]
        interval = rules['m_damageInterval']
        old = effects.get(kind)
        if old and now >= old['expires']:
            old = None
        left = old['left'] if old else 0
        if kind == 'poison':
            if payload < left:
                return
            left = payload
            ttl = rules['m_baseTTL'] + (left * rules['m_TTLPerDamage']) ** rules['m_TTLPower']
        else:
            ttl = rules['m_ttl']
            if payload / int(ttl / interval) < 0.2 and left == 0:
                return
            left += payload
        effects[kind] = dict(left=left, tick=left / int(ttl / interval),
                             next=old['next'] if old else now,
                             expires=now + ttl, interval=interval)

    def dots_until(stop):
        nonlocal health
        while effects:
            kind = min(effects, key=lambda k: effects[k]['next'])
            effect = effects[kind]
            when = effect['next']
            if when > stop:
                break
            if when >= effect['expires']:
                del effects[kind]
                continue
            health -= effect['tick']
            effect['left'] = max(0, effect['left'] - effect['tick'])
            effect['next'] += effect['interval']
            if health <= 0:
                return when
        return None

    while hits < 10000:
        if available < cost:
            ready = max(next_start, last_start + delay)
            # dS/dt = regen * multiplier * (2 - S / maximum).
            wait = maximum / (regen * multiplier) * math.log((2 * maximum - available) / (2 * maximum - cost))
            idle_seconds += ready - next_start + wait
            next_start = ready + wait
            available = cost
        # A DoT can finish the target before another attack is initiated.
        killed = dots_until(next_start)
        if killed is not None:
            return dict(htk=hits, ttk=killed, stamina_wait_seconds=idle_seconds)
        last_start = next_start
        available -= cost
        time = next_start + windup
        killed = dots_until(time)
        if killed is not None:
            return dict(htk=hits, ttk=killed, stamina_wait_seconds=idle_seconds)
        hits += 1
        result = strike(profile, target, profile['context'], rng.uniform(lo, hi),
                        rng.random() < profile['effects']['double_damage_chance_percent'] / 100, order)
        health -= result['immediate_damage']
        if result['spirit_payload']:
            raise ValueError('Spirit DoT is not implemented in this scenario simulator')
        for kind in ('fire', 'poison'):
            add_dot(kind, result[kind + '_payload'], time)
        if proc_hits:
            for name in ('native_chain', 'epic_chain'):
                proc = profile['proc_inputs'][name]
                if rng.random() < proc['chance']:
                    health -= proc.get('scaled_lightning', proc['base_lightning']) * target['native_resistance']['lightning'] * target['sls_damage_received']['lightning']
        if health <= 0:
            return dict(htk=hits, ttk=time, stamina_wait_seconds=idle_seconds)
        killed = dots_until(time)
        if killed is not None:
            return dict(htk=hits, ttk=killed, stamina_wait_seconds=idle_seconds)
        next_start += cycle
    raise ValueError('No kill within 10000 attacks')


def distribution(profile, target, health, stamina, trials, seed, proc_hits=True):
    if not isinstance(trials, int) or not 1 <= trials <= 100000:
        raise ValueError('Use 1–100000 trials')
    results = {}
    for order in profile['sls_order_candidates']:
        rng = random.Random(seed)
        rows = [simulate(profile, target, health, order, rng, stamina, proc_hits) for _ in range(trials)]
        results[order] = {}
        for key in ('htk', 'ttk', 'stamina_wait_seconds'):
            values = sorted(row[key] for row in rows)
            results[order][key] = {name: values[math.ceil(q * trials) - 1]
                                    for name, q in (('p10', .1), ('p50', .5), ('p90', .9))}
    return results


def calibrate(profile, scenario):
    """Report sampled offense by patch order and separate unblocked incoming hits."""
    profile = deepcopy(profile)
    if scenario.get('use_verified_patch_order', False):
        profile['sls_order_candidates'] = [verified_patch_order(profile)]
    targets = {t['name']: t for t in profile['targets']}
    rows = []
    p = scenario['player_defense']
    for enemy in scenario['enemies']:
        stars = finite(enemy['stars'], 'Stars', 0, 10000)
        if int(stars) != stars:
            raise ValueError('Stars must be whole numbers')
        target = targets[enemy['prefab']]
        health = target['base_health'] * (1 + stars)
        physical = enemy['base_physical'] * (1 + .25 * stars)
        incoming = dict(physical=physical, elemental=0)
        for modifier in enemy['sls_modifiers']:
            if modifier not in ('Lightning', 'Frost'):
                raise ValueError('Unsupported incoming modifier: ' + modifier)
            base, per_level = scenario['sls_modifier_powers'][modifier]
            incoming['resolved_' + modifier.lower()] = physical * (base + per_level * (stars + 1))
        normal, low = (received(incoming, p, p[key]) for key in ('armor', 'low_armor'))
        htd = hits_to_die(p, normal, low)
        outcomes = distribution(profile, target, health, scenario['stamina'], scenario['trials'], scenario['seed'], scenario['include_initial_chain_hits'])
        limits = scenario['roles'][enemy['role']]
        checks = {order: dict(ttk=rating(r['ttk']['p50'], *limits[:2]),
                              htk=rating(r['htk']['p50'], *limits[2:4])) for order, r in outcomes.items()}
        rows.append(dict(prefab=enemy['prefab'], role=enemy['role'], stars=stars, health=health,
                         raw_physical=physical, raw_lightning=incoming.get('resolved_lightning', 0),
                         raw_frost=incoming.get('resolved_frost', 0),
                         received_normal=normal, received_low_health=low, htd=htd,
                         htd_rating=rating(htd, *limits[4:]), median_ratings=checks, offense=outcomes))
    return dict(status='Nominal single-target simulation; not live validated',
                selected_patch_orders=profile['sls_order_candidates'],
                patch_order_evidence=profile.get('observed_patch_order') if scenario.get('use_verified_patch_order', False) else None,
                trials_per_patch_order=scenario['trials'], seed=scenario['seed'],
                timing=animation_landmarks(profile), assumptions=scenario['assumptions'], enemies=rows)
