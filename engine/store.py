"""Filesystem layout, atomic JSON I/O, history merge rules, and the git lock proof.

Two stores: the full history file (data/history/draws_full.json, every draw ever)
and the site/data/*.json files the static dashboard reads. All writes are atomic
(tmp file + os.replace) so a crashed run never leaves a torn JSON behind.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from engine import timeutil

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "data"
HISTORY_FILE = ROOT / "data" / "history" / "draws_full.json"
BACKTEST_LEDGER = ROOT / "data" / "history" / "backtest_ledger.json"

DRAWS = SITE_DATA / "draws.json"
PREDICTION = SITE_DATA / "prediction.json"
LEDGER = SITE_DATA / "ledger.json"
WEIGHTS = SITE_DATA / "weights.json"
STATS = SITE_DATA / "stats.json"
COMMUNITY = SITE_DATA / "community.json"


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    """Atomic write: dump to <name>.tmp alongside the target, then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def _sorted_dedup(draws):
    """Dedupe by id (last one in wins) and sort chronologically."""
    by_id = {dr["id"]: dr for dr in draws}
    return sorted(by_id.values(), key=lambda dr: timeutil.sort_key(dr["id"]))


def load_history():
    """Full draw history, oldest first. [] if the file doesn't exist yet."""
    doc = load_json(HISTORY_FILE, {}) or {}
    return doc.get("draws", [])


def save_history(draws):
    ordered = _sorted_dedup(draws)
    save_json(HISTORY_FILE, {"updated_at": _utc_now_iso(), "draws": ordered})
    return ordered


def upsert_draws(existing_list, new_list):
    """Merge new draws into existing. The first-recorded draw wins on conflict,
    EXCEPT when the newcomer is Socrata (the audited open-data source) with
    different digits — then Socrata wins and the replacement is flagged
    "corrected": true so the ledger can re-grade."""
    merged = {dr["id"]: dr for dr in existing_list}
    for dr in new_list:
        cur = merged.get(dr["id"])
        if cur is None:
            merged[dr["id"]] = dr
        elif dr.get("source") == "socrata" and list(dr["digits"]) != list(cur["digits"]):
            repl = dict(dr)
            repl["corrected"] = True
            merged[dr["id"]] = repl
    return sorted(merged.values(), key=lambda dr: timeutil.sort_key(dr["id"]))


def window_draws(history, n=400):
    """Last n draws — the slice published to the site file."""
    return history[-n:]


def lock_proof():
    """Git receipt for the current prediction: sha + commit time of the last commit
    touching site/data/prediction.json. Proves picks were locked pre-draw. Never
    raises — {"sha": None, "committed_at": None} when git/commit is unavailable."""
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%H|%cI", "--", "site/data/prediction.json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )
        line = res.stdout.strip()
        if res.returncode != 0 or "|" not in line:
            return {"sha": None, "committed_at": None}
        sha, committed_at = line.split("|", 1)
        return {"sha": sha, "committed_at": committed_at}
    except Exception:
        return {"sha": None, "committed_at": None}
