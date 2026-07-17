"""Stats-family tactics: hotcold.py, sums.py, patterns.py."""
import math
import os
import random
import sys
import types
from datetime import date

import pytest

# Sibling tactic modules are built concurrently; stub any that don't exist yet so
# the registry import in engine/tactics/__init__.py succeeds. No-op once they land.
_TACTICS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine", "tactics")
for _name in ("hotcold", "mirrors", "vtrac", "ttt", "rundowns", "sums",
              "pairs", "followers", "patterns", "datesum", "community"):
    if not os.path.exists(os.path.join(_TACTICS_DIR, _name + ".py")):
        sys.modules.setdefault("engine.tactics." + _name, types.ModuleType("engine.tactics." + _name))

from engine import lmath  # noqa: E402
from engine.tactics import TACTICS, Ctx  # noqa: E402

KEYS = ("hot_digits", "due_digits", "sum_due", "pattern_balance", "structure_due", "carryover")


def make_ctx(draws):
    return Ctx(draws, date(2026, 7, 17), "eve")


def varied_history(n=60, seed=7):
    rng = random.Random(seed)
    draws = [tuple(rng.randrange(10) for _ in range(3)) for _ in range(n - 3)]
    draws += [(4, 4, 2), (7, 7, 7), (1, 2, 3)]  # guarantee a double, triple, series
    return draws


def test_all_keys_registered():
    for key in KEYS:
        assert key in TACTICS


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("draws", [varied_history(), [(1, 2, 3), (4, 5, 6)], []],
                         ids=["60-draws", "2-draws", "empty"])
def test_returns_1000_finite_floats(key, draws):
    draws = list(draws)
    before = list(draws)
    scores = TACTICS[key](make_ctx(draws))
    assert len(scores) == 1000
    assert all(isinstance(s, (int, float)) and math.isfinite(s) for s in scores)
    assert draws == before  # ctx.draws never mutated


def test_hot_digits_ranks_hot_over_absent():
    draws = [(7, 1, 2), (7, 4, 5)] * 15  # 7 hammered in pos 0; 3 never appears anywhere
    scores = TACTICS["hot_digits"](make_ctx(draws))
    assert scores[lmath.idx((7, 1, 2))] > scores[lmath.idx((3, 1, 2))]
    assert scores[lmath.idx((7, 0, 0))] > scores[lmath.idx((3, 0, 0))]


def test_due_digits_prefers_long_skipped_positional_digit():
    rng = random.Random(3)
    draws = [(rng.randrange(5), rng.randrange(10), rng.randrange(10)) for _ in range(40)]
    draws.append((0, 1, 2))
    scores = TACTICS["due_digits"](make_ctx(draws))
    # 9 never hit position 0; 0 just did
    assert scores[lmath.idx((9, 1, 2))] > scores[lmath.idx((0, 1, 2))]


def test_sum_due_prefers_overdue_sum_family():
    draws = [(5, 5, 3)] * 40  # sum 13 / root 4 / SLD 3 hammered; sum 14 families untouched
    scores = TACTICS["sum_due"](make_ctx(draws))
    assert scores[lmath.idx((5, 5, 4))] > scores[lmath.idx((5, 5, 3))]


def test_pattern_balance_prefers_mixed_patterns():
    scores = TACTICS["pattern_balance"](make_ctx([]))
    # (1,2,7) is mixed HL and mixed EO; (0,2,4) is all-low all-even
    assert scores[lmath.idx((1, 2, 7))] > scores[lmath.idx((0, 2, 4))]


def test_pattern_balance_dueness_lifts_absent_group():
    draws = [(1, 2, 7)] * 30  # HL (1,2) / EO (1,2) on repeat -> (3,0) groups deeply due
    scores = TACTICS["pattern_balance"](make_ctx(draws))
    assert scores[lmath.idx((5, 6, 7))] > scores[lmath.idx((1, 2, 7))]


def test_structure_due_boosts_overdue_doubles():
    draws = [(1, 3, 7), (2, 5, 9), (0, 4, 8), (1, 5, 8)] * 3  # 12 draws, all singles
    assert all(lmath.classify(d) == "single" for d in draws)
    scores = TACTICS["structure_due"](make_ctx(draws))
    double_score = scores[lmath.idx((4, 4, 2))]
    single_score = scores[lmath.idx((1, 3, 7))]
    assert double_score > 2.0  # skip 12 / 3.7 expected gap ≈ 3.24
    assert double_score > single_score > 0
    # a double in the very last draw resets the skip -> no boost
    scores2 = TACTICS["structure_due"](make_ctx(draws + [(4, 4, 2)]))
    assert scores2[lmath.idx((5, 5, 1))] == 0.0


def test_structure_due_boosts_overdue_triples_and_series():
    rng = random.Random(11)
    draws = []
    while len(draws) < 250:
        d = tuple(rng.randrange(10) for _ in range(3))
        if lmath.classify(d) == "single" and not lmath.is_series(d):
            draws.append(d)
    scores = TACTICS["structure_due"](make_ctx(draws))
    assert scores[lmath.idx((7, 7, 7))] > scores[lmath.idx((1, 3, 7))]  # triples due
    assert scores[lmath.idx((1, 2, 3))] > scores[lmath.idx((1, 3, 7))]  # series due


def test_carryover_scores():
    scores = TACTICS["carryover"](make_ctx([(9, 9, 9), (1, 2, 3)]))
    assert scores[lmath.idx((1, 4, 5))] == 1.0  # exactly one digit returns — classic play
    assert scores[lmath.idx((1, 2, 4))] == 0.6
    assert scores[lmath.idx((1, 2, 3))] == 0.2
    assert scores[lmath.idx((4, 5, 6))] == 0.3
    assert TACTICS["carryover"](make_ctx([])) == [0.0] * 1000
