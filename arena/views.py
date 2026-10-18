"""What each seat is sent: built field by field from an explicit list, never by passing state through.

Every function takes the room and ONE pid and returns a plain dict (the protocol message, docs/arena/GODOT_FOUNDATION.md
section 5.2). Nothing here may read another player's pick, goal, private lines or exact rations, or whether a seat is
a bot; arena/tests/test_views.py changes all of those and requires the view to stay byte-identical.

A goal and its progress each travel twice: as a line (`line` = code + values, worded by the client's theme from
arena/lines_en.json) and as English `text` (the same words, kept as a fallback). Both come from the one template table
in engine/finish.py, which Torch's /status uses too. Still English only: wilderness event sentences (see lines.py).
"""
import hashlib
import re

from bot.core import RADIO_PHRASES
from engine.finish import goal_line, goal_progress_line, objective_text, render_line
from engine.visibility import band_index

from .lines import news_codes as _news_codes, render


def news_codes(events):
    """The public news for a night in an order that depends only on the lines themselves. The engine resolves seats in
    seat order and humans take the low seats, so its order would tell a watcher which seats are people (the same
    reason the radio is sorted by wording). Wilderness stories first, as in Torch, then everything else by wording."""
    return sorted(_news_codes(events), key=lambda line: (line["code"] != "event", render(line)))

BANDS = ("well_fed", "getting_by", "starving", "bandit")
PROTO = 1


def _band(p):
    return BANDS[min(band_index(p), len(BANDS) - 1)]


def _goal(g, p):
    """The goal: its id, its target, and its wording as a line (code + values) with the English kept as a fallback."""
    tgt = g.players[p.obj_target].name if p.obj_target >= 0 else None
    code, args = goal_line(p.objective, g.rules, tgt or "")
    return {"code": p.objective, "target": tgt, "text": objective_text(p.objective, g.rules, tgt or ""),
            "line": {"code": code, "args": args}}


def _board(g):
    if not g.ranges:
        return None
    return [{"alias": p.name, "band": _band(p)} for p in sorted(g._active(), key=lambda p: p.name)]


def seat_handle(g, pid):
    """An opaque name for one seat's current occupant, so the host can point at a seat without the lobby showing aliases
    or join order. A hash of the room's secret salt, the pid, the alias and the occupant's key: it changes when a seat
    changes hands, so a stale handle can never hit the next person who takes that seat."""
    alias = next(j[1] for j in g.joined if j[0] == pid)
    seed = f"{g.seed_key}:kick:{pid}:{alias}:{g.identity.key_for(pid)}"
    return hashlib.sha256(seed.encode()).hexdigest()[:8]


def lobby(g, pid, room_code, host):
    msg = {"t": "lobby", "room_code": room_code, "seats_taken": len(g.joined), "seats_total": g.settings.seats,
           "host": bool(host)}
    if host:           # the host alone is told which other seats are there and whether anyone is connected to them
        msg["seats"] = sorted(({"id": seat_handle(g, j[0]), "connected": j[0] in g.present}
                               for j in g.joined if j[0] != pid), key=lambda s: s["id"])    # by handle, never by join order
    return msg


def round_view(g, pid):
    p = g.players[pid]
    move = g.moves.get(pid)
    tgt_band = band_index(g.players[p.obj_target]) if g.ranges and p.obj_target >= 0 else None
    from engine.visibility import band_label
    state, pcode, pargs = goal_progress_line(p, list(g.players.values()), g.rules, frozenset(g.quit_ids),
                                             band_label(g.players[p.obj_target]) if tgt_band is not None else None)
    legal, amounts = g.legal_for(pid) if pid not in g.quit_ids else ({}, [])
    return {
        "t": "round", "round": g.round, "rounds": g.rules.rounds,
        "seconds_left": max(0.0, round(g.deadline - g.sched.now(), 1)),
        "me": {"alias": p.name, "rations": p.rations, "bandit": p.bandit,
               "guards_left": (g.rules.guard_limit - p.guards_used) if g.rules.guard_limit else None,
               "guarded": p.guard_until >= g.round,
               "goal": _goal(g, p),
               "goal_progress": {"state": state, "text": render_line(pcode, pargs),
                                 "line": {"code": pcode, "args": pargs}}},
        "legal": legal, "gift_amounts": amounts,
        "my_pick": None if not move else {"kind": move[0], "target": g.players[move[1]].name if move[1] is not None
                                          else None, "amount": move[2]},
        "my_locked": pid in g.locked,
        "locked_count": len(g.locked & {q.pid for q in g._active()}), "seats_total": len(g._active()),
        "radio_available": not g.radio_used(pid),
        "radio_phrases": [{"key": k, "needs_player": "{a}" in t} for k, t in RADIO_PHRASES.items()],
        "aliases": sorted(q.name for q in g._active() if q.pid != pid),
        "board": _board(g),
    }


_PHRASE_RE = {k: re.compile("^" + re.escape(t).replace(re.escape("{a}"), "(?P<a>.+)") + "$")
              for k, t in RADIO_PHRASES.items()}


def _radio_line(text):
    for k, rx in _PHRASE_RE.items():
        m = rx.match(text)
        if m:
            return {"phrase": k, "about": m.groupdict().get("a")}
    return {"phrase": None, "about": None}


def reveal_view(g, pid):
    n = g.closed
    rec = g.night_record(n)
    texts = sorted(g.texts.get(ref) for ref in g.radio_pending if ref.startswith(f"r{n}-"))
    return {
        "t": "reveal", "round": n,
        "news": news_codes(rec["events"]),
        "private": rec["private"].get(str(pid), []),
        # sorted by wording, never by when it was sent: bots decide at the close, so send order would unmask them
        "radio": [_radio_line(t) for t in texts],
        "board": _board(g),
        "seconds_left": max(0.0, round(g.reveal_until - g.sched.now(), 1)),
    }


def end_view(g, pid):
    fin = next(r for r in g.store.load() if r["type"] == "finish")
    ext = next(e for e in fin["events"] if e["type"] == "extraction")["extracted"]
    end = next(e for e in fin["events"] if e["type"] == "game_end")
    by_name = {p.name: p for p in g.players.values()}
    results = []
    for e in sorted((e for e in fin["events"] if e["type"] == "result"), key=lambda e: (-e["score"], e["player"])):
        results.append({"alias": e["player"], "score": e["score"], "rations": e["rations"],
                        "seat": e["player"] in ext, "goal": _goal(g, by_name[e["player"]]),
                        "goal_done": e["objective_done"], "stole": e["stole"], "times_robbed": e["times_robbed"],
                        "gave_away": e["gave_away"]})
    return {"t": "end", "extracted": ext, "winners": end["winners"], "results": results}


def view_for(g, pid):
    """The current screen for `pid` (None in the lobby: the server sends `lobby` with the room code)."""
    return {"round": round_view, "reveal": reveal_view, "end": end_view}.get(g.phase, lambda g, p: None)(g, pid)
