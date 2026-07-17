"""Walk-forward backtest: replays history through the exact same predict->grade->
update step the live pipeline uses. No look-ahead: step t sees only draws < t.

Usage: python3 -m engine.backtest --draws 730 [--write]
--write persists the resulting weights to site/data/weights.json (live init) and
the backtest ledger to data/history/backtest_ledger.json.
"""
import argparse
import json
import time

from engine import ensemble, grade, stats, store, timeutil, weights
from engine.tactics import Ctx


def run(n_draws=730, history=None, progress=False):
    history = history if history is not None else store.load_history()
    if len(history) < n_draws + 50:
        raise SystemExit(f"need >= {n_draws + 50} draws of history, have {len(history)}")
    state = weights.fresh_state()
    entries = []
    start = len(history) - n_draws
    combos = [tuple(d["digits"]) for d in history]
    t0 = time.time()
    for t in range(start, len(history)):
        target = history[t]
        d, period = timeutil.parse_draw_id(target["id"])
        ctx = Ctx(combos[:t], d, period)
        wmap = weights.weight_map(state)
        prediction, scores = ensemble.predict(ctx, wmap, generated_at=target["date"])
        result = combos[t]
        lock = {"sha": None, "committed_at": None, "hours_before_draw": None}
        entries.append(grade.ledger_entry(prediction, list(result), lock, mode="backtest"))
        weights.update(state, scores, result, updated_at=target["date"])
        if progress and (t - start) % 100 == 0:
            print(f"  {t - start}/{n_draws} ({time.time() - t0:.0f}s)")
    return state, entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=730)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    state, entries = run(args.draws, progress=True)
    summary = stats._pnl_summary(entries)
    sb = stats._scoreboard(entries)
    print(json.dumps({"scoreboard": sb, "pnl_summary": summary}, indent=2))
    top = sorted(state["tactics"].items(), key=lambda kv: -kv[1]["weight"])[:5]
    print("top tactic weights:", [(k, v["weight"], v["ewma"]) for k, v in top])

    if args.write:
        store.save_json(store.WEIGHTS, state)
        store.save_json(store.BACKTEST_LEDGER, {"entries": entries})
        print(f"wrote {store.WEIGHTS} and {store.BACKTEST_LEDGER}")


if __name__ == "__main__":
    main()
