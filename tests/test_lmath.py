"""Golden values from the research dossier — these anchor every workout."""
from engine import lmath


def test_lottery_math_no_carry():
    assert lmath.lmath_add((9, 1, 4), (1, 2, 3)) == (0, 3, 7)
    assert lmath.lmath_sub((9, 1, 4), (1, 1, 1)) == (8, 0, 3)
    assert lmath.lmath_sub((0, 0, 0), (1, 1, 1)) == (9, 9, 9)


def test_mirror_and_sister():
    assert lmath.sister((1, 2, 3)) == (6, 7, 8)
    assert [lmath.mirror(d) for d in range(10)] == [5, 6, 7, 8, 9, 0, 1, 2, 3, 4]
    assert len(lmath.mirror_variants((1, 2, 3))) == 8
    assert (1, 2, 3) in lmath.mirror_variants((1, 2, 3))


def test_vtrac():
    assert lmath.vtrac((5, 8, 6)) == (1, 4, 2)
    exp = lmath.vtrac_expand((1, 4, 2))
    assert len(exp) == 8
    assert (5, 8, 6) in exp and (0, 3, 1) in exp
    # 125 straight vtracs, each expanding to 8 disjoint straights = full 1000 space
    assert 125 * 8 == 1000


def test_classify_and_perms():
    assert lmath.classify((1, 2, 3)) == "single" and lmath.perm_count((1, 2, 3)) == 6
    assert lmath.classify((1, 1, 2)) == "double" and lmath.perm_count((1, 1, 2)) == 3
    assert lmath.classify((7, 7, 7)) == "triple" and lmath.perm_count((7, 7, 7)) == 1
    singles = sum(1 for c in lmath.ALL_1000 if lmath.classify(c) == "single")
    doubles = sum(1 for c in lmath.ALL_1000 if lmath.classify(c) == "double")
    triples = sum(1 for c in lmath.ALL_1000 if lmath.classify(c) == "triple")
    assert (singles, doubles, triples) == (720, 270, 10)
    assert len(lmath.ALL_BOXED) == 220


def test_sums_roots_sld():
    assert lmath.SUM_COUNTS[13] == 75 and lmath.SUM_COUNTS[14] == 75
    assert lmath.SUM_COUNTS[0] == 1 and lmath.SUM_COUNTS[27] == 1
    assert all(lmath.SUM_COUNTS[s] == lmath.SUM_COUNTS[27 - s] for s in range(28))
    assert lmath.root_sum((5, 8, 9)) == 4  # 22 -> 4
    assert lmath.root_sum((0, 0, 0)) == 0
    for r in range(1, 10):
        assert sum(1 for c in lmath.ALL_1000 if lmath.root_sum(c) == r) == 111
    for d in range(10):
        assert sum(1 for c in lmath.ALL_1000 if lmath.sld(c) == d) == 100


def test_patterns():
    for pat in [(0, 3), (3, 0)]:
        assert sum(1 for c in lmath.ALL_1000 if lmath.hl_boxed(c) == pat) == 125
    mixed = sum(1 for c in lmath.ALL_1000 if lmath.hl_boxed(c) in [(1, 2), (2, 1)])
    assert mixed == 750
    assert len(lmath.SERIES_BOXED) == 10
    assert lmath.is_series((0, 9, 8)) and lmath.is_series((1, 2, 0))
    assert not lmath.is_series((1, 3, 5))


def test_one_off_and_comp():
    cloud = lmath.one_off_cloud((0, 0, 0))
    assert len(cloud) == 27 and (9, 9, 9) in cloud and (1, 1, 1) in cloud
    assert lmath.comp((9, 1, 4)) == (0, 8, 5)
    assert lmath.flip(6) == 9 and lmath.flip(9) == 6 and lmath.flip(4) == 4


def test_indexing():
    for i, c in enumerate(lmath.ALL_1000):
        assert lmath.idx(c) == i
    assert lmath.from_idx(586) == (5, 8, 6)
