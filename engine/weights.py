"""Self-adjusting tactic weights.

Reward per draw: r = this tactic's Borda points for the ACTUAL combo, in [0,1].
Under pure randomness E[r] = 0.5, so the random baseline is built into the math —
a tactic only gains weight by consistently ranking actual draws above average.
EWMA smooths it (alpha=0.02, half-life ~35 draws); weight = exp(tau*(ewma-0.5))
normalized with a floor so no tactic ever dies (it might get hot again).
"""
import math

from engine import ensemble

ALPHA = 0.02
TAU = 12.0
FLOOR_FRAC = 0.3  # each weight floored at FLOOR_FRAC / n_tactics
SPARK_LEN = 60


def fresh_state(alpha=ALPHA, tau=TAU, floor_frac=FLOOR_FRAC):
    from engine.tactics import TACTICS
    return {
        "updated_at": None,
        "params": {"alpha": alpha, "tau": tau, "floor_frac": floor_frac},
        "tactics": {
            key: {"ewma": 0.5, "weight": 1.0 / len(TACTICS), "draws_seen": 0, "spark": []}
            for key in TACTICS
        },
    }


def _params(state):
    """Read (alpha, tau, floor_frac) from the state, falling back to module
    constants for state files written before params were honored."""
    p = state.get("params", {})
    return p.get("alpha", ALPHA), p.get("tau", TAU), p.get("floor_frac", FLOOR_FRAC)


def weight_map(state):
    return {key: t["weight"] for key, t in state["tactics"].items()}


def _renormalize(state):
    _, tau, floor_frac = _params(state)
    tactics = state["tactics"]
    n = len(tactics)
    raw = {k: math.exp(tau * (t["ewma"] - 0.5)) for k, t in tactics.items()}
    total = sum(raw.values())
    floor = floor_frac / n
    w = {k: max(v / total, floor) for k, v in raw.items()}
    total = sum(w.values())
    for k, t in tactics.items():
        t["weight"] = round(w[k] / total, 6)


def update(state, scores_by_tactic, actual, updated_at=None):
    """Apply one draw's reward to every tactic that was active for that draw.
    `scores_by_tactic` must be the SAME dict used to generate the prediction
    (recomputed deterministically from pre-draw history when grading live)."""
    alpha, _, _ = _params(state)
    for key, scores in scores_by_tactic.items():
        t = state["tactics"].get(key)
        if t is None:  # tactic added after state was created
            t = state["tactics"][key] = {"ewma": 0.5, "weight": 0.0, "draws_seen": 0, "spark": []}
        r = ensemble.borda_rank_of(scores, tuple(actual))
        t["ewma"] = round((1 - alpha) * t["ewma"] + alpha * r, 6)
        t["draws_seen"] += 1
        t["spark"] = (t["spark"] + [round(r, 3)])[-SPARK_LEN:]
    _renormalize(state)
    if updated_at:
        state["updated_at"] = updated_at
    return state
