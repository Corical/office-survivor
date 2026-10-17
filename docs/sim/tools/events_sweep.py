#!/usr/bin/env python3
"""Do wilderness events (docs/sim/events.py) help trailing players catch up? Sweep them against the current rules.

    python -I docs/sim/tools/events_sweep.py [--games 1000] [--procs N]

Configs: events off, then 0.5 / 1 / 2 events per night camp-wide, each with bias "random" and "trailing".
Every config plays the SAME seeds (1..games), so differences between rows are paired, not luck of the draw.
Every game is logged and its books are checked: per-night transfers net to zero, and every player's final
rations equal their start plus every ledger line (so no food is created or lost without a ledger line).

Uses at most half the cores, below normal priority. Writes docs/sim/results/events_sweep.md (the table; the
"What it shows" lines under it are written by hand from that table, so a re-run replaces them).
"""
import argparse
import math
import os
import statistics
import sys
from dataclasses import replace
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import survivors_sim as S  # noqa: E402
from experiments import lower_priority  # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
CHECK_NIGHT = 5
CREATE = {"scavenge", "guard_income", "gift_bonus", "investigate_find", "event_found"}
DESTROY = {"eat", "fine", "event_lost"}
PERSONALITIES = list(S.OFFICE_MIX)
CONFIGS = [("events off", 0.0, "random")] + [
    (f"{n:g}/night {bias}", n, bias) for n in (0.5, 1.0, 2.0) for bias in ("random", "trailing")]


def play_one(job):
    """One logged game -> its numbers. Pure function of (config, seed)."""
    name, per_night, bias, seed = job
    base = S.load_game_rules(S.DEFAULT_GAME)[0]
    rules = replace(base, events_per_night=per_night, events_bias=bias)
    g = S.Game(rules, seed, log=True)
    for _ in range(CHECK_NIGHT):
        g.play_night()
    alive = [p for p in g.players if not p.bandit]
    top = max(p.rations for p in alive)
    leaders = {p.pid for p in alive if p.rations == top}
    for _ in range(rules.rounds - CHECK_NIGHT):
        g.play_night()
    res = g.finish()
    ext = {p.pid for p in res["extracted"]}
    wins = {p.pid for p in res["winners"]}

    # the books: transfers net to zero each night, and every player's rations rebuild exactly from the ledger
    net, held = {}, {p.name: rules.start_rations for p in g.players}
    for e in g.events:
        if e["type"] == "ration":
            held[e["player"]] += e["delta"]
            if e["reason"] not in CREATE | DESTROY:
                net[e["night"]] = net.get(e["night"], 0) + e["delta"]
    unbooked = any(v != 0 for v in net.values()) or any(held[p.name] != p.rations for p in g.players)

    per_arch = {}
    for p in g.players:
        a = per_arch.setdefault(p.arch, [0, 0, 0.0])
        a[0] += 1
        a[1] += p.pid in ext
        a[2] += (1 / len(wins)) if p.pid in wins else 0
    return dict(
        name=name,
        leader_seat=len(leaders & ext) / len(leaders), leader_win=len(leaders & wins) / len(leaders),
        comebacks=sum(p.comebacks for p in g.players), alive=sum(not p.bandit for p in g.players),
        found=g.event_tally["found"], lost=g.event_tally["lost"],
        feast_saved=sum(n.get("feast_saved", 0) for n in g.night_stats),
        storm_lost=sum(n.get("storm_lost", 0) for n in g.night_stats),
        idol_used=sum(n.get("idol_used", 0) for n in g.night_stats), fizzled=g.event_tally["fizzled"],
        fired=sum(v for k, v in g.event_tally.items() if k not in ("found", "lost", "fizzled")),
        seats=res["seats"], players=rules.players, unbooked=unbooked, per_arch=per_arch)


def mean_se(xs):
    m = statistics.mean(xs)
    return m, (statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0)


def summarise(rows):
    n = len(rows)
    out = {}
    for key in ("leader_seat", "leader_win"):
        m, se = mean_se([r[key] for r in rows])
        out[key] = (100 * m, 100 * 1.96 * se)
    for key in ("comebacks", "alive", "found", "lost", "feast_saved", "storm_lost", "idol_used", "fizzled", "fired"):
        out[key] = statistics.mean(r[key] for r in rows)
    out["unbooked"] = sum(r["unbooked"] for r in rows)
    out["n"] = n
    seat_rate = statistics.mean(r["seats"] / r["players"] for r in rows)    # fair share of seats per player
    win_rate = 1 / rows[0]["players"]                                          # fair share of wins per player
    edge = {}
    for a in PERSONALITIES:
        cnt = sum(r["per_arch"].get(a, [0, 0, 0])[0] for r in rows)
        ext = sum(r["per_arch"].get(a, [0, 0, 0])[1] for r in rows)
        win = sum(r["per_arch"].get(a, [0, 0, 0])[2] for r in rows)
        edge[a] = (win / cnt / win_rate, ext / cnt / seat_rate) if cnt else (float("nan"), float("nan"))
    out["edge"] = edge
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    a = ap.parse_args()
    lower_priority()
    jobs = [(name, n, bias, seed) for name, n, bias in CONFIGS for seed in range(1, a.games + 1)]
    print(f"{len(CONFIGS)} configs x {a.games} games on {a.procs} processes (below normal priority)", flush=True)
    with Pool(a.procs, initializer=lower_priority) as pool:
        rows = pool.map(play_one, jobs, chunksize=25)
    by = {name: [] for name, _, _ in CONFIGS}
    for r in rows:
        by[r["name"]].append(r)
    sums = {name: summarise(rs) for name, rs in by.items()}

    head = ["Events", "N5 leader takes a seat %", "N5 leader wins %", "Bandit comebacks / game",
            "Alive at end (of 15)", "Events fired / game", "Food found / game", "Food lost / game",
            "Feast saved / game", "Storm cost / game", "Unbooked-food games"] + \
           [f"{p} win× / seat×" for p in PERSONALITIES]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for name, _, _ in CONFIGS:
        s = sums[name]
        cells = [name, f"{s['leader_seat'][0]:.1f} ±{s['leader_seat'][1]:.1f}",
                 f"{s['leader_win'][0]:.1f} ±{s['leader_win'][1]:.1f}", f"{s['comebacks']:.2f}",
                 f"{s['alive']:.2f}", f"{s['fired']:.2f}", f"{s['found']:.2f}", f"{s['lost']:.2f}",
                 f"{s['feast_saved']:.2f}", f"{s['storm_lost']:.2f}", f"{s['unbooked']} of {s['n']}"]
        cells += [f"{s['edge'][p][0]:.2f} / {s['edge'][p][1]:.2f}" for p in PERSONALITIES]
        lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(lines)

    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "events_sweep.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Wilderness events sweep\n\n"
                f"{a.games} games per row, same seeds 1..{a.games} in every row, current rules (game.json), "
                f"15 players, 10 nights. ± is the 95% margin. Personality cells are win share / seat rate as a "
                f"multiple of a fair share (1.00 = fair). Food and weather columns are per game.\n\n{table}\n")
    print(table)
    print(f"\nwrote {os.path.normpath(path)}")
    bad = sum(s["unbooked"] for s in sums.values())
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
