"""Tests for the workout tactics: mirrors, ttt, rundowns, datesum."""
import math
import os
import sys
import types
from datetime import date

# The tactics registry (__init__) imports every sibling module. Some are being
# written concurrently by other agents — stub any that don't exist yet so this
# file stays runnable standalone. No-op once all modules are present.
_TACTICS_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "tactics")
for _name in ("hotcold", "mirrors", "vtrac", "ttt", "rundowns", "sums",
              "pairs", "followers", "patterns", "datesum", "community"):
    if not os.path.exists(os.path.join(_TACTICS_DIR, _name + ".py")):
        sys.modules["engine.tactics." + _name] = types.ModuleType("engine.tactics." + _name)

from engine import lmath  # noqa: E402
from engine.tactics import TACTICS, Ctx  # noqa: E402
from engine.tactics import datesum, rundowns, ttt  # noqa: E402

MY_KEYS = [
    "mirror_cloud", "ttt_plus1", "ttt_mirror",
    "rundown_111", "rundown_317", "rundown_123_stack", "rundown_pi",
    "datesum_key",
]

HISTORY = [
    (1, 2, 3), (4, 4, 7), (9, 9, 9), (0, 5, 2), (8, 1, 1),
    (3, 6, 0), (7, 7, 2), (5, 0, 9), (2, 8, 4), (6, 3, 3),
    (9, 1, 4), (0, 0, 0), (4, 2, 8), (1, 5, 7), (8, 8, 8),
] * 2  # 30 draws with doubles and triples mixed in


def make_ctx(draws, d=date(2026, 7, 17), period="mid"):
    return Ctx(list(draws), d, period)


def check_scores(scores):
    assert isinstance(scores, list) and len(scores) == 1000
    assert all(isinstance(x, float) and math.isfinite(x) and x >= 0.0 for x in scores)


def test_all_registered_and_valid_on_synthetic_history():
    for key in MY_KEYS:
        assert key in TACTICS, f"missing tactic {key}"
        check_scores(TACTICS[key](make_ctx(HISTORY)))


def test_short_and_empty_history():
    for draws in ([], [(1, 2, 3)], [(5, 5, 5), (0, 1, 2)]):
        for key in MY_KEYS:
            scores = TACTICS[key](make_ctx(draws))
            check_scores(scores)
    # Pool tactics return all zeros on empty history (datesum still has its base).
    for key in MY_KEYS:
        scores = TACTICS[key](make_ctx([]))
        if key != "datesum_key":
            assert scores == [0.0] * 1000, key
    # ttt_mirror needs >= 3 draws.
    assert TACTICS["ttt_mirror"](make_ctx([(1, 2, 3), (4, 5, 6)])) == [0.0] * 1000


def test_no_ctx_mutation():
    draws = [list(d) for d in HISTORY]  # independent copy for comparison
    ctx = make_ctx(HISTORY)
    for key in MY_KEYS:
        TACTICS[key](ctx)
    assert [tuple(d) for d in draws] == ctx.draws


def test_mirror_cloud_sister_is_max():
    scores = TACTICS["mirror_cloud"](make_ctx([(1, 2, 3)]))
    sister_idx = lmath.idx((6, 7, 8))
    top = max(scores)
    assert scores[sister_idx] == top == 1.2
    assert scores.count(top) == 1
    # The last draw itself is excluded from the pool.
    assert scores[lmath.idx((1, 2, 3))] == 0.0
    # Partial-mirror variants score 1.0; their perms 0.6x.
    assert scores[lmath.idx((6, 2, 3))] == 1.0
    assert scores[lmath.idx((2, 6, 3))] == 0.6


def test_ttt_variant_a_grid_golden():
    # Diagonal = 1,2,3; fill 4..9 placed per traversal (2,1),(2,0),(1,0),(0,1),(0,2),(1,2).
    g = ttt.diagonal_grid((1, 2, 3), +1)
    assert g == [[1, 7, 8], [6, 2, 9], [5, 4, 3]]
    lines, extras = ttt.readout(g)
    assert len(lines) == 8 and len(extras) == 6
    assert (1, 7, 8) in lines and (1, 2, 3) in lines  # top row + main diagonal
    scores = TACTICS["ttt_plus1"](make_ctx([(1, 2, 3)]))
    assert scores[lmath.idx((1, 7, 8))] == 1.0
    assert scores[lmath.idx((8, 7, 1))] == 1.0  # boxed expansion at full weight


