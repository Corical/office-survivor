"""Harvest real server views as client test fixtures.

Plays whole games in-process with the arena's own RoomGame (no network), choosing varied LEGAL moves so every kind of
night happens (steals, catches, exposures, gifts, idols, bandits, events), and records exactly what views.py would
send each human. Read-only use of the server code; writes only to godot/tests/fixtures/.

    cd <repo root> && python godot/tools/harvest_fixtures.py [--games 40]

Output:
  godot/tests/fixtures/harvest.jsonl   one {"game", "pid", "msg"} per distinct view
  godot/tests/fixtures/codes.json      every line code seen -> how many times, and the args names it carried
The game count is a chosen default, not derived.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.getcwd())

from arena import views  # noqa: E402
from arena.room import FakeScheduler, RoomGame, RoomSettings  # noqa: E402
from bot.core import GameError  # noqa: E402
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore  # noqa: E402
from bot.tests.test_core_fixtures import _official  # noqa: E402

ALIASES = [f"Alias{i:02d}" for i in range(30)]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "fixtures")
# Heavier than a uniform pick on the moves that make interesting nights.
WEIGHTS = {"scavenge": 2, "guard": 2, "steal": 5, "investigate": 4, "gift": 3}
RADIO = ["saw", "trust", "lying", "guarding", "easy", "innocent", "watch", "me"]


def play(seed, sink0):
    rng = random.Random(seed)
    store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
    sched = FakeScheduler()
    g = RoomGame(_official(), store, ident, texts, ALIASES, f"harvest-{seed}", sched,
                 RoomSettings(ranges=rng.random() < 0.6))
    humans = rng.randint(2, 4)
    for i in range(humans):
        g.add_human(f"u{i}")
        g.connect(i)                  # a real client is connected; early advance only waits for connected humans
    g.start()

    last_round = {}                       # pid -> the round view that opened the night: a reveal's before-state

    def sink(seed_, pid, msg, before=None):
        """Record a view with whose it is (`me`, the other aliases) and, for a reveal, the round view it followed."""
        sink0(seed_, pid, msg, g.players[pid].name, sorted(q.name for q in g._active() if q.pid != pid), before)

    sink(seed, 0, views.lobby(g, 0, "HARV", True))
    steps = 0
    while not g.finished and steps < 60:                # 10 rounds x (round + reveal) = 20 expected steps
        steps += 1
        if g.phase == "round":
            for pid in range(humans):
                last_round[pid] = views.round_view(g, pid)
                sink(seed, pid, last_round[pid])
                legal, amounts = g.legal_for(pid)
                kinds = [k for k in legal if k != "gift" or amounts]
                if not kinds:
                    continue
                kind = rng.choices(kinds, [WEIGHTS.get(k, 1) for k in kinds])[0]
                target = rng.choice(legal[kind]) if legal[kind] else None
                try:
                    g.pick(pid, kind, target, rng.choice(amounts) if kind == "gift" else 0)
                    sink(seed, pid, views.round_view(g, pid))          # with my_pick filled in
                    if rng.random() < 0.3:
                        g.record_radio(f"u{pid}", rng.choice(RADIO), rng.choice(sorted(p.name for p in g.players.values())))
                    g.lock(pid)
                except GameError:
                    pass
            if g.phase == "round":                      # early advance did not fire: run out the clock
                sched.advance(sched.now() + 200)        # past the 180 s timer and every bot's lock moment
        elif g.phase == "reveal":
            for pid in range(humans):
                sink(seed, pid, views.reveal_view(g, pid), last_round.get(pid))
            for pid in range(humans):
                try:
                    g.continue_(pid)
                except GameError:
                    pass
            sched.advance(sched.now() + 30)
        else:
            sched.advance(sched.now() + 30)
    for pid in range(humans):
        if g.finished:
            sink(seed, pid, views.end_view(g, pid))
    return g.finished


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    seen, rows, codes = set(), [], {}

    def sink(seed, pid, msg, me, others, before=None):
        key = json.dumps([msg, before], sort_keys=True, ensure_ascii=False)
        if key in seen:
            return
        seen.add(key)
        row = {"game": seed, "pid": pid, "me": me, "others": others, "msg": msg}
        if before is not None:
            row["before"] = before
        rows.append(row)
        if msg["t"] == "reveal":
            for part in ("news", "private"):
                for ln in msg[part]:
                    c = codes.setdefault(ln["code"], {"count": 0, "args": set(), "in": set()})
                    c["count"] += 1
                    c["args"].update(ln.get("args", {}).keys())
                    c["in"].add(part)

    ended = sum(play(s, sink) for s in range(args.games))
    chosen, covered = [], set()
    for r in rows:
        m = r["msg"]
        why = []
        if r["game"] == 0:
            why.append("game0")                      # one complete game, in order
        if m["t"] == "reveal":
            for ln in m["news"] + m["private"]:
                if ln["code"] not in covered:
                    covered.add(ln["code"])
                    why.append("code:" + ln["code"])
            if m["board"] is not None and "board" not in covered:
                covered.add("board")
                why.append("reveal-with-board")
            if len(m["radio"]) > 1 and "radio" not in covered:
                covered.add("radio")
                why.append("reveal-with-radio")
        if m["t"] == "end" and "end" not in covered:
            covered.add("end")
            why.append("first-end")
        if why:
            chosen.append(dict(r, why=why))
    with open(os.path.join(OUT, "harvest.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for r in chosen:
            f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")
    rows = chosen
    out = {k: {"count": v["count"], "args": sorted(v["args"]), "in": sorted(v["in"])} for k, v in sorted(codes.items())}
    with open(os.path.join(OUT, "codes.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"{args.games} games, {ended} ended, {len(rows)} distinct views, {len(codes)} line codes")
    table = json.load(open(os.path.join("arena", "lines_en.json"), encoding="utf-8"))
    missing = sorted(set(table) - set(codes))
    print("codes in lines_en.json never seen:", missing or "none")
    print("codes seen but not in lines_en.json:", sorted(set(codes) - set(table)) or "none")


if __name__ == "__main__":
    main()
