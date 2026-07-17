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


@tactic("community")
def community(ctx):
    """Each picked combo scores 1.0 + 0.25 per extra member picking it (cap 2.0);
    its boxed arrangements score 0.5x that. No picks -> all zeros."""
    if not ctx.community:
        return [0.0] * 1000
    members = {}
    for item in ctx.community:
        try:
            member, combo = _extract(item)
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        if len(combo) != 3 or any(d < 0 or d > 9 for d in combo):
            continue
        members.setdefault(combo, set()).add(member)
    weights = {}
    for combo, who in members.items():
        w = min(1.0 + 0.25 * (len(who) - 1), 2.0)
        weights[combo] = max(weights.get(combo, 0.0), w)
        for perm in set(permutations(combo)):
            if perm != combo:
                weights[perm] = max(weights.get(perm, 0.0), 0.5 * w)
    return pool_scores(weights)
