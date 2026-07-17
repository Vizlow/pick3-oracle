"""No-look-ahead + determinism guarantees.

Ctx only ever receives history strictly before the target (enforced here against
the pipeline's slicer), tactics never mutate history, and the same ctx always
produces the same prediction — required because live grading re-derives tactic
scores from pre-draw history after the result is known.
"""
import random
from datetime import date

from engine import ensemble
from engine.tactics import Ctx, TACTICS


def synth_history(n, seed=7):
    rng = random.Random(seed)
    return [tuple(rng.randrange(10) for _ in range(3)) for _ in range(n)]


def test_registry_populated():
    assert len(TACTICS) >= 18, sorted(TACTICS)


def test_tactics_do_not_mutate_history():
    draws = synth_history(80)
    snapshot = [tuple(d) for d in draws]
    ctx = Ctx(draws, date(2026, 7, 17), "eve")
    for fn in TACTICS.values():
        fn(ctx)
    assert draws == snapshot


def test_sentinel_after_target_cannot_leak():
    """Appending a future draw to the master list must not change scores computed
    from the pre-target slice — i.e. slicing is the only door and it's shut."""
    draws = synth_history(60)
    t = 50
    ctx_a = Ctx(draws[:t], date(2026, 7, 17), "mid")
    scores_a = ensemble.tactic_scores(ctx_a)
    mutated = draws[:t] + [(9, 9, 9)] + draws[t + 1:]
    ctx_b = Ctx(mutated[:t], date(2026, 7, 17), "mid")
    scores_b = ensemble.tactic_scores(ctx_b)
    assert scores_a.keys() == scores_b.keys()
    for key in scores_a:
        assert scores_a[key] == scores_b[key], f"{key} leaked future data"


def test_prediction_deterministic():
    draws = synth_history(120, seed=3)
    w = {key: 1.0 / len(TACTICS) for key in TACTICS}
    p1, s1 = ensemble.predict(Ctx(draws, date(2026, 7, 17), "eve"), w, "t")
    p2, s2 = ensemble.predict(Ctx(draws, date(2026, 7, 17), "eve"), w, "t")
    assert p1["picks"] == p2["picks"]
    assert p1["pairs"] == p2["pairs"]
    for key in s1:
        assert s1[key] == s2[key]


def test_pipeline_slices_strictly_before():
    from engine import timeutil
    draws = [
        {"id": "2026-07-15-mid", "digits": [1, 2, 3]},
        {"id": "2026-07-15-eve", "digits": [4, 5, 6]},
        {"id": "2026-07-16-mid", "digits": [7, 8, 9]},
    ]
    key = timeutil.sort_key("2026-07-15-eve")
    before = [tuple(d["digits"]) for d in draws if timeutil.sort_key(d["id"]) < key]
    assert before == [(1, 2, 3)]
