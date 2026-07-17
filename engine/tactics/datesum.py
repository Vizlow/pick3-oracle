"""Date-sum key digits + dateline pyramid — dossier sections 'Date sum workout' and
'Pyramid / dateline pyramid workout'. Dense scorer (not pool-only): every combo gets
a key-digit base score, pyramid candidates add a bonus on top.
"""
from itertools import permutations

from engine import lmath
from engine.tactics import tactic


def key_digits(target_date):
    """Both date-sum variants and their mirrors. ds = (m+d)%10; ds2 = MMDD digit sum %10."""
    ds = (target_date.month + target_date.day) % 10
    ds2 = sum(int(c) for c in f"{target_date.month:02d}{target_date.day:02d}") % 10
    return {ds, lmath.mirror(ds), ds2, lmath.mirror(ds2)}


def build_pyramid(base):
    """Mod-10 pyramid: each row is pairwise sums of the row below it."""
    pyramid = [list(base)]
    while len(pyramid[-1]) > 1:
        prev = pyramid[-1]
        pyramid.append([(prev[i] + prev[i + 1]) % 10 for i in range(len(prev) - 1)])
    return pyramid


def pyramid_candidates(pyramid):
    """Horizontal triples (r[i],r[i+1],r[i+2]) + triangle groups (r[i],r[i+1],above[i])."""
    cands = []
    for k, row in enumerate(pyramid):
        for i in range(len(row) - 2):
            cands.append((row[i], row[i + 1], row[i + 2]))
        if k + 1 < len(pyramid):
            above = pyramid[k + 1]
            for i in range(len(row) - 1):
                cands.append((row[i], row[i + 1], above[i]))
    return cands


@tactic("datesum_key")
def datesum_key(ctx):
    """Base: combos with >=2 distinct key digits score 1.0, >=1 scores 0.4.
    Pyramid (base = MMDDYY digits + last draw if any): candidates intersecting
    {ds, mirror(ds)} add +0.8, box-expanded at 0.5x (+0.4 for permutations)."""
    td = ctx.target_date
    keys = key_digits(td)
    scores = []
    for c in lmath.ALL_1000:
        k = len(set(c) & keys)
        scores.append(1.0 if k >= 2 else (0.4 if k == 1 else 0.0))

    ds = (td.month + td.day) % 10
    highlight = {ds, lmath.mirror(ds)}
    base = [int(x) for x in f"{td.month:02d}{td.day:02d}{td.year % 100:02d}"]
    if ctx.last is not None:
        base += list(ctx.last)
    bonus = {}
    for cand in pyramid_candidates(build_pyramid(base)):
        if not set(cand) & highlight:
            continue
        for p in permutations(cand):
            b = 0.8 if p == cand else 0.4
            if b > bonus.get(p, 0.0):
                bonus[p] = b
    for combo, b in bonus.items():
        scores[lmath.idx(combo)] += b
    return scores
