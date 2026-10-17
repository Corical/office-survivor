#!/usr/bin/env python3
"""Round 2: can RARE wilderness events (docs/sim/events.py) cut how often the early leader runs away with it?

    python -I docs/sim/tools/events_sweep2.py [--games 2000] [--procs N] [--only substring]

Round 1 (events_sweep.py) found that up to 2 random/trailing events a night barely move the leader. Round 2 tries
designs aimed at the leader, at 0.5 and 1 events a night camp-wide:

    top       events_bias="top": bad player-events strike the top third of rations, good ones the bottom third
    raid      a "-2, top quarter only, never the last ration" event, drawn RAID_X times its library weight
    rats      the rats tax everyone within 1 of the richest, instead of a fixed 7 or more
    (and the combinations)

Baselines (same seeds, same rows' code path): events off, and 0.5 / 1 events a night with random bias.
Every config plays the SAME seeds (1..games), so differences between rows are paired, not luck of the draw.
Every game is logged and its books are checked: per-night transfers net to zero and every player's final rations equal
their start plus every ledger line.

Spearman = rank correlation between everyone's rations at the end of night 5 (bandits included) and their final score
(ties get average ranks). Lower = the early order matters less to the final order.

Uses at most half the cores, below normal priority. Writes docs/sim/results/events_sweep2.md (the table; the "What it
shows" lines under it are written by hand from that table, so a re-run replaces them).
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
RAID_X = 4.0          # raid is drawn 4 x its library weight (4): about a fifth of all events

OFF = "events off"
# (name, events per night, bias, raid multiplier, relative rats)
CONFIGS = [(OFF, 0.0, "random", 0.0, False)]
for _rate in (0.5, 1.0):
    CONFIGS += [
        (f"{_rate:g}/night random (baseline)", _rate, "random", 0.0, False),
        (f"{_rate:g}/night top", _rate, "top", 0.0, False),
        (f"{_rate:g}/night raid", _rate, "random", RAID_X, False),
        (f"{_rate:g}/night rats-relative", _rate, "random", 0.0, True),
        (f"{_rate:g}/night top + raid", _rate, "top", RAID_X, False),
        (f"{_rate:g}/night top + rats-relative", _rate, "top", 0.0, True),
        (f"{_rate:g}/night raid + rats-relative", _rate, "random", RAID_X, True),
        (f"{_rate:g}/night top + raid + rats-relative", _rate, "top", RAID_X, True),
    ]
CONFIGS += [("1/night top + raid x12 + rats-relative", 1.0, "top", 12.0, True)]


def ranks(xs):
    """Average ranks (1 = smallest); equal values share the mean of their positions."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a, b):
    """Rank correlation; None when either side has no spread (everyone tied)."""
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def play_one(job):
    """One logged game -> its numbers. Pure function of (config, seed)."""
    name, per_night, bias, raid, rats, seed = job
    base = S.load_game_rules(S.DEFAULT_GAME)[0]
    rules = replace(base, events_per_night=per_night, events_bias=bias, events_raid=raid, events_rats_relative=rats)
    g = S.Game(rules, seed, log=True)
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
        moved=g.event_tally["found"] + g.event_tally["lost"],
        fired=sum(v for k, v in g.event_tally.items() if k not in ("found", "lost", "fizzled")),
        seats=res["seats"], players=rules.players, unbooked=unbooked, per_arch=per_arch)


def mean_moe(xs):
    """(mean, 95% margin)."""
    m = statistics.mean(xs)
    return m, (1.96 * statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0)


def summarise(rows, off_rows):
    out = {"n": len(rows)}
    for key in ("leader_seat", "leader_win"):
        m, e = mean_moe([100 * r[key] for r in rows])
        out[key] = (m, e)
        d = [100 * (r[key] - o[key]) for r, o in zip(rows, off_rows)]          # paired by seed
        out[key + "_d"] = mean_moe(d)
    out["rho"] = mean_moe([r["rho"] for r in rows if r["rho"] is not None])
    for key in ("comebacks", "alive", "fired", "moved"):
        out[key] = mean_moe([r[key] for r in rows])
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


def pm(t, d=1):
    return f"{t[0]:.{d}f} ±{t[1]:.{d}f}"


def sgn(t):
    return f"{t[0]:+.1f} ±{t[1]:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=2000)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--only", default="", help="run only configs whose name contains this (plus events off)")
    ap.add_argument("--out", default="events_sweep2.md")
    a = ap.parse_args()
    configs = [c for c in CONFIGS if c[0] == OFF or a.only in c[0]]
    lower_priority()
    jobs = [(*c, seed) for c in configs for seed in range(1, a.games + 1)]
    print(f"{len(configs)} configs x {a.games} games on {a.procs} processes (below normal priority)", flush=True)
    with Pool(a.procs, initializer=lower_priority) as pool:
        rows = pool.map(play_one, jobs, chunksize=25)
    by = {c[0]: [] for c in configs}
    for r in rows:
        by[r["name"]].append(r)
    for rs in by.values():
        rs.sort(key=lambda r: r["seed"])
    sums = {name: summarise(rs, by[OFF]) for name, rs in by.items()}

    head = ["Design", "N5 leader takes a seat %", "N5 leader wins %", "Seat change vs off (pts, paired)",
            "Win change vs off (pts, paired)", "Spearman N5 rations vs final score", "Bandit comebacks / game",
            "Alive at end (of 15)", "Events fired / game", "Rations moved by events / game",
            "Biggest personality win× (who)", "Smallest personality win× (who)", "Biggest personality seat× (who)",
            "Unbooked-food games"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for name in by:
        s = sums[name]
        wmax = max(PERSONALITIES, key=lambda p: s["edge"][p][0])
        wmin = min(PERSONALITIES, key=lambda p: s["edge"][p][0])
        smax = max(PERSONALITIES, key=lambda p: s["edge"][p][1])
        cells = [name, pm(s["leader_seat"]), pm(s["leader_win"]),
                 "-" if name == OFF else sgn(s["leader_seat_d"]), "-" if name == OFF else sgn(s["leader_win_d"]),
                 pm(s["rho"], 3), pm(s["comebacks"], 2), pm(s["alive"], 2), pm(s["fired"], 2), pm(s["moved"], 2),
                 f"{s['edge'][wmax][0]:.2f} ({wmax})", f"{s['edge'][wmin][0]:.2f} ({wmin})",
                 f"{s['edge'][smax][1]:.2f} ({smax})", f"{s['unbooked']} of {s['n']}"]
        lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(lines)

    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, a.out)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Wilderness events sweep, round 2\n\n"
                f"{a.games} games per row, same seeds 1..{a.games} in every row, current rules (game.json), "
                f"15 players, 10 nights. ± is the 95% margin. Raid is drawn {RAID_X:g} x its library weight "
                f"(about a fifth of all events); the last row draws it 12 x. Seat/win change is the per-seed "
                f"difference from events off, so its margin is tighter than the two columns beside it. "
                f"Personality columns are a multiple of a fair share (1.00 = fair).\n\n{table}\n")
    print(table)
    print(f"\nwrote {os.path.normpath(path)}")
    sys.exit(1 if sum(s["unbooked"] for s in sums.values()) else 0)


if __name__ == "__main__":
    main()
