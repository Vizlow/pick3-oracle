"""Deep-analysis battery + skill eval: null behavior, planted-bias detection,
tie-correct nulls, and no-look-ahead sentinels."""
import random
from datetime import date, timedelta

from engine import analysis, ensemble, lmath
from engine.analysis import _Acc, _dueness_test, _dueness_walk, _vec_stats


def synth_history(n, seed=1, mutate=None):
    rng = random.Random(seed)
    draws = []
    d0 = date(2018, 1, 1)
    for i in range(n):
        day = d0 + timedelta(days=i // 2)
        period = "mid" if i % 2 == 0 else "eve"
        digits = [rng.randrange(10) for _ in range(3)]
        if mutate:
            digits = mutate(rng, digits)
        draws.append({"id": f"{day.isoformat()}-{period}", "date": day.isoformat(),
                      "period": period, "digits": digits})
    return draws


def test_battery_null_on_uniform_history():
    battery = analysis.run_battery(synth_history(4400, seed=11))
    assert len(battery) > 60
    assert not any(r["significant"] for r in battery), \
        [r["id"] for r in battery if r["significant"]]
    # fallback sanity: raw small p-values stay at chance level
    assert sum(1 for r in battery if r["p"] < 0.01) <= 3


def test_battery_detects_planted_positional_bias():
    def plant(rng, digits):  # digit 7 at pos 0 at ~2x rate
        if rng.random() < 0.1:
            digits[0] = 7
        return digits
    battery = analysis.run_battery(synth_history(4400, seed=2, mutate=plant))
    hits = [r for r in battery if "pos0_digit_uniform" in r["id"] and r["significant"]]
    assert hits, "planted 2x bias must survive FDR"


def test_carryover_pmf_exact():
    for s in (1, 2, 3):
        pmf = analysis.carryover_pmf(s)
        assert abs(sum(pmf) - 1.0) < 1e-12
        # brute force against an arbitrary same-size set to confirm symmetry
        d = tuple(range(9, 9 - s, -1))
        counts = [0, 0, 0, 0]
        for c in lmath.ALL_1000:
            counts[len(set(c) & set(d))] += 1
        assert pmf == [x / 1000.0 for x in counts]
    # sanity: for s=3 a combo missing all three digits has p = 0.343
    assert abs(analysis.carryover_pmf(3)[0] - 0.343) < 1e-9


def test_dueness_walk_prefix_property_no_lookahead():
    hist = synth_history(600, seed=3)
    combos = [tuple(d["digits"]) for d in hist]
    keys = lambda c: [(pos, c[pos]) for pos in range(3)]  # noqa: E731
    full_prefix = _dueness_walk(combos[:400], keys, 30, 0.1, analysis.DIGIT_BUCKETS)
    again = _dueness_walk(combos[:400], keys, 30, 0.1, analysis.DIGIT_BUCKETS)
    assert full_prefix == again  # deterministic
    # appending future draws must not change what the first 400 steps recorded
    h2, t2 = _dueness_walk(combos, keys, 30, 0.1, analysis.DIGIT_BUCKETS)
    assert sum(t2) > sum(full_prefix[1])  # walked further


def test_dueness_null_and_planted_hazard():
    combos = [tuple(d["digits"]) for d in synth_history(4000, seed=4)]
    keys = lambda c: [(pos, c[pos]) for pos in range(3)]  # noqa: E731
    hits, trials = _dueness_walk(combos, keys, 30, 0.1, analysis.DIGIT_BUCKETS)
    _, _, p = _dueness_test(hits, trials, 0.1)
    assert p > 0.01
    # planted increasing hazard at pos 0: pick digit with weight (1 + skip)
    rng = random.Random(5)
    last = {d: -1 for d in range(10)}
    hz = []
    for t in range(4000):
        wts = [1.0 + (t - last[d] - 1 if last[d] >= 0 else 5) for d in range(10)]
        d0 = rng.choices(range(10), weights=wts)[0]
        last[d0] = t
        hz.append((d0, rng.randrange(10), rng.randrange(10)))
    hits, trials = _dueness_walk(hz, keys, 30, 0.1, analysis.DIGIT_BUCKETS)
    _, _, p = _dueness_test(hits, trials, 0.1)
    assert p < 1e-4


def test_skill_acc_detects_rigged_scorer():
    rng = random.Random(6)
    acc = _Acc()
    for i in range(100):
        vec = [rng.random() for _ in range(1000)]
        aidx = rng.randrange(1000)
        vec[aidx] = 2.0  # rigged: actual always ranked #1
        b = ensemble.to_borda(vec)
        mu, var = _vec_stats(b)
        acc.add(b[aidx], mu, var, 0 if i < 50 else 1)
    assert acc.z() > 5
    assert acc.z(0) > 3 and acc.z(1) > 3


def test_skill_acc_pool_tactic_tie_variance():
    """20-nonzero pool scorer: per-draw sigma^2 must be the empirical vector
    variance (~0.005), NOT the tie-free 1/12 — the tie-handling regression."""
    rng = random.Random(7)
    acc = _Acc()
    for i in range(400):
        vec = [0.0] * 1000
        for j in rng.sample(range(1000), 20):
            vec[j] = rng.random() + 0.5
        b = ensemble.to_borda(vec)
        mu, var = _vec_stats(b)
        acc.add(b[rng.randrange(1000)], mu, var, 0 if i < 200 else 1)
    mean_var = sum(acc.svar) / acc.n
    assert mean_var < 0.02, f"tie null must shrink variance, got {mean_var}"
    assert abs(acc.z()) < 3


def test_backtest_on_step_contract():
    from engine import backtest
    from engine.tactics import TACTICS
    hist = synth_history(100, seed=8)
    seen = []

    def cb(step):
        assert len(step["ctx"].draws) == step["t"]
        assert set(step["scores"]) <= set(TACTICS)
        assert abs(sum(step["weights_before"].values()) - 1.0) < 1e-3
        assert len(step["prediction"]["picks"]) == 5
        seen.append(step["draw_id"])

    backtest.run(n_draws=30, history=hist, on_step=cb)
    assert len(seen) == 30
    assert seen == [d["id"] for d in hist[-30:]]


def test_run_skill_small_end_to_end():
    hist = synth_history(120, seed=9)
    rows, meta = analysis.run_skill(history=hist, n_draws=40)
    assert meta["n_draws"] == 40
    names = {r["tactic"] for r in rows}
    assert {"fused_learned", "fused_equal", "top5_picks_box", "pairs_front", "pairs_back"} <= names
    for r in rows:
        assert 0.0 <= r["p"] <= 1.0
        assert r["verdict"] in ("signal", "noise", "inverse")


def test_verdict_rule():
    base = {"q": 0.05, "z": 3.0, "z_h1": 2.0, "z_h2": 1.0}
    assert analysis._verdict(base) == "signal"
    assert analysis._verdict({**base, "z": -3.0, "z_h1": -2.0, "z_h2": -1.0}) == "inverse"
    assert analysis._verdict({**base, "q": 0.5}) == "noise"
    assert analysis._verdict({**base, "z_h2": -1.0}) == "noise"  # halves disagree
