"""Orchestrator. Subcommands:
  backfill              full Socrata history + nyl-api top-up -> data/history + site window
  postdraw              poll for the latest expected draw, grade, learn, predict next
  reconcile [--days 7]  Socrata truth pass: fill gaps, verify, guarantee pending prediction
  rebuild               recompute stats.json + draws.json window from current state
  last-processed        print last graded draw id (used in commit messages)

Flags: --now <iso> (fake clock), --max-wait-min N, --no-poll (single fetch pass),
--allow-unlocked (grade predictions without a lock commit — local testing only).

Honesty rule: a prediction is graded into the ledger ONLY if its lock commit
(git commit of site/data/prediction.json) predates the draw. Tactic weights,
by contrast, learn from every draw — that never requires a published prediction.
"""
import argparse
import sys
import time
from datetime import datetime, timezone

from engine import ensemble, fetch, grade, skill, stats, store, timeutil, weights
from engine.tactics import Ctx

ENGINE_VERSION = "1.0.0"


def _now_utc(args):
    if args.now:
        dt = datetime.fromisoformat(args.now)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class State:
    def __init__(self):
        self.draws = store.load_history()
        self.ledger = store.load_json(store.LEDGER, {"entries": []})
        self.weights = store.load_json(store.WEIGHTS, None) or weights.fresh_state()
        self.prediction = store.load_json(store.PREDICTION, None)
        self.community = store.load_json(store.COMMUNITY, {"picks": {}})
        self.backtest = store.load_json(store.BACKTEST_LEDGER, {"entries": []})
        # The one prediction eligible for live grading this run: the pending one,
        # only if its lock commit predates its draw. Predictions generated later
        # in this same run are unlocked and must never be graded.
        self.lock = store.lock_proof()
        self.gradeable_id = None
        if self.prediction:
            did = self.prediction["draw_id"]
            d, period = timeutil.parse_draw_id(did)
            if self.lock.get("committed_at"):
                lock_dt = datetime.fromisoformat(self.lock["committed_at"])
                if lock_dt < timeutil.draw_datetime(d, period):
                    self.gradeable_id = did

    def combos_before(self, draw_id):
        key = timeutil.sort_key(draw_id)
        return [tuple(d["digits"]) for d in self.draws
                if timeutil.sort_key(d["id"]) < key]

    def ctx_for(self, draw_id):
        d, period = timeutil.parse_draw_id(draw_id)
        key = timeutil.sort_key(draw_id)
        results = {dr["id"]: tuple(dr["digits"]) for dr in self.draws
                   if timeutil.sort_key(dr["id"]) < key}
        skills = skill.member_skills(self.community, results, before_key=key)
        picks = [dict(e, skill=skills.get(e.get("member"), 1.0))
                 for e in self.community.get("picks", {}).get(draw_id, [])]
        picks += [
            {"member": e.get("member"), "skill": skills.get(e.get("member"), 1.0),
             "pair": {"kind": e.get("kind"), "digits": e.get("digits")}}
            for e in self.community.get("pair_hints", {}).get(draw_id, [])
        ]
        return Ctx(self.combos_before(draw_id), d, period, community=picks)

    def save(self, now_iso):
        store.save_history(self.draws)
        store.save_json(store.DRAWS, {
            "updated_at": now_iso,
            "draws": store.window_draws(self.draws),
        })
        store.save_json(store.LEDGER, self.ledger)
        store.save_json(store.WEIGHTS, self.weights)
        store.save_json(store.STATS, stats.build(
            self.draws, self.ledger["entries"],
            self.backtest.get("entries", []), self.weights, now_iso,
            community_doc=self.community))


def process_draw(state, draw, now, allow_unlocked=False):
    """One new resulted draw: record it, maybe grade the pending prediction,
    learn, and publish the next prediction."""
    state.draws = store.upsert_draws(state.draws, [draw])
    result = list(draw["digits"])
    ctx = state.ctx_for(draw["id"])
    scores = ensemble.tactic_scores(ctx)

    graded = False
    if state.prediction and state.prediction["draw_id"] == draw["id"]:
        if state.gradeable_id == draw["id"] or allow_unlocked:
            d, period = timeutil.parse_draw_id(draw["id"])
            lock = dict(state.lock)
            if lock.get("committed_at"):
                lock_dt = datetime.fromisoformat(lock["committed_at"])
                lock["hours_before_draw"] = timeutil.hours_before_draw(lock_dt, d, period)
            else:
                lock["hours_before_draw"] = None
            state.ledger["entries"].append(
                grade.ledger_entry(state.prediction, result, lock, mode="live"))
            graded = True
            state.gradeable_id = None
        else:
            print(f"WARN: prediction for {draw['id']} not lock-committed pre-draw; "
                  f"recorded draw without grading", file=sys.stderr)

    weights.update(state.weights, scores, tuple(result), updated_at=_iso(now))

    next_date, next_period = timeutil.draw_after(*timeutil.parse_draw_id(draw["id"]))
    next_id = timeutil.draw_id(next_date, next_period)
    next_ctx = state.ctx_for(next_id)
    prediction, _ = ensemble.predict(
        next_ctx, weights.weight_map(state.weights), _iso(now), ENGINE_VERSION)
    state.prediction = prediction
    store.save_json(store.PREDICTION, prediction)
    return graded


def cmd_backfill(args):
    now = _now_utc(args)
    rows = fetch.fetch_socrata(limit=20000)
    live = fetch.fetch_nyl_api()
    merged = store.upsert_draws(rows, live)
    store.save_history(merged)
    state = State()
    state.save(_iso(now))
    print(f"backfilled {len(merged)} draws "
          f"({merged[0]['id']} .. {merged[-1]['id']})")


