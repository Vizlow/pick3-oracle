"""LotteryPost community-picks reader. The fixture is a real rendered capture
of thread 360017 ("New York: 7/1 - 7/31/2026") page 5, fetched 2026-07-17.
No network: firecrawl is monkeypatched in the update() test."""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from community import lp_reader
from engine import store

ET = ZoneInfo("America/New_York")
FIXTURE = Path(__file__).parent / "fixtures" / "lp_page5.html"
FETCHED_AT = datetime(2026, 7, 17, 1, 0, tzinfo=ET)  # when the capture was made


def _posts():
    return lp_reader.parse_posts(FIXTURE.read_text(), FETCHED_AT)


# ------------------------------------------------------------------ parse_posts


def test_parse_posts_finds_all_members():
    posts = _posts()
    assert len(posts) == 15
    members = {p["member"] for p in posts}
    assert members == {
        "NY216", "Gameover44", "CASH34OLOGIST", "Andrew1209",
        "Soledad", "sully16", "Ranett", "JonnyB5775",
    }


def test_parse_posts_timestamps_are_plausible_et():
    posts = _posts()
    stamps = [datetime.fromisoformat(p["posted_at"]) for p in posts]
    for dt in stamps:
        assert dt.tzinfo is not None
        assert dt.utcoffset() == dt.astimezone(ET).utcoffset()
        assert datetime(2026, 7, 13, tzinfo=ET) <= dt <= FETCHED_AT
    # thread pages are chronological
    assert stamps == sorted(stamps)
    # first post: Jul 13, 2026, 10:36 pm ET
    assert stamps[0] == datetime(2026, 7, 13, 22, 36, tzinfo=ET)
    # last post: "Yesterday, 8:46 am" relative to the 7/17 fetch -> 7/16
    assert stamps[-1] == datetime(2026, 7, 16, 8, 46, tzinfo=ET)


def test_relative_and_absolute_time_text_fallback():
    # synthetic posts with NO datetime attribute -> text parsing path
    html = """
    <ul class="threadview">
      <li id="i1"><div class="memberinfo"><a href="/member/9" data-member="9"><strong>alpha</strong></a></div>
        <div class="postdetail"><time>Yesterday, 2:32 pm</time></div>
        <div class="postbody"><div class="postbodyinner"><p>123</p></div></div></li>
      <li id="i2"><div class="memberinfo"><a href="/member/8" data-member="8"><strong>beta</strong></a></div>
        <div class="postdetail"><time>Today, 9:07 am</time></div>
        <div class="postbody"><div class="postbodyinner"><p>456</p></div></div></li>
      <li id="i3"><div class="memberinfo"><a href="/member/7" data-member="7"><strong>gamma</strong></a></div>
        <div class="postdetail"><time>Jul 13, 2026</time></div>
        <div class="postbody"><div class="postbodyinner"><p>789</p></div></div></li>
    </ul>"""
    posts = lp_reader.parse_posts(html, FETCHED_AT)
    got = {p["member"]: datetime.fromisoformat(p["posted_at"]) for p in posts}
    assert got["alpha"] == datetime(2026, 7, 16, 14, 32, tzinfo=ET)
    assert got["beta"] == datetime(2026, 7, 17, 9, 7, tzinfo=ET)
    assert got["gamma"] == datetime(2026, 7, 13, 12, 0, tzinfo=ET)  # missing time -> 12:00


def test_quoted_predictions_not_attributed_to_replier():
    posts = _posts()
    # Andrew1209 replied "Congratulations" quoting sully16's list
    # (009 109 ... 909 / 150 ... 159); none of it may leak into his post.
    andrew = [p for p in posts if p["member"] == "Andrew1209"]
    assert len(andrew) == 1
    assert "Congratulations" in andrew[0]["text"]
    assert "009" not in andrew[0]["text"]
    assert lp_reader.extract_picks(andrew[0]["text"]) == []
    # Soledad's 11:18 pm reply quotes her own earlier "or 234" post but only
    # genuinely re-states 809 in the reply body.
    soledad = [p for p in posts if p["member"] == "Soledad"
               and datetime.fromisoformat(p["posted_at"]).hour == 23]
    assert len(soledad) == 1
    picks = lp_reader.extract_picks(soledad[0]["text"])
    assert [8, 0, 9] in picks
    assert [2, 3, 4] not in picks
    # signatures are excluded too
    assert "Wambulance" not in " ".join(p["text"] for p in posts)


