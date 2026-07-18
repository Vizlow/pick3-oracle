"""Sequence-family tactic tests: vtrac, pairs, followers, community.

engine.tactics imports every tactic module at the bottom of its __init__, so any
sibling module another work stream has not written yet is stubbed first to keep
the package importable in isolation. Once all modules exist, no stubs are used.
"""
import pathlib
import sys
import types

_PKG = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tactics"
for _name in ("hotcold", "mirrors", "vtrac", "ttt", "rundowns", "sums",
              "pairs", "followers", "patterns", "datesum", "community"):
    if not (_PKG / (_name + ".py")).exists():
        sys.modules["engine.tactics." + _name] = types.ModuleType("engine.tactics." + _name)

import math                              # noqa: E402
import random                            # noqa: E402
from datetime import date                # noqa: E402

import pytest                            # noqa: E402

from engine import lmath                 # noqa: E402
from engine.tactics import TACTICS, Ctx  # noqa: E402
from engine.tactics import followers as followers_mod  # noqa: E402
from engine.tactics import pairs as pairs_mod          # noqa: E402

SEQ_KEYS = ("vtrac_due", "vtrac_return", "pair_due", "follower_digit", "follower_pair", "community")


def make_ctx(draws, community=None):
    return Ctx(list(draws), date(2026, 7, 17), "eve", community=community)


def rand_history(n, seed=7):
    rng = random.Random(seed)
    return [tuple(rng.randrange(10) for _ in range(3)) for _ in range(n)]


def test_all_registered():
    for key in SEQ_KEYS:
        assert key in TACTICS


def test_valid_vectors_on_all_history_shapes():
    histories = [
        [],
        [(5, 8, 6)],
        [(1, 1, 1), (2, 2, 7), (9, 9, 9), (0, 0, 5)],  # <5 draws, doubles + triples
        rand_history(60),
        rand_history(400, seed=11),
    ]
    picks = [{"member": "al", "combo": [1, 2, 3]}, {"member": "bo", "combo": [4, 4, 9]}]
    for draws in histories:
        for key in SEQ_KEYS:
            ctx = make_ctx(draws, community=picks)
            before = list(ctx.draws)
            scores = TACTICS[key](ctx)
            assert len(scores) == 1000, key
            assert all(isinstance(x, float) and math.isfinite(x) for x in scores), key
            assert ctx.draws == before, key  # never mutate history


# --- vtrac ---------------------------------------------------------------

def test_vtrac_due_prefers_absent_vtracs():
    ctx = make_ctx([(9, 9, 9)] * 40)  # vtrac 5 hot in every position, 1-4 long out
    scores = TACTICS["vtrac_due"](ctx)
    assert scores[lmath.idx((0, 0, 0))] > scores[lmath.idx((9, 9, 9))]


def test_vtrac_return_pool():
    ctx = make_ctx([(1, 2, 3), (5, 8, 6)])  # vtrac(5,8,6) = (1,4,2)
    scores = TACTICS["vtrac_return"](ctx)
    assert scores[lmath.idx((0, 3, 1))] == pytest.approx(1.0)  # straight expansion member
    assert scores[lmath.idx((5, 8, 6))] == pytest.approx(0.3)  # exact repeat damped
    assert scores[lmath.idx((3, 0, 1))] == pytest.approx(0.6)  # boxed arrangement (4,1,2)
    assert scores[lmath.idx((1, 1, 1))] == 0.0                 # outside the vtrac family


def test_vtrac_return_double_vtrac_boost():
    ctx = make_ctx([(0, 0, 1)])  # vtrac (1,1,2) is a double-vtrac
    scores = TACTICS["vtrac_return"](ctx)
    assert scores[lmath.idx((0, 0, 6))] == pytest.approx(1.4)  # real double boosted
    assert scores[lmath.idx((0, 5, 1))] == pytest.approx(1.0)  # single, unboosted
    assert scores[lmath.idx((0, 0, 1))] == pytest.approx(0.3)  # last draw still damped


def test_vtrac_return_empty_history():
    assert TACTICS["vtrac_return"](make_ctx([])) == [0.0] * 1000


# --- pairs ---------------------------------------------------------------

def test_pair_due_prefers_unseen_pairs():
    ctx = make_ctx([(1, 2, 3)] * 10)
    scores = TACTICS["pair_due"](ctx)
    assert scores[lmath.idx((4, 5, 6))] > scores[lmath.idx((1, 2, 3))]


