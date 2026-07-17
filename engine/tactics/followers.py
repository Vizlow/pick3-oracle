"""Follower-theory tactics — digit and back-pair transition matrices over history."""
from engine import lmath
from engine.tactics import tactic


def _digit_matrix(ctx):
    """Laplace row-normalized digit transition probs P(j next | i last) over the
    last 2000 transitions."""
    def build():
        M = [[0] * 10 for _ in range(10)]
        draws = ctx.draws[-2001:]
        for t in range(len(draws) - 1):
            nxt = set(draws[t + 1])
            for i in set(draws[t]):
                for j in nxt:
                    M[i][j] += 1
        return [[(M[i][j] + 1.0) / (sum(M[i]) + 10.0) for j in range(10)] for i in range(10)]
    return ctx.memo(("followers", "digit_matrix"), build)


def _digit_score_vector(ctx):
    """score(c) = sum over distinct j in c of mean_{i in set(last)} P(j|i)."""
    def build():
        last = ctx.last
        if last is None:
            return [0.0] * 1000
        P = _digit_matrix(ctx)
        srcs = sorted(set(last))
        g = [sum(P[i][j] for i in srcs) / len(srcs) for j in range(10)]
        return [sum(g[j] for j in set(c)) for c in lmath.ALL_1000]
    return ctx.memo(("followers", "digit_scores"), build)


def pair_transition_table(ctx):
    """Back-pair -> next front/back pair transition counts over the last 2000
    transitions, plus per-predecessor totals. Shared with pairs.predict_pairs."""
    def build():
        fol = {"front": {}, "back": {}}
        totals = {}
        draws = ctx.draws[-2001:]
        for t in range(len(draws) - 1):
            prev = (draws[t][1], draws[t][2])
            nxt = draws[t + 1]
            totals[prev] = totals.get(prev, 0) + 1
            for kind, pair in (("front", (nxt[0], nxt[1])), ("back", (nxt[1], nxt[2]))):
                row = fol[kind].setdefault(prev, {})
                row[pair] = row.get(pair, 0) + 1
        return fol, totals
    return ctx.memo(("followers", "pair_table"), build)


@tactic("follower_digit")
def follower_digit(ctx):
    """Digit follower matrix score, plus the Old Man's Zero rule: 0 hit without
    3 or 6 -> boost combos containing 3 or 6."""
    last = ctx.last
    if last is None:
        return [0.0] * 1000
    scores = list(_digit_score_vector(ctx))
    if 0 in last and {3, 6}.isdisjoint(last):
        for i, c in enumerate(lmath.ALL_1000):
            if 3 in c or 6 in c:
                scores[i] += 0.3
    return scores


@tactic("follower_pair")
def follower_pair(ctx):
    """P(next back pair | last back pair), Laplace-smoothed; backs off to 0.5x the
    digit-level score when the last back pair was a predecessor fewer than 3 times."""
    last = ctx.last
    if last is None:
        return [0.0] * 1000
    fol, totals = pair_transition_table(ctx)
    prev = (last[1], last[2])
    total = totals.get(prev, 0)
    if total < 3:
        return [0.5 * x for x in _digit_score_vector(ctx)]
    row = fol["back"].get(prev, {})
    p = {(x, y): (row.get((x, y), 0) + 1.0) / (total + 100.0) for x in range(10) for y in range(10)}
    return [p[(b, c)] for a, b, c in lmath.ALL_1000]
