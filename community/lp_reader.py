#!/usr/bin/env python3
"""LotteryPost community-picks reader.

Reads the monthly "New York: M/1 - M/<last>/YYYY" Pick 3 thread on
lotterypost.com (via the Firecrawl API — the site Cloudflare-blocks direct
HTTP), parses member posts, extracts 3-digit predictions, and attributes each
pick to every NY draw in the 48 hours after the post. Results merge into
site/data/community.json for the dashboard and the community tactic.

Thread page DOM (from a rendered capture):
  <ul class="threadview">
    <li id="i8196764">
      <div class="memberinfo"> ... <a href=".../member/72480" data-member="72480"><strong>NY216</strong></a>
      <div class="postdetail"> ... <time datetime="2026-07-13T22:36-05:00">Jul 13, 2026, 10:36 pm</time>
      <div class="postbody ...">
        <div class="quote"><div class="quotemessage">Quote: Originally posted by ...</div></div>  <- EXCLUDED
        <div class="postbodyinner"> ...post content... </div>
        <div class="signature"> ... </div>                                                        <- EXCLUDED
The <time> datetime attribute's wall clock matches the displayed ET time (the
offset it carries is unreliable), so we read the wall clock as ET. Relative
text ("Today", "Yesterday", "2 hours ago") is a fallback resolved against the
page fetch time.

update() is FAIL-SOFT: any exception prints a WARN to stderr and returns
False; it never crashes the caller.
"""
import calendar
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, time, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import store, timeutil  # noqa: E402
from engine.timeutil import ET  # noqa: E402

BASE_URL = "https://www.lotterypost.com"
FORUM_URL = f"{BASE_URL}/forum/3"  # Pick 3 forum
STATE_FILE = Path(__file__).resolve().parent / "state.json"

ATTRIBUTION_WINDOW_HOURS = 48
MAX_PICKS_PER_POST = 40
PRUNE_AFTER_DAYS = 14

# ------------------------------------------------------------------ firecrawl


