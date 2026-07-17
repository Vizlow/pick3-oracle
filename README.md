# Pick 3 Oracle 🔮

A NY Lottery **Numbers** (Pick 3) prediction + tracking system that implements the
community's tactics — mirrors, VTRACs, tic-tac-toe workouts, rundowns, hot/cold/due
digits, pairs analysis, followers, date sums — as an ensemble of ~19 scorers with
self-adjusting weights, and then **honestly measures whether any of it beats chance**.

## How it works

- **Twice daily** (draws: midday 2:30 PM, evening 10:30 PM ET) a GitHub Actions run
  pulls the official result minutes after the draw, grades the pending prediction,
  updates tactic weights, generates the next 5 picks + top pick + pairs, and commits.
- **The git commit is the lock**: every prediction is committed *before* its draw —
  the ledger links each graded pick to its pre-draw commit sha.
- **Honest by construction**: hit rates are shown against exact random baselines and
  a seeded random control; the P&L simulation ($5/day across 4 bet structures) is
  charted against the −50% house-edge reference line. Straight odds are 1/1000 and
  pay 500:1 — expect the red line. That's the point.

## Layout

- `engine/` — stdlib-only Python: fetch (nyl-api → LotteryUSA → Socrata), tactics,
  Borda-fusion ensemble, EWMA weights, grading/payouts, walk-forward backtest, pipeline
- `site/` — the dashboard (vanilla HTML/JS/SVG, deployed on Vercel)
- `data/history/` — full draw history since 1980 + backtest ledger
- `community/` — LotteryPost NY thread reader (member picks become a tracked tactic)
- `research/dossier.json` — the tactic/source research this system is built from

## Commands

```bash
python3 -m pytest -q                       # test suite
python3 -m engine.pipeline backfill        # pull full history
python3 -m engine.backtest --draws 730     # 1-year walk-forward (--write to init live weights)
python3 -m engine.pipeline postdraw        # what the cron runs after each draw
python3 -m engine.pipeline reconcile       # morning truth pass vs data.ny.gov
python3 -m http.server -d site 8080        # local dashboard
```

*Not affiliated with the New York Lottery. Entertainment analytics — no system
changes the odds of independent draws. Play responsibly.*
