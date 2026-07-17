"""Fetchers + store. Fixture payloads are trimmed captures of the real responses
(2026-07-17). Live-network tests run locally but are skipped in CI."""
import json
import os
import urllib.parse

import pytest

from engine import fetch, store

LIVE = not os.environ.get("CI")

# ------------------------------------------------------------------- fixtures

# nylottery.ny.gov/nyl-api/games/numbers/draws — pending draw + one of each
# resulted status (20 and 22). drawTime = epoch ms, midnight ET of draw date.
NYL_PAYLOAD = {
    "data": {
        "draws": [
            {"drawTime": 1784260800000, "gameId": "9", "drawPeriod": 1, "gameName": "numbers",
             "drawNumber": 23224, "status": 4},  # pending — must be skipped
            {"drawTime": 1784174400000, "gameId": "9", "drawPeriod": 2, "gameName": "numbers",
             "drawNumber": 23223, "status": 20,
             "results": [{"primary": ["6", "0", "0"], "secondary": [""], "prizeTierId": "Regular"}]},
            {"drawTime": 1784174400000, "gameId": "9", "drawPeriod": 1, "gameName": "numbers",
             "drawNumber": 23222, "status": 20,
             "results": [{"primary": ["8", "0", "9"], "secondary": [""], "prizeTierId": "Regular"}]},
            {"drawTime": 1784088000000, "gameId": "9", "drawPeriod": 2, "gameName": "numbers",
             "drawNumber": 23221, "status": 22,
             "results": [{"primary": ["8", "0", "0"], "secondary": [""], "prizeTierId": "Regular"}]},
        ]
    }
}

# lotteryusa.com/new-york/numbers/ — two draw cards with an ad row between them.
LOTTERYUSA_HTML = """
<table class="c-results-table">
 <tbody id="js-state-results-table">
  <tr class="c-results-table__item c-results-table__item--medium c-draw-card">
   <th class="c-draw-card__date" scope="row">
    <time class="c-draw-card__draw-date">
     <span class="c-draw-card__draw-date-dow">Thursday,</span>
     <span class="c-draw-card__draw-date-sub">Jul 16, 2026</span>
    </time>
   </th>
   <td class="c-draw-card__result">
    <ul  class="c-result c-draw-card__ball-list">
     <li class="c-ball c-ball--sm">6</li>
     <li class="c-ball c-ball--sm">0</li>
     <li class="c-ball c-ball--sm">0</li>
    </ul>
   </td>
   <td class="c-draw-card__prize"><dd class="c-draw-card__prize-value">$500</dd></td>
  </tr>
  <tr class="c-results-table__item c-results-table__item--medium c-ad-wrapper ">
   <td colspan="3"><div class="js-raptive-ad-slot-video"></div></td>
  </tr>
  <tr class="c-results-table__item c-results-table__item--medium c-draw-card">
   <th class="c-draw-card__date" scope="row">
    <time class="c-draw-card__draw-date">
     <span class="c-draw-card__draw-date-dow">Wednesday,</span>
     <span class="c-draw-card__draw-date-sub">Jul 15, 2026</span>
    </time>
   </th>
   <td class="c-draw-card__result">
    <ul  class="c-result c-draw-card__ball-list">
     <li class="c-ball c-ball--sm">8</li>
     <li class="c-ball c-ball--sm">0</li>
     <li class="c-ball c-ball--sm">0</li>
    </ul>
   </td>
  </tr>
 </tbody>
</table>
"""

# data.ny.gov/resource/hsys-3def.json — real rows incl. truncated values
# ("56" = 056, "20" = 020) plus a today-row with no evening result yet.
SOCRATA_ROWS = [
    {"draw_date": "2026-07-16T00:00:00.000", "midday_daily": "809"},  # eve missing
    {"draw_date": "2026-07-15T00:00:00.000", "midday_daily": "976", "evening_daily": "800"},
    {"draw_date": "2026-07-12T00:00:00.000", "midday_daily": "56", "evening_daily": "283"},
    {"draw_date": "2026-07-10T00:00:00.000", "midday_daily": "20", "evening_daily": "839"},
]


