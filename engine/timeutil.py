"""All NY Numbers draw-schedule logic. Every time decision in the codebase goes
through this module, always in America/New_York. Draw times: midday 2:30 PM,
evening 10:30 PM ET, daily (sales cutoffs 2:15 / 10:20 PM).
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

PERIODS = ("mid", "eve")
DRAW_TIMES = {"mid": time(14, 30), "eve": time(22, 30)}
CUTOFF_TIMES = {"mid": time(14, 15), "eve": time(22, 20)}


def draw_id(d, period):
    return f"{d.isoformat()}-{period}"


def parse_draw_id(did):
    ds, period = did.rsplit("-", 1)
    return date.fromisoformat(ds), period


def draw_datetime(d, period):
    return datetime.combine(d, DRAW_TIMES[period], tzinfo=ET)


def cutoff_datetime(d, period):
    return datetime.combine(d, CUTOFF_TIMES[period], tzinfo=ET)


def sort_key(did):
    d, period = parse_draw_id(did)
    return (d, PERIODS.index(period))


def latest_expected_draw(now=None):
    """Most recent scheduled draw whose draw time is <= now. Returns (date, period)."""
    now = now.astimezone(ET) if now else datetime.now(ET)
    d = now.date()
    for _ in range(3):
        for period in reversed(PERIODS):
            if draw_datetime(d, period) <= now:
                return d, period
        d -= timedelta(days=1)
    raise RuntimeError("no draw found in lookback window")


def next_draw(now=None):
    """Next scheduled draw strictly after now. Returns (date, period)."""
    now = now.astimezone(ET) if now else datetime.now(ET)
    d = now.date()
    for _ in range(3):
        for period in PERIODS:
            if draw_datetime(d, period) > now:
                return d, period
        d += timedelta(days=1)
    raise RuntimeError("no draw found in lookahead window")


def draw_after(d, period):
    """The draw immediately following (date, period)."""
    if period == "mid":
        return d, "eve"
    return d + timedelta(days=1), "mid"


def hours_before_draw(lock_dt, d, period):
    return round((draw_datetime(d, period) - lock_dt.astimezone(ET)).total_seconds() / 3600, 1)
