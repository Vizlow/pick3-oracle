"""Weighted Borda rank fusion over all tactic scorers -> 5 picks + top pick + pairs.

Flow per draw:
    scores = tactic_scores(ctx)          # {key: [1000 floats]}, constant vectors dropped
    prediction = select(scores, weights, ctx)
    # ...after the result is known, the same `scores` dict feeds weights.update()
"""
from engine import lmath


def tactic_scores(ctx):
    """Run every registered tactic. Constant vectors (e.g. empty community, empty
    history pools) carry no information and are dropped — the ensemble and the
    weight updater both treat them as 'did not play this draw'."""
    from engine.tactics import TACTICS
    out = {}
    for key, fn in TACTICS.items():
        scores = fn(ctx)
        assert len(scores) == 1000, f"{key} returned {len(scores)} scores"
        first = scores[0]
        if any(s != first for s in scores):
            out[key] = scores
    return out


def to_borda(scores):
    """Scores -> Borda points in [0,1]. Ties share their average rank, so a
    20-combo pool tactic neither dominates nor gets penalized (E[borda]=~0.5)."""
    order = sorted(range(1000), key=lambda i: scores[i])
    borda = [0.0] * 1000
    i = 0
    while i < 1000:
        j = i
        while j + 1 < 1000 and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0  # 0 = worst, 999 = best
        pts = avg_rank / 999.0
        for k in range(i, j + 1):
            borda[order[k]] = pts
        i = j + 1
    return borda


def borda_rank_of(scores, combo):
    """This tactic's Borda points for one combo (used for the reward signal)."""
    target = scores[lmath.idx(combo)]
    below = sum(1 for s in scores if s < target)
    equal = sum(1 for s in scores if s == target)
    avg_rank = below + (equal - 1) / 2.0
    return avg_rank / 999.0


def fuse(scores_by_tactic, weights_by_tactic):
    """Weighted sum of Borda vectors, weights renormalized over active tactics."""
    active = {k: w for k, w in weights_by_tactic.items() if k in scores_by_tactic}
    total_w = sum(active.values()) or 1.0
    fused = [0.0] * 1000
    for key, scores in scores_by_tactic.items():
        w = active.get(key, 0.0) / total_w
        if w == 0.0:
            continue
        borda = to_borda(scores)
        for i in range(1000):
            fused[i] += w * borda[i]
    return fused


def select_picks(fused, n=5, max_per_box=2):
    """Greedy top-N with a boxed-key diversity cap; deterministic tie-break by index."""
    order = sorted(range(1000), key=lambda i: (-fused[i], i))
    picks, box_counts = [], {}
    for i in order:
        combo = lmath.from_idx(i)
        bk = lmath.box_key(combo)
        if box_counts.get(bk, 0) >= max_per_box:
            continue
        picks.append(combo)
        box_counts[bk] = box_counts.get(bk, 0) + 1
        if len(picks) == n:
            break
    return picks


def explain_top(scores_by_tactic, weights_by_tactic, top_pick, k=3):
    """Which tactics pushed the top pick hardest (weight x borda contribution)."""
    contrib = {}
    total_w = sum(w for key, w in weights_by_tactic.items() if key in scores_by_tactic) or 1.0
    for key, scores in scores_by_tactic.items():
        w = weights_by_tactic.get(key, 0.0) / total_w
        contrib[key] = w * borda_rank_of(scores, top_pick)
    return [key for key, _ in sorted(contrib.items(), key=lambda kv: -kv[1])[:k]]


def predict(ctx, weights_by_tactic, generated_at, engine_version="1.0.0"):
    """Full prediction object for the target draw. Returns (prediction, scores)."""
    from engine import timeutil
    from engine.tactics.pairs import predict_pairs

    scores = tactic_scores(ctx)
    fused = fuse(scores, weights_by_tactic)
    picks = select_picks(fused)
    pairs = predict_pairs(ctx)
    prediction = {
        "draw_id": timeutil.draw_id(ctx.target_date, ctx.target_period),
        "generated_at": generated_at,
        "picks": [list(p) for p in picks],
        "top_pick": list(picks[0]),
        "pairs": pairs,
        "engine_version": engine_version,
        "explain": {
            "top_tactics_for_top_pick": explain_top(scores, weights_by_tactic, picks[0]),
        },
    }
    return prediction, scores
