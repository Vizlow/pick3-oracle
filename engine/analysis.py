"""Deep pattern analysis: bias battery over the draw history + walk-forward
skill evaluation of every tactic. Offline research tool — never runs in cron.

Usage: python3 -m engine.analysis --draws 4000 [--write]

Two pre-registered test families, each BH-FDR-corrected at q=0.10:
  A. Bias battery — is anything about the drawn numbers non-uniform?
     Segments: all / last4000 / last1000 / mid2000 / eve2000. Ball sets change,
     so only the recent era is actionable; full-history findings are labeled
     historical. ~80 p-values.
  B. Tactic skill — does any tactic rank actual draws above its own empirical
     null? Rides backtest.run's sentinel-tested walk-forward loop. Empirical
     per-draw nulls (mean/var of each tactic's Borda vector) make pool tactics
     with heavy ties scale correctly (sigma ~0.07 vs 0.289 tie-free). ~25
     p-values.

Verdict rule (fixed before the numbers were run): "signal" iff q < 0.10 over
the full window AND the z-score has the same sign in both halves; "inverse"
when that holds with z < 0; otherwise "noise".

Outputs: research/deep_analysis.json, research/deep_analysis_report.md, and
(with --write) site/data/analysis.json for the dashboard's Pattern lab panel.
"""
import argparse
import json
import math
import os
import time
from collections import defaultdict
from datetime import date as _date
from datetime import datetime, timezone
from heapq import nlargest

from engine import backtest, ensemble, lmath, statutil, store

try:
    import numpy as _np
except ImportError:  # CI has no numpy — pure-python fallback below
    _np = None

FDR_Q = 0.10
DIGIT_BUCKETS = ((0, 9), (10, 24), (25, 49), (50, None))
PAIR_BUCKETS = ((0, 49), (50, 99), (100, 199), (200, None))
REPORT_JSON = os.path.join(store.ROOT, "research", "deep_analysis.json")
REPORT_MD = os.path.join(store.ROOT, "research", "deep_analysis_report.md")
SITE_ANALYSIS = os.path.join(store.ROOT, "site", "data", "analysis.json")


# ---------------------------------------------------------------- segments

def build_segments(history):
    """Ordered segments; 'all' is a historical curiosity (ball sets changed),
    the last-4000 era (~2021->) and its mid/eve halves are the actionable ones."""
    segs = {"all": history}
    if len(history) > 4000:
        segs["last4000"] = history[-4000:]
    if len(history) > 1000:
        segs["last1000"] = history[-1000:]
    recent = history[-4000:]
    mid = [d for d in recent if d["period"] == "mid"]
    eve = [d for d in recent if d["period"] == "eve"]
    if len(mid) >= 300:
        segs["mid2000"] = mid
    if len(eve) >= 300:
        segs["eve2000"] = eve
    return segs


# ---------------------------------------------------------------- battery

def _bucket_of(skip, buckets):
    for i, (lo, hi) in enumerate(buckets):
        if hi is None or lo <= skip <= hi:
            if skip >= lo:
                return i
    return len(buckets) - 1


_CARRY_PMF = {}


def carryover_pmf(s):
    """Exact null pmf of k = |set(combo) ∩ D| over all 1000 straights, for a
    distinct-digit set D of size s (depends only on s by symmetry)."""
    if s not in _CARRY_PMF:
        d = tuple(range(s))
        counts = [0, 0, 0, 0]
        for c in lmath.ALL_1000:
            counts[len(set(c) & set(d))] += 1
        _CARRY_PMF[s] = [x / 1000.0 for x in counts]
    return _CARRY_PMF[s]


def _dueness_walk(combos, keys_of, key_space, rate, buckets):
    """Forward walk: at each draw, every already-seen key is one Bernoulli(rate)
    trial assigned to its current skip bucket; hit iff the key occurs. last_seen
    updates strictly AFTER scoring, so no step ever sees its own draw (prefix
    property: results after t steps depend only on combos[:t+1])."""
    last_seen = {}
    nb = len(buckets)
    hits, trials = [0] * nb, [0] * nb
    for t, combo in enumerate(combos):
        occurring = set(keys_of(combo))
        for key, seen_at in last_seen.items():
            b = _bucket_of(t - seen_at - 1, buckets)
            trials[b] += 1
            if key in occurring:
                hits[b] += 1
        for key in occurring:
            last_seen[key] = t
    return hits, trials


