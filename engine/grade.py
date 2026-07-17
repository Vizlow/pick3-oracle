"""Grading + P&L honesty core: official NY Numbers payouts, prediction grading,
the four fixed $2.50 play structures, and the seeded-random control line.

Payout constants are dollars won per $1 stake ($0.50 plays pay half):

    Straight                      $500
    Box 6-way                      $80
    Box 3-way                     $160
    Straight/Box 6-way            $290 exact / $40 any other order
    Straight/Box 3-way            $330 exact / $80 any other order
    Front or Back Pair             $50

NY sells no triple box — any "box" leg on a triple pick is graded as a
straight at the same stake ($0.50 -> $250, $1.00 -> $500).
"""
import hashlib
import random

from engine import lmath

STRAIGHT_1 = 500
BOX6_1 = 80
BOX3_1 = 160
SB6_EXACT_1, SB6_OTHER_1 = 290, 40
SB3_EXACT_1, SB3_OTHER_1 = 330, 80
FRONT_PAIR_1 = BACK_PAIR_1 = 50
HALF = 0.5

WAY_TYPE = {"single": "6-way", "double": "3-way", "triple": "triple"}


def match(pick, result):
    """Full match report of one pick against the drawn result.

    box is any-order INCLUDING exact; box_type is the PICK's way type (None when
    no box match); one_off is the 26-member 1-off cloud with 9<->0 wrap, exact
    excluded; pairs are positional.
    """
    pick, result = tuple(pick), tuple(result)
    straight = pick == result
    box = lmath.box_key(pick) == lmath.box_key(result)
    return {
        "straight": straight,
        "box": box,
        "box_type": WAY_TYPE[lmath.classify(pick)] if box else None,
        "one_off": (result in lmath.one_off_cloud(pick)) and not straight,
        "front_pair": pick[0:2] == result[0:2],
        "split_pair": pick[0] == result[0] and pick[2] == result[2],
        "back_pair": pick[1:3] == result[1:3],
    }


def _pair(pairs, kind):
    p = (pairs or {}).get(kind)
    return tuple(p) if p is not None else None


def _straight_won(pick, result, stake):
    return stake * STRAIGHT_1 if tuple(pick) == tuple(result) else 0.0


def _box_won(pick, result, stake):
    """Box leg at `stake`. NY sells no triple box: a triple pick grades as straight."""
    pick, result = tuple(pick), tuple(result)
    kind = lmath.classify(pick)
    if kind == "triple":
        return _straight_won(pick, result, stake)
    if lmath.box_key(pick) != lmath.box_key(result):
        return 0.0
    return stake * (BOX3_1 if kind == "double" else BOX6_1)


def _sb_won(pick, result, stake):
    """Straight/Box leg at total `stake` (a $1 SB = 50c straight + 50c box).
    Pays by the PICK's way type: 6-way 290/40, 3-way 330/80 per $1;
    triple -> graded as a $1 straight (500 exact)."""
    pick, result = tuple(pick), tuple(result)
    kind = lmath.classify(pick)
    if kind == "triple":
        return _straight_won(pick, result, stake)
    if pick == result:
        return stake * (SB3_EXACT_1 if kind == "double" else SB6_EXACT_1)
    if lmath.box_key(pick) == lmath.box_key(result):
        return stake * (SB3_OTHER_1 if kind == "double" else SB6_OTHER_1)
    return 0.0


def _box_hit(matches):
    i = next((i for i, m in enumerate(matches) if m["box"]), None)
    return {"pick_index": i, "type": matches[i]["box_type"] if i is not None else None}


def grade_prediction(picks, top_pick, pairs, result):
    """The ledger 'grade' block. `pairs` carries the predicted front/back pairs;
    no split pair is predicted, so pair_hits['split'] is graded from the TOP
    PICK's digits 1 & 3 against the result's digits 1 & 3."""
    picks = [tuple(p) for p in picks]
    top_pick, result = tuple(top_pick), tuple(result)
    matches = [match(p, result) for p in picks]
    tm = match(top_pick, result)
    return {
        "straight_hit": any(m["straight"] for m in matches),
        "box_hit": _box_hit(matches),
        "top_pick": {"straight": tm["straight"], "box": tm["box"], "one_off": tm["one_off"]},
        "pair_hits": {
            "front": _pair(pairs, "front") == result[0:2],
            "split": tm["split_pair"],
            "back": _pair(pairs, "back") == result[1:3],
        },
        "any_pick_pairs": {
            "front": sum(1 for m in matches if m["front_pair"]),
            "split": sum(1 for m in matches if m["split_pair"]),
            "back": sum(1 for m in matches if m["back_pair"]),
        },
    }


