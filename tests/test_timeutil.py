from datetime import date, datetime
from zoneinfo import ZoneInfo

from engine import timeutil

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def test_draw_id_roundtrip():
    d, p = timeutil.parse_draw_id("2026-07-17-mid")
    assert (d, p) == (date(2026, 7, 17), "mid")
    assert timeutil.draw_id(d, p) == "2026-07-17-mid"


def test_latest_expected_ordinary_day():
    # 3:00 PM ET -> today's midday
    now = datetime(2026, 7, 17, 15, 0, tzinfo=ET)
    assert timeutil.latest_expected_draw(now) == (date(2026, 7, 17), "mid")
    # 11:00 PM ET -> today's evening
    now = datetime(2026, 7, 17, 23, 0, tzinfo=ET)
    assert timeutil.latest_expected_draw(now) == (date(2026, 7, 17), "eve")
    # 9:00 AM ET -> yesterday's evening
    now = datetime(2026, 7, 17, 9, 0, tzinfo=ET)
    assert timeutil.latest_expected_draw(now) == (date(2026, 7, 16), "eve")
    # exactly 2:30 PM counts as drawn
    now = datetime(2026, 7, 17, 14, 30, tzinfo=ET)
    assert timeutil.latest_expected_draw(now) == (date(2026, 7, 17), "mid")


def test_utc_date_line_crossing():
    # 10:33 PM EDT = 02:33 UTC next day — must still resolve to the ET date's evening
    now = datetime(2026, 7, 18, 2, 33, tzinfo=UTC)
    assert timeutil.latest_expected_draw(now) == (date(2026, 7, 17), "eve")


def test_dst_spring_forward_2026():
    # US DST began 2026-03-08 (2 AM EST -> 3 AM EDT). 18:33 UTC on 03-07 (EST) = 1:33 PM ET
    # (midday not yet drawn); on 03-08 (EDT) 18:33 UTC = 2:33 PM ET (midday drawn).
    before = datetime(2026, 3, 7, 18, 33, tzinfo=UTC)
    assert timeutil.latest_expected_draw(before) == (date(2026, 3, 6), "eve")
    after = datetime(2026, 3, 8, 18, 33, tzinfo=UTC)
    assert timeutil.latest_expected_draw(after) == (date(2026, 3, 8), "mid")


def test_dst_fall_back_2026():
    # US DST ends 2026-11-01. 19:33 UTC = 2:33 PM EST on 11-01 (drawn);
    # on 10-31 (EDT) 19:33 UTC = 3:33 PM EDT (also drawn — the later cron is the retry).
    assert timeutil.latest_expected_draw(datetime(2026, 11, 1, 19, 33, tzinfo=UTC)) == (
        date(2026, 11, 1), "mid")
    assert timeutil.latest_expected_draw(datetime(2026, 10, 31, 19, 33, tzinfo=UTC)) == (
        date(2026, 10, 31), "mid")
    # 18:33 UTC on 11-01 (EST) = 1:33 PM — midday NOT drawn yet: previous evening
    assert timeutil.latest_expected_draw(datetime(2026, 11, 1, 18, 33, tzinfo=UTC)) == (
        date(2026, 10, 31), "eve")


def test_next_and_after():
    now = datetime(2026, 7, 17, 15, 0, tzinfo=ET)
    assert timeutil.next_draw(now) == (date(2026, 7, 17), "eve")
    assert timeutil.draw_after(date(2026, 7, 17), "mid") == (date(2026, 7, 17), "eve")
    assert timeutil.draw_after(date(2026, 7, 17), "eve") == (date(2026, 7, 18), "mid")


def test_sort_key():
    ids = ["2026-07-17-eve", "2026-07-17-mid", "2026-07-16-eve"]
    assert sorted(ids, key=timeutil.sort_key) == [
        "2026-07-16-eve", "2026-07-17-mid", "2026-07-17-eve"]
