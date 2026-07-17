"""Pair tactics — positional/unordered pair dueness, plus predict_pairs, the
front/back positional-pair prediction hook the ensemble calls directly."""
from itertools import combinations

from engine import lmath
from engine.tactics import tactic
from engine.tactics.followers import pair_transition_table

_POS_KINDS = ("f", "s", "b")
_EXP_UNORDERED_DISTINCT = 18.5  # 1000/54 draws between hits of a distinct pair
_EXP_UNORDERED_DOUBLE = 35.7    # 1000/28 for a doubled pair


def _pos_pair_key(draw):
    a, b, c = draw
    return (("f", (a, b)), ("s", (a, c)), ("b", (b, c)))


def _unordered_pair_key(draw):
    return set(combinations(sorted(draw), 2))


def _due_tables(ctx):
    """Dueness (capped 3.0) per positional ordered pair (by kind) and per
    unordered pair. Positional expected gap = 100 draws."""
    skips = ctx.skip_map("pos_pairs", _pos_pair_key)
    uskips = ctx.skip_map("unordered_pairs", _unordered_pair_key)
    pos = {}
    for kind in _POS_KINDS:
        pos[kind] = {
            (x, y): min(skips.get((kind, (x, y)), 1000) / 100.0, 3.0)
            for x in range(10) for y in range(10)
        }
    udue = {}
    for x in range(10):
        for y in range(x, 10):
            exp = _EXP_UNORDERED_DOUBLE if x == y else _EXP_UNORDERED_DISTINCT
            udue[(x, y)] = min(uskips.get((x, y), 1000) / exp, 3.0)
    return pos, udue


@tactic("pair_due")
def pair_due(ctx):
    """Max positional-pair dueness among a combo's 3 pairs + 0.5 * max unordered
    pair dueness."""
    pos, udue = _due_tables(ctx)
    fdue, sdue, bdue = pos["f"], pos["s"], pos["b"]
    scores = []
    for a, b, c in lmath.ALL_1000:
        lo, md, hi = sorted((a, b, c))
        p = max(fdue[(a, b)], sdue[(a, c)], bdue[(b, c)])
        u = max(udue[(lo, md)], udue[(lo, hi)], udue[(md, hi)])
        scores.append(p + 0.5 * u)
    return scores


def predict_pairs(ctx):
    """Argmax front/back positional pairs for the ensemble's pairs prediction.
    Blend: 0.5*dueness + 0.3*windowed z-freq + 0.2*follower P(pair | last back
    pair) when that predecessor has been observed."""
    pos, _ = _due_tables(ctx)
    counts = ctx.freq_map("pos_pairs", _pos_pair_key, 100)
    n = min(len(ctx.draws), 100)
    sd = (n * 0.01 * 0.99) ** 0.5 if n else 0.0
    fol, totals = pair_transition_table(ctx)
    prev = (ctx.last[1], ctx.last[2]) if ctx.last else None
    result = {}
    for kind_key, kind in (("f", "front"), ("b", "back")):
        due = pos[kind_key]
        total = totals.get(prev, 0) if prev is not None else 0
        row = fol[kind].get(prev, {}) if total else None
        best, best_score = (0, 0), float("-inf")
        for x in range(10):
            for y in range(10):
                pair = (x, y)
                score = 0.5 * due[pair]
                if sd:
                    score += 0.3 * (counts.get((kind_key, pair), 0) - n * 0.01) / sd
                if row is not None:
                    score += 0.2 * row.get(pair, 0) / total
                if score > best_score:
                    best, best_score = pair, score
        result[kind] = list(best)
    return result
