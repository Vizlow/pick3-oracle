"""Draw-result fetchers. Three independent sources, all normalized to one shape:

    {"id": "<YYYY-MM-DD>-<mid|eve>", "date": "YYYY-MM-DD", "period": "mid"|"eve",
     "digits": [a, b, c], "source": str, "draw_number": int|None, "fetched_at": iso-utc}

Sources: NY Lottery API (primary, fastest), LotteryUSA scrape (secondary check),
Socrata open-data (backfill/audit — authoritative but lags ~1 day). Every request
sends a User-Agent header (Cloudflare rejects bare urllib clients). Number strings
are zfill(3)-normalized because Socrata stores truncated values ("56" -> 056,
"0" -> 000) and validated against ^\\d{3}$.
"""
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

from html.parser import HTMLParser

from engine import timeutil

USER_AGENT = "pick3-oracle/1.0"
NUMBER_RE = re.compile(r"^\d{3}$")

NYL_URL = "https://nylottery.ny.gov/nyl-api/games/numbers/draws"
NYL_PERIODS = {1: "mid", 2: "eve"}
NYL_RESULTED_STATUSES = {20, 22}  # 4 = pending; 20/22 = resulted

LOTTERYUSA_URLS = {
    "mid": "https://www.lotteryusa.com/new-york/midday-numbers/",
    "eve": "https://www.lotteryusa.com/new-york/numbers/",
}

SOCRATA_URL = "https://data.ny.gov/resource/hsys-3def.json"
_SOCRATA_PAGE = 5000  # rows per request when paginating a big backfill


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_number(s):
    """'56' -> [0,5,6], '0' -> [0,0,0], '600' -> [6,0,0]; None if not a 3-digit number."""
    s = str(s).strip()
    if not s:  # missing value, NOT the number 000
        return None
    s = s.zfill(3)
    if not NUMBER_RE.match(s):
        return None
    return [int(ch) for ch in s]


def _draw(d, period, digits, source, draw_number=None):
    return {
        "id": timeutil.draw_id(d, period),
        "date": d.isoformat(),
        "period": period,
        "digits": digits,
        "source": source,
        "draw_number": draw_number,
        "fetched_at": _utc_now_iso(),
    }


# ---------------------------------------------------------------- NY Lottery API

def fetch_nyl_api():
    """Last ~10 draws from the official app API. Skips pending draws (status 4)."""
    payload = json.loads(_get(NYL_URL))
    out = []
    for raw in (payload.get("data") or {}).get("draws", []):
        if raw.get("status") not in NYL_RESULTED_STATUSES:
            continue
        period = NYL_PERIODS.get(raw.get("drawPeriod"))
        if period is None:
            continue
        results = raw.get("results") or []
        primary = (results[0].get("primary") or []) if results else []
        if len(primary) != 3:
            continue
        digits = normalize_number("".join(str(p).strip() for p in primary))
        if digits is None:
            continue
        # drawTime is epoch ms at midnight ET of the draw date.
        d = datetime.fromtimestamp(raw["drawTime"] / 1000, tz=timeutil.ET).date()
        out.append(_draw(d, period, digits, "nyl_api", raw.get("drawNumber")))
    return out


# ------------------------------------------------------------------- LotteryUSA

class _LotteryUsaParser(HTMLParser):
    """Collects (date_text, ball_texts) per <tr class="... c-draw-card"> row.

    Markup (July 2026): date in <span class="c-draw-card__draw-date-sub">Jul 16, 2026
    </span>, digits as <li class="c-ball ..."> inside <ul class="c-result
    c-draw-card__ball-list">. Ad rows share the table but lack c-draw-card.
    """

    def __init__(self):
        super().__init__()
        self.rows = []
        self._in_card = False
        self._capture = None  # "date" | "ball"
        self._date_parts = []
        self._balls = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if tag == "tr":
            self._in_card = "c-draw-card" in cls
            self._date_parts, self._balls = [], []
        elif self._in_card and tag == "span" and "c-draw-card__draw-date-sub" in cls:
            self._capture = "date"
        elif self._in_card and tag == "li" and "c-ball" in cls:
            self._capture = "ball"
            self._balls.append("")

    def handle_endtag(self, tag):
        if tag in ("span", "li"):
            self._capture = None
        elif tag == "tr" and self._in_card:
            self._in_card = False
            self.rows.append(("".join(self._date_parts).strip(), [b.strip() for b in self._balls]))

    def handle_data(self, data):
        if self._capture == "date":
            self._date_parts.append(data)
        elif self._capture == "ball" and self._balls:
            self._balls[-1] += data


def _parse_lotteryusa(html, period):
    parser = _LotteryUsaParser()
    parser.feed(html)
    out = []
    for date_text, balls in parser.rows:
        try:
            d = datetime.strptime(date_text, "%b %d, %Y").date()
        except ValueError:
            continue
        if len(balls) != 3:
            continue
        digits = normalize_number("".join(balls))
        if digits is None:
            continue
        out.append(_draw(d, period, digits, "lotteryusa"))
    return out


def fetch_lotteryusa(period):
    """Last ~10 draws for one period, scraped. Returns [] on ANY failure — this is
    a secondary source and must never take the pipeline down."""
    try:
        return _parse_lotteryusa(_get(LOTTERYUSA_URLS[period]), period)
    except Exception:
        return []


# ---------------------------------------------------------------------- Socrata

def fetch_socrata(limit=100, since=None):
    """NY open-data (dataset hsys-3def). One row per date with midday_daily +
    evening_daily columns -> up to two draws per row (today's row may lack evening).
    `since` = date or 'YYYY-MM-DD' lower bound; `limit` counts rows (dates)."""
    if isinstance(since, date):
        since = since.isoformat()
    out = []
    offset = 0
    while offset < limit:
        page = min(_SOCRATA_PAGE, limit - offset)
        params = {
            "$select": "draw_date,midday_daily,evening_daily",
            "$order": "draw_date DESC",
            "$limit": str(page),
            "$offset": str(offset),
        }
        if since:
            params["$where"] = f"draw_date >= '{since}'"
        rows = json.loads(_get(SOCRATA_URL + "?" + urllib.parse.urlencode(params)))
        for row in rows:
            try:
                d = date.fromisoformat((row.get("draw_date") or "")[:10])
            except ValueError:
                continue
            for field, period in (("midday_daily", "mid"), ("evening_daily", "eve")):
                val = row.get(field)
                if val in (None, ""):
                    continue
                digits = normalize_number(val)
                if digits is None:
                    continue
                out.append(_draw(d, period, digits, "socrata"))
        if len(rows) < page:
            break
        offset += page
    return out
