"""Source-based weapon calculations. No assumed damage or attack cadence.

TTK/HTK always describe player -> monster. TTD/HTD describe monster -> player.
Damage-over-time payloads are never counted as immediate health loss.
"""
import math

TYPES = ('blunt', 'slash', 'pierce', 'fire', 'frost', 'lightning', 'poison', 'spirit')
CONVERSION_ORDER = tuple(t for t in TYPES if t != 'poison')
IMMEDIATE = ('blunt', 'slash', 'pierce', 'frost', 'lightning')


def finite(value, name, minimum=0, maximum=1e9):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be a finite number in [{minimum}, {maximum}]')
    return value


def skill_range(skill):
    skill = finite(skill, 'Weapon skill', 0, 100)
    center = 0.4 + 0.6 * skill / 100
    return max(0, center - 0.15), min(1, center + 0.15)


def verified_patch_order(profile):
    """Use an observed order only for its recorded game and mod binary inputs."""
    evidence = profile['observed_patch_order']
    if evidence.get('validation') != 'controlled-hit':
        raise ValueError('Patch order needs controlled-hit evidence')
    if evidence['game_version'] != profile['game_version']:
        raise ValueError('Patch-order evidence is for a different game version')
    for key in ('sls_assembly_sha256', 'epicloot_assembly_sha256'):
        if evidence[key] != profile['sources'][key]:
            raise ValueError('Patch-order evidence does not match ' + key)
    order = evidence['order']
    if order not in ('before_conversion', 'after_conversion'):
        raise ValueError('Unknown observed patch order')
    return order


def coin_bonus(effect, coins):
    finite(effect, 'CoinHoarder effect')
    finite(coins, 'Carried coins')
    if effect == 0 or coins == 0:
        return 0
    if coins <= 1000:
        return coins * 0.000145
    return math.log10(effect * coins) * 6.258 / 150


def weapon_damage(profile, context):
    weapon = profile['weapon']
    effects = profile['effects']
    quality = finite(weapon['quality'], 'Quality', 1, 100)
    if int(quality) != quality:
        raise ValueError('Quality must be an integer')
    damage = {kind: finite(weapon['base_damage'][kind], kind) + (quality - 1) * finite(weapon['per_quality'][kind], kind) for kind in TYPES}
    original = sum(damage.values())
    for kind in TYPES:
        damage[kind] += original * finite(effects['added_damage_percent'][kind], 'Added ' + kind) / 100
    maximum_health = finite(context['max_health'], 'Maximum health', 0.001)
    health = finite(context['health'], 'Current health', 0, maximum_health)
    if not isinstance(context['dodge_buff_active'], bool):
        raise ValueError('dodge_buff_active must be true or false')
    increase = 1 + finite(effects['modify_damage_percent'], 'ModifyDamage') / 100
    increase += coin_bonus(effects['coin_hoarder'], profile['coins'])
    if context['dodge_buff_active']:
        increase += finite(effects['dodge_buff_percent'], 'DodgeBuff') / 100
    multiplier = increase * finite(weapon['attack_damage_multiplier'], 'Attack multiplier')
    multiplier *= 1 + (maximum_health - health) * finite(weapon['damage_per_missing_hp'], 'Missing HP coefficient')
    return {kind: amount * multiplier for kind, amount in damage.items()}


def strike(profile, target, context, skill_roll, double_damage, sls_order):
    """One weapon hit. Returns immediate damage and separate post-defense DoT budgets.

    Caller specifies random outcomes and SLS/Harmony order; no averaging or guessing.
    Does not silently activate backstab, stagger, dodge buffs, or bonus hits.
    """
    lo, hi = skill_range(profile['skill'])
    finite(skill_roll, 'Skill damage roll', lo, hi)
    if not isinstance(double_damage, bool):
        raise ValueError('double_damage must be true or false')
    if sls_order not in ('before_conversion', 'after_conversion'):
        raise ValueError('Specify verified SLS/poison-conversion order')
    native = {t: finite(target['native_resistance'][t], 'Native ' + t, 0, 10) for t in TYPES}
    sls = {t: finite(target['sls_damage_received'][t], 'SLS ' + t, 0, 10) for t in TYPES}
    damage = {t: amount * skill_roll for t, amount in weapon_damage(profile, context).items()}
    if sls_order == 'before_conversion':
        damage = {t: damage[t] * sls[t] for t in TYPES}
    conversion = finite(profile['effects']['poison_conversion_percent'], 'Poison conversion', 0, 100) / 100
    converted_type = max(CONVERSION_ORDER, key=lambda t: native[t])
    converted = damage['poison'] * conversion
    damage['poison'] -= converted
    damage[converted_type] += converted
    if double_damage:
        multiplier = finite(profile['effects']['double_damage_multiplier'], 'Double damage multiplier', 1)
        damage = {t: damage[t] * multiplier for t in TYPES}
    if sls_order == 'after_conversion':
        damage = {t: damage[t] * sls[t] for t in TYPES}
    received = {t: damage[t] * native[t] for t in TYPES}
    armor = finite(target['armor'], 'Monster armor')
    total = sum(received.values())
    if total > 0 and armor > 0:
        reduced = total - armor if total >= 2 * armor else total * total / (4 * armor)
        received = {t: d * reduced / total for t, d in received.items()}
    return {'converted_to': converted_type, 'damage_by_type': received,
            'immediate_damage': sum(received[t] for t in IMMEDIATE),
            'fire_payload': received['fire'], 'poison_payload': received['poison'],
            'spirit_payload': received['spirit']}


