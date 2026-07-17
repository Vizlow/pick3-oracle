"""Sum-family dueness (research: 'Sums (sum totals) filter', 'Root sums',
'Sum last digit').

Every component depends only on the combo's digit sum, so the whole tactic reduces
to a 28-entry table composed over ALL_1000. Expected straight gaps: sum s recurs
every 1000/SUM_COUNTS[s] draws, roots 1-9 every ~9, each SLD every ~10.
"""
from engine import lmath
from engine.tactics import tactic

DUE_CAP = 4.0
ROOT_GAP = 9.0       # roots 1-9; root 0 only hits on 000 (gap 1000)
SLD_GAP = 10.0


@tactic("sum_due")
def sum_due(ctx):
    """0.5*sum + 0.3*root + 0.2*SLD dueness, plus a small mid-range centrality prior."""
    n = min(len(ctx.draws), 1000)
    sum_skips = ctx.skip_map("sum", lambda d: (sum(d),))
    root_skips = ctx.skip_map("root_sum", lambda d: (lmath.root_sum(d),))
    sld_skips = ctx.skip_map("sld", lambda d: (lmath.sld(d),))
    # dueness = min(skip / expected_gap, 4); gap for sum s is 1000/SUM_COUNTS[s]
    due_sum = [min(sum_skips.get(s, n) * lmath.SUM_COUNTS[s] / 1000.0, DUE_CAP) for s in range(28)]
    due_root = [min(root_skips.get(r, n) / (1000.0 if r == 0 else ROOT_GAP), DUE_CAP) for r in range(10)]
    due_sld = [min(sld_skips.get(d, n) / SLD_GAP, DUE_CAP) for d in range(10)]
    tab = [
        0.5 * due_sum[s]
        + 0.3 * due_root[0 if s == 0 else 1 + (s - 1) % 9]
        + 0.2 * due_sld[s % 10]
        + 0.1 * (lmath.SUM_COUNTS[s] / 75.0)
        for s in range(28)
    ]
    return [tab[a + b + c] for a, b, c in lmath.ALL_1000]