def _dueness_test(hits, trials, rate):
    """Per-bucket binomial deviations combined as chi-square (df = merged bins;
    buckets are independent binomials, no sum constraint, so df is NOT bins-1)."""
    expected = [tr * rate for tr in trials]
    obs, exp = statutil.merge_bins(hits, expected)
    if not exp or all(e == 0 for e in exp):
        return 0.0, 0, 1.0
    stat = sum((o - e) ** 2 / (e * (1 - rate)) for o, e in zip(obs, exp) if e > 0)
    df = len(exp)
    return stat, df, statutil.chi2_sf(stat, df)


def _cramers_v(stat, n, r, c):
    denom = n * (min(r, c) - 1)
    return math.sqrt(stat / denom) if denom > 0 else 0.0


def battery_for_segment(name, seg, include_midveve=False):
    combos = [tuple(d["digits"]) for d in seg]
    n = len(combos)
    out = []

    def add(test, stat, df, p, effect=None, note=""):
        out.append({"id": f"{name}:{test}", "segment": name, "test": test, "n": n,
                    "stat": round(stat, 4), "df": df, "p": p,
                    "effect": round(effect, 4) if effect is not None else None,
                    "note": note})

    # 1-3. positional digit uniformity
    for pos in range(3):
        counts = [0] * 10
        for c in combos:
            counts[c[pos]] += 1
        stat, df, p = statutil.chi_square_gof(counts, [n / 10.0] * 10)
        add(f"pos{pos}_digit_uniform", stat, df, p, _cramers_v(stat, n, 10, 2))

    # 4. pooled digit uniformity
    pooled = [0] * 10
    for c in combos:
        for d in c:
            pooled[d] += 1
    stat, df, p = statutil.chi_square_gof(pooled, [3 * n / 10.0] * 10)
    add("pooled_digit_uniform", stat, df, p, _cramers_v(stat, 3 * n, 10, 2))

    # 5. sum distribution vs exact combinatorial null
    sums = [0] * 28
    for c in combos:
        sums[sum(c)] += 1
    exp = [lmath.SUM_COUNTS[s] / 1000.0 * n for s in range(28)]
    stat, df, p = statutil.chi_square_gof(sums, exp)
    add("sum_distribution", stat, df, p)

    # 6. structure mix vs 720/270/10
    struct = {"single": 0, "double": 0, "triple": 0}
    for c in combos:
        struct[lmath.classify(c)] += 1
    stat, df, p = statutil.chi_square_gof(
        [struct["single"], struct["double"], struct["triple"]],
        [0.72 * n, 0.27 * n, 0.01 * n])
    add("structure_mix", stat, df, p)

    # 7-9. per-position serial dependence (independence: marginal bias can't
    # masquerade as dependence)
    for pos in range(3):
        table = [[0] * 10 for _ in range(10)]
        for prev, cur in zip(combos, combos[1:]):
            table[prev[pos]][cur[pos]] += 1
        stat, df, p = statutil.chi_square_independence(table)
        add(f"pos{pos}_serial_dependence", stat, df, p, _cramers_v(stat, n - 1, 10, 10))

    # 10. exact straight repeat
    k = sum(1 for prev, cur in zip(combos, combos[1:]) if prev == cur)
    upper = statutil.binom_sf(k, n - 1, 0.001)
    lower = 1.0 - statutil.binom_sf(k + 1, n - 1, 0.001)
    add("straight_repeat", float(k), 0, min(1.0, 2 * min(upper, lower)),
        note=f"{k} exact repeats in {n - 1} transitions")

    # 11. box repeat (per-draw null depends on previous structure)
    p_by_struct = {"single": 0.006, "double": 0.003, "triple": 0.001}
    hits = mu = var = 0.0
    for prev, cur in zip(combos, combos[1:]):
        pt = p_by_struct[lmath.classify(prev)]
        mu += pt
        var += pt * (1 - pt)
        if lmath.box_key(prev) == lmath.box_key(cur):
            hits += 1
    z = (hits - mu) / math.sqrt(var) if var > 0 else 0.0
    add("box_repeat", z, 0, 2 * statutil.normal_sf(abs(z)),
        note=f"{int(hits)} box repeats vs {mu:.1f} expected")

    # 12. carryover count vs exact enumerated null
    carry_obs = [0, 0, 0, 0]
    carry_exp = [0.0, 0.0, 0.0, 0.0]
    for prev, cur in zip(combos, combos[1:]):
        carry_obs[len(set(cur) & set(prev))] += 1
        pmf = carryover_pmf(len(set(prev)))
        for i in range(4):
            carry_exp[i] += pmf[i]
    stat, df, p = statutil.chi_square_gof(carry_obs, carry_exp)
    add("carryover_count", stat, df, p)

    # 13. day-of-week x pooled digit
    dow = defaultdict(lambda: [0] * 10)
    for d, c in zip(seg, combos):
        wd = _date.fromisoformat(d["date"]).weekday()
        for digit in c:
            dow[wd][digit] += 1
    table = [dow[w] for w in sorted(dow)]
    stat, df, p = statutil.chi_square_independence(table)
    add("weekday_digit", stat, df, p, _cramers_v(stat, 3 * n, len(table), 10))

    # 14. mid vs eve x pooled digit (only meaningful on the mixed segment)
    if include_midveve:
        per = {"mid": [0] * 10, "eve": [0] * 10}
        for d, c in zip(seg, combos):
            for digit in c:
                per[d["period"]][digit] += 1
        stat, df, p = statutil.chi_square_independence([per["mid"], per["eve"]])
        add("mid_vs_eve_digit", stat, df, p)

    # 15-17. dueness reality checks — the folklore premise behind
    # due_digits/pair_due/vtrac_due: does a longer skip raise the hit rate?
    hits_d, trials_d = _dueness_walk(
        combos, lambda c: [(pos, c[pos]) for pos in range(3)],
        30, 0.1, DIGIT_BUCKETS)
    stat, df, p = _dueness_test(hits_d, trials_d, 0.1)
    add("dueness_positional_digits", stat, df, p)

    hits_f, trials_f = _dueness_walk(
        combos, lambda c: [("f", c[0], c[1])], 100, 0.01, PAIR_BUCKETS)
    stat, df, p = _dueness_test(hits_f, trials_f, 0.01)
    add("dueness_front_pairs", stat, df, p)

    hits_b, trials_b = _dueness_walk(
        combos, lambda c: [("b", c[1], c[2])], 100, 0.01, PAIR_BUCKETS)
    stat, df, p = _dueness_test(hits_b, trials_b, 0.01)
    add("dueness_back_pairs", stat, df, p)

    return out