# ------------------------------------------------------------------ extract_picks


def test_extract_picks_sully_style_list():
    text = ("Congrats to all winners. Mon./Tue./Wed./Thur.\n"
            "009 109 209 309 409 509 609 709 809 909\n"
            "good luck in 2026, ticket 1098")
    picks = lp_reader.extract_picks(text)
    assert picks == [[0, 0, 9], [1, 0, 9], [2, 0, 9], [3, 0, 9], [4, 0, 9],
                     [5, 0, 9], [6, 0, 9], [7, 0, 9], [8, 0, 9], [9, 0, 9]]
    # 4-digit groups ("2026", "1098") contribute nothing
    flat = ["".join(map(str, c)) for c in picks]
    assert "202" not in flat and "026" not in flat
    assert "109" in flat and flat.count("109") == 1  # from the list, not from 1098


def test_extract_picks_dedup_grouping_and_cap():
    assert lp_reader.extract_picks("111 111 222") == [[1, 1, 1], [2, 2, 2]]
    # thousand separators and decimals are not picks
    assert lp_reader.extract_picks("25,503 posts and 0.123 avg") == []
    # sentence punctuation is fine
    assert lp_reader.extract_picks("617.   117.   177") == [[6, 1, 7], [1, 1, 7], [1, 7, 7]]
    # cap at 40 per post
    many = " ".join(f"{n:03d}" for n in range(50))
    assert len(lp_reader.extract_picks(many)) == 40


# ------------------------------------------------------------------ attribution


def test_attribution_window_48h():
    posted = datetime(2026, 7, 16, 9, 0, tzinfo=ET)
    assert lp_reader.draws_for_post(posted) == [
        "2026-07-16-mid", "2026-07-16-eve", "2026-07-17-mid", "2026-07-17-eve",
    ]


def test_attribution_strictly_after_post():
    # posted exactly at the midday draw time -> that draw is excluded
    posted = datetime(2026, 7, 16, 14, 30, tzinfo=ET)
    draws = lp_reader.draws_for_post(posted)
    assert draws[0] == "2026-07-16-eve"
    assert "2026-07-16-mid" not in draws


def test_merge_dedupes_and_keeps_existing():
    existing = {"2026-07-16-mid": [
        {"member": "alpha", "combo": [1, 2, 3], "posted_at": "2026-07-15T09:00:00-04:00"},
    ]}
    new = [
        ("2026-07-16-mid", {"member": "alpha", "combo": [1, 2, 3], "posted_at": "2026-07-16T08:00:00-04:00"}),
        ("2026-07-16-mid", {"member": "beta", "combo": [1, 2, 3], "posted_at": "2026-07-16T08:00:00-04:00"}),
        ("2026-07-16-mid", {"member": "beta", "combo": [1, 2, 3], "posted_at": "2026-07-16T08:00:00-04:00"}),
        ("2026-07-16-eve", {"member": "alpha", "combo": [1, 2, 3], "posted_at": "2026-07-16T08:00:00-04:00"}),
    ]
    merged = lp_reader.merge_picks(existing, new)
    mid = merged["2026-07-16-mid"]
    assert len(mid) == 2  # alpha deduped (existing kept), beta deduped
    alpha = next(e for e in mid if e["member"] == "alpha")
    assert alpha["posted_at"] == "2026-07-15T09:00:00-04:00"  # existing wins
    assert len(merged["2026-07-16-eve"]) == 1


