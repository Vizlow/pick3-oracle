"""Hot / cold / overdue digit tactics (research: 'Hot / cold / overdue digits
with skip tracking').

Both tactics work positionally: build a 10-float score table per position, then
compose combo scores as the sum of the 3 positional digit scores. The (pos, digit)
skip/decay maps share the cache name 'pos_digit' with any other tactic that wants them.
"""
from engine import lmath
from engine.tactics import tactic

HALF_LIFE = 30       # draws — decay half-life for "hot" weighting
POS_GAP = 20.0       # 2x the 10-draw expected positional gap (skip_pos > 20 = due)
DUE_CAP = 3.0


@tactic("hot_digits")
def hot_digits(ctx):
    """Decay-weighted positional digit frequency; recent hits weigh most."""
    counts = ctx.decay_freq_map("pos_digit", enumerate, half_life=HALF_LIFE)
    t0, t1, t2 = ([counts.get((p, d), 0.0) for d in range(10)] for p in range(3))
    return [t0[a] + t1[b] + t2[c] for a, b, c in lmath.ALL_1000]


@tactic("due_digits")
def due_digits(ctx):
    """Positional skip ratio: score(p, d) = min(skip / 20, 3), summed over positions."""
    if not ctx.draws:
        return [0.0] * 1000
    skips = ctx.skip_map("pos_digit", enumerate)
    # A digit unseen in n draws is at least n out — that is all the history can say.
    default = min(len(ctx.draws), 1000)
    t0, t1, t2 = (
        [min(skips.get((p, d), default) / POS_GAP, DUE_CAP) for d in range(10)] for p in range(3)
    )
    return [t0[a] + t1[b] + t2[c] for a, b, c in lmath.ALL_1000]
