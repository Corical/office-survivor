"""History and Hall of Fame across finished seasons: every alias tied back to the person who played it.

Owner, 17 Oct 2026: aliases are only linked to people once a season has ENDED (the in-season promise in
docs/rules.md stands), and the Hall of Fame shows totals and praise only: never who robbed whom, never a
"most robbed" list. Sims are not people and are left out. Pure: records in, summaries out.
"""
import json
import os
from collections import defaultdict


def season_summary(records, identity):
    """One finished season -> [per-person dict]. [] if the season never finished."""
    start = next((r for r in records if r["type"] == "start"), None)
    fin = next((r for r in records if r["type"] == "finish"), None)
    if not start or not fin:
        return []
    winners = set(next(e for e in fin["events"] if e["type"] == "game_end")["winners"])
    exposures = defaultdict(int)
    for r in records:
        if r["type"] == "night":
            for e in r["events"]:
                if e["type"] == "exposed":
                    exposures[e["investigator"]] += 1
    by_alias = {e["player"]: e for e in fin["events"] if e["type"] == "result"}
    out = []
    for key, who in identity.items():
        res = by_alias.get(who["alias"])
        if res is None or who.get("sim"):
            continue
        out.append({
            "key": key, "alias": who["alias"], "season": start.get("season", ""), "started": start["start_ts"],
            "won": who["alias"] in winners, "seat": res["extracted"], "points": res["score"],
            "stolen": res["stole"], "clean_steals": res.get("steals_ok", 0), "caught": res.get("steals_caught", 0),
            "exposed": exposures[who["alias"]], "given": res["gave_away"], "goal": res["objective_done"],
            "survived": res["survived"],
        })
    return out


def load_seasons(data_dir):
    """Every finished season on disk (the archives, plus the current one if it has ended), oldest first."""
    dirs = sorted(os.path.join(data_dir, d) for d in os.listdir(data_dir) if d.startswith("archive-"))
    dirs.append(data_dir)
    seasons = []
    for d in dirs:
        log, ident = os.path.join(d, "season.jsonl"), os.path.join(d, "identity.json")
        if not (os.path.exists(log) and os.path.exists(ident)):
            continue
        records = []
        with open(log, encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except ValueError:
                    break                    # a torn last line: the season is unfinished anyway
        rows = season_summary(records, json.load(open(ident, encoding="utf-8")))
        if rows:
            seasons.append(rows)
    return seasons


def history(seasons, key=None):
    """Rows for /gm history, newest season first; only `key`'s rows when given."""
    rows = [r for s in reversed(seasons) for r in s if key is None or r["key"] == key]
    return rows


TOTALS = ("games", "won", "seat", "points", "stolen", "exposed", "given", "goal")
AWARDS = [  # praise only (owner): nothing here names a victim or ranks who suffered most
    ("🏆", "Most wins", "won"), ("🚁", "Most helicopter seats", "seat"), ("⭐", "Most points", "points"),
    ("🥷", "Most rations stolen", "stolen"), ("🕵️", "Most thieves exposed", "exposed"),
    ("🎁", "Most generous", "given"), ("🎯", "Most secret goals met", "goal"),
]


def totals(seasons, since=None):
    """Per person, over finished seasons that started on or after `since` (a timestamp)."""
    t = defaultdict(lambda: dict.fromkeys(TOTALS, 0))
    for s in seasons:
        for r in s:
            if since is not None and r["started"] < since:
                continue
            row = t[r["key"]]
            row["games"] += 1
            for k in TOTALS[1:]:
                row[k] += int(r[k])
    return dict(t)


def hall_of_fame(tot):
    """[(emoji, title, [keys], value)] for each award somebody actually earned (a top of 0 earns nothing)."""
    out = []
    for emoji, title, field in AWARDS:
        top = max((row[field] for row in tot.values()), default=0)
        if top > 0:
            out.append((emoji, title, sorted(k for k, row in tot.items() if row[field] == top), top))
    return out