def _api_key():
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        return key
    env_path = Path.home() / "Workspace" / ".env"
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("FIRECRAWL_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    raise RuntimeError("FIRECRAWL_API_KEY not set (env or ~/Workspace/.env)")


def firecrawl_scrape(url, fmt):
    """Fetch a Cloudflare-protected page through Firecrawl. Returns the
    requested format ("html" or "markdown") as a string. Raises on failure."""
    payload = json.dumps({"url": url, "formats": [fmt], "timeout": 60000}).encode()
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.load(resp)
    data = body.get("data") or {}
    if not body.get("success") or not data.get(fmt):
        raise RuntimeError(f"firecrawl scrape failed for {url}: {str(body)[:300]}")
    return data[fmt]


# ------------------------------------------------------------------ discovery

_TITLE_RE = re.compile(r"New York:\s*(\d{1,2})/1\s*-\s*\d{1,2}/\d{1,2}/(\d{4})")


def _thread_month(title):
    m = _TITLE_RE.search(title or "")
    return (int(m.group(2)), int(m.group(1))) if m else None


def discover_thread(now_et=None):
    """Find the current month's NY thread in the Pick 3 forum. Cached in
    community/state.json; only re-scrapes when the month rolls over."""
    now_et = (now_et or datetime.now(ET)).astimezone(ET)
    state = store.load_json(STATE_FILE, None) or {}
    cached = state.get("thread")
    if cached and _thread_month(cached.get("title", "")) == (now_et.year, now_et.month):
        return cached

    md = firecrawl_scrape(FORUM_URL, "markdown")
    last_day = calendar.monthrange(now_et.year, now_et.month)[1]
    title = f"New York: {now_et.month}/1 - {now_et.month}/{last_day}/{now_et.year}"
    md_clean = md.replace("\\", "")  # markdown escapes (\_ etc.)
    m = re.search(
        re.escape(title) + r"[^\]]*\]\((?:https?://(?:www\.)?lotterypost\.com)?/?thread/(\d+)",
        md_clean,
    )
    if not m:  # tolerate the title and the link being separated
        idx = md_clean.find(title)
        if idx != -1:
            m = re.search(r"/thread/(\d+)", md_clean[idx : idx + 500])
    if not m:
        raise RuntimeError(f"thread titled {title!r} not found in {FORUM_URL}")
    tid = int(m.group(1))
    thread = {"id": tid, "title": title, "url": f"{BASE_URL}/thread/{tid}"}
    state["thread"] = thread
    state["checked_at"] = now_et.isoformat(timespec="seconds")
    store.save_json(STATE_FILE, state)
    return thread


def _page_url(thread_url, page):
    return thread_url if page <= 1 else f"{thread_url}/{page}"


def _page_info(html):
    """(current_page, total_pages) from the 'Page 5 of 6' pager. (1, 1) when
    the thread has a single page (no pager)."""
    m = re.search(r"Page\s*<strong>(\d+)</strong>\s*of\s*<strong>(\d+)</strong>", html)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", html)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1, 1


# ------------------------------------------------------------------ post parsing

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
_BLOCK_NL = {
    "p", "div", "li", "ul", "ol", "table", "tbody", "tr", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre",
}
_BLOCK_SP = {"td", "th"}
_EXCLUDE_CLASSES = {"quote", "quotemessage", "quotemessagehead", "signature"}
_POST_ID_RE = re.compile(r"i\d+")


class _ThreadHTMLParser(HTMLParser):
    """Stateful parser for a LotteryPost thread page. Collects, per post <li>:
    member name, posted-at datetime (ET), and body text with quoted-reply
    blocks and signatures excluded."""

    def __init__(self, page_fetched_at_et):
        super().__init__(convert_charrefs=True)
        self._ref = page_fetched_at_et.astimezone(ET)
        self.posts = []
        self._stack = []  # [{tag, classes, capture, post_root}]
        self._post = None
        self._member_buf = []
        self._time_buf = []
        self._time_attr = None
        self._body_buf = []

    # -- helpers
    def _in_class(self, cls):
        return any(cls in e["classes"] for e in self._stack)

    def _body_active(self):
        if self._post is None:
            return False
        blocked = any(
            e["classes"] & _EXCLUDE_CLASSES or e["tag"] in ("script", "style")
            for e in self._stack
        )
        return self._in_class("postbodyinner") and not blocked

    def _active_capture(self):
        for e in reversed(self._stack):
            if e["capture"]:
                return e["capture"]
        return None

    # -- tag events
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        post_root = False

        if tag == "li" and _POST_ID_RE.fullmatch(a.get("id") or ""):
            if self._post is not None:  # unclosed previous post: finalize
                self._finalize_post()
            self._post = {"member": None, "posted_at": None}
            self._member_buf, self._time_buf, self._body_buf = [], [], []
            self._time_attr = None
            post_root = True

        if tag in _VOID_TAGS:
            if tag == "br" and self._body_active():
                self._body_buf.append("\n")
            return

        capture = None
        if self._post is not None:
            if (
                tag == "a"
                and a.get("data-member")
                and self._post["member"] is None
                and not self._body_active()
            ):
                capture = "member"
            elif tag == "time" and self._post["posted_at"] is None:
                capture = "time"
                self._time_attr = a.get("datetime")

        self._stack.append({"tag": tag, "classes": classes, "capture": capture, "post_root": post_root})

        if self._body_active():
            if tag in _BLOCK_NL:
                self._body_buf.append("\n")
            elif tag in _BLOCK_SP:
                self._body_buf.append(" ")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._body_active():
            self._body_buf.append("\n")

    def handle_endtag(self, tag):
        if tag in _VOID_TAGS:
            return
        # find the matching open tag (tolerate minor imbalance)
        idx = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                idx = i
                break
        if idx is None:
            return
        if self._body_active():
            if tag in _BLOCK_NL:
                self._body_buf.append("\n")
            elif tag in _BLOCK_SP:
                self._body_buf.append(" ")
        popped = self._stack[idx:]
        del self._stack[idx:]
        for e in popped:
            if e["capture"] == "member" and self._post is not None:
                name = "".join(self._member_buf).strip()
                if name:
                    self._post["member"] = name
                self._member_buf = []
            elif e["capture"] == "time" and self._post is not None:
                self._post["posted_at"] = self._resolve_time()
                self._time_buf = []
            if e["post_root"]:
                self._finalize_post()

    def handle_data(self, data):
        cap = self._active_capture()
        if cap == "member":
            self._member_buf.append(data)
        elif cap == "time":
            self._time_buf.append(data)
        elif self._body_active():
            self._body_buf.append(data)

    def close(self):
        super().close()
        if self._post is not None:
            self._finalize_post()

    # -- finalization
    def _resolve_time(self):
        if self._time_attr:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", self._time_attr)
            if m:
                y, mo, d, h, mi = (int(g) for g in m.groups())
                # wall clock is site-local ET; the attr's UTC offset is unreliable
                return datetime(y, mo, d, h, mi, tzinfo=ET)
        txt = "".join(self._time_buf).strip()
        if txt:
            return _parse_time_text(txt, self._ref)
        return None

    def _finalize_post(self):
        post, self._post = self._post, None
        if not post or not post.get("member") or not post.get("posted_at"):
            return
        text = "".join(self._body_buf).replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" ?\n ?", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text).strip()
        self.posts.append(
            {
                "member": post["member"],
                "posted_at": post["posted_at"].isoformat(),
                "text": text,
            }
        )


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_time_text(txt, ref_et):
    """Parse a LotteryPost timestamp string to an aware ET datetime.
    Handles "Today, 2:32 pm" / "Yesterday, 2:32 pm" / "2 hours ago" /
    "Jul 13, 2026, 10:36 pm" / "July 13, 2026" (missing time -> 12:00)."""
    t = txt.replace("\xa0", " ").strip().lower()
    ref = ref_et.astimezone(ET)
    tm = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", t)

    def clock():
        if not tm:
            return time(12, 0)
        h = int(tm.group(1)) % 12
        if tm.group(3) == "pm":
            h += 12
        return time(h, int(tm.group(2)))

    if t.startswith("today"):
        return datetime.combine(ref.date(), clock(), tzinfo=ET)
    if t.startswith("yesterday"):
        return datetime.combine(ref.date() - timedelta(days=1), clock(), tzinfo=ET)
    m = re.match(r"(?:about\s+)?(?:an?\s+|(\d+)\s*)(minute|hour|day)s?\s+ago", t)
    if m:
        n = int(m.group(1) or 1)
        return ref - timedelta(**{m.group(2) + "s": n})
    m = re.search(r"([a-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", t)
    if m and m.group(1)[:3] in _MONTHS:
        d = datetime(int(m.group(3)), _MONTHS[m.group(1)[:3]], int(m.group(2)))
        return datetime.combine(d.date(), clock(), tzinfo=ET)
    return None


