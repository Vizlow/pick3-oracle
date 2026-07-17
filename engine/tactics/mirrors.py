"""Mirror (+5) workout tactics — dossier section 'Mirror numbers (+5) and mirror workouts'."""
from itertools import permutations

from engine import lmath
from engine.tactics import pool_scores, tactic


@tactic("mirror_cloud")
def mirror_cloud(ctx):
    """Pool around the last draw's mirror family: the 7 partial-mirror variants at 1.0,
    the full sister at 1.2 (players favor it), the 6/9-flip variant at 0.8. Every pool
    member is box-expanded — straight permutations score 0.6x the direct member."""
    last = ctx.last
    if last is None:
        return [0.0] * 1000
    pool = {}

    def add(combo, w):
        if w > pool.get(combo, 0.0):
            pool[combo] = w

    sis = lmath.sister(last)
    for v in lmath.mirror_variants(last):
        if v != last:
            add(v, 1.2 if v == sis else 1.0)
    flipped = tuple(lmath.flip(d) for d in last)
    if flipped != last:
        add(flipped, 0.8)
    for combo, w in list(pool.items()):
        for p in permutations(combo):
            add(p, 0.6 * w)
    return pool_scores(pool)
