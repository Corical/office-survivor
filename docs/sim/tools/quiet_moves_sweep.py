#!/usr/bin/env python3
"""Do the two quiet moves become worth a night? (Rules.investigate_find and Rules.gift_bonus; exposure_undo = "full".)

    python -I docs/sim/tools/quiet_moves_sweep.py [--games 3000] [--procs N] [--only substring]

Rows (all with exposure_undo="full", investigate_bounty 1):
    baseline        investigate_find 0, gift_bonus 0
    I 0..1          an investigator also finds 0..1 new rations (uniform), booked "investigate_find"
    I 0..2          the same, 0..2
    G 1             gift_bonus 1: the receiver gets +1 on top of each gift
    I 0..1 + G 1    both
The same AI in every row (Game(ai_quiet=True)): investigating is weighed up by (1 + expected find) / 1, gifting by
(gift + bonus) / gift, and a player who was given food by an alias and has not returned it is likelier to give back
(+0.25 on the gift weight, and the gift goes to the most recent giver). With both knobs at 0 only the give-back is live.
Visibility: ranges 7/3/1 + human memory (the likely default). Every row plays the SAME seeds, so rows are paired.

Per game: moves (scavenge / steal / guard / investigate / gift, auto-scavenges included), exposures, steals landed and
kept, gifts, reciprocal gifts (a gift to someone who had already given to the giver), reciprocal pairs (two players who
gave each other food), the most gifts inside one pair, food created by scavenging / investigation / gift bonus, the mean
rations a player holds at the end, N5 leader seat/win, personality win/seat multiples of a fair share, bandits created,
comebacks, alive at end, and games whose books do not balance (transfers net to zero each night, every player's final
rations = start + ledger).

Uses at most half the cores, below normal priority. Writes docs/sim/results/quiet_moves_sweep.md (the table; the lines
under it are written by hand from that table, so a re-run replaces them).
"""
import argparse
import os
import sys
from dataclasses import replace
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import survivors_sim as S  # noqa: E402
import visibility as V  # noqa: E402
from experiments import lower_priority  # noqa: E402
from events_sweep2 import mean_moe, CREATE, DESTROY  # noqa: E402
from investigate_sweep import ratio_moe, pm2, PERSONALITIES  # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
CHECK_NIGHT = 5
HUMAN = V.HumanMemory()
# (row, investigate_find, gift_bonus)
ROWS = [("baseline", 0, 0), ("I 0..1", 1, 0), ("I 0..2", 2, 0), ("G 1", 0, 1), ("I 0..1 + G 1", 1, 1)]
MOVES = ("scavenge", "steal", "guard", "investigate", "gift")


def play_one(job):
    name, find, bonus, seed = job
    rules = replace(S.load_game_rules(S.DEFAULT_GAME)[0], exposure_undo="full", investigate_find=find, gift_bonus=bonus)
    g = S.Game(rules, seed, log=True, vis="ranges", memory=replace(HUMAN), ai_quiet=True)
    for _ in range(CHECK_NIGHT):
        g.play_night()
    alive = [p for p in g.players if not p.bandit]
    top = max(p.rations for p in alive)
    leaders = {p.pid for p in alive if p.rations == top}
    for _ in range(rules.rounds - CHECK_NIGHT):
        g.play_night()
    held_at_end = sum(p.rations for p in g.players) / len(g.players)
    res = g.finish()
    ext = {p.pid for p in res["extracted"]}
    wins = {p.pid for p in res["winners"]}

    net, held = {}, {p.name: rules.start_rations for p in g.players}
    landed = undone = exposures = gifts = recip = 0
    made = {"scavenge": 0, "investigate_find": 0, "gift_bonus": 0}
    given, pair_n = set(), {}
    for e in g.events:
        t = e["type"]
        if t == "ration":
            held[e["player"]] += e["delta"]
            if e["reason"] not in CREATE | DESTROY:
                net[e["night"]] = net.get(e["night"], 0) + e["delta"]
            if e["reason"] in made:
                made[e["reason"]] += e["delta"]
        elif t == "steal":
            landed += e["outcome"] == "success"
        elif t == "exposed":
            exposures += 1
            undone += e.get("loot_back", 0) > 0
        elif t == "gift":
            gifts += 1
            recip += (e["receiver"], e["giver"]) in given
            given.add((e["giver"], e["receiver"]))
            key = frozenset((e["giver"], e["receiver"]))
            pair_n[key] = pair_n.get(key, 0) + 1
    unbooked = any(v != 0 for v in net.values()) or any(held[p.name] != p.rations for p in g.players)
    pairs_both = sum(1 for a, b in given if a < b and (b, a) in given)

    per_arch = {}
    for p in g.players:
        a = per_arch.setdefault(p.arch, [0, 0, 0.0])
        a[0] += 1
        a[1] += p.pid in ext
        a[2] += (1 / len(wins)) if p.pid in wins else 0
    row = dict(
        name=name, leader_seat=len(leaders & ext) / len(leaders), leader_win=len(leaders & wins) / len(leaders),
        comebacks=sum(p.comebacks for p in g.players), alive=sum(not p.bandit for p in g.players),
        bandits=sum(p.deaths for p in g.players), landed=landed, kept=landed - undone, exposures=exposures,
        gifts=gifts, recip=recip, pairs_both=pairs_both, max_pair=max(pair_n.values(), default=0),
        from_scavenge=made["scavenge"], from_find=made["investigate_find"], from_gift=made["gift_bonus"],
        held_end=held_at_end, seats=res["seats"], players=rules.players, unbooked=unbooked, per_arch=per_arch)
    for m in MOVES:
        row["mv_" + m] = sum(p.actions[m] for p in g.players)
    return row


