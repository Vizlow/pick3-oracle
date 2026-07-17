"""Site data invariants — runs against whatever is currently in site/data
(fixtures during development, REAL pipeline output in CI). Ledger grades are
recomputed from first principles; the site must stay fully self-contained.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from engine import lmath, timeutil  # noqa: E402

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
ROOT = os.path.join(SITE, "..")
DATA = os.path.join(SITE, "data")


def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def load_backtest():
    path = os.path.join(ROOT, "data", "history", "backtest_ledger.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)["entries"]


def is_combo(x):
    return isinstance(x, list) and len(x) == 3 and all(isinstance(d, int) and 0 <= d <= 9 for d in x)


def is_pair(x):
    return isinstance(x, list) and len(x) == 2 and all(isinstance(d, int) and 0 <= d <= 9 for d in x)


# ---------------------------------------------------------------- draws.json
def test_draws_contract():
    doc = load("draws.json")
    draws = doc["draws"]
    assert len(draws) >= 30
    for d in draws:
        for key in ("id", "date", "period", "digits", "source"):
            assert key in d, f"draw missing {key}"
        assert d["id"] == f"{d['date']}-{d['period']}"
        assert d["period"] in ("mid", "eve")
        assert is_combo(d["digits"])
    ids = [d["id"] for d in draws]
    assert ids == sorted(ids, key=timeutil.sort_key), "draws must be newest last"
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------ prediction.json
def check_prediction_shape(p):
    for key in ("draw_id", "generated_at", "picks", "top_pick", "pairs",
                "engine_version", "explain"):
        assert key in p, f"prediction missing {key}"
    assert len(p["picks"]) == 5
    assert all(is_combo(pk) for pk in p["picks"])
    assert p["top_pick"] == p["picks"][0]
    assert is_pair(p["pairs"]["front"]) and is_pair(p["pairs"]["back"])
    assert isinstance(p["explain"]["top_tactics_for_top_pick"], list)


def test_prediction_contract():
    p = load("prediction.json")
    check_prediction_shape(p)
    # pending prediction must be for the draw AFTER the last recorded result
    draws = load("draws.json")["draws"]
    last_date, last_period = timeutil.parse_draw_id(draws[-1]["id"])
    assert p["draw_id"] == timeutil.draw_id(*timeutil.draw_after(last_date, last_period))


# ---------------------------------------------------------------- ledger.json
PNL_STRUCTS = ("all_straight", "all_box", "sb_top", "pairs_mix")


def check_pnl_block(pnl):
    for st in PNL_STRUCTS:
        assert pnl[st]["stake"] > 0
        assert pnl[st]["won"] >= 0


def check_grade(grade, picks, top, result):
    result_t = tuple(result)
    assert grade["straight_hit"] == any(tuple(p) == result_t for p in picks)
    bh = grade["box_hit"]
    box_idxs = [i for i, p in enumerate(picks) if sorted(p) == sorted(result)]
    if box_idxs:
        assert bh["pick_index"] == box_idxs[0]
    else:
        assert bh["pick_index"] is None and bh["type"] is None
    tp = grade["top_pick"]
    assert tp["straight"] == (tuple(top) == result_t)
    assert tp["box"] == (sorted(top) == sorted(result))
    in_cloud = result_t in lmath.one_off_cloud(tuple(top))
    assert tp["one_off"] == (in_cloud and not tp["straight"])


def check_entry(e, results_by_id):
    for key in ("draw_id", "mode", "prediction", "lock", "result", "grade", "pnl",
                "baseline", "corrected"):
        assert key in e, f"ledger entry missing {key}"
    check_prediction_shape(e["prediction"])
    assert e["prediction"]["draw_id"] == e["draw_id"]
    if e["lock"].get("sha") is not None:
        assert re.fullmatch(r"[0-9a-f]{40}", e["lock"]["sha"])
    assert is_combo(e["result"])
    if e["draw_id"] in results_by_id:
        assert e["result"] == results_by_id[e["draw_id"]], "ledger vs draws.json mismatch"
    p = e["prediction"]
    check_grade(e["grade"], p["picks"], p["top_pick"], e["result"])
    assert e["grade"]["pair_hits"]["front"] == (p["pairs"]["front"] == e["result"][:2])
    assert e["grade"]["pair_hits"]["back"] == (p["pairs"]["back"] == e["result"][1:])
    check_pnl_block(e["pnl"])
    b = e["baseline"]
    assert len(b["random_picks"]) == 5 and all(is_combo(pk) for pk in b["random_picks"])
    result_t = tuple(e["result"])
    assert b["grade"]["straight_hit"] == any(tuple(pk) == result_t for pk in b["random_picks"])
    bbh = b["grade"]["box_hit"]
    bbh_hit = bbh.get("pick_index") is not None if isinstance(bbh, dict) else bool(bbh)
    assert bbh_hit == any(sorted(pk) == sorted(e["result"]) for pk in b["random_picks"])
    check_pnl_block(b["pnl"])
    assert isinstance(e["corrected"], bool)


def test_ledger_contract():
    entries = load("ledger.json")["entries"]
    ids = [e["draw_id"] for e in entries]
    assert ids == sorted(ids, key=timeutil.sort_key), "ledger must be chronological"
    results_by_id = {d["id"]: d["digits"] for d in load("draws.json")["draws"]}
    for e in entries:
        assert e["mode"] == "live", "site ledger holds live entries only"
        check_entry(e, results_by_id)


def test_backtest_ledger_contract():
    entries = load_backtest()
    for e in entries[:25] + entries[-25:]:
        assert e["mode"] == "backtest"
        check_entry(e, {})


# --------------------------------------------------------------- weights.json
def test_weights_contract():
    doc = load("weights.json")
    for key in ("updated_at", "params", "tactics"):
        assert key in doc
    tactics = doc["tactics"]
    assert len(tactics) >= 18
    for t in tactics.values():
        assert 0.0 <= t["ewma"] <= 1.0
        assert len(t["spark"]) <= 60
        assert all(0.0 <= r <= 1.0 for r in t["spark"])
        assert t["draws_seen"] >= 0
    assert abs(sum(t["weight"] for t in tactics.values()) - 1.0) < 1e-3


# ----------------------------------------------------------------- stats.json
def test_stats_contract():
    doc = load("stats.json")
    for key in ("updated_at", "scoreboard", "pnl", "charts", "tactics_order"):
        assert key in doc

    live = doc["scoreboard"]["live"]
    n = live["n_draws"]
    entries = load("ledger.json")["entries"]
    assert n == len(entries)
    for key, baseline in [("any_straight", 0.005), ("any_box", 0.0295), ("top_box", 0.006),
                          ("front_pair", 0.01), ("back_pair", 0.01)]:
        m = live[key]
        assert m["baseline"] == baseline
        if n:
            assert abs(m["rate"] - m["hits"] / n) < 1e-3

    pnl = doc["pnl"]
    assert pnl["headline"] in pnl["structures"]
    assert pnl["structures"] == ["all_box", "all_straight", "sb_top", "pairs_mix"]
    counts = {"live": len(entries), "backtest": len(load_backtest())}
    for mode in ("live", "backtest"):
        blk = pnl[mode]
        assert len(blk["labels"]) == counts[mode]
        expect_series = set(pnl["structures"]) | {"random_control", "house_edge_ref"}
        assert set(blk["series"]) == expect_series
        for s in blk["series"].values():
            assert len(s) == counts[mode]
    for key in pnl["structures"] + ["random_control"]:
        s = pnl["summary"][key]
        assert abs(s["net"] - (s["won"] - s["stake"])) < 0.01

    c = doc["charts"]
    assert len(c["positional_freq"]) == 3 and all(len(r) == 10 for r in c["positional_freq"])
    ds = c["digit_skips"]
    assert len(ds["any"]) == 10 and len(ds["median_any"]) == 10
    assert len(ds["pos"]) == 3 and all(len(r) == 10 for r in ds["pos"])
    for kind in ("front", "split", "back"):
        g = c["pairs_heat"][kind]
        assert len(g) == 10 and all(len(r) == 10 for r in g)
    vt = c["vtrac"]
    assert len(vt["pos_skips"]) == 3 and all(len(r) == 5 for r in vt["pos_skips"])
    assert len(vt["freq30"]) == 3 and all(len(r) == 5 for r in vt["freq30"])
    assert vt["last"] is None or (len(vt["last"]) == 3 and all(1 <= v <= 5 for v in vt["last"]))
    sd = c["sum_dist"]
    assert len(sd["observed"]) == 28 and len(sd["theoretical"]) == 28
    st = c["structure"]
    assert set(st["observed"]) == {"single", "double", "triple"}
    assert st["expected_pct"] == [72, 27, 1]

    assert set(doc["tactics_order"]) == set(load("weights.json")["tactics"].keys())


def test_stats_cumulative_series_match_ledgers():
    doc = load("stats.json")
    for mode, entries in (("live", load("ledger.json")["entries"]),
                          ("backtest", load_backtest())):
        blk = doc["pnl"][mode]
        assert blk["labels"] == [e["draw_id"] for e in entries]
        total = 0.0
        for i, e in enumerate(entries):
            total += e["pnl"]["all_box"]["won"] - e["pnl"]["all_box"]["stake"]
            assert abs(blk["series"]["all_box"][i] - total) < 0.01


# ------------------------------------------------------------- site invariants
def read_site(name):
    with open(os.path.join(SITE, name)) as f:
        return f.read()


def test_site_files_exist():
    for name in ("index.html", "app.js", "charts.js", "style.css"):
        assert os.path.getsize(os.path.join(SITE, name)) > 0


def test_no_external_resources():
    """CSP-clean: no CDN scripts, external styles, fonts, or remote fetches."""
    html = read_site("index.html")
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", html)
    assert "@import" not in read_site("style.css")
    assert "url(http" not in read_site("style.css")
    for js in ("app.js", "charts.js"):
        assert not re.search(r"""fetch\(\s*["']https?://""", read_site(js))


def test_app_js_contract_hooks():
    app = read_site("app.js")
    assert re.search(r'^const REPO_URL\s*=', app, re.M)
    assert "Date.now()" in app, "cache-busting ?v=<Date.now()> required"
    assert "community.json" in app, "must attempt (optional) community.json load"
    assert "America/New_York" in app, "countdown must compute in ET"
    for name in ("draws.json", "prediction.json", "ledger.json", "weights.json", "stats.json"):
        assert name in app


def test_index_references_assets():
    html = read_site("index.html")
    assert 'href="style.css"' in html
    assert 'src="charts.js"' in html and 'src="app.js"' in html
    assert "house edge" in html, "honesty banner must be present"
    assert "1-800-GAMBLER" in html


def test_vercel_json():
    with open(os.path.join(ROOT, "vercel.json")) as f:
        cfg = json.load(f)
    assert cfg["outputDirectory"] == "site"
    assert cfg["buildCommand"] is None