def draw_shape_ok(dr):
    assert set(dr) >= {"id", "date", "period", "digits", "source", "draw_number", "fetched_at"}
    assert dr["id"] == f"{dr['date']}-{dr['period']}"
    assert dr["period"] in ("mid", "eve")
    assert isinstance(dr["digits"], list) and len(dr["digits"]) == 3
    assert all(isinstance(d, int) and 0 <= d <= 9 for d in dr["digits"])
    assert "T" in dr["fetched_at"]


# --------------------------------------------------------------- normalization

def test_normalize_number_zfill():
    assert fetch.normalize_number("56") == [0, 5, 6]   # Socrata truncation
    assert fetch.normalize_number("0") == [0, 0, 0]
    assert fetch.normalize_number("600") == [6, 0, 0]
    assert fetch.normalize_number(" 20 ") == [0, 2, 0]
    assert fetch.normalize_number("") is None
    assert fetch.normalize_number("1234") is None
    assert fetch.normalize_number("6-0") is None
    assert fetch.normalize_number("abc") is None


# --------------------------------------------------------------------- NYL API

def test_fetch_nyl_api_parses_and_skips_pending(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url, timeout=30: json.dumps(NYL_PAYLOAD))
    draws = fetch.fetch_nyl_api()
    assert len(draws) == 3  # pending status 4 skipped
    for dr in draws:
        draw_shape_ok(dr)
        assert dr["source"] == "nyl_api"
    by_id = {dr["id"]: dr for dr in draws}
    assert by_id["2026-07-16-eve"]["digits"] == [6, 0, 0]
    assert by_id["2026-07-16-eve"]["draw_number"] == 23223
    assert by_id["2026-07-16-mid"]["digits"] == [8, 0, 9]
    assert by_id["2026-07-15-eve"]["digits"] == [8, 0, 0]  # status 22 accepted


# ----------------------------------------------------------------- LotteryUSA

def test_parse_lotteryusa_fixture():
    draws = fetch._parse_lotteryusa(LOTTERYUSA_HTML, "eve")
    assert [(dr["id"], dr["digits"]) for dr in draws] == [
        ("2026-07-16-eve", [6, 0, 0]),
        ("2026-07-15-eve", [8, 0, 0]),
    ]
    for dr in draws:
        draw_shape_ok(dr)
        assert dr["source"] == "lotteryusa"
        assert dr["draw_number"] is None


def test_parse_lotteryusa_skips_malformed():
    bad = LOTTERYUSA_HTML.replace("Jul 15, 2026", "not a date")
    assert [dr["id"] for dr in fetch._parse_lotteryusa(bad, "mid")] == ["2026-07-16-mid"]
    # a card missing a ball is dropped, not mis-zfilled into a wrong number
    bad = LOTTERYUSA_HTML.replace('<li class="c-ball c-ball--sm">6</li>', "", 1)
    assert [dr["id"] for dr in fetch._parse_lotteryusa(bad, "eve")] == ["2026-07-15-eve"]


def test_fetch_lotteryusa_never_raises(monkeypatch):
    def boom(url, timeout=30):
        raise OSError("network down")
    monkeypatch.setattr(fetch, "_get", boom)
    assert fetch.fetch_lotteryusa("eve") == []
    monkeypatch.setattr(fetch, "_get", lambda url, timeout=30: "<html>redesigned</html>")
    assert fetch.fetch_lotteryusa("mid") == []
    assert fetch.fetch_lotteryusa("bogus-period") == []


# -------------------------------------------------------------------- Socrata

