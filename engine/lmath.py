"""Lottery-math primitives shared by every tactic.

Convention: a combo/draw is a tuple of 3 ints 0-9, positional (straight) order.
Index into the 1000-combo space is always 100*a + 10*b + c.
All workout arithmetic is digit-wise mod 10 with NO carry/borrow ("lottery math").
"""
from itertools import combinations_with_replacement, permutations, product

ALL_1000 = [(a, b, c) for a in range(10) for b in range(10) for c in range(10)]
ALL_BOXED = sorted(set(tuple(sorted(t)) for t in ALL_1000))  # 220 boxed keys


def idx(combo):
    return combo[0] * 100 + combo[1] * 10 + combo[2]


def from_idx(i):
    return (i // 100, (i // 10) % 10, i % 10)


def lmath_add(a, b):
    return tuple((x + y) % 10 for x, y in zip(a, b))


def lmath_sub(a, b):
    return tuple((x - y) % 10 for x, y in zip(a, b))


def lottery_sum(n):
    """Scalar 'keep the last digit' reduction used in date sums."""
    return n % 10


def mirror(d):
    return (d + 5) % 10


def sister(combo):
    return tuple(mirror(d) for d in combo)


def flip(d):
    return {6: 9, 9: 6}.get(d, d)


def comp(combo):
    """999 complement — no mod needed."""
    return tuple(9 - d for d in combo)


def mirror_variants(combo):
    """All 8 partial-mirror variants (2^3 masks), including the original."""
    return {
        tuple(combo[i] if not m[i] else mirror(combo[i]) for i in range(3))
        for m in product((0, 1), repeat=3)
    }


def to_vtrac(d):
    return (d % 5) + 1


def vtrac(combo):
    return tuple(to_vtrac(d) for d in combo)


def vtrac_expand(vt):
    """A straight vtrac expands to exactly 8 straight combos."""
    return set(product(*[((v - 1), (v - 1) + 5) for v in vt]))


def box_key(combo):
    return tuple(sorted(combo))


def classify(combo):
    """'single' (6-way), 'double' (3-way), or 'triple'."""
    u = len(set(combo))
    return "single" if u == 3 else ("double" if u == 2 else "triple")


def perm_count(combo):
    return len(set(permutations(combo)))


def digit_sum(combo):
    return sum(combo)


def root_sum(combo):
    s = sum(combo)
    return 0 if s == 0 else 1 + (s - 1) % 9


def sld(combo):
    return sum(combo) % 10


def hl_pattern(combo):
    return tuple("H" if d >= 5 else "L" for d in combo)


def eo_pattern(combo):
    return tuple("E" if d % 2 == 0 else "O" for d in combo)


def hl_boxed(combo):
    """(num_high, num_low)"""
    h = sum(1 for d in combo if d >= 5)
    return (h, 3 - h)


def eo_boxed(combo):
    e = sum(1 for d in combo if d % 2 == 0)
    return (e, 3 - e)


def one_off_cloud(combo):
    """27 combos including the original (3^3 +/-1 perturbations, 9<->0 wrap)."""
    return {
        tuple((combo[i] + delta[i]) % 10 for i in range(3))
        for delta in product((-1, 0, 1), repeat=3)
    }


def is_series(combo):
    return box_key(combo) in SERIES_BOXED


SERIES_BOXED = {tuple(sorted(((s) % 10, (s + 1) % 10, (s + 2) % 10))) for s in range(10)}

# Exact straight-count distribution of digit sums 0..27 (symmetric, peak 75 at 13/14).
SUM_COUNTS = [0] * 28
for _c in ALL_1000:
    SUM_COUNTS[sum(_c)] += 1


def wheel_box(pool, with_doubles=False):
    """Full box wheel over a digit pool -> sorted boxed combos."""
    it = combinations_with_replacement(sorted(set(pool)), 3) if with_doubles else (
        tuple(sorted(t)) for t in permutations(sorted(set(pool)), 3)
    )
    return sorted(set(tuple(sorted(t)) for t in it))
