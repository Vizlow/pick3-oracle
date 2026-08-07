"""weights.py must honor state['params'] — and the default path must be
bit-identical to the module constants (golden sequence)."""
import random

from engine import weights


def _fake_scores(rng):
    return {"a": [rng.random() for _ in range(1000)], "b": [rng.random() for _ in range(1000)]}


def _run_sequence(state, seed=7, n=25):
    rng = random.Random(seed)
    for _ in range(n):
        scores = _fake_scores(rng)
        actual = (rng.randrange(10), rng.randrange(10), rng.randrange(10))
        weights.update(state, scores, actual)
    return {k: (t["ewma"], t["weight"]) for k, t in state["tactics"].items() if k in ("a", "b")}


def test_default_path_matches_constants_golden():
    got_default = _run_sequence(weights.fresh_state())
    explicit = weights.fresh_state(
        alpha=weights.ALPHA, tau=weights.TAU, floor_frac=weights.FLOOR_FRAC)
    got_explicit = _run_sequence(explicit)
    assert got_default == got_explicit


def test_custom_params_change_behavior():
    tame = _run_sequence(weights.fresh_state(tau=0.0))
    sharp = _run_sequence(weights.fresh_state(tau=24.0))
    # tau=0 -> weights stay uniform over all registered tactics regardless of ewma
    ws = {t["weight"] for t in weights.fresh_state(tau=0.0)["tactics"].values()}
    state0 = weights.fresh_state(tau=0.0)
    _run_sequence(state0)
    w_vals = [t["weight"] for t in state0["tactics"].values()]
    assert max(w_vals) - min(w_vals) < 1e-6
    # sharper tau produces more weight spread than tau=0 on the same sequence
    assert tame != sharp


def test_custom_alpha_moves_ewma_faster():
    slow = weights.fresh_state(alpha=0.01)
    fast = weights.fresh_state(alpha=0.5)
    rng = random.Random(3)
    scores = _fake_scores(rng)
    weights.update(slow, scores, (1, 2, 3))
    weights.update(fast, scores, (1, 2, 3))
    assert abs(fast["tactics"]["a"]["ewma"] - 0.5) > abs(slow["tactics"]["a"]["ewma"] - 0.5)


def test_legacy_state_without_params_falls_back():
    state = weights.fresh_state()
    del state["params"]
    _run_sequence(state)  # must not raise
    assert all(0.0 <= t["weight"] <= 1.0 for t in state["tactics"].values())