def run_battery(history):
    segments = build_segments(history)
    results = []
    for name, seg in segments.items():
        results.extend(battery_for_segment(name, seg, include_midveve=(name == "last4000")))
    qvals = statutil.bh_fdr([r["p"] for r in results])
    for r, q in zip(results, qvals):
        r["q"] = q
        r["significant"] = q < FDR_Q
    return results


# ---------------------------------------------------------------- skill

class _Acc:
    """Sum accumulator for z = (sum r - sum mu) / sqrt(sum var), split-half."""

    def __init__(self):
        self.n = 0
        self.sr = [0.0, 0.0]
        self.smu = [0.0, 0.0]
        self.svar = [0.0, 0.0]

    def add(self, r, mu, var, half):
        self.n += 1
        self.sr[half] += r
        self.smu[half] += mu
        self.svar[half] += var

    def z(self, half=None):
        halves = (0, 1) if half is None else (half,)
        sr = sum(self.sr[h] for h in halves)
        smu = sum(self.smu[h] for h in halves)
        svar = sum(self.svar[h] for h in halves)
        return (sr - smu) / math.sqrt(svar) if svar > 0 else 0.0

    def mean_r(self):
        return sum(self.sr) / self.n if self.n else 0.0


def _vec_stats(vec):
    """(value_lookup, mean, population variance) with numpy fast path."""
    if _np is not None:
        a = _np.asarray(vec)
        return float(a.mean()), float(a.var())
    m = sum(vec) / len(vec)
    return m, sum(v * v for v in vec) / len(vec) - m * m