def parse_posts(html, page_fetched_at_et):
    """Parse a thread page into [{"member", "posted_at" (iso ET), "text"}].
    Quoted-reply blocks and signatures are excluded from text, so quoted
    predictions are never attributed to the replier."""
    parser = _ThreadHTMLParser(page_fetched_at_et)
    parser.feed(html)
    parser.close()
    return parser.posts


# ------------------------------------------------------------------ picks

# standalone 3-digit group: not part of a longer digit run, and not a segment
# of a comma/period-grouped number ("25,503", "0.123", "123.45")
_PICK_RE = re.compile(r"(?<!\d)(?<!\d[.,])\d{3}(?!\d)(?![.,]\d)")


def extract_picks(text):
    """All standalone 3-digit combos in a post, as [a, b, c] int lists.
    Deduped preserving order, capped at MAX_PICKS_PER_POST. 4-digit groups
    (years, Win-4 picks) never match."""
    out, seen = [], set()
    for m in _PICK_RE.finditer(text or ""):
        combo = tuple(int(c) for c in m.group(0))
        if combo in seen:
            continue
        seen.add(combo)
        out.append(list(combo))
        if len(out) >= MAX_PICKS_PER_POST:
            break
    return out


# Community pair-call notation: "80x" = front pair, "x01" = back pair,
# "8x1" = split pair (1st & 3rd digits). Case-insensitive on the x.
_PAIR_FRONT_RE = re.compile(r"(?<![\dxX])(\d{2})[xX](?![\dxX])")
_PAIR_BACK_RE = re.compile(r"(?<![\dxX])[xX](\d{2})(?![\dxX])")
_PAIR_SPLIT_RE = re.compile(r"(?<![\dxX])(\d)[xX](\d)(?![\dxX])")
MAX_PAIRS_PER_POST = 20


def extract_pair_hints(text):
    """Pair calls in a post, as {"kind": front|back|split, "digits": [a, b]}."""
    out, seen = [], set()
    for kind, rx in (("front", _PAIR_FRONT_RE), ("back", _PAIR_BACK_RE),
                     ("split", _PAIR_SPLIT_RE)):
        for m in rx.finditer(text or ""):
            digits = tuple(int(c) for c in "".join(m.groups()))
            key = (kind, digits)
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": kind, "digits": list(digits)})
            if len(out) >= MAX_PAIRS_PER_POST:
                return out
    return out


# ------------------------------------------------------------------ attribution


def draws_for_post(posted_at, window_hours=ATTRIBUTION_WINDOW_HOURS):
    """Draw ids strictly after posted_at and within window_hours of it."""
    posted_at = posted_at.astimezone(ET)
    limit = posted_at + timedelta(hours=window_hours)
    d, p = timeutil.latest_expected_draw(posted_at)  # last draw <= posted_at
    out = []
    while True:
        d, p = timeutil.draw_after(d, p)
        dt = timeutil.draw_datetime(d, p)
        if dt > limit:
            break
        if dt > posted_at:
            out.append(timeutil.draw_id(d, p))
    return out


def attribute_posts(posts):
    """[(draw_id, {"member", "combo", "posted_at"}), ...] for parsed posts."""
    entries = []
    for post in posts:
        combos = extract_picks(post["text"])
        if not combos:
            continue
        posted_at = datetime.fromisoformat(post["posted_at"])
        for did in draws_for_post(posted_at):
            for combo in combos:
                entries.append(
                    (did, {"member": post["member"], "combo": combo, "posted_at": post["posted_at"]})
                )
    return entries


