"""Table-driven grading tests — every expected dollar below is read straight off
the official NY Numbers payout table (dollars per $1 stake; $0.50 pays half):

    Straight                      $500   ($0.50 -> $250)
    Box 6-way                      $80   ($0.50 -> $40)
    Box 3-way                     $160   ($0.50 -> $80)
    Straight/Box 6-way            $290 exact / $40 any other order (per $1)
    Straight/Box 3-way            $330 exact / $80 any other order (per $1)
    Front or Back Pair             $50 (per $1)
    Triple (no box sold in NY)    box legs grade straight: $0.50 -> $250, $1 -> $500

Structures (each stakes exactly $2.50; all four = $10.00/draw):
    all_straight  50c straight on each of 5 picks
    all_box       50c box on each of 5 picks (triple pick -> 50c straight)
    sb_top        $1 straight/box on top pick + 50c box on picks 2-4 (pick 5 unplayed)
    pairs_mix     $1 front pair + $1 back pair + 50c straight on top pick
"""
import hashlib
import json

from engine import grade, lmath


def test_payout_constants_match_official_table():
    assert grade.STRAIGHT_1 == 500
    assert grade.BOX6_1 == 80 and grade.BOX3_1 == 160
    assert (grade.SB6_EXACT_1, grade.SB6_OTHER_1) == (290, 40)
    assert (grade.SB3_EXACT_1, grade.SB3_OTHER_1) == (330, 80)
    assert grade.FRONT_PAIR_1 == 50 and grade.BACK_PAIR_1 == 50


# (name, picks[5] (top = picks[0]), pairs, result, expected won per structure)
CASES = [
    ("clean_miss",
     [(0, 0, 1), (0, 0, 2), (0, 0, 3), (0, 0, 4), (0, 1, 1)],
     {"front": (0, 0), "back": (0, 1)}, (5, 6, 7),
     {"all_straight": 0.0, "all_box": 0.0, "sb_top": 0.0, "pairs_mix": 0.0}),

    # top pick exact 6-way: straight 250 (50c), box-incl-exact 40 (50c),
    # SB exact 290 ($1), pairs_mix = front 50 + back 50 + straight 250.
    ("straight_on_top_6way",
     [(1, 2, 3), (4, 5, 6), (7, 8, 9), (0, 1, 2), (3, 4, 5)],
     {"front": (1, 2), "back": (2, 3)}, (1, 2, 3),
     {"all_straight": 250.0, "all_box": 40.0, "sb_top": 290.0, "pairs_mix": 350.0}),

    # 6-way pick (1,2,3) vs (3,1,2): box-only. all_box 40 (50c 6-way); the same
    # pick sits in sb_top's 50c box legs -> 40; predicted front (3,1) hits -> 50.
    ("box_6way_off_top",
     [(9, 9, 8), (1, 2, 3), (4, 5, 6), (7, 8, 0), (2, 2, 2)],
     {"front": (3, 1), "back": (9, 9)}, (3, 1, 2),
     {"all_straight": 0.0, "all_box": 40.0, "sb_top": 40.0, "pairs_mix": 50.0}),

    # 3-way pick (1,1,2) vs (2,1,1): 50c box 3-way -> 80; $1 SB 3-way any-other-order -> 80.
    ("box_3way_top",
     [(1, 1, 2), (0, 3, 5), (6, 7, 8), (9, 0, 1), (2, 4, 6)],
     {"front": (0, 0), "back": (0, 0)}, (2, 1, 1),
     {"all_straight": 0.0, "all_box": 80.0, "sb_top": 80.0, "pairs_mix": 0.0}),

    # 3-way top exact: straight 250; 50c box 3-way (exact counts) 80; $1 SB exact 330;
    # pairs_mix = 50 + 50 + 250.
    ("sb_exact_3way",
     [(1, 1, 2), (3, 4, 5), (6, 7, 8), (9, 0, 2), (5, 5, 5)],
     {"front": (1, 1), "back": (1, 2)}, (1, 1, 2),
     {"all_straight": 250.0, "all_box": 80.0, "sb_top": 330.0, "pairs_mix": 350.0}),

    # triple top exact: NY sells no triple box -> all_box 50c leg grades straight (250),
    # sb_top $1 grades straight (500); pairs_mix = 50 + 50 + 250.
    ("triple_exact",
     [(7, 7, 7), (1, 2, 3), (4, 5, 6), (8, 9, 0), (2, 3, 4)],
     {"front": (7, 7), "back": (7, 7)}, (7, 7, 7),
     {"all_straight": 250.0, "all_box": 250.0, "sb_top": 500.0, "pairs_mix": 350.0}),
]