def run_skill(history=None, n_draws=4000, progress=False):
    """Walk-forward skill eval riding backtest.run. Returns (rows, meta)."""
    accs = defaultdict(_Acc)          # borda-of-actual vs empirical null
    top50 = defaultdict(_Acc)         # tie-safe head-of-list metric
    picks_acc = _Acc()                # top-5 box hit vs exact coverage
    pair_hits = {"front": 0, "back": 0}
    half_at = n_draws // 2
    step_no = {"i": 0}

    def cb(step):
        i = step_no["i"]
        step_no["i"] += 1
        half = 0 if i < half_at else 1
        aidx = lmath.idx(step["result"])
        scores = step["scores"]
        bordas = {}
        for key, vec in scores.items():
            b = ensemble.to_borda(vec)
            bordas[key] = b
            mu, var = _vec_stats(b)
            accs[key].add(b[aidx], mu, var, half)
            thr = nlargest(50, vec)[-1]
            cov = sum(1 for s in vec if s >= thr) / 1000.0
            top50[key].add(1.0 if vec[aidx] >= thr else 0.0, cov, cov * (1 - cov), half)

        # fused pseudo-tactics: learned weights (exactly what the pick used)
        # and frozen equal weights (isolates whether weight learning helps)
        for fkey, wmap in (("__fused_learned__", step["weights_before"]),
                           ("__fused_equal__", {k: 1.0 for k in scores})):
            active = {k: wmap.get(k, 0.0) for k in bordas}
            tw = sum(active.values()) or 1.0
            if _np is not None:
                fused = _np.zeros(1000)
                for k, b in bordas.items():
                    w = active[k] / tw
                    if w:
                        fused += w * _np.asarray(b)
                fused = fused.tolist()
            else:
                fused = [0.0] * 1000
                for k, b in bordas.items():
                    w = active[k] / tw
                    if w:
                        for j in range(1000):
                            fused[j] += w * b[j]
            mu, var = _vec_stats(fused)
            accs[fkey].add(fused[aidx], mu, var, half)

        # top-5 picks: box hit vs exact per-draw coverage
        boxes = {lmath.box_key(p) for p in step["prediction"]["picks"]}
        cov = sum(lmath.perm_count(b) for b in boxes) / 1000.0
        hit = 1.0 if lmath.box_key(step["result"]) in boxes else 0.0
        picks_acc.add(hit, cov, cov * (1 - cov), half)

        # pairs predictor
        pairs = step["prediction"]["pairs"]
        if tuple(pairs["front"]) == (step["result"][0], step["result"][1]):
            pair_hits["front"] += 1
        if tuple(pairs["back"]) == (step["result"][1], step["result"][2]):
            pair_hits["back"] += 1

    backtest.run(n_draws, history=history, progress=progress, on_step=cb)
    n = step_no["i"]

    rows = []
    for key in sorted(accs, key=lambda k: (k.startswith("__"), k)):
        a = accs[key]
        z = a.z()
        row = {"tactic": key.strip("_"), "kind": "ensemble" if key.startswith("__") else "tactic",
               "n": a.n, "mean_r": round(a.mean_r(), 4), "z": round(z, 3),
               "p": 2 * statutil.normal_sf(abs(z)),
               "z_h1": round(a.z(0), 3), "z_h2": round(a.z(1), 3)}
        if key in top50:
            row["top50_z"] = round(top50[key].z(), 3)
        rows.append(row)

    z = picks_acc.z()
    rows.append({"tactic": "top5_picks_box", "kind": "picks", "n": picks_acc.n,
                 "mean_r": round(picks_acc.mean_r(), 4), "z": round(z, 3),
                 "p": 2 * statutil.normal_sf(abs(z)),
                 "z_h1": round(picks_acc.z(0), 3), "z_h2": round(picks_acc.z(1), 3)})

    for side in ("front", "back"):
        k = pair_hits[side]
        upper = statutil.binom_sf(k, n, 0.01)
        lower = 1.0 - statutil.binom_sf(k + 1, n, 0.01)
        rows.append({"tactic": f"pairs_{side}", "kind": "pairs", "n": n,
                     "mean_r": round(k / n, 4) if n else 0.0,
                     "z": round((k - 0.01 * n) / math.sqrt(n * 0.01 * 0.99), 3) if n else 0.0,
                     "p": min(1.0, 2 * min(upper, lower)),
                     "z_h1": None, "z_h2": None,
                     "note": f"{k} hits in {n} draws vs {0.01 * n:.0f} expected"})

    qvals = statutil.bh_fdr([r["p"] for r in rows])
    for r, q in zip(rows, qvals):
        r["q"] = q
        r["verdict"] = _verdict(r)
    return rows, {"n_draws": n, "half_at": half_at}