def test_ttt_mirror_grids():
    # Oldest first: last 3 draws newest-first are (3,3,3),(2,2,2),(1,1,1).
    scores = TACTICS["ttt_mirror"](make_ctx([(1, 1, 1), (2, 2, 2), (3, 3, 3)]))
    assert scores[lmath.idx((3, 3, 3))] == 1.0  # left top row
    assert scores[lmath.idx((1, 2, 3))] == 1.0  # perm of left column (3,2,1)
    assert scores[lmath.idx((8, 8, 8))] == 0.9  # right (mirror) top row


def test_rundown_golden():
    assert rundowns.rundown((9, 1, 4), (1, 2, 3))[1] == (0, 3, 7)
    assert rundowns.stack_123((9, 1, 4)) == [(0, 3, 7), (8, 0, 3), (1, 4, 9)]
    ctx = make_ctx([(9, 1, 4)])
    scores = TACTICS["rundown_123_stack"](ctx)
    for row in [(0, 3, 7), (8, 0, 3), (1, 4, 9)]:
        assert scores[lmath.idx(row)] == 1.0  # grid rows read out at full weight
    # 111 rundown: row 1 from (9,1,4) is (0,2,5).
    s111 = TACTICS["rundown_111"](ctx)
    assert s111[lmath.idx((0, 2, 5))] > 0
    assert s111[lmath.idx((9, 1, 4))] == 0.0  # seed row skipped


def test_rundown_317_both_directions():
    ctx = make_ctx([(0, 0, 0)])
    scores = TACTICS["rundown_317"](ctx)
    # +row1 (3,1,7) is also -row9 — every full-cycle row appears in both ladders,
    # so direct rows carry the x1.5 both-directions boost.
    assert scores[lmath.idx((3, 1, 7))] > 0
    assert scores[lmath.idx((5, 5, 5))] > 0  # +/- row 5
    assert scores[lmath.idx((0, 0, 0))] == 0.0  # seed skipped


def test_rundown_pi_form2_window():
    # last (1,2,3) -> 123 * 3.14 = 386.22 -> "386"; not a (3,1,4)-rundown row or perm.
    scores = TACTICS["rundown_pi"](make_ctx([(1, 2, 3)]))
    assert abs(scores[lmath.idx((3, 8, 6))] - 0.9) < 1e-9
    assert scores[lmath.idx((4, 3, 7))] > 0  # form-1 row 1


def test_datesum_keys_golden():
    # 3/14: ds=(3+14)%10=7 (mirror 2); ds2=0+3+1+4=8 (mirror 3).
    d = date(2026, 3, 14)
    assert datesum.key_digits(d) == {7, 2, 8, 3}
    scores = TACTICS["datesum_key"](make_ctx([], d=d))
    keys = {7, 2, 8, 3}
    assert scores[lmath.idx((7, 2, 0))] >= 1.0  # two distinct keys
    assert scores[lmath.idx((7, 0, 0))] >= 0.4  # one key
    # Combos with no key digit score exactly 0 (pyramid bonus implies a key digit).
    for c in lmath.ALL_1000:
        if not set(c) & keys:
            assert scores[lmath.idx(c)] == 0.0
    # Pyramid runs off MMDDYY (+ last draw when history exists).
    with_hist = TACTICS["datesum_key"](make_ctx([(9, 1, 4)], d=d))
    check_scores(with_hist)


def test_pyramid_shape():
    pyr = datesum.build_pyramid([1, 2, 3, 4, 5, 6])
    assert [len(r) for r in pyr] == [6, 5, 4, 3, 2, 1]
    assert pyr[1] == [3, 5, 7, 9, 1]  # pairwise mod-10 sums
    cands = datesum.pyramid_candidates(pyr)
    assert all(len(c) == 3 for c in cands)
    assert (1, 2, 3) in cands  # horizontal triple in the base row
    assert (1, 2, 3) == cands[0] or (1, 2, 3) in cands
    assert (1, 2, 3) in cands and (1, 2, pyr[1][0]) in cands  # triangle (r[0],r[1],above[0])