def test_fetch_socrata_two_draws_per_row(monkeypatch):
    seen = []

    def fake_get(url, timeout=30):
        seen.append(url)
        return json.dumps(SOCRATA_ROWS)

    monkeypatch.setattr(fetch, "_get", fake_get)
    draws = fetch.fetch_socrata(limit=10, since="2026-07-01")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(seen[0]).query))
    assert q["$select"] == "draw_date,midday_daily,evening_daily"
    assert q["$order"] == "draw_date DESC"
    assert q["$limit"] == "10" and q["$offset"] == "0"
    assert q["$where"] == "draw_date >= '2026-07-01'"

    for dr in draws:
        draw_shape_ok(dr)
        assert dr["source"] == "socrata"
    by_id = {dr["id"]: dr for dr in draws}
    assert len(draws) == 7 and "2026-07-16-eve" not in by_id  # missing eve skipped
    assert by_id["2026-07-16-mid"]["digits"] == [8, 0, 9]
    assert by_id["2026-07-12-mid"]["digits"] == [0, 5, 6]  # "56" zfilled
    assert by_id["2026-07-10-mid"]["digits"] == [0, 2, 0]  # "20" zfilled
    assert by_id["2026-07-15-eve"]["digits"] == [8, 0, 0]


def test_fetch_socrata_paginates(monkeypatch):
    monkeypatch.setattr(fetch, "_SOCRATA_PAGE", 2)
    offsets = []

    def fake_get(url, timeout=30):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        offsets.append((q["$offset"], q["$limit"]))
        lo = int(q["$offset"])
        return json.dumps(SOCRATA_ROWS[lo:lo + int(q["$limit"])])

    monkeypatch.setattr(fetch, "_get", fake_get)
    draws = fetch.fetch_socrata(limit=5)
    assert offsets == [("0", "2"), ("2", "2"), ("4", "1")]  # stops on short page
    assert len(draws) == 7
    assert len({dr["id"] for dr in draws}) == 7


# ---------------------------------------------------------------------- store

def test_save_load_json_atomic_roundtrip(tmp_path):
    path = tmp_path / "deep" / "nested" / "obj.json"
    obj = {"draws": [{"id": "2026-07-16-eve", "digits": [6, 0, 0]}], "n": 1}
    store.save_json(path, obj)  # parents auto-created
    assert store.load_json(path) == obj
    assert not (path.parent / (path.name + ".tmp")).exists()
    store.save_json(path, {"n": 2})  # overwrite in place
    assert store.load_json(path) == {"n": 2}
    assert store.load_json(tmp_path / "missing.json") is None
    assert store.load_json(tmp_path / "missing.json", default=[]) == []
    (tmp_path / "torn.json").write_text('{"half":')
    assert store.load_json(tmp_path / "torn.json", default="fallback") == "fallback"


def mk(did, digits, source="nyl_api", **extra):
    d, period = did.rsplit("-", 1)
    dr = {"id": did, "date": d, "period": period, "digits": digits,
          "source": source, "draw_number": None, "fetched_at": "2026-07-17T05:00:00+00:00"}
    dr.update(extra)
    return dr


def test_history_roundtrip_sorted_deduped(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "HISTORY_FILE", tmp_path / "history" / "draws_full.json")
    assert store.load_history() == []
    draws = [
        mk("2026-07-16-eve", [6, 0, 0]),
        mk("2026-07-15-mid", [9, 7, 6]),
        mk("2026-07-16-mid", [8, 0, 9]),
        mk("2026-07-16-eve", [6, 0, 0], source="lotteryusa"),  # dupe id
    ]
    store.save_history(draws)
    loaded = store.load_history()
    assert [dr["id"] for dr in loaded] == ["2026-07-15-mid", "2026-07-16-mid", "2026-07-16-eve"]
    doc = store.load_json(store.HISTORY_FILE)
    assert set(doc) == {"updated_at", "draws"} and "T" in doc["updated_at"]