def _verdict(row):
    """Pre-registered: signal iff q < FDR_Q AND same-sign z in both halves."""
    if row["q"] >= FDR_Q:
        return "noise"
    h1, h2 = row.get("z_h1"), row.get("z_h2")
    if h1 is not None and h2 is not None and (h1 > 0) != (h2 > 0):
        return "noise"
    return "inverse" if row["z"] < 0 else "signal"


# ---------------------------------------------------------------- reports

def _headlines(battery, skill_rows):
    sig_b = [r for r in battery if r["significant"]]
    tactics = [r for r in skill_rows if r["kind"] == "tactic"]
    sig_t = [r for r in tactics if r["verdict"] != "noise"]
    heads = []
    heads.append(
        f"Draw bias battery: {len(sig_b)} of {len(battery)} tests significant after FDR"
        + (f" ({', '.join(r['id'] for r in sig_b[:3])})" if sig_b else " — draws look uniform"))
    heads.append(
        f"Tactic skill: {len(sig_t)} of {len(tactics)} tactics beat their empirical null"
        + (f" ({', '.join(r['tactic'] for r in sig_t[:3])})" if sig_t else " — all noise, as honest math predicts"))
    fl = next((r for r in skill_rows if r["tactic"] == "fused_learned"), None)
    fe = next((r for r in skill_rows if r["tactic"] == "fused_equal"), None)
    if fl and fe:
        heads.append(f"Ensemble: learned-weights z={fl['z']}, equal-weights z={fe['z']} — "
                     + ("weight learning adds nothing measurable" if abs(fl["z"]) < 2 and abs(fe["z"]) < 2
                        else "see report"))
    pk = next((r for r in skill_rows if r["tactic"] == "top5_picks_box"), None)
    if pk:
        heads.append(f"Top-5 picks hit boxes at {pk['mean_r']:.1%} per draw vs 3.0% coverage ceiling (z={pk['z']})")
    return heads[:4]


