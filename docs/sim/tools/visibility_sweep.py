#!/usr/bin/env python3
"""Should players see how many rations the others have?

    python -I docs/sim/tools/visibility_sweep.py [--games 3000] [--procs N] [--only substring]

Rows = what the camp is shown each morning (docs/sim/visibility.py)
    hidden   today: only #news tells you who lost what
    ranges   everyone's band is posted (well fed 7+, getting by 3-6, starving 1-2, bandit); one extra pair of rows
             uses wider edges to see whether the cut points matter
    exact    everyone's true ration count is posted
crossed with how well the simulated players remember it
    bot-accurate   today: they read and remember every line, every night
    human          follow 3 players closely, estimates of the rest fade toward the camp average, guards forgotten
The information only feeds the AI's choice of who to rob / help. The rules and the night's resolution are untouched.

Every row plays the SAME seeds (1..games), so differences between rows are paired. Every game is logged and its books
are checked (transfers net to zero, each player's final rations = start + every ledger line).

Metrics (rows are per game unless stated):
    N5 leader seat / win %   the player(s) richest after night 5 (survivors; ties share) -> extracted / won
    Spearman                 rank correlation of everyone's rations after night 5 with their final score
    bandits created          times a player ran out of food and became a bandit
    theft attempts           every steal action that named a target, caught ones included
    blind hits               theft attempts on a player holding <= BLIND_MAX rations at the start of that night
    comebacks, alive at end  as in the other sweeps
    personality edge         win and seat multiple of a fair share, biggest and smallest personality

Uses at most half the cores, below normal priority. Writes docs/sim/results/visibility_sweep.md (the table; the
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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import survivors_sim as S  # noqa: E402
import visibility as V  # noqa: E402
from experiments import lower_priority  # noqa: E402
from events_sweep2 import ranks, spearman, mean_moe, pm, sgn, CREATE, DESTROY  # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
CHECK_NIGHT = 5
BLIND_MAX = 2
PERSONALITIES = list(S.OFFICE_MIX)
WIDE_EDGES = (9, 5, 2)          # well fed 9+, getting by 5-8, starving 2-4, near-dead 1, bandit

REF = "hidden / bot-accurate (today)"
HUMAN = V.HumanMemory()
# (name, visibility, edges, human memory?)
CONFIGS = []
for _vis, _label in (("hidden", "hidden"), ("ranges", "ranges 7/3/1"), ("exact", "exact")):
    for _human in (False, True):
        _name = f"{_label} / {'human' if _human else 'bot-accurate'}" + (" (today)" if _label == "hidden" and not _human else "")
        CONFIGS.append((_name, _vis, V.BAND_EDGES, _human))
for _human in (False, True):
    CONFIGS.append((f"ranges 9/5/2 / {'human' if _human else 'bot-accurate'}", "ranges", WIDE_EDGES, _human))
CONFIGS = [(REF if n.startswith("hidden / bot") else n, v, e, h) for n, v, e, h in CONFIGS]


def theft_counts(events, start_rations):
    """(theft attempts, blind hits) from the replay log: a steal event is blind when its target held <= BLIND_MAX
    rations at the start of that night (= the last night_end's balance)."""
    held, thefts, blind = dict(start_rations), 0, 0
    for e in events:
        if e["type"] == "steal":
            thefts += 1
            blind += held[e["target"]] <= BLIND_MAX
        elif e["type"] == "night_end":
            held = dict(e["rations"])
    return thefts, blind


def play_one(job):
    """One logged game -> its numbers. Pure function of (config, seed)."""
    name, vis, edges, human, seed = job
    rules = S.load_game_rules(S.DEFAULT_GAME)[0]
    g = S.Game(rules, seed, log=True, vis=vis, edges=edges, memory=replace(HUMAN) if human else None)
    for _ in range(CHECK_NIGHT):
        g.play_night()
    alive = [p for p in g.players if not p.bandit]
    top = max(p.rations for p in alive)
    leaders = {p.pid for p in alive if p.rations == top}
    n5 = {p.pid: p.rations for p in g.players}
    for _ in range(rules.rounds - CHECK_NIGHT):
        g.play_night()
    res = g.finish()
    ext = {p.pid for p in res["extracted"]}
    wins = {p.pid for p in res["winners"]}
    rho = spearman([n5[p.pid] for p in g.players], [p.score for p in g.players])

    net, held = {}, {p.name: rules.start_rations for p in g.players}
    for e in g.events:
        if e["type"] == "ration":
            held[e["player"]] += e["delta"]
            if e["reason"] not in CREATE | DESTROY:
                net[e["night"]] = net.get(e["night"], 0) + e["delta"]
    unbooked = any(v != 0 for v in net.values()) or any(held[p.name] != p.rations for p in g.players)
    thefts, blind = theft_counts(g.events, {p.name: rules.start_rations for p in g.players})

    per_arch = {}
    for p in g.players:
        a = per_arch.setdefault(p.arch, [0, 0, 0.0])
        a[0] += 1
        a[1] += p.pid in ext
        a[2] += (1 / len(wins)) if p.pid in wins else 0
    return dict(
        name=name, seed=seed, rho=rho,
        leader_seat=len(leaders & ext) / len(leaders), leader_win=len(leaders & wins) / len(leaders),
        comebacks=sum(p.comebacks for p in g.players), alive=sum(not p.bandit for p in g.players),
        bandits=sum(p.deaths for p in g.players), thefts=thefts, blind=blind,
        seats=res["seats"], players=rules.players, unbooked=unbooked, per_arch=per_arch)


def summarise(rows, ref_rows):
    out = {"n": len(rows)}
    for key in ("leader_seat", "leader_win"):
        out[key] = mean_moe([100 * r[key] for r in rows])
        out[key + "_d"] = mean_moe([100 * (r[key] - o[key]) for r, o in zip(rows, ref_rows)])   # paired by seed
    out["rho"] = mean_moe([r["rho"] for r in rows if r["rho"] is not None])
    for key in ("comebacks", "alive", "bandits", "thefts", "blind"):
        out[key] = mean_moe([r[key] for r in rows])
    out["blind_d"] = mean_moe([r["blind"] - o["blind"] for r, o in zip(rows, ref_rows)])
    out["unbooked"] = sum(r["unbooked"] for r in rows)
    seat_rate = statistics.mean(r["seats"] / r["players"] for r in rows)
    win_rate = 1 / rows[0]["players"]
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
    ap.add_argument("--games", type=int, default=3000)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--only", default="", help="run only configs whose name contains this (plus the reference row)")
    ap.add_argument("--out", default="visibility_sweep.md")
    a = ap.parse_args()
    procs = min(a.procs, max(1, (os.cpu_count() or 2) // 2))          # never more than half the cores
    configs = [c for c in CONFIGS if c[0] == REF or a.only in c[0]]
    lower_priority()
    jobs = [(*c, seed) for c in configs for seed in range(1, a.games + 1)]
    print(f"{len(configs)} configs x {a.games} games on {procs} processes (below normal priority)", flush=True)
    with Pool(procs, initializer=lower_priority) as pool:
        rows = pool.map(play_one, jobs, chunksize=25)
    by = {c[0]: [] for c in configs}
    for r in rows:
        by[r["name"]].append(r)
    for rs in by.values():
        rs.sort(key=lambda r: r["seed"])
    sums = {name: summarise(rs, by[REF]) for name, rs in by.items()}

    head = ["Visibility / memory", "N5 leader takes a seat %", "N5 leader wins %", "Seat change vs today (pts, paired)",
            "Win change vs today (pts, paired)", "Spearman N5 rations vs final score", "Bandits created / game",
            "Theft attempts / game", f"Blind hits (target <= {BLIND_MAX} rations) / game",
            "Blind-hit change vs today (paired)", "Bandit comebacks / game", "Alive at end (of 15)",
            "Biggest personality win× (who)", "Smallest personality win× (who)", "Biggest personality seat× (who)",
            "Unbooked-food games"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for name in by:
        s = sums[name]
        wmax = max(PERSONALITIES, key=lambda p: s["edge"][p][0])
        wmin = min(PERSONALITIES, key=lambda p: s["edge"][p][0])
        smax = max(PERSONALITIES, key=lambda p: s["edge"][p][1])
        today = name == REF
        cells = [name, pm(s["leader_seat"]), pm(s["leader_win"]),
                 "-" if today else sgn(s["leader_seat_d"]), "-" if today else sgn(s["leader_win_d"]),
                 pm(s["rho"], 3), pm(s["bandits"], 2), pm(s["thefts"], 2), pm(s["blind"], 2),
                 "-" if today else sgn(s["blind_d"]), pm(s["comebacks"], 2), pm(s["alive"], 2),
                 f"{s['edge'][wmax][0]:.2f} ({wmax})", f"{s['edge'][wmin][0]:.2f} ({wmin})",
                 f"{s['edge'][smax][1]:.2f} ({smax})", f"{s['unbooked']} of {s['n']}"]
        lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(lines)

    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, a.out)
    h = HUMAN
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Rations visibility sweep\n\n"
                f"{a.games} games per row, same seeds 1..{a.games} in every row, current rules (game.json), 15 players, "
                f"10 nights, no wilderness events. ± is the 95% margin; the 'change vs today' columns are per-seed "
                f"differences from the first row, so their margins are tighter than the columns beside them. "
                f"Ranges 7/3/1 = well fed 7+, getting by 3-6, starving 1-2, bandit; ranges 9/5/2 = 9+, 5-8, 2-4, 1, "
                f"bandit. Human memory = follows {h.k} players closely ({h.k - h.random_slots} by recent dealings, "
                f"{h.random_slots} random), estimates of the rest close {h.decay:.0%} of the gap to the camp average "
                f"each night without news, a guard is forgotten {h.guard_forget:.0%} of the time and never remembered "
                f"for players not followed. Blind hit = a theft attempt on a player holding {BLIND_MAX} or fewer "
                f"rations at the start of that night. Personality columns are a multiple of a fair share "
                f"(1.00 = fair).\n\n{table}\n")
    print(table)
    print(f"\nwrote {os.path.normpath(path)}")
    sys.exit(1 if sum(s["unbooked"] for s in sums.values()) else 0)




if __name__ == "__main__":
    main()