def test_pnl_structures_table():
    for name, picks, pairs, result, expected in CASES:
        pnl = grade.pnl_structures(picks, picks[0], pairs, result)
        for structure, won in expected.items():
            assert pnl[structure]["won"] == won, f"{name}/{structure}"


def test_stakes_always_2_50_totalling_10():
    for name, picks, pairs, result, _ in CASES:
        pnl = grade.pnl_structures(picks, picks[0], pairs, result)
        assert set(pnl) == {"all_straight", "all_box", "sb_top", "pairs_mix"}, name
        for structure in pnl.values():
            assert structure["stake"] == 2.5, name
        assert sum(s["stake"] for s in pnl.values()) == 10.0, name


def test_match_straight_box_types():
    m = grade.match((1, 2, 3), (1, 2, 3))
    assert m["straight"] and m["box"] and m["box_type"] == "6-way"
    assert not m["one_off"]  # exact excluded from 1-off
    assert m["front_pair"] and m["split_pair"] and m["back_pair"]
    m = grade.match((1, 2, 3), (3, 1, 2))
    assert not m["straight"] and m["box"] and m["box_type"] == "6-way"
    assert not m["one_off"]  # deltas (2,9,9) — not a 1-off
    m = grade.match((1, 1, 2), (2, 1, 1))
    assert m["box"] and m["box_type"] == "3-way"
    m = grade.match((7, 7, 7), (7, 7, 7))
    assert m["box_type"] == "triple"
    m = grade.match((1, 2, 3), (5, 6, 7))
    assert m["box_type"] is None and not any(
        m[k] for k in ("straight", "box", "one_off", "front_pair", "split_pair", "back_pair"))


def test_match_one_off_with_wrap():
    # deltas (-1, 0, +1) -> one_off
    assert grade.match((1, 2, 3), (0, 2, 4))["one_off"] is True
    # 9<->0 wrap: every digit one below 0 is 9
    assert grade.match((0, 0, 0), (9, 9, 9))["one_off"] is True
    assert grade.match((1, 2, 3), (1, 2, 3))["one_off"] is False  # exact excluded
    assert grade.match((1, 2, 3), (1, 2, 5))["one_off"] is False  # 2 away
    # cross-check against the canonical cloud definition
    for pick in [(1, 2, 3), (0, 0, 0), (9, 5, 0)]:
        for result in lmath.one_off_cloud(pick):
            assert grade.match(pick, result)["one_off"] == (result != pick)


def test_match_pairs_positional():
    m = grade.match((3, 1, 9), (3, 1, 2))
    assert m["front_pair"] and not m["split_pair"] and not m["back_pair"]
    m = grade.match((3, 5, 2), (3, 1, 2))
    assert m["split_pair"] and not m["front_pair"] and not m["back_pair"]
    m = grade.match((0, 1, 2), (3, 1, 2))
    assert m["back_pair"] and not m["front_pair"] and not m["split_pair"]