def _md_table(rows, cols, headers):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c)
            if isinstance(v, float):
                v = f"{v:.4g}"
            cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_reports(battery, skill_rows, skill_meta, history, write_site=False):
    as_of = history[-1]["id"]
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = {"generated_at": generated, "as_of_draw": as_of,
           "fdr_q": FDR_Q, "battery": battery,
           "skill": {"window": skill_meta, "rows": skill_rows},
           "headlines": _headlines(battery, skill_rows)}
    store.save_json(REPORT_JSON, doc)

    sig_b = [r for r in battery if r["significant"]]
    md = [
        "# Deep pattern analysis — NY Numbers (Pick 3)",
        f"\nGenerated {generated} · history through `{as_of}` · "
        f"skill window: last {skill_meta['n_draws']} draws · BH-FDR q < {FDR_Q}\n",
        "## Honest framing\n",
        "NY Numbers is drawn from audited physical machines. The prior is overwhelmingly "
        "that no exploitable signal exists; with ~80 battery p-values, ~4 raw p<0.05 are "
        "expected under the global null, which is why only FDR-surviving, era-stable, "
        "split-half-consistent findings count. Ball sets change over the years, so only "
        "the last-4000-draw era (2021→) is actionable; full-history findings are "
        "historical curiosities.\n",
        "## A. Draw bias battery\n",
        f"{len(sig_b)} of {len(battery)} tests significant after FDR.\n",
        "### Significant findings\n" if sig_b else "No test survived FDR — the drawn numbers are "
        "statistically indistinguishable from uniform in every way tested.\n",
    ]
    if sig_b:
        md.append(_md_table(sig_b, ["id", "n", "stat", "df", "p", "q", "note"],
                            ["test", "n", "stat", "df", "p", "q", "note"]))
    md.append("\n<details><summary>All battery results</summary>\n")
    md.append(_md_table(battery, ["id", "n", "stat", "df", "p", "q"],
                        ["test", "n", "stat", "df", "p", "q"]))
    md.append("\n</details>\n")
    md.append("## B. Tactic skill (walk-forward, empirical per-draw nulls)\n")
    md.append(_md_table(
        skill_rows,
        ["tactic", "kind", "n", "mean_r", "z", "z_h1", "z_h2", "top50_z", "p", "q", "verdict"],
        ["tactic", "kind", "n", "mean r", "z", "z h1", "z h2", "top50 z", "p", "q", "verdict"]))
    md.append("\n## Headlines\n")
    md.extend(f"- {h}" for h in doc["headlines"])
    md.append("\n## Method notes\n")
    md.append(
        "- Skill metric: tactic's Borda points for the actual combo vs the mean/variance of its own "
        "full 1000-combo Borda vector that draw (tie-correct: pool tactics' per-draw sigma is ~0.07, "
        "not the tie-free 0.289 — assuming Var=1/12 would mis-scale their z by ~4x).\n"
        "- No look-ahead: skill rides the backtest walk-forward loop (sentinel-tested); dueness "
        "walkers update last-seen strictly after scoring.\n"
        "- Verdict rule was fixed in code before the numbers were run: signal iff q<0.10 AND "
        "same-sign z in both halves of the window.\n")
    with open(REPORT_MD, "w") as f:
        f.write("\n".join(md) + "\n")

    if write_site:
        site = {"generated_at": generated, "as_of_draw": as_of,
                "window": skill_meta["n_draws"], "fdr_q": FDR_Q,
                "battery": {"n_tests": len(battery), "n_significant": len(sig_b),
                            "significant_ids": [r["id"] for r in sig_b]},
                "tactics": {r["tactic"]: {"z": r["z"], "q": round(r["q"], 4), "verdict": r["verdict"]}
                            for r in skill_rows if r["kind"] == "tactic"},
                "ensemble": {r["tactic"]: {"z": r["z"], "verdict": r["verdict"]}
                             for r in skill_rows if r["kind"] in ("ensemble", "picks", "pairs")},
                "headlines": doc["headlines"]}
        store.save_json(SITE_ANALYSIS, site)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=4000)
    ap.add_argument("--write", action="store_true", help="also write site/data/analysis.json")
    args = ap.parse_args()

    history = store.load_history()
    t0 = time.time()
    print(f"battery over {len(history)} draws...")
    battery = run_battery(history)
    print(f"  {len(battery)} tests, {sum(r['significant'] for r in battery)} significant "
          f"({time.time() - t0:.0f}s)")
    print(f"skill eval over last {args.draws} draws...")
    skill_rows, meta = run_skill(history=history, n_draws=args.draws, progress=True)
    doc = write_reports(battery, skill_rows, meta, history, write_site=args.write)
    print(json.dumps({"headlines": doc["headlines"]}, indent=2))
    print(f"wrote {REPORT_JSON} and {REPORT_MD}" + (f" and {SITE_ANALYSIS}" if args.write else ""))


if __name__ == "__main__":
    main()