def animation_landmarks(profile):
    """Integrate verified clip Speed events, without pretending to simulate Unity's animator."""
    animation = profile['animation']
    changes = sorted(animation['speed_events'], key=lambda e: e['time'])
    def elapsed(stop):
        result, position = 0.0, 0.0
        speed = finite(animation['state_speed'], 'Animation state speed', 0.001)
        factor = finite(animation['equipment_speed_multiplier'], 'Equipment speed multiplier', 0.001)
        for event in changes:
            time = finite(event['time'], 'Animation event time')
            if time > stop:
                break
            result += (time - position) / (speed * factor)
            position = time
            speed = finite(event['speed'], 'Animation Speed event', 0.001) * animation['state_speed']
        return result + (stop - position) / (speed * factor)
    return {
        'clip_hit_landmark_seconds': elapsed(animation['hit_time']),
        'clip_end_landmark_seconds': elapsed(animation['clip_duration']),
        'on_hit_freeze_seconds': animation['hit_freeze'],
        'exit_normalized_time': animation['exit_normalized_time'],
        'exit_transition_seconds': animation['exit_transition'],
        'entry_transition_seconds': animation['entry_transition'],
        'nominal_successful_cycle_seconds': elapsed(animation['clip_duration'] * animation['exit_normalized_time']) + animation['hit_freeze'] + animation['exit_transition'],
        'attack_interval_seconds': None,
        'status': 'Clip landmarks verified. Nominal cycle integrates speed events through exit time plus hit pause and exit transition; it excludes frame/input scheduling and stamina gaps. Not a verified live TTK input.'}


def audit(profile):
    if profile.get('version') != 1:
        raise ValueError('Expected weapon profile version 1')
    context = profile['context']
    lo, hi = skill_range(profile['skill'])
    outcomes = []
    for target in profile['targets']:
        variants = []
        # Keep the unresolved patch ordering explicit rather than selecting a convenient value.
        for order in profile['sls_order_candidates']:
            for roll in (lo, hi):
                for proc in (False, True):
                    variants.append({'sls_order': order, 'skill_roll': roll, 'double_damage': proc,
                                     **strike(profile, target, context, roll, proc, order)})
        outcomes.append({'target': target['name'], 'variants': variants})
    return {'metric_definitions': {'ttk': 'Seconds for player to kill monster', 'htk': 'Player hits to kill monster',
                                  'htd': 'Monster hits to kill player', 'ttd': 'Seconds until monster or pack kills player'},
            'weapon': profile['weapon']['prefab'], 'quality': profile['weapon']['quality'],
            'skill_damage_range': [lo, hi], 'coin_damage_bonus': coin_bonus(profile['effects']['coin_hoarder'], profile['coins']),
            'weapon_damage_before_skill_and_conversion': weapon_damage(profile, context),
            'timing': animation_landmarks(profile), 'targets': outcomes,
            'proc_inputs': profile['proc_inputs'], 'dot_rules': profile['dot_rules'],
            'unresolved': profile['unresolved'], 'ttk': None, 'htk': None,
            'status': 'Not ready for encounter calibration until the unresolved inputs are resolved.'}


def evaluate_events(encounter):
    """Exact kill metrics for a supplied damage event sequence, including timed/proc damage.

    Events contain authoritative target HP loss and times, not weapon tooltip payloads.
    Weapon hit events count toward HTK; DoT/proc events do not add weapon hits.
    """
    health = finite(encounter['monster_health'], 'Monster health', 0.001)
    start = finite(encounter['attack_start'], 'Attack start')
    previous = start
    hits = 0
    for event in encounter['events']:
        time = finite(event['time'], 'Event time', previous)
        previous = time
        if event['kind'] not in ('weapon_hit', 'dot', 'proc', 'heal'):
            raise ValueError('Unknown damage event kind')
        amount = finite(event['amount'], 'Applied HP change')
        if event['kind'] == 'weapon_hit':
            hits += 1
        health += amount if event['kind'] == 'heal' else -amount
        health = min(health, encounter['monster_health'])
        if health <= 0:
            return {'htk': hits, 'ttk': time - start, 'killing_event': event['kind'], 'remaining_health': 0}
    return {'htk': None, 'ttk': None, 'killing_event': None, 'remaining_health': health}
