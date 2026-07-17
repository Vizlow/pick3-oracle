import math

from engine import ensemble, lmath, weights


def test_to_borda_ties_average():
    # pool tactic: 20 combos at 1.0, 980 at 0 -> zeros share avg rank, mean borda ~0.5
    scores = [0.0] * 1000
    for i in range(20):
        scores[i] = 1.0
    borda = ensemble.to_borda(scores)
    assert borda[0] == borda[19] > borda[500]
    mean = sum(borda) / 1000
    assert abs(mean - 0.5) < 1e-9
    # tied zeros: avg rank of positions 0..979 = 489.5 -> 489.5/999
    assert abs(borda[500] - 489.5 / 999) < 1e-9


def test_borda_rank_of_matches_to_borda():
    scores = [float((i * 7919) % 1000) for i in range(1000)]
    borda = ensemble.to_borda(scores)
    for i in (0, 123, 586, 999):
        assert abs(ensemble.borda_rank_of(scores, lmath.from_idx(i)) - borda[i]) < 1e-9


def test_select_picks_diversity_and_determinism():
    fused = [0.0] * 1000
    # make all 6 perms of (1,2,3) the top scorers — diversity cap must kick in
    for p in [(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]:
        fused[lmath.idx(p)] = 10.0 - lmath.idx(p) * 1e-4
    picks = ensemble.select_picks(fused)
    assert len(picks) == 5
    box_keys = [lmath.box_key(p) for p in picks]
    assert box_keys.count((1, 2, 3)) == 2  # capped at 2, not 5
    assert picks == ensemble.select_picks(fused)  # deterministic


def test_fuse_skips_missing_tactics_and_renormalizes():
    scores = {"a": [float(i) for i in range(1000)]}
    fused = ensemble.fuse(scores, {"a": 0.2, "b": 0.8})
    assert abs(fused[999] - 1.0) < 1e-9  # 'a' gets all the weight since 'b' inactive


def test_weights_update_math():
    state = weights.fresh_state()
    n = len(state["tactics"])
    assert abs(sum(t["weight"] for t in state["tactics"].values()) - 1.0) < 1e-4
    key = next(iter(state["tactics"]))
    scores = {key: [float(i) for i in range(1000)]}
    weights.update(state, scores, lmath.from_idx(999))  # perfect call: r = 1.0
    t = state["tactics"][key]
    assert abs(t["ewma"] - ((1 - weights.ALPHA) * 0.5 + weights.ALPHA * 1.0)) < 1e-6
    assert t["draws_seen"] == 1 and len(t["spark"]) == 1
    assert abs(sum(x["weight"] for x in state["tactics"].values()) - 1.0) < 1e-4
    # floor: no tactic below FLOOR_FRAC/n after renormalization headroom
    assert all(x["weight"] >= weights.FLOOR_FRAC / n / 2 for x in state["tactics"].values())


def test_weight_transform_monotone():
    assert math.exp(weights.TAU * 0.05) > 1.5  # ewma 0.55 -> meaningfully above uniform