def pnl_structures(picks, top_pick, pairs, result):
    """The four fixed play structures, each staking exactly $2.50 with 5 picks
    ($10.00/draw total): all_straight (50c straight x5), all_box (50c box x5,
    triples grade straight), sb_top ($1 SB on top pick + 50c box on picks 2-4;
    pick 5 unplayed by design), pairs_mix ($1 front + $1 back + 50c straight top).
    """
    picks = [tuple(p) for p in picks]
    top_pick, result = tuple(top_pick), tuple(result)
    front, back = _pair(pairs, "front"), _pair(pairs, "back")
    box_legs = picks[1:4]
    return {
        "all_straight": {
            "stake": round(HALF * len(picks), 2),
            "won": float(sum(_straight_won(p, result, HALF) for p in picks)),
        },
        "all_box": {
            "stake": round(HALF * len(picks), 2),
            "won": float(sum(_box_won(p, result, HALF) for p in picks)),
        },
        "sb_top": {
            "stake": round(1.0 + HALF * len(box_legs), 2),
            "won": float(_sb_won(top_pick, result, 1.0)
                         + sum(_box_won(p, result, HALF) for p in box_legs)),
        },
        "pairs_mix": {
            "stake": 2.5,
            "won": float((FRONT_PAIR_1 if front == result[0:2] else 0.0)
                         + (BACK_PAIR_1 if back == result[1:3] else 0.0)
                         + _straight_won(top_pick, result, HALF)),
        },
    }


def _rng(draw_id, salt=""):
    return random.Random(int(hashlib.sha256((draw_id + salt).encode()).hexdigest(), 16))


def random_picks(draw_id, n=5):
    """Deterministic control picks: sha256(draw_id)-seeded uniform draws over 0..999."""
    rng = _rng(draw_id)
    return [lmath.from_idx(rng.randrange(1000)) for _ in range(n)]


def random_pairs(draw_id):
    """Deterministic control pairs; seed is salted so they don't echo random_picks."""
    rng = _rng(draw_id, "|pairs")
    return {"front": (rng.randrange(10), rng.randrange(10)),
            "back": (rng.randrange(10), rng.randrange(10))}


def baseline_block(draw_id, result):
    """Seeded-random control line: same four structures, same $10 stake, random
    picks/pairs (top pick = first random pick) — every structure gets a true control."""
    result = tuple(result)
    picks = random_picks(draw_id)
    pairs = random_pairs(draw_id)
    matches = [match(p, result) for p in picks]
    return {
        "seed": hashlib.sha256(draw_id.encode()).hexdigest()[:16],
        "random_picks": [list(p) for p in picks],
        "random_pairs": {k: list(v) for k, v in pairs.items()},
        "grade": {
            "straight_hit": any(m["straight"] for m in matches),
            "box_hit": _box_hit(matches),
        },
        "pnl": pnl_structures(picks, picks[0], pairs, result),
    }


def ledger_entry(prediction, result, lock, mode="live"):
    """Full ledger row: the locked prediction embedded verbatim, its grade, the
    four-structure P&L, and the seeded-random baseline. `prediction` must carry
    draw_id, picks, top_pick, pairs; `lock` is the pre-draw lock metadata."""
    result = tuple(result)
    picks = [tuple(p) for p in prediction["picks"]]
    top_pick = tuple(prediction["top_pick"])
    pairs = prediction["pairs"]
    return {
        "draw_id": prediction["draw_id"],
        "mode": mode,
        "lock": lock,
        "result": list(result),
        "prediction": prediction,
        "grade": grade_prediction(picks, top_pick, pairs, result),
        "pnl": pnl_structures(picks, top_pick, pairs, result),
        "baseline": baseline_block(prediction["draw_id"], result),
        "corrected": False,
    }
