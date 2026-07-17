"""Rundown workout tactics — dossier sections '111 rundown', '123 rundown and the
123 workout stack', '317 rundown', 'Pi system (3.14 rundowns)'.
"""
from itertools import permutations

from engine import lmath
from engine.tactics import pool_scores, tactic
from engine.tactics.ttt import add_readout

# Weights for rows 1-9 (row 0 is the seed itself and is skipped).
ROW_WEIGHTS = (1.0, 0.95, 0.9, 0.85, 0.8, 0.4, 0.4, 0.4, 0.4)


def rundown(seed, step, op=lmath.lmath_add):
    """10 rows: the seed plus 9 successive lottery-math steps."""
    rows = [seed]
    for _ in range(9):
        rows.append(op(rows[-1], step))
    return rows


def date_keys(ctx):
    ds = (ctx.target_date.month + ctx.target_date.day) % 10
    return {ds, lmath.mirror(ds)}


def add_member(pool, combo, w):
    """Direct member at w, straight permutations at 0.6*w (max-merge)."""
    for p in permutations(combo):
        pw = w if p == combo else 0.6 * w
        if pw > pool.get(p, 0.0):
            pool[p] = pw


def score_rundown(pool, rows, keys, scale=1.0):
    """Rows 1-5 at 1.0..0.8, rows 6-9 at 0.4; x1.3 boost for rows containing the
    date-sum digit or its mirror. Rows are box-expanded (perms at 0.6x)."""
    for i in range(1, 10):
        w = ROW_WEIGHTS[i - 1] * scale
        if set(rows[i]) & keys:
            w *= 1.3
        add_member(pool, rows[i], w)


def stack_123(draw):
    """The '123 workout' stack grid: +123 / -111 / +235 rows."""
    return [
        lmath.lmath_add(draw, (1, 2, 3)),
        lmath.lmath_sub(draw, (1, 1, 1)),
        lmath.lmath_add(draw, (2, 3, 5)),
    ]


@tactic("rundown_111")
def rundown_111(ctx):
    if ctx.last is None:
        return [0.0] * 1000
    pool = {}
    score_rundown(pool, rundown(ctx.last, (1, 1, 1)), date_keys(ctx))
    return pool_scores(pool)


@tactic("rundown_317")
def rundown_317(ctx):
    """+317 and -317 ladders; combos landing in both directions get x1.5."""
    if ctx.last is None:
        return [0.0] * 1000
    keys = date_keys(ctx)
    up = rundown(ctx.last, (3, 1, 7))
    down = rundown(ctx.last, (3, 1, 7), op=lmath.lmath_sub)
    pool = {}
    score_rundown(pool, up, keys)
    score_rundown(pool, down, keys)
    for combo in set(up[1:]) & set(down[1:]):
        pool[combo] *= 1.5
    return pool_scores(pool)


@tactic("rundown_123_stack")
def rundown_123_stack(ctx):
    """123 workout stack as a TTT grid (readout 1.0/0.7) + plain +123 rundown at 0.6."""
    if ctx.last is None:
        return [0.0] * 1000
    pool = {}
    add_readout(pool, stack_123(ctx.last), 1.0, 0.7)
    score_rundown(pool, rundown(ctx.last, (1, 2, 3)), date_keys(ctx), scale=0.6)
    return pool_scores(pool)


@tactic("rundown_pi")
def rundown_pi(ctx):
    """Form 1: (3,1,4) rundown at standard weights. Form 2: 3-digit windows of
    str(round(last_as_int * 3.14)), zero-padded, each at 0.9."""
    if ctx.last is None:
        return [0.0] * 1000
    pool = {}
    score_rundown(pool, rundown(ctx.last, (3, 1, 4)), date_keys(ctx))
    s = str(round(lmath.idx(ctx.last) * 3.14)).zfill(3)
    for i in range(len(s) - 2):
        add_member(pool, tuple(int(x) for x in s[i:i + 3]), 0.9)
    return pool_scores(pool)