def test_predict_pairs_valid():
    for draws in ([], rand_history(150, seed=3)):
        res = pairs_mod.predict_pairs(make_ctx(draws))
        assert set(res) == {"front", "back"}
        for kind in ("front", "back"):
            pair = res[kind]
            assert len(pair) == 2
            assert all(isinstance(d, int) and 0 <= d <= 9 for d in pair)


# --- followers -----------------------------------------------------------

def test_follower_digit_learns_transitions():
    draws = [(1, 1, 1), (7, 7, 7)] * 25 + [(1, 1, 1)]  # 7 always follows 1
    scores = TACTICS["follower_digit"](make_ctx(draws))
    with7 = [s for c, s in zip(lmath.ALL_1000, scores) if 7 in c]
    without7 = [s for c, s in zip(lmath.ALL_1000, scores) if 7 not in c]
    assert min(with7) > max(without7)


def test_follower_digit_old_mans_zero():
    ctx = make_ctx([(5, 5, 5), (0, 1, 2)])  # 0 hit, 3 and 6 absent -> rule fires
    scores = TACTICS["follower_digit"](ctx)
    assert scores[lmath.idx((3, 3, 3))] == pytest.approx(0.4)  # uniform 0.1 + 0.3
    assert scores[lmath.idx((4, 4, 4))] == pytest.approx(0.1)


def test_follower_pair_transitions():
    draws = [(0, 2, 3), (0, 5, 6)] * 20 + [(0, 2, 3)]  # back (2,3) -> back (5,6)
    scores = TACTICS["follower_pair"](make_ctx(draws))
    assert scores[lmath.idx((0, 5, 6))] == max(scores)
    assert scores[lmath.idx((0, 5, 6))] > scores[lmath.idx((0, 6, 5))]


def test_follower_pair_backoff_when_thin():
    ctx = make_ctx([(1, 2, 3), (4, 5, 6)])  # back pair (5,6) never a predecessor
    scores = TACTICS["follower_pair"](ctx)
    base = followers_mod._digit_score_vector(ctx)
    assert scores == [0.5 * x for x in base]


# --- community -----------------------------------------------------------

def test_community_single_pick_argmax():
    picks = [{"member": "al", "combo": [1, 2, 3]}]
    scores = TACTICS["community"](make_ctx(rand_history(10), community=picks))
    assert scores.index(max(scores)) == 123
    assert scores[lmath.idx((1, 2, 3))] == pytest.approx(1.0)
    assert scores[lmath.idx((3, 2, 1))] == pytest.approx(0.5)  # boxed arrangement
    assert sum(1 for s in scores if s > 0) == 6  # straight + 5 perms


def test_community_multi_member_and_cap():
    picks = [{"member": m, "combo": [7, 7, 8]} for m in "abcdefgh"]  # 8 members
    scores = TACTICS["community"](make_ctx([], community=picks))
    assert scores[lmath.idx((7, 7, 8))] == pytest.approx(3.0)  # sum of skills, capped
    assert scores[lmath.idx((8, 7, 7))] == pytest.approx(1.5)  # 0.5x perm coverage
    two = [{"member": "a", "combo": [1, 2, 3]}, {"member": "b", "combo": [1, 2, 3]}]
    scores = TACTICS["community"](make_ctx([], community=two))
    assert scores[lmath.idx((1, 2, 3))] == pytest.approx(2.0)  # 1.0 + 1.0


def test_community_skill_weighting():
    picks = [{"member": "hot", "combo": [1, 2, 3], "skill": 2.5},
             {"member": "cold", "combo": [4, 5, 6], "skill": 0.5}]
    scores = TACTICS["community"](make_ctx([], community=picks))
    assert scores[lmath.idx((1, 2, 3))] == pytest.approx(2.5)
    assert scores[lmath.idx((4, 5, 6))] == pytest.approx(0.5)
    assert scores[lmath.idx((1, 2, 3))] > scores[lmath.idx((4, 5, 6))]


def test_community_empty_and_malformed():
    assert TACTICS["community"](make_ctx(rand_history(5))) == [0.0] * 1000
    bad = [{"member": "x", "combo": [1, 2]}, {"member": "y", "combo": [1, 12, 3]}]
    assert TACTICS["community"](make_ctx([], community=bad)) == [0.0] * 1000
