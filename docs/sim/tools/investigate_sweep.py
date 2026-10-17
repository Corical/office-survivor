#!/usr/bin/env python3
"""Should an exposure undo the theft? (Rules.exposure_undo; the detective personality comes last in every sweep.)

    python -I docs/sim/tools/investigate_sweep.py [--games 3000] [--procs N] [--only substring]

Rules rows (investigators watch one player; if that player stole that night they are EXPOSED):
    A  today          the theft stands; the thief pays the investigator the bounty (1) from their own stash
    B  split          the loot is taken back from the thief: half (rounded UP, so a lone stolen ration goes home) back
                      to the victim, the rest to the investigator; PLUS the bounty (1) to the investigator
    C  full return    all the loot back to the victim; the investigator gets the bounty (1)
    D  full return+2  all the loot back to the victim; the investigator gets a bounty of 2
In B, C and D the thief pays loot first, then the bounty, and only from what they hold. If several thieves hit one
victim only the exposed thief's own share goes back. Every move is a ration ledger line (exposed_return,
exposed_loot, bounty_paid/received); the books must net to zero each night.

AI rows (the same two AIs for every rule row, so rows are comparable):
    AI today   the players ignore the new payouts
    AI weighs  investigating is weighed by (what an exposure pays the investigator) / (today's 1), and a thief who
               is exposed turns cautious (stealing odds halved, like one who was caught). See Game(ai_exposure=True).
Visibility rows: hidden + bot-accurate (today's default) and ranges 7/3/1 + human memory (the likely next default).

Every row plays the SAME seeds (1..games), so rows are paired. Every game is logged and its books checked
(transfers net to zero each night, each player's final rations = start + every ledger line).

Metrics are per game unless stated: steals tried (every steal that named a target, caught ones included), steals
landed (took something at the time), landed and kept (landed minus those where an exposure took the loot back),
investigations, exposures, N5 leader seat/win %, detective and shark win/seat multiples of a fair share (with 95%
margins), bandits created, comebacks, alive at end, games with unbooked food.

Uses at most half the cores, below normal priority. Writes docs/sim/results/investigate_sweep.md (the table; the
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
from events_sweep2 import spearman, mean_moe, pm, CREATE, DESTROY  # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
CHECK_NIGHT = 5
PERSONALITIES = list(S.OFFICE_MIX)
HUMAN = V.HumanMemory()

RULES = [("A today", "none", 1), ("B split", "split", 1), ("C full return", "full", 1), ("D full return + bounty 2", "full", 2)]
AIS = [("AI today", False), ("AI weighs payout", True)]
VIS = [("hidden / bot-accurate", "hidden", False), ("ranges 7/3/1 / human", "ranges", True)]
# (row name, visibility, human memory?, ai_exposure, exposure_undo, bounty)
CONFIGS = [(f"{v[0]} | {a[0]} | {r[0]}", v[1], v[2], a[1], r[1], r[2]) for v in VIS for a in AIS for r in RULES]


def play_one(job):
    """One logged game -> its numbers. Pure function of (config, seed)."""
    name, vis, human, ai, undo, bounty, seed = job
    rules = replace(S.load_game_rules(S.DEFAULT_GAME)[0], exposure_undo=undo, investigate_bounty=bounty)
    g = S.Game(rules, seed, log=True, vis=vis, memory=replace(HUMAN) if human else None, ai_exposure=ai)
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

    net, held = {}, {p.name: rules.start_rations for p in g.players}
    tried = landed = investigations = exposures = undone = 0
    for e in g.events:
        t = e["type"]
        if t == "ration":
            held[e["player"]] += e["delta"]
            if e["reason"] not in CREATE | DESTROY:
                net[e["night"]] = net.get(e["night"], 0) + e["delta"]
        elif t == "steal":
            tried += 1
            landed += e["outcome"] == "success"
        elif t == "investigate":
            investigations += 1
        elif t == "exposed":
            exposures += 1
            undone += e.get("loot_back", 0) > 0
    unbooked = any(v != 0 for v in net.values()) or any(held[p.name] != p.rations for p in g.players)

    per_arch = {}
    for p in g.players:
        a = per_arch.setdefault(p.arch, [0, 0, 0.0])
        a[0] += 1
        a[1] += p.pid in ext
        a[2] += (1 / len(wins)) if p.pid in wins else 0
    return dict(
        name=name, seed=seed, leader_seat=len(leaders & ext) / len(leaders), leader_win=len(leaders & wins) / len(leaders),
        comebacks=sum(p.comebacks for p in g.players), alive=sum(not p.bandit for p in g.players),
        bandits=sum(p.deaths for p in g.players), tried=tried, landed=landed, kept=landed - undone,
        investigations=investigations, exposures=exposures, seats=res["seats"], players=rules.players,
        unbooked=unbooked, per_arch=per_arch)


def ratio_moe(rows, arch, idx, rate_of):
    """Multiple of a fair share for one personality, with a 95% margin by the delta method over games.
    idx 2 = win credit, 1 = seats. rate_of(row) is the fair share per player for that game."""
    num = [r["per_arch"].get(arch, [0, 0, 0])[idx] / rate_of(r) for r in rows]
    den = [r["per_arch"].get(arch, [0, 0, 0])[0] for r in rows]
    big_r = sum(num) / sum(den)
    se = math.sqrt(sum((n - big_r * d) ** 2 for n, d in zip(num, den))) / sum(den)
    return big_r, 1.96 * se


def summarise(rows):
    out = {"n": len(rows)}
    for key in ("leader_seat", "leader_win"):
        out[key] = mean_moe([100 * r[key] for r in rows])
    for key in ("comebacks", "alive", "bandits", "tried", "landed", "kept", "investigations", "exposures"):
        out[key] = mean_moe([r[key] for r in rows])
    out["unbooked"] = sum(r["unbooked"] for r in rows)
    win_rate = lambda r: 1 / r["players"]                      # noqa: E731
    seat_rate = lambda r: r["seats"] / r["players"]            # noqa: E731
    out["edge"] = {a: (ratio_moe(rows, a, 2, win_rate), ratio_moe(rows, a, 1, seat_rate)) for a in PERSONALITIES}
    return out


def pm2(t, d=2):
    return f"{t[0]:.{d}f} ±{t[1]:.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=3000)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--only", default="", help="run only configs whose name contains this")
    ap.add_argument("--out", default="investigate_sweep.md")
    a = ap.parse_args()
    procs = min(a.procs, max(1, (os.cpu_count() or 2) // 2))          # never more than half the cores
    configs = [c for c in CONFIGS if a.only in c[0]]
    lower_priority()
    jobs = [(*c, seed) for c in configs for seed in range(1, a.games + 1)]
    print(f"{len(configs)} configs x {a.games} games on {procs} processes (below normal priority)", flush=True)
    with Pool(procs, initializer=lower_priority) as pool:
        rows = pool.map(play_one, jobs, chunksize=25)
    by = {c[0]: [] for c in configs}
    for r in rows:
        by[r["name"]].append(r)
    sums = {name: summarise(rs) for name, rs in by.items()}

    head = ["Visibility", "AI", "Rule", "Steals tried / game", "Steals landed / game", "Landed and kept / game",
            "Investigations / game", "Exposures / game", "N5 leader takes a seat %", "N5 leader wins %",
            "Detective win×", "Shark win×", "Detective seat×", "Bandits created / game", "Comebacks / game",
            "Alive at end (of 15)", "Unbooked-food games"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for name, s in sums.items():
        vis, ai, rule = name.split(" | ")
        d, sh = s["edge"]["detective"], s["edge"]["shark"]
        cells = [vis, ai, rule, pm(s["tried"], 2), pm(s["landed"], 2), pm(s["kept"], 2), pm(s["investigations"], 2),
                 pm(s["exposures"], 2), pm(s["leader_seat"]), pm(s["leader_win"]), pm2(d[0]), pm2(sh[0]), pm2(d[1]),
                 pm(s["bandits"], 2), pm(s["comebacks"], 2), pm(s["alive"], 2), f"{s['unbooked']} of {s['n']}"]
        lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(lines)

    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, a.out)
    h = HUMAN
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Investigate sweep: should an exposure undo the theft?\n\n"
                f"{a.games} games per row, same seeds 1..{a.games} in every row, current rules (game.json) plus the rule "
                f"in the row, 15 players, 10 nights, no wilderness events. ± is the 95% margin. Rules: A today (theft "
                f"stands, thief pays the investigator 1); B the loot is taken back, half (rounded up) to the victim and "
                f"the rest to the investigator, plus the bounty 1; C all loot back to the victim, bounty 1; D all loot "
                f"back, bounty 2. The thief pays loot first, then the bounty, only from what they hold. AI today = "
                f"players ignore the new payouts; AI weighs payout = investigating is scaled by what an exposure pays the "
                f"investigator (relative to today's 1) and an exposed thief turns cautious. Ranges 7/3/1 + human memory: "
                f"well fed 7+, getting by 3-6, starving 1-2, bandit; players follow {h.k} others closely. Steals landed = "
                f"took something at the time; landed and kept = landed minus those an exposure took back. Detective and "
                f"shark columns are a multiple of a fair share (1.00 = fair).\n\n{table}\n")
    print(table)
    print(f"\nwrote {os.path.normpath(path)}")
    sys.exit(1 if sum(s["unbooked"] for s in sums.values()) else 0)


if __name__ == "__main__":
    main()