def test_grade_prediction_block():
    picks = [(3, 1, 9), (0, 1, 2), (3, 5, 2), (1, 2, 3), (3, 1, 2)]
    pairs = {"front": (3, 1), "back": (1, 2)}
    result = (3, 1, 2)
    g = grade.grade_prediction(picks, picks[0], pairs, result)
    assert g["straight_hit"] is True  # picks[4] exact
    assert g["box_hit"] == {"pick_index": 3, "type": "6-way"}  # first box match
    assert g["top_pick"] == {"straight": False, "box": False, "one_off": False}
    # split is graded from the TOP PICK's digits 1 & 3: (3,_,9) vs (3,_,2) -> miss
    assert g["pair_hits"] == {"front": True, "split": False, "back": True}
    # fronts (3,1): picks 0,4; splits 3_2: picks 2,4; backs (1,2): picks 1,4
    assert g["any_pick_pairs"] == {"front": 2, "split": 2, "back": 2}


def test_grade_prediction_no_box_hit():
    picks = [(0, 0, 1), (0, 0, 2), (0, 0, 3), (0, 0, 4), (0, 1, 1)]
    g = grade.grade_prediction(picks, picks[0], {"front": (0, 0), "back": (0, 1)}, (5, 6, 7))
    assert g["straight_hit"] is False
    assert g["box_hit"] == {"pick_index": None, "type": None}
    assert g["any_pick_pairs"] == {"front": 0, "split": 0, "back": 0}


def test_random_picks_deterministic():
    did = "2026-07-16-eve"
    a, b = grade.random_picks(did), grade.random_picks(did)
    assert a == b and len(a) == 5
    assert all(c in lmath.ALL_1000 for c in a)
    assert grade.random_picks(did, n=3) == a[:3]  # same stream, shorter
    assert grade.random_picks("2026-07-16-mid") != a
    p1, p2 = grade.random_pairs(did), grade.random_pairs(did)
    assert p1 == p2 and set(p1) == {"front", "back"}
    assert all(0 <= d <= 9 for pair in p1.values() for d in pair)


def test_baseline_block():
    did, result = "2026-07-16-eve", (1, 2, 3)
    b = grade.baseline_block(did, result)
    assert b["seed"] == hashlib.sha256(did.encode()).hexdigest()[:16]
    assert b["random_picks"] == [list(c) for c in grade.random_picks(did)]
    assert set(b["grade"]) == {"straight_hit", "box_hit"}
    assert set(b["pnl"]) == {"all_straight", "all_box", "sb_top", "pairs_mix"}
    for s in b["pnl"].values():
        assert s["stake"] == 2.5
    # control is fully reproducible: same pnl as re-grading its own picks/pairs
    picks = grade.random_picks(did)
    repnl = grade.pnl_structures(picks, picks[0], grade.random_pairs(did), result)
    assert b["pnl"] == repnl
    assert grade.baseline_block(did, result) == b


def test_ledger_entry():
    pred = {
        "draw_id": "2026-07-16-eve",
        "picks": [[1, 2, 3], [4, 5, 6], [7, 8, 9], [0, 1, 2], [3, 4, 5]],
        "top_pick": [1, 2, 3],
        "pairs": {"front": [1, 2], "back": [2, 3]},
    }
    lock = {"locked_at": "2026-07-16T13:00:00-04:00", "hours_before": 9.5}
    row = grade.ledger_entry(pred, (1, 2, 3), lock, mode="live")
    assert row["draw_id"] == "2026-07-16-eve" and row["mode"] == "live"
    assert row["lock"] is lock and row["prediction"] is pred
    assert row["result"] == [1, 2, 3]
    assert row["corrected"] is False
    # grading works off JSON-shaped (list) inputs
    assert row["grade"]["straight_hit"] is True
    assert row["grade"]["pair_hits"] == {"front": True, "split": True, "back": True}
    assert row["pnl"]["all_straight"]["won"] == 250.0
    assert row["pnl"]["sb_top"]["won"] == 290.0
    assert row["baseline"]["seed"] == hashlib.sha256(b"2026-07-16-eve").hexdigest()[:16]
    json.dumps(row)  # whole row must be JSON-serializable
    backtest_row = grade.ledger_entry(pred, (9, 9, 9), lock, mode="backtest")
    assert backtest_row["mode"] == "backtest"
    assert backtest_row["grade"]["straight_hit"] is False