def test_prune_old_draws():
    now_et = datetime(2026, 7, 17, 1, 0, tzinfo=ET)
    picks = {
        "2026-07-16-mid": [{"member": "a", "combo": [1, 2, 3], "posted_at": "x"}],
        "2026-07-01-eve": [{"member": "a", "combo": [1, 2, 3], "posted_at": "x"}],
    }
    pruned = lp_reader.prune_picks(picks, now_et)
    assert "2026-07-16-mid" in pruned
    assert "2026-07-01-eve" not in pruned  # 16 days old


# ------------------------------------------------------------------ update (no network)

FORUM_MD = ("| [New York: 7/1 - 7/31/2026](https://www.lotterypost.com/thread/360017"
            "/new-york-7-1-7-31-2026) | 85 | 12,345 |")


def test_update_end_to_end(monkeypatch, tmp_path):
    fixture_html = FIXTURE.read_text()

    def fake_scrape(url, fmt):
        if "/forum/" in url:
            assert fmt == "markdown"
            return FORUM_MD
        assert "/thread/360017" in url
        return fixture_html

    monkeypatch.setattr(lp_reader, "firecrawl_scrape", fake_scrape)
    monkeypatch.setattr(lp_reader, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(store, "COMMUNITY", tmp_path / "community.json")

    now_utc = datetime(2026, 7, 17, 5, 0, tzinfo=timezone.utc)  # 1:00 am ET
    assert lp_reader.update(now_utc=now_utc) is True

    doc = json.loads((tmp_path / "community.json").read_text())
    assert doc["thread"] == {"id": 360017, "title": "New York: 7/1 - 7/31/2026",
                             "url": "https://www.lotterypost.com/thread/360017"}
    picks = doc["picks"]
    # Ranett posted "349" on Jul 15, 8:21 am -> attributed to the next 4 draws
    for did in ("2026-07-15-mid", "2026-07-15-eve", "2026-07-16-mid", "2026-07-16-eve"):
        assert {"member": "Ranett", "combo": [3, 4, 9],
                "posted_at": "2026-07-15T08:21:00-04:00"} in picks[did]
    assert not any(
        e["member"] == "Ranett" and e["combo"] == [3, 4, 9]
        for e in picks.get("2026-07-17-mid", [])
    )
    # quoted sully16 list never attributed to Andrew1209
    assert not any(
        e["member"] == "Andrew1209" and e["combo"] == [0, 0, 9]
        for lst in picks.values() for e in lst
    )
    # duplicate page fetches (page 5 and 6 both return the fixture) deduped
    for lst in picks.values():
        keys = [(e["member"], tuple(e["combo"])) for e in lst]
        assert len(keys) == len(set(keys))
    # state remembers pagination for the next incremental run
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["page_count"] == 6
    assert state["thread"]["id"] == 360017

    # second run merges instead of clobbering, keeps existing entries
    assert lp_reader.update(now_utc=now_utc) is True
    doc2 = json.loads((tmp_path / "community.json").read_text())
    assert doc2["picks"] == picks


def test_update_is_fail_soft(monkeypatch, tmp_path, capsys):
    def boom(url, fmt):
        raise RuntimeError("cloudflare says no")

    monkeypatch.setattr(lp_reader, "firecrawl_scrape", boom)
    monkeypatch.setattr(lp_reader, "STATE_FILE", tmp_path / "state.json")
    assert lp_reader.update(now_utc=datetime(2026, 7, 17, 5, 0, tzinfo=timezone.utc)) is False
    assert "WARN" in capsys.readouterr().err


# ------------------------------------------------------------- pair hints
def test_extract_pair_hints_soledad_style():
    from community.lp_reader import extract_pair_hints
    text = "paper trails for a few games or days\n43x x33 or 4x3\n80x x01 or 8x1\nor 21x"
    hints = extract_pair_hints(text)
    got = {(h["kind"], tuple(h["digits"])) for h in hints}
    assert ("front", (4, 3)) in got and ("front", (8, 0)) in got and ("front", (2, 1)) in got
    assert ("back", (3, 3)) in got and ("back", (0, 1)) in got
    assert ("split", (4, 3)) in got and ("split", (8, 1)) in got


def test_pair_hints_ignore_plain_numbers_and_years():
    from community.lp_reader import extract_pair_hints
    assert extract_pair_hints("617 117 177 good luck until 2026") == []


def test_community_tactic_scores_pair_calls():
    from datetime import date
    from engine.tactics import Ctx
    from engine.tactics.community import community
    picks = [
        {"member": "Soledad", "pair": {"kind": "front", "digits": [8, 0]}},
        {"member": "Andrew1209", "combo": [2, 1, 6]},
    ]
    ctx = Ctx([(1, 2, 3)] * 10, date(2026, 7, 17), "mid", community=picks)
    scores = community(ctx)
    from engine import lmath
    assert scores[lmath.idx((8, 0, 9))] > 0      # 80x covers 809
    assert scores[lmath.idx((8, 0, 0))] > 0      # ...and 800
    assert scores[lmath.idx((0, 8, 9))] == 0.0   # front pair is positional
    assert scores[lmath.idx((2, 1, 6))] > scores[lmath.idx((8, 0, 9))]  # full pick > pair


# ------------------------------------------------------------- member skill
def test_member_skills_shrinkage_and_no_lookahead():
    from engine import skill, timeutil
    doc = {"picks": {
        "2026-07-10-mid": [{"member": "hot", "combo": [1, 2, 3]},
                           {"member": "cold", "combo": [7, 8, 9]}],
        "2026-07-11-mid": [{"member": "hot", "combo": [4, 5, 6]}],
    }, "pair_hints": {}}
    results = {"2026-07-10-mid": (3, 2, 1), "2026-07-11-mid": (0, 0, 0)}
    skills = skill.member_skills(doc, results)
    # hot boxed a hit ($40 on $1 staked) -> above 1.0 but shrunk well below cap
    assert 1.0 < skills["hot"] < 3.0
    assert skills["cold"] < 1.0 or skills["cold"] == 0.5 or skills["cold"] < skills["hot"]
    # unknown member -> absent (callers default to 1.0)
    assert "nobody" not in skills
    # before_key excludes the hit draw -> hot loses the credit
    key = timeutil.sort_key("2026-07-10-mid")
    skills_before = skill.member_skills(doc, results, before_key=key)
    assert "hot" not in skills_before or skills_before["hot"] <= 1.0


# ------------------------------------------------------------- list lifetimes
def test_valid_until_day_sequence_sully_style():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from community.lp_reader import valid_until, draws_for_post
    ET = ZoneInfo("America/New_York")
    text = ("Thank you Andrew1209, congrats NY216, Soledad and all winners.\n"
            "Fri./Sat./Sun./Mon.\n270 271 272\n007 107 207\ngood luck")
    posted = datetime(2026, 7, 17, 3, 7, tzinfo=ET)  # a Friday
    until = valid_until(text, posted)
    assert until is not None and until.date().isoformat() == "2026-07-20"  # Monday
    dids = draws_for_post(posted, until=until)
    assert "2026-07-19-eve" in dids and "2026-07-20-eve" in dids
    assert "2026-07-21-mid" not in dids


def test_valid_until_till_sunday_and_default():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from community.lp_reader import valid_until, draws_for_post
    ET = ZoneInfo("America/New_York")
    posted = datetime(2026, 7, 15, 19, 10, tzinfo=ET)  # Wednesday evening
    until = valid_until("I like till sunday.\n617. 117. 177\nGood luck", posted)
    assert until is not None and until.date().isoformat() == "2026-07-19"
    # no declaration -> default 48h window unchanged
    assert valid_until("617 117 177 good luck", posted) is None
    dids = draws_for_post(posted)
    assert dids[0] == "2026-07-15-eve" and len(dids) == 4