def test_upsert_precedence_and_corrected_flag():
    existing = [mk("2026-07-15-eve", [8, 0, 0]), mk("2026-07-16-mid", [8, 0, 9])]
    new = [
        mk("2026-07-16-mid", [1, 1, 1], source="lotteryusa"),  # non-socrata conflict: existing wins
        mk("2026-07-15-eve", [8, 0, 0], source="socrata"),     # socrata, same digits: no correction
        mk("2026-07-16-eve", [6, 0, 0], source="socrata"),     # brand new
    ]
    merged = {dr["id"]: dr for dr in store.upsert_draws(existing, new)}
    assert merged["2026-07-16-mid"]["digits"] == [8, 0, 9]
    assert merged["2026-07-16-mid"]["source"] == "nyl_api"
    assert merged["2026-07-15-eve"]["source"] == "nyl_api"
    assert "corrected" not in merged["2026-07-15-eve"]
    assert merged["2026-07-16-eve"]["source"] == "socrata"

    # socrata with DIFFERENT digits overrides and flags corrected
    fix = [mk("2026-07-16-mid", [8, 1, 9], source="socrata")]
    merged2 = {dr["id"]: dr for dr in store.upsert_draws(list(merged.values()), fix)}
    assert merged2["2026-07-16-mid"]["digits"] == [8, 1, 9]
    assert merged2["2026-07-16-mid"]["corrected"] is True
    # result is sorted
    ids = [dr["id"] for dr in store.upsert_draws(existing, new)]
    assert ids == ["2026-07-15-eve", "2026-07-16-mid", "2026-07-16-eve"]


def test_window_draws():
    hist = [mk(f"2026-07-{d:02d}-mid", [0, 0, d % 10]) for d in range(1, 16)]
    assert store.window_draws(hist, n=5) == hist[-5:]
    assert store.window_draws(hist) == hist  # n=400 > len


def test_lock_proof_never_raises():
    proof = store.lock_proof()
    assert set(proof) == {"sha", "committed_at"}
    assert proof["sha"] is None or len(proof["sha"]) == 40


def test_paths():
    assert store.SITE_DATA == store.ROOT / "site" / "data"
    assert store.HISTORY_FILE.name == "draws_full.json"
    for p in (store.DRAWS, store.PREDICTION, store.LEDGER, store.WEIGHTS,
              store.STATS, store.COMMUNITY):
        assert p.parent == store.SITE_DATA and p.suffix == ".json"


# ----------------------------------------------------------------- live network

@pytest.mark.skipif(not LIVE, reason="no network in CI")
def test_live_nyl_api():
    draws = fetch.fetch_nyl_api()
    assert draws, "NYL API returned no resulted draws"
    for dr in draws:
        draw_shape_ok(dr)
        assert isinstance(dr["draw_number"], int)
    by_id = {dr["id"]: dr for dr in draws}
    if "2026-07-16-eve" in by_id:  # golden anchor while it stays in the ~10-draw window
        assert by_id["2026-07-16-eve"]["digits"] == [6, 0, 0]


@pytest.mark.skipif(not LIVE, reason="no network in CI")
def test_live_lotteryusa_agrees_with_nyl():
    nyl = {dr["id"]: dr["digits"] for dr in fetch.fetch_nyl_api()}
    for period in ("mid", "eve"):
        draws = fetch.fetch_lotteryusa(period)
        assert len(draws) >= 5, f"lotteryusa {period} parser broke (markup change?)"
        for dr in draws:
            draw_shape_ok(dr)
            assert dr["period"] == period
            if dr["id"] in nyl:
                assert dr["digits"] == nyl[dr["id"]], f"source disagreement on {dr['id']}"


@pytest.mark.skipif(not LIVE, reason="no network in CI")
def test_live_socrata():
    draws = fetch.fetch_socrata(limit=10)
    assert 10 <= len(draws) <= 20  # 10 rows, today may lack evening
    for dr in draws:
        draw_shape_ok(dr)
