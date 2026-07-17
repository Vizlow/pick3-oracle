"""Tic-tac-toe workout tactics — dossier section 'Tic-Tac-Toe (TTT) workouts'.

Shared grid/readout helpers live here; rundowns.py reuses them for the 123 stack.
"""
from itertools import permutations

from engine import lmath
from engine.tactics import pool_scores, tactic

# The 8 base lines: 3 rows, 3 cols, 2 diagonals.
LINE_CELLS = (
    [tuple((r, c) for c in range(3)) for r in range(3)]
    + [tuple((r, c) for r in range(3)) for c in range(3)]
    + [((0, 0), (1, 1), (2, 2)), ((0, 2), (1, 1), (2, 0))]
)
# Extended patterns: 4 corner-triples + 2 diamonds.
EXTRA_CELLS = [
    ((0, 0), (0, 2), (2, 0)),
    ((0, 0), (0, 2), (2, 2)),
    ((0, 0), (2, 0), (2, 2)),
    ((0, 2), (2, 0), (2, 2)),
    ((0, 1), (1, 0), (2, 1)),
    ((0, 1), (1, 2), (2, 1)),
]
# Documented fill traversal for the diagonal variants (A/B).
FILL_ORDER = ((2, 1), (2, 0), (1, 0), (0, 1), (0, 2), (1, 2))


def readout(grid):
    """Read a 3x3 grid -> (line_combos, extra_combos), 8 + 6 raw candidates."""
    lines = [tuple(grid[r][c] for r, c in cells) for cells in LINE_CELLS]
    extras = [tuple(grid[r][c] for r, c in cells) for cells in EXTRA_CELLS]
    return lines, extras


def add_boxed(pool, combos, w):
    """Merge candidates BOXED: every straight permutation scores w (max-merge dedupes)."""
    for combo in combos:
        for p in permutations(combo):
            if w > pool.get(p, 0.0):
                pool[p] = w


def add_readout(pool, grid, line_w, extra_w):
    lines, extras = readout(grid)
    add_boxed(pool, lines, line_w)
    add_boxed(pool, extras, extra_w)


def diagonal_grid(draw, sign=1):
    """Variant A (+1) / B (-1) grid: draw down the main diagonal, the 6 empty cells
    filled d3 +/- 1..6 (mod 10) in FILL_ORDER."""
    g = [[0] * 3 for _ in range(3)]
    g[0][0], g[1][1], g[2][2] = draw
    for k, (r, c) in enumerate(FILL_ORDER, start=1):
        g[r][c] = (draw[2] + sign * k) % 10
    return g


@tactic("ttt_plus1")
def ttt_plus1(ctx):
    """Variant A (+1 fill) readouts at 1.0/0.7, variant B (-1 fill) at 0.8/0.5."""
    if ctx.last is None:
        return [0.0] * 1000
    pool = {}
    add_readout(pool, diagonal_grid(ctx.last, +1), 1.0, 0.7)
    add_readout(pool, diagonal_grid(ctx.last, -1), 0.8, 0.5)
    return pool_scores(pool)


@tactic("ttt_mirror")
def ttt_mirror(ctx):
    """Variant C: left grid rows = last 3 draws newest first, right grid = +5 mirror.
    Left readouts at 1.0/0.7, right at 0.9/0.6."""
    if len(ctx.draws) < 3:
        return [0.0] * 1000
    left = [list(d) for d in reversed(ctx.window(3))]
    right = [[lmath.mirror(d) for d in row] for row in left]
    pool = {}
    add_readout(pool, left, 1.0, 0.7)
    add_readout(pool, right, 0.9, 0.6)
    return pool_scores(pool)
