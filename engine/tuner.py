"""(alpha, tau, floor_frac) tuning protocol — variance reduction, not edge.

The deep analysis (research/deep_analysis_report.md) found every tactic at its
empirical null, so weight concentration can only chase noise. This tuner asks:
which (tau, floor) is most stable without costing anything on train data?

Protocol (pre-registered before the holdout was touched):
  - Train: walk-forward backtest over draws -6000..-2001 (history minus the
    last 2000). Holdout: the last 2000 draws, run EXACTLY ONCE at the end.
  - Grid: alpha=0.02 fixed; tau in {0,6,12,24} x floor in {0.1,0.3,0.6}
    (tau=0 => uniform weights, floor irrelevant, single point).
  - Selection on train only: among candidates within 1 SE of the best train
    any-box rate, prefer lowest tau, then highest floor, then lowest weight
    churn (all-noise world: concentration is noise-chasing).
  - Acceptance on the single holdout run: adopt iff candidate any-box rate
    >= incumbent - 0.5*SE_diff AND all_box net P&L not worse by > $10.

Usage: python3 -m engine.tuner            (grid + selection + holdout verdict)
       python3 -m engine.tuner --train-only   (grid + selection, no holdout)
"""
import argparse
import json
import math
import os
import time

from engine import backtest, stats, store

INCUMBENT = {"alpha": 0.02, "tau": 12.0, "floor_frac": 0.3}
GRID = [{"alpha": 0.02, "tau": 0.0, "floor_frac": 0.3}] + [
    {"alpha": 0.02, "tau": t, "floor_frac": f}
    for t in (6.0, 12.0, 24.0) for f in (0.1, 0.3, 0.6)
]
TRAIN_DRAWS = 4000
HOLDOUT_DRAWS = 2000
RESULTS_PATH = os.path.join(store.ROOT, "research", "tuning_results.json")


def _run_one(history, n_draws, params):
    churn = {"prev": None, "total": 0.0, "steps": 0}

    def cb(step):
        w = step["weights_before"]
        if churn["prev"] is not None:
            churn["total"] += sum(abs(w[k] - churn["prev"].get(k, 0.0)) for k in w)
            churn["steps"] += 1
        churn["prev"] = dict(w)

    _, entries = backtest.run(n_draws, history=history, on_step=cb, params=params)
    sb = stats._scoreboard(entries)
    pnl = stats._pnl_summary(entries)
    return {
        "params": params,
        "any_box_rate": sb["any_box"]["rate"],
        "any_box_hits": sb["any_box"]["hits"],
        "any_straight_hits": sb["any_straight"]["hits"],
        "all_box_net": pnl["all_box"]["net"],
        "churn": round(churn["total"] / churn["steps"], 6) if churn["steps"] else 0.0,
    }


def run_train_grid(history, progress=True):
    train_hist = history[:-HOLDOUT_DRAWS]
    results = []
    t0 = time.time()
    for i, params in enumerate(GRID):
        r = _run_one(train_hist, TRAIN_DRAWS, params)
        results.append(r)
        if progress:
            print(f"  [{i + 1}/{len(GRID)}] tau={params['tau']} floor={params['floor_frac']}: "
                  f"box_rate={r['any_box_rate']:.4f} net={r['all_box_net']:+.1f} "
                  f"churn={r['churn']} ({time.time() - t0:.0f}s)")
    return results


def select_candidate(results):
    best = max(r["any_box_rate"] for r in results)
    n = TRAIN_DRAWS
    se = math.sqrt(best * (1 - best) / n)
    cands = [r for r in results if r["any_box_rate"] >= best - se]
    cands.sort(key=lambda r: (r["params"]["tau"], -r["params"]["floor_frac"], r["churn"]))
    return cands[0], {"best_rate": best, "se": round(se, 5), "n_candidates": len(cands)}


def run_holdout(history, candidate_params):
    """The single holdout pass: candidate vs incumbent (and notes if identical)."""
    out = {"candidate": _run_one(history, HOLDOUT_DRAWS, candidate_params)}
    if candidate_params != INCUMBENT:
        out["incumbent"] = _run_one(history, HOLDOUT_DRAWS, INCUMBENT)
    else:
        out["incumbent"] = out["candidate"]
    c, i = out["candidate"], out["incumbent"]
    se_diff = math.sqrt(2 * 0.03 * 0.97 / HOLDOUT_DRAWS)
    accept = (c["any_box_rate"] >= i["any_box_rate"] - 0.5 * se_diff
              and c["all_box_net"] >= i["all_box_net"] - 10.0)
    out["se_diff"] = round(se_diff, 5)
    out["accept"] = accept
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-only", action="store_true")
    args = ap.parse_args()

    history = store.load_history()
    print(f"train grid: {len(GRID)} points x {TRAIN_DRAWS} draws "
          f"(train = history minus last {HOLDOUT_DRAWS})")
    results = run_train_grid(history)
    candidate, sel = select_candidate(results)
    print(f"selected on train: {candidate['params']} "
          f"(box_rate={candidate['any_box_rate']:.4f}, best={sel['best_rate']:.4f}, "
          f"1SE={sel['se']}, {sel['n_candidates']} candidates within 1 SE)")

    doc = {"grid": results, "selection": {"candidate": candidate, **sel},
           "incumbent": INCUMBENT}
    if not args.train_only:
        print("holdout (single pass, last 2000 draws)...")
        holdout = run_holdout(history, candidate["params"])
        doc["holdout"] = holdout
        print(json.dumps(holdout, indent=2))
        verdict = "ADOPT" if holdout["accept"] else "KEEP INCUMBENT"
        print(f"verdict: {verdict} -> {candidate['params']}")
    store.save_json(RESULTS_PATH, doc)
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