def summarise(rows):
    out = {"n": len(rows)}
    for key in ("leader_seat", "leader_win"):
        out[key] = mean_moe([100 * r[key] for r in rows])
    keys = ["comebacks", "alive", "bandits", "landed", "kept", "exposures", "gifts", "recip", "pairs_both", "max_pair",
            "from_scavenge", "from_find", "from_gift", "held_end"] + ["mv_" + m for m in MOVES]
    for key in keys:
        out[key] = mean_moe([r[key] for r in rows])
    out["unbooked"] = sum(r["unbooked"] for r in rows)
    win_rate = lambda r: 1 / r["players"]                      # noqa: E731
    seat_rate = lambda r: r["seats"] / r["players"]            # noqa: E731
    out["edge"] = {a: (ratio_moe(rows, a, 2, win_rate), ratio_moe(rows, a, 1, seat_rate)) for a in PERSONALITIES}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=3000)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="quiet_moves_sweep.md")
    a = ap.parse_args()
    procs = min(a.procs, max(1, (os.cpu_count() or 2) // 2))
    rows_cfg = [c for c in ROWS if a.only in c[0]]
    lower_priority()
    jobs = [(*c, seed) for c in rows_cfg for seed in range(1, a.games + 1)]
    print(f"{len(rows_cfg)} rows x {a.games} games on {procs} processes (below normal priority)", flush=True)
    with Pool(procs, initializer=lower_priority) as pool:
        rows = pool.map(play_one, jobs, chunksize=25)
    by = {c[0]: [] for c in rows_cfg}
    for r in rows:
        by[r["name"]].append(r)
    sums = {name: summarise(rs) for name, rs in by.items()}

    head = ["Row", "Scavenge / game", "Steal / game", "Guard / game", "Investigate / game", "Gift / game",
            "Exposures / game", "Steals landed and kept / game", "Reciprocal gifts / game", "Reciprocal pairs / game",
            "Most gifts in one pair", "Food from scavenging / game", "Food from investigating / game",
            "Food from gift bonus / game", "Rations held per player at end", "N5 leader takes a seat %",
            "N5 leader wins %", "Detective win×", "Detective seat×", "Saint win×", "Shark win×", "Bandits created / game",
            "Comebacks / game", "Alive at end (of 15)", "Unbooked-food games"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for name, s in sums.items():
        d, sa, sh = s["edge"]["detective"], s["edge"]["saint"], s["edge"]["shark"]
        cells = [name] + [pm2(s[k]) for k in ("mv_scavenge", "mv_steal", "mv_guard", "mv_investigate", "mv_gift",
                                              "exposures", "kept", "recip", "pairs_both", "max_pair", "from_scavenge",
                                              "from_find", "from_gift", "held_end")]
        cells += [f"{s['leader_seat'][0]:.1f} ±{s['leader_seat'][1]:.1f}", f"{s['leader_win'][0]:.1f} ±{s['leader_win'][1]:.1f}",
                  pm2(d[0]), pm2(d[1]), pm2(sa[0]), pm2(sh[0]), pm2(s["bandits"]), pm2(s["comebacks"]), pm2(s["alive"]),
                  f"{s['unbooked']} of {s['n']}"]
        lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(lines)

    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, a.out)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Quiet moves sweep: do investigating and gifting become worth a night?\n\n"
                f"{a.games} games per row, same seeds 1..{a.games} in every row, current rules (game.json) with "
                f"exposure_undo full, 15 players, 10 nights, no wilderness events, ranges 7/3/1 and human memory. "
                f"± is the 95% margin. I = an investigator also finds 0..N new rations; G = the receiver of a gift gets "
                f"N extra. Same AI in every row. Win and seat columns are a multiple of a fair share (1.00 = fair).\n\n"
                f"{table}\n")
    print(table)
    print(f"\nwrote {os.path.normpath(path)}")
    sys.exit(1 if sum(s["unbooked"] for s in sums.values()) else 0)


if __name__ == "__main__":
    main()
