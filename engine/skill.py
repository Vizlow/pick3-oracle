"""Per-member skill scores for the community tactic.

A member's skill is their return-per-dollar on graded plays, Bayesian-shrunk
toward chance so small samples stay near neutral: with PRIOR_STAKE dollars of
imaginary chance-level history mixed in, a hot streak must be sustained before
it earns real influence. Multiplier = shrunk_return / CHANCE_RETURN, clamped.

  1.0  = plays like chance (or unproven)
  >1.0 = track record beats chance -> picks count more
  <1.0 = sustained underperformance -> picks count less

No-look-ahead: pass before_key (a timeutil.sort_key) so a target draw's own
result never feeds the skills used to predict or grade it.
"""
from engine import timeutil

CHANCE_RETURN = 0.48   # EV per $1 of a box play (pair plays are ~0.50; close enough)
PRIOR_STAKE = 100.0    # dollars of imaginary chance-level history (200 plays)
CLAMP = (0.5, 3.0)

BOX_PAY = {1: 250.0, 2: 80.0, 3: 40.0}  # $0.50 box by distinct-digit count


def grade_entry(entry, result):
    """(stake, won) for one community entry — $0.50 box for combos,
    $0.50 front/back pair for pair calls (split pairs aren't sold)."""
    if "combo" in entry:
        pick = tuple(entry["combo"])
        won = 0.0
        if sorted(pick) == sorted(result):
            won = BOX_PAY[len(set(pick))]
        return 0.5, won
    kind = entry.get("kind")
    if kind not in ("front", "back"):
        return 0.0, 0.0
    dg = tuple(entry["digits"])
    hit = (result[0], result[1]) == dg if kind == "front" else (result[1], result[2]) == dg
    return 0.5, 25.0 if hit else 0.0


def member_skills(community_doc, results_by_id, before_key=None):
    """{member: multiplier} from all graded entries strictly before before_key."""
    totals = {}
    for section in ("picks", "pair_hints"):
        for did, entries in (community_doc.get(section) or {}).items():
            if before_key is not None and timeutil.sort_key(did) >= before_key:
                continue
            result = results_by_id.get(did)
            if not result:
                continue
            for e in entries:
                stake, won = grade_entry(e, result)
                if stake == 0.0:
                    continue
                t = totals.setdefault(e["member"], [0.0, 0.0])
                t[0] += stake
                t[1] += won
    skills = {}
    for member, (stake, won) in totals.items():
        shrunk = (won + CHANCE_RETURN * PRIOR_STAKE) / (stake + PRIOR_STAKE)
        skills[member] = round(min(max(shrunk / CHANCE_RETURN, CLAMP[0]), CLAMP[1]), 3)
    return skills
