"""VTRAC tactics — positional vtrac dueness and last-draw vtrac-return pools."""
from itertools import permutations

from engine import lmath
from engine.tactics import pool_scores, tactic

_VT = [lmath.to_vtrac(d) for d in range(10)]  # digit -> vtrac 1-5


def _pos_vtrac_key(draw):
    return ((p, _VT[draw[p]]) for p in range(3))


@tactic("vtrac_due")
def vtrac_due(ctx):
    """Per-position vtrac dueness (expected positional gap = 5 draws) plus a
    0.3-weight hot component over the last 30 draws."""
    skips = ctx.skip_map("pos_vtrac", _pos_vtrac_key)
    hots = ctx.freq_map("pos_vtrac", _pos_vtrac_key, 30)
    tables = []
    for p in range(3):
        row = [0.0] * 6  # vtrac digits 1-5; slot 0 unused
        for v in range(1, 6):
            due = min(skips.get((p, v), 1000) / 10.0, 3.0)
            hot = 0.3 * hots.get((p, v), 0) / 6.0  # 6 = expected hits in 30 draws
            row[v] = due + hot
        tables.append(row)
    t0, t1, t2 = tables
    return [t0[_VT[a]] + t1[_VT[b]] + t2[_VT[c]] for a, b, c in lmath.ALL_1000]


@tactic("vtrac_return")
def vtrac_return(ctx):
    """Pool: straight expansion of last draw's vtrac at 1.0, expansions of its
    other boxed arrangements at 0.6, the last draw itself damped to 0.3 (exact
    repeats are rare). If the last vtrac is a double-vtrac, real doubles in the
    pool get a 1.4x boost."""
    last = ctx.last
    if last is None:
        return [0.0] * 1000
    vt = lmath.vtrac(last)
    weights = {c: 1.0 for c in lmath.vtrac_expand(vt)}
    for arr in set(permutations(vt)):
        if arr == vt:
            continue
        for c in lmath.vtrac_expand(arr):
            if c not in weights:
                weights[c] = 0.6
    if len(set(vt)) == 2:
        for c in weights:
            if lmath.classify(c) == "double":
                weights[c] *= 1.4
    weights[last] = 0.3
    return pool_scores(weights)
