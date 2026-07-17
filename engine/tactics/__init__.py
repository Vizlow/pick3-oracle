"""Tactic protocol + registry.

A tactic is a function `fn(ctx) -> list[float]` of length exactly 1000, indexed by
100*a + 10*b + c (see lmath.ALL_1000). Higher = better; scale is irrelevant because
the ensemble rank-normalizes (Borda). Pool-style tactics score pool members > 0 and
everything else 0. Tactics MUST derive everything from ctx only — ctx.draws contains
history strictly BEFORE the target draw (no-look-ahead is enforced by tests).
"""
from engine import lmath

TACTICS = {}


def tactic(key):
    def deco(fn):
        assert key not in TACTICS, f"duplicate tactic key {key}"
        TACTICS[key] = fn
        return fn
    return deco


class Ctx:
    """History + target metadata + a memo cache shared across tactics for one step.

    draws: list of 3-tuples (ints 0-9), oldest first, strictly before the target draw.
    target_date: datetime.date of the draw being predicted (known pre-draw, so legal).
    target_period: 'mid' | 'eve'.
    community: list of (member, combo) community picks for the target draw, may be [].
    """

    def __init__(self, draws, target_date, target_period, community=None):
        self.draws = draws
        self.target_date = target_date
        self.target_period = target_period
        self.community = community or []
        self.cache = {}

    @property
    def last(self):
        return self.draws[-1] if self.draws else None

    def window(self, n):
        return self.draws[-n:]

    def memo(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def skip_map(self, name, key_fn, cap=1000):
        """{object: draws since it last appeared} scanning newest-first up to `cap`
        draws back. key_fn(draw) -> iterable of objects present in that draw.
        Objects never seen within cap are absent — callers use .get(obj, cap)."""
        def build():
            skips = {}
            for back, draw in enumerate(reversed(self.draws)):
                if back >= cap:
                    break
                for obj in key_fn(draw):
                    if obj not in skips:
                        skips[obj] = back
            return skips
        return self.memo(("skip", name), build)

    def freq_map(self, name, key_fn, window):
        """{object: hit count} over the last `window` draws."""
        def build():
            counts = {}
            for draw in self.draws[-window:]:
                for obj in key_fn(draw):
                    counts[obj] = counts.get(obj, 0) + 1
            return counts
        return self.memo(("freq", name, window), build)

    def decay_freq_map(self, name, key_fn, half_life, cap=1000):
        """{object: exponentially decay-weighted count}, newest draws weigh most."""
        def build():
            counts = {}
            factor = 0.5 ** (1.0 / half_life)
            w = 1.0
            for back, draw in enumerate(reversed(self.draws)):
                if back >= cap:
                    break
                for obj in key_fn(draw):
                    counts[obj] = counts.get(obj, 0.0) + w
                w *= factor
            return counts
        return self.memo(("decay", name, half_life), build)


def pool_scores(pool_with_weights):
    """Helper: {combo: weight} -> dense list[1000] (0 elsewhere). Boxed pools should
    expand to all straight arrangements before calling this."""
    scores = [0.0] * 1000
    for combo, w in pool_with_weights.items():
        scores[lmath.idx(combo)] = max(scores[lmath.idx(combo)], w)
    return scores


def all_scores(score_fn):
    """Helper: evaluate a per-combo function over the full space."""
    return [float(score_fn(c)) for c in lmath.ALL_1000]


# Populate the registry. Order here defines display order on the dashboard.
from engine.tactics import (  # noqa: E402,F401
    hotcold,
    mirrors,
    vtrac,
    ttt,
    rundowns,
    sums,
    pairs,
    followers,
    patterns,
    datesum,
    community,
)
