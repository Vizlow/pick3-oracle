"""Community-picks tactic — score member picks submitted for the target draw."""
from itertools import permutations

from engine.tactics import pool_scores, tactic


def _extract(item):
    """Accept {'member':..., 'combo': [a,b,c]} dicts or (member, combo) tuples."""
    if isinstance(item, dict):
        member, combo = item.get("member"), item.get("combo")
    else:
        member, combo = item
    return member, tuple(int(d) for d in combo)


_PAIR_POSITIONS = {"front": (0, 1), "back": (1, 2), "split": (0, 2)}


@tactic("community")
def community(ctx):
    """Each picked combo scores the SUM of its pickers' skill multipliers
    (cap 3.0) — a proven caller like a hot streak member counts ~2-3x a
    neutral one (skill attached by pipeline.ctx_for, Bayesian-shrunk, computed
    only from draws before the target). Boxed arrangements score 0.5x. Pair
    calls ("80x" front / "x01" back) score their 10 straights at 0.6x summed
    skill (cap 1.8). No picks -> all zeros."""
    if not ctx.community:
        return [0.0] * 1000

    def skill_of(item):
        s = item.get("skill", 1.0) if isinstance(item, dict) else 1.0
        return s if isinstance(s, (int, float)) and s > 0 else 1.0

    members, pair_members = {}, {}
    for item in ctx.community:
        if isinstance(item, dict) and "pair" in item:
            p = item["pair"]
            try:
                key = (p["kind"], tuple(int(d) for d in p["digits"]))
            except (TypeError, ValueError, KeyError):
                continue
            if key[0] in _PAIR_POSITIONS and len(key[1]) == 2:
                pair_members.setdefault(key, {})[item.get("member")] = skill_of(item)
            continue
        try:
            member, combo = _extract(item)
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        if len(combo) != 3 or any(d < 0 or d > 9 for d in combo):
            continue
        members.setdefault(combo, {})[member] = skill_of(item)
    weights = {}
    for (kind, digits), who in pair_members.items():
        w = min(0.6 * sum(who.values()), 1.8)
        i, j = _PAIR_POSITIONS[kind]
        k = 3 - i - j
        for z in range(10):
            combo = [0, 0, 0]
            combo[i], combo[j] = digits
            combo[k] = z
            combo = tuple(combo)
            weights[combo] = max(weights.get(combo, 0.0), w)
    for combo, who in members.items():
        w = min(sum(who.values()), 3.0)
        weights[combo] = max(weights.get(combo, 0.0), w)
        for perm in set(permutations(combo)):
            if perm != combo:
                weights[perm] = max(weights.get(perm, 0.0), 0.5 * w)
    return pool_scores(weights)