def attribute_pair_hints(posts):
    """[(draw_id, {"member", "kind", "digits", "posted_at"}), ...] for pair calls."""
    entries = []
    for post in posts:
        hints = extract_pair_hints(post["text"])
        if not hints:
            continue
        posted_at = datetime.fromisoformat(post["posted_at"])
        for did in draws_for_post(posted_at):
            for h in hints:
                entries.append(
                    (did, {"member": post["member"], "kind": h["kind"],
                           "digits": h["digits"], "posted_at": post["posted_at"]})
                )
    return entries


def _entry_key(entry):
    if "combo" in entry:
        return (entry["member"], tuple(entry["combo"]))
    return (entry["member"], entry["kind"], tuple(entry["digits"]))


def merge_picks(picks, entries):
    """Merge new entries into the by-draw dict, deduping per draw_id on
    (member, combo) for picks or (member, kind, digits) for pair hints.
    Existing entries always win."""
    keysets = {did: {_entry_key(e) for e in lst} for did, lst in picks.items()}
    for did, entry in entries:
        keys = keysets.setdefault(did, set())
        key = _entry_key(entry)
        if key in keys:
            continue
        keys.add(key)
        picks.setdefault(did, []).append(entry)
    return picks


def prune_picks(picks, now_et, max_age_days=PRUNE_AFTER_DAYS):
    """Drop draw_ids whose date is more than max_age_days old."""
    today = now_et.astimezone(ET).date()
    out = {}
    for did, lst in picks.items():
        try:
            d, _ = timeutil.parse_draw_id(did)
        except Exception:
            continue
        if (today - d).days <= max_age_days:
            out[did] = lst
    return out


# ------------------------------------------------------------------ update


def _to_et(now_utc):
    if now_utc is None:
        return datetime.now(ET)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(ET)


def update(now_utc=None, backfill_pages=0):
    """Main entrypoint: discover thread, fetch new pages, merge picks into
    site/data/community.json. FAIL-SOFT: never raises, returns False on any
    error."""
    try:
        return _update(now_utc, backfill_pages)
    except Exception as e:  # noqa: BLE001 — fail-soft by design
        print(f"WARN lp_reader.update failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def _update(now_utc, backfill_pages):
    now_et = _to_et(now_utc)
    thread = discover_thread(now_et)
    state = store.load_json(STATE_FILE, None) or {}
    last_known = max(1, int(state.get("page_count") or 1))

    # best guess at the last page; its pager tells us the real total
    pages_html = {}
    html = firecrawl_scrape(_page_url(thread["url"], last_known), "html")
    current, total = _page_info(html)
    pages_html[current] = html

    if backfill_pages > 0:
        wanted = list(range(max(1, total - backfill_pages + 1), total + 1))
    else:
        wanted = [total]
        if total > last_known and total > 1:  # a new page appeared: catch the tail
            wanted = [total - 1, total]

    posts = []
    for page in wanted:
        page_html = pages_html.get(page)
        if page_html is None:
            page_html = firecrawl_scrape(_page_url(thread["url"], page), "html")
            pages_html[page] = page_html
        posts.extend(parse_posts(page_html, now_et))

    entries = attribute_posts(posts)
    pair_entries = attribute_pair_hints(posts)

    doc = store.load_json(store.COMMUNITY, None) or {}
    picks = doc.get("picks") or {}
    pair_hints = doc.get("pair_hints") or {}
    merge_picks(picks, entries)
    merge_picks(pair_hints, pair_entries)
    picks = prune_picks(picks, now_et)
    pair_hints = prune_picks(pair_hints, now_et)

    out = {
        "updated_at": now_et.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "thread": thread,
        "picks": {did: picks[did] for did in sorted(picks, key=timeutil.sort_key)},
        "pair_hints": {did: pair_hints[did]
                       for did in sorted(pair_hints, key=timeutil.sort_key)},
    }
    store.save_json(store.COMMUNITY, out)

    state["thread"] = thread
    state["checked_at"] = now_et.isoformat(timespec="seconds")
    state["page_count"] = total
    store.save_json(STATE_FILE, state)
    return True


# ------------------------------------------------------------------ CLI


def main():
    if "--update" not in sys.argv:
        print(json.dumps({"error": "Usage: python3 -m community.lp_reader --update [--backfill N]"}))
        sys.exit(1)
    backfill = 0
    if "--backfill" in sys.argv:
        try:
            backfill = int(sys.argv[sys.argv.index("--backfill") + 1])
        except (IndexError, ValueError):
            print(json.dumps({"error": "--backfill requires an integer"}))
            sys.exit(1)
    ok = update(backfill_pages=backfill)
    print(json.dumps({"success": ok}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
