"""Structural pattern tactics (research: 'High/low and even/odd pattern filters',
'Doubles tracking', 'Triples tracking', 'Series / consecutive numbers',
'Repeat / carryover digit rule').
"""
from engine import lmath
from engine.tactics import tactic

MIXED = {(1, 2), (2, 1)}
PAT_GAPS = {(0, 3): 8.0, (1, 2): 2.7, (2, 1): 2.7, (3, 0): 8.0}
PAT_CAP = 3.0

DOUBLE_GAP = 3.7     # doubles hit ~27% of draws
TRIPLE_GAP = 100.0   # 10/1000 straights
SERIES_GAP = 16.7    # 60/1000 straights
DDD_GAP = 1000.0     # a specific triple ddd
DUE_RATIO = 2.0      # "due" = skip past 2x expected gap
SINGLES_BASE = 0.2

CARRY_SCORE = (0.3, 1.0, 0.6, 0.2)  # indexed by |set(last) & set(combo)|

# Per-combo structure, fixed for all time — precompute once at import.
_HL = [lmath.hl_boxed(c) for c in lmath.ALL_1000]
_EO = [lmath.eo_boxed(c) for c in lmath.ALL_1000]
_CLASS = [lmath.classify(c) for c in lmath.ALL_1000]
_SERIES = [lmath.is_series(c) for c in lmath.ALL_1000]


@tactic("pattern_balance")
def pattern_balance(ctx):
    """Mixed HL/EO preference (750/1000 straights) + dueness of the exact boxed groups."""
    n = min(len(ctx.draws), 1000)
    hl_skips = ctx.skip_map("hl_boxed", lambda d: (lmath.hl_boxed(d),))
    eo_skips = ctx.skip_map("eo_boxed", lambda d: (lmath.eo_boxed(d),))

    def group_score(skips, pat):
        due = min(skips.get(pat, n) / PAT_GAPS[pat], PAT_CAP)
        return (1.0 if pat in MIXED else 0.0) + due

    hl = {p: group_score(hl_skips, p) for p in PAT_GAPS}
    eo = {p: group_score(eo_skips, p) for p in PAT_GAPS}
    return [hl[h] + eo[e] for h, e in zip(_HL, _EO)]


def _structure_labels(draw):
    labels = [lmath.classify(draw)]
    if labels[0] == "triple":
        labels.append(("ddd", draw[0]))
    if lmath.is_series(draw):
        labels.append("series")
    return labels


@tactic("structure_due")
def structure_due(ctx):
    """Boost doubles / triples / series once their skip runs past 2x expected gap."""
    n = min(len(ctx.draws), 1000)
    skips = ctx.skip_map("structure", _structure_labels)
    double_ratio = skips.get("double", n) / DOUBLE_GAP
    triple_ratio = skips.get("triple", n) / TRIPLE_GAP
    series_ratio = skips.get("series", n) / SERIES_GAP
    double_score = double_ratio if double_ratio > DUE_RATIO else 0.0
    series_bonus = series_ratio if series_ratio > DUE_RATIO else 0.0
    if triple_ratio > DUE_RATIO:
        # grade individual triples by how long each specific ddd has been out
        triple_score = [triple_ratio + skips.get(("ddd", d), n) / DDD_GAP for d in range(10)]
    else:
        triple_score = [0.0] * 10
    scores = []
    for i, c in enumerate(lmath.ALL_1000):
        cls = _CLASS[i]
        if cls == "single":
            scores.append(SINGLES_BASE + (series_bonus if _SERIES[i] else 0.0))
        elif cls == "double":
            scores.append(double_score)
        else:
            scores.append(triple_score[c[0]])
    return scores


@tactic("carryover")
def carryover(ctx):
    """At least one digit usually returns; exactly one carryover is the classic play."""
    if ctx.last is None:
        return [0.0] * 1000
    last = set(ctx.last)
    return [CARRY_SCORE[len(last.intersection(c))] for c in lmath.ALL_1000]
