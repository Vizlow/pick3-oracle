"""Builds site/data/stats.json — every number the dashboard renders, precomputed.
The frontend does zero math beyond scaling pixels.
"""
import statistics

from engine import lmath

FREQ_WINDOW = 100
DIST_WINDOW = 200
SKIP_CAP = 200

BASELINES = {
    "any_straight": 0.005,   # 5 distinct straight picks
    "any_box": 0.0295,       # ~5 x 6/1000 for singles (slightly less w/ overlap)
    "top_box": 0.006,
    "front_pair": 0.01,
    "back_pair": 0.01,
}


def _digits(draws):
    return [tuple(d["digits"]) for d in draws]


def _skip_of(seq, pred):
    for back, item in enumerate(reversed(seq)):
        if pred(item):
            return min(back, SKIP_CAP)
    return SKIP_CAP


def _charts(history):
    combos = _digits(history)
    w = combos[-FREQ_WINDOW:]
    positional_freq = [[0] * 10 for _ in range(3)]
    for c in w:
        for p, d in enumerate(c):
            positional_freq[p][d] += 1

    digit_any = [_skip_of(combos, lambda c, d=d: d in c) for d in range(10)]
    digit_pos = [[_skip_of(combos, lambda c, p=p, d=d: c[p] == d) for d in range(10)]
                 for p in range(3)]
    median_any = []
    recent = combos[-400:]
    for d in range(10):
        hits = [i for i, c in enumerate(recent) if d in c]
        gaps = [b - a for a, b in zip(hits, hits[1:])]
        median_any.append(round(statistics.median(gaps), 1) if len(gaps) >= 2 else None)

    def pair_grid(key_fn):
        return [[_skip_of(combos, lambda c, x=x, y=y: key_fn(c) == (x, y))
                 for y in range(10)] for x in range(10)]

    pairs_heat = {
        "front": pair_grid(lambda c: (c[0], c[1])),
        "split": pair_grid(lambda c: (c[0], c[2])),
        "back": pair_grid(lambda c: (c[1], c[2])),
    }

    vtracs = [lmath.vtrac(c) for c in combos]
    vt_pos_skips = [[_skip_of(vtracs, lambda v, p=p, x=x: v[p] == x) for x in range(1, 6)]
                    for p in range(3)]
    vt30 = vtracs[-30:]
    vt_freq30 = [[sum(1 for v in vt30 if v[p] == x) for x in range(1, 6)] for p in range(3)]

    dist = combos[-DIST_WINDOW:]
    sum_obs = [0] * 28
    struct_obs = {"single": 0, "double": 0, "triple": 0}
    for c in dist:
        sum_obs[sum(c)] += 1
        struct_obs[lmath.classify(c)] += 1
    n_dist = max(len(dist), 1)
    sum_theo = [round(lmath.SUM_COUNTS[s] / 1000 * n_dist, 2) for s in range(28)]

    return {
        "window": FREQ_WINDOW,
        "positional_freq": positional_freq,
        "digit_skips": {"any": digit_any, "median_any": median_any, "pos": digit_pos},
        "pairs_heat": pairs_heat,
        "vtrac": {
            "pos_skips": vt_pos_skips,
            "freq30": vt_freq30,
            "last": list(lmath.vtrac(combos[-1])) if combos else None,
        },
        "sum_dist": {"observed": sum_obs, "theoretical": sum_theo, "window": n_dist},
        "structure": {"observed": struct_obs, "expected_pct": [72, 27, 1], "window": n_dist},
    }


def _bool_box(box_hit):
    if isinstance(box_hit, dict):
        return box_hit.get("pick_index") is not None
    return bool(box_hit)


def _scoreboard(entries):
    n = len(entries)
    def block(hits, baseline=None):
        b = {"hits": hits, "rate": round(hits / n, 4) if n else 0.0}
        if baseline is not None:
            b["baseline"] = baseline
        return b
    g = [e["grade"] for e in entries]
    return {
        "n_draws": n,
        "any_straight": block(sum(1 for x in g if x["straight_hit"]), BASELINES["any_straight"]),
        "any_box": block(sum(1 for x in g if _bool_box(x["box_hit"])), BASELINES["any_box"]),
        "top_box": block(sum(1 for x in g if x["top_pick"]["box"]), BASELINES["top_box"]),
        "front_pair": block(sum(1 for x in g if x["pair_hits"]["front"]), BASELINES["front_pair"]),
        "back_pair": block(sum(1 for x in g if x["pair_hits"]["back"]), BASELINES["back_pair"]),
        "control_any_box": block(
            sum(1 for e in entries if _bool_box(e["baseline"]["grade"].get("box_hit")))),
    }


STRUCTURES = ["all_box", "all_straight", "sb_top", "pairs_mix"]


def _pnl_series(entries):
    labels, cum = [], {s: 0.0 for s in STRUCTURES}
    cum["random_control"] = 0.0
    series = {s: [] for s in list(cum)}
    series["house_edge_ref"] = []
    for i, e in enumerate(entries):
        labels.append(e["draw_id"])
        for s in STRUCTURES:
            p = e["pnl"][s]
            cum[s] += p["won"] - p["stake"]
            series[s].append(round(cum[s], 2))
        bp = e["baseline"]["pnl"]["all_box"]
        cum["random_control"] += bp["won"] - bp["stake"]
        series["random_control"].append(round(cum["random_control"], 2))
        series["house_edge_ref"].append(round(-1.25 * (i + 1), 2))
    return {"labels": labels, "series": series}


def _pnl_summary(entries):
    out = {}
    for s in STRUCTURES + ["random_control"]:
        stake = won = 0.0
        wins = streak = max_streak = 0
        peak = dd = cum = 0.0
        for e in entries:
            p = e["baseline"]["pnl"]["all_box"] if s == "random_control" else e["pnl"][s]
            stake += p["stake"]
            won += p["won"]
            cum += p["won"] - p["stake"]
            if p["won"] > 0:
                wins += 1
                streak = 0
            else:
                streak += 1
                max_streak = max(max_streak, streak)
            peak = max(peak, cum)
            dd = max(dd, peak - cum)
        out[s] = {
            "stake": round(stake, 2), "won": round(won, 2), "net": round(won - stake, 2),
            "roi": round((won - stake) / stake, 4) if stake else 0.0,
            "win_rate": round(wins / len(entries), 4) if entries else 0.0,
            "max_losing_streak": max_streak, "max_drawdown": round(dd, 2),
        }
    return out


def build(history_draws, live_entries, backtest_entries, weights_state, updated_at):
    from engine.tactics import TACTICS
    return {
        "updated_at": updated_at,
        "scoreboard": {"live": _scoreboard(live_entries)},
        "pnl": {
            "headline": "all_box",
            "structures": STRUCTURES,
            "live": _pnl_series(live_entries),
            "backtest": _pnl_series(backtest_entries),
            "summary": _pnl_summary(live_entries),
            "backtest_summary": _pnl_summary(backtest_entries),
        },
        "charts": _charts(history_draws),
        "tactics_order": list(TACTICS.keys()),
    }