def cmd_postdraw(args):
    now = _now_utc(args)
    target_date, target_period = timeutil.latest_expected_draw(now)
    target_id = timeutil.draw_id(target_date, target_period)
    state = State()
    known = {d["id"] for d in state.draws}
    if target_id in known:
        print(f"up to date: {target_id} already recorded")
        # still guarantee a pending prediction exists; only touch files if it was missing
        if _ensure_prediction(state, now):
            state.save(_iso(now))
        return

    deadline = time.time() + args.max_wait_min * 60
    attempt = 0
    draw = None
    while True:
        attempt += 1
        try:
            found = [d for d in fetch.fetch_nyl_api() if d["id"] == target_id]
        except Exception as e:
            print(f"nyl-api attempt {attempt}: {e}", file=sys.stderr)
            found = []
        if not found and attempt > 10:
            found = [d for d in fetch.fetch_lotteryusa(target_period) if d["id"] == target_id]
        if found:
            draw = found[0]
            break
        if args.no_poll or time.time() >= deadline:
            break
        time.sleep(90)

    if not draw:
        print(f"WARN: {target_id} not available after {attempt} attempts; "
              f"reconcile will catch it", file=sys.stderr)
        return

    _community_refresh(state)
    graded = process_draw(state, draw, now, args.allow_unlocked)
    state.save(_iso(now))
    print(f"processed {target_id} = {''.join(map(str, draw['digits']))}"
          f"{' (graded)' if graded else ''}; next prediction: "
          f"{state.prediction['draw_id']}")


def _community_refresh(state):
    """Pull fresh LotteryPost member picks (Firecrawl) so the next prediction can
    use them. Strictly best-effort: failures never block the pipeline."""
    try:
        from community import lp_reader
        if lp_reader.update():
            state.community = store.load_json(store.COMMUNITY, {"picks": {}})
    except Exception as e:  # noqa: BLE001 — enhancement layer, never fatal
        print(f"WARN: community refresh failed: {e}", file=sys.stderr)


def _ensure_prediction(state, now):
    """Safety net: make sure a pending prediction exists for the next draw.
    Returns True when a new prediction had to be generated."""
    latest = state.draws[-1]["id"] if state.draws else None
    if not latest:
        return False
    next_id = timeutil.draw_id(*timeutil.draw_after(*timeutil.parse_draw_id(latest)))
    if not state.prediction or state.prediction["draw_id"] != next_id:
        ctx = state.ctx_for(next_id)
        prediction, _ = ensemble.predict(
            ctx, weights.weight_map(state.weights), _iso(now), ENGINE_VERSION)
        state.prediction = prediction
        store.save_json(store.PREDICTION, prediction)
        print(f"generated missing prediction for {next_id}")
        return True
    return False


def cmd_reconcile(args):
    now = _now_utc(args)
    state = State()
    _community_refresh(state)
    rows = fetch.fetch_socrata(limit=args.days + 2)
    known = {d["id"]: d for d in state.draws}

    # corrections: socrata disagrees with a stored result
    corrected = []
    for r in rows:
        prev = known.get(r["id"])
        if prev and prev["digits"] != r["digits"]:
            corrected.append((r["id"], prev["digits"], r["digits"]))
    if corrected:
        state.draws = store.upsert_draws(state.draws, rows)
        for did, old, new in corrected:
            print(f"CORRECTED {did}: {old} -> {new}", file=sys.stderr)
            for e in state.ledger["entries"]:
                if e["draw_id"] == did:
                    fixed = grade.ledger_entry(e["prediction"], new, e["lock"], mode="live")
                    fixed["corrected"] = True
                    e.update(fixed)

    # gap fill: process any resulted draw we never recorded, oldest first,
    # but only up to draws that have actually happened
    latest_date, latest_period = timeutil.latest_expected_draw(now)
    latest_key = timeutil.sort_key(timeutil.draw_id(latest_date, latest_period))
    missing = sorted(
        (r for r in rows
         if r["id"] not in known and timeutil.sort_key(r["id"]) <= latest_key),
        key=lambda r: timeutil.sort_key(r["id"]))
    for r in missing:
        graded = process_draw(state, r, now, args.allow_unlocked)
        print(f"filled {r['id']} = {''.join(map(str, r['digits']))}"
              f"{' (graded)' if graded else ''}")

    # mark reconciled
    socrata_ids = {r["id"] for r in rows}
    for d in state.draws:
        if d["id"] in socrata_ids:
            d["reconciled"] = True

    _ensure_prediction(state, now)
    state.save(_iso(now))
    print(f"reconciled {len(rows)} socrata rows, filled {len(missing)}, "
          f"corrected {len(corrected)}")


def cmd_rebuild(args):
    now = _now_utc(args)
    state = State()
    state.save(_iso(now))
    print("rebuilt stats + windows")


def cmd_last_processed(args):
    entries = store.load_json(store.LEDGER, {"entries": []})["entries"]
    print(entries[-1]["draw_id"] if entries else "init")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=[
        "backfill", "postdraw", "reconcile", "rebuild", "last-processed"])
    ap.add_argument("--now", default=None)
    ap.add_argument("--max-wait-min", type=int, default=30)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--no-poll", action="store_true")
    ap.add_argument("--allow-unlocked", action="store_true")
    args = ap.parse_args()
    {
        "backfill": cmd_backfill,
        "postdraw": cmd_postdraw,
        "reconcile": cmd_reconcile,
        "rebuild": cmd_rebuild,
        "last-processed": cmd_last_processed,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
