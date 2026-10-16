#!/usr/bin/env python3
"""
Reruns every balance experiment from the 16 Oct 2026 design session, in order,
with fixed seeds, and writes the results to sim/results/.

  python3 sim/experiments.py            all phases (about 10 minutes on a laptop, longer on a Pi)
  python3 sim/experiments.py --runs 100 quicker, noisier

Every config is written as changes on top of the FIRST DRAFT rules (v1), so the
table reads as "what we tried, starting from where we started". Outputs:
  results/experiments.csv   one row per config, every metric
  results/experiments.md    the same, as readable tables per phase
"""

import argparse
import csv
import os
import statistics as st
import sys
from dataclasses import fields, replace
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survivors_sim as S  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
SEED = 7

V1 = S.variant("v1_original")             # first-draft values for every rule we later changed
R1 = dict(start_rations=7, bandit_steal_amount=1, guard_nights=2, caught_penalty=2, guard_reward=2,
          tiebreak="kindness", winner_tiebreak="kindness", give_goal=3, grudge_goal="rob",
          grudge_robs=1, robbed_goal=1)
TUNED = dict(bandit_steal_amount=1, guard_nights=2, tiebreak="kindness", give_goal=3, grudge_goal="rob")

PHASES = [
    ("1. First draft", "The rules as first written.", [
        ("v1_first_draft", {}),
    ]),
    ("2. Single fixes on the first draft", "One change at a time, to see what each knob does.", [
        ("start_7", {"start_rations": 7}),
        ("scavenge_1_2", {"scavenge_min": 1}),
        ("scavenge_0_3", {"scavenge_max": 3}),
        ("guard_reward_1", {"guard_reward": 1}),
        ("guard_income_0_1", {"guard_income_max": 1}),
        ("harsh_catch", {"caught_penalty": 2, "guard_reward": 1}),
        ("steal_1", {"steal_amount": 1, "bandit_steal_amount": 1}),
        ("bandit_rejoin_5", {"bandit_rejoin": 5}),
        ("bandit_steal_1", {"bandit_steal_amount": 1}),
        ("guard_2_nights", {"guard_nights": 2}),
        ("kindness_tiebreak", {"tiebreak": "kindness"}),
        ("objectives_give3_rob2", {"give_goal": 3, "grudge_goal": "rob", "grudge_robs": 2}),
        ("missed_deadline_0_1", {"missed_scavenge_max": 1}),
        ("investigate_bounty_1", {"investigate_bounty": 1}),
    ]),
    ("3. Combined packages", "Economy fix + slower bandits + 2-night guard + kindness tiebreak + easier objectives.", [
        ("tuned_a_start7", {**TUNED, "start_rations": 7}),
        ("tuned_b_scavenge1_2", {**TUNED, "scavenge_min": 1}),
        ("tuned_c_scavenge0_3", {**TUNED, "scavenge_max": 3}),
        ("tuned_a+missed_0_1", {**TUNED, "start_rations": 7, "missed_scavenge_max": 1}),
        ("tuned_a+bounty", {**TUNED, "start_rations": 7, "investigate_bounty": 1}),
        ("tuned_c+missed_0_1", {**TUNED, "scavenge_max": 3, "missed_scavenge_max": 1}),
        ("tuned_c+bounty", {**TUNED, "scavenge_max": 3, "investigate_bounty": 1}),
    ]),
    ("4. First recommendation (R1) and variants", "R1 = start 7, bandits steal 1, 2-night guard, thief pays guard 2, kindness tiebreaks, easier objectives.", [
        ("R1", R1),
        ("R1_no_winner_tiebreak", {**R1, "winner_tiebreak": "none"}),
        ("R1_rations_win_ties", {**R1, "winner_tiebreak": "rations"}),
        ("R1+steal_1", {**R1, "steal_amount": 1}),
        ("R1+catch_3", {**R1, "caught_penalty": 3, "guard_reward": 3}),
        ("R1+gift_bonus", {**R1, "gift_bonus": 1}),
        ("R1+bounty", {**R1, "investigate_bounty": 1}),
    ]),
    ("5. Fixing the turtle loophole in R1", "R1's 2-night guard let players guard, scavenge, repeat. Candidate fixes.", [
        ("R1+guard_1_night", {**R1, "guard_nights": 1}),
        ("R1+guard_1_night+income", {**R1, "guard_nights": 1, "guard_income_max": 1}),
        ("R1+guard_limit_3", {**R1, "guard_limit": 3}),
        ("R1+guard_limit_4", {**R1, "guard_limit": 4}),
        ("R1+cooldown_1", {**R1, "guard_cooldown": 1}),
        ("R1+cooldown_2", {**R1, "guard_cooldown": 2}),
        ("R1+guard_1_night+limit_3", {**R1, "guard_nights": 1, "guard_limit": 3}),
        ("R1+guard_1_night+limit_4", {**R1, "guard_nights": 1, "guard_limit": 4}),
        ("R1+limit_3+catch_3", {**R1, "guard_limit": 3, "caught_penalty": 3, "guard_reward": 3}),
        ("R1+limit_4+catch_3", {**R1, "guard_limit": 4, "caught_penalty": 3, "guard_reward": 3}),
        ("R1+limit_3+steal_1", {**R1, "guard_limit": 3, "steal_amount": 1}),
        ("R1+limit_3+bounty = v2", {**R1, "guard_limit": 3, "investigate_bounty": 1}),
    ]),
    ("6. Current rules", "v2 as written in game.json, and the open steal-size dial.", [
        ("v2_current", "GAME"),
        ("v2+steal_1", "GAME+steal_1"),
    ]),
]

MAIN = ["casual", "farmer", "opportunist", "shark", "paranoid", "saint", "detective", "chaos"]
METRICS = ["survivors_end", "ever_bandit", "comebacks", "died_never_robbed", "first_death_night",
           "catch_rate", "robberies_per_night", "quiet_nights", "coin_flip_finale", "seats_unfilled",
           "extracted_heavy_thieves", "winners_per_game", "extraction_cutoff", "max_rations"]


def rules_for(over):
    if over == "GAME":
        return S.load_game_rules(S.DEFAULT_GAME)[0]
    if over == "GAME+steal_1":
        return replace(S.load_game_rules(S.DEFAULT_GAME)[0], steal_amount=1, bandit_steal_amount=1)
    return replace(S.Rules(), **{**V1, **over})


def run_one(job):
    phase, name, over, runs = job
    r = rules_for(over)
    row = {"phase": phase, "config": name}
    changed = {f.name: getattr(r, f.name) for f in fields(S.Rules)
               if getattr(r, f.name) != getattr(replace(S.Rules(), **V1), f.name)}
    row["changes_vs_first_draft"] = "; ".join(f"{k}={v}" for k, v in changed.items()) or "-"
    for mixname in ("default", "honest", "cutthroat"):
        R = S.simulate(r, runs, SEED, S.MIXES[mixname])
        tot = sum(R["arch_count"].values())
        ratios = {}
        for a in MAIN:
            if R["arch_count"][a]:
                ratios[a] = (R["arch_win"][a] / runs) / (R["arch_count"][a] / tot)
        if mixname == "default":
            for m in METRICS:
                row[m] = round(st.mean(R["M"][m]), 3)
            for o in S.OBJECTIVES:
                row[f"objective_{o}"] = round(st.mean(R["obj"][o]), 3)
            for a in MAIN:
                row[f"winx_{a}"] = round(ratios.get(a, 0), 2)
        lo = min(ratios, key=ratios.get)
        hi = max(ratios, key=ratios.get)
        row[f"{mixname}_weakest"] = f"{lo} {ratios[lo]:.2f}"
        row[f"{mixname}_strongest"] = f"{hi} {ratios[hi]:.2f}"
    fair = 1 / r.players
    for t in ("turtle", "always_guard", "always_steal", "always_scavenge", "always_investigate", "always_gift"):
        F = S.simulate(r, runs, SEED, None, [t])["F"]
        row[f"lone_{t}_winx"] = round(st.mean(F["win"]) / fair, 2)
        row[f"lone_{t}_extract"] = round(st.mean(F["extract"]), 3)
    return row


def fmt_pct(x):
    return f"{x:.0%}"


def lower_priority():
    """Run below normal priority so the machine stays usable; worker processes inherit it."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        if not k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS):
            print("(could not lower priority; running at normal priority)")
    else:
        os.nice(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="worker processes (default: half the logical processors, so the machine stays usable)")
    a = ap.parse_args()
    lower_priority()
    jobs = [(ph, name, over, a.runs) for ph, _, items in PHASES for name, over in items]
    with Pool(a.procs) as pool:
        rows = pool.map(run_one, jobs)
    os.makedirs(RESULTS, exist_ok=True)
    keys = list(rows[0].keys())
    with open(os.path.join(RESULTS, "experiments.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    by = {r["config"]: r for r in rows}
    out = [f"# Experiment results\n\n{a.runs} simulated games per config and office mix, seed {SEED}, "
           f"15 players, 10 nights. Regenerate with `python3 sim/experiments.py`.\n\n"
           "Columns: **Alive** = survivors at the end (of 15). **Died** = players who hit zero at some point. "
           "**Back** = bandit comebacks. **Catch** = share of steals caught by a guard. **Robs** = robberies "
           "per night. **Quiet** = nights with no robbery, catch or death. **Coin** = last seat decided by coin flip. "
           "**Thief seats** = share of seats won by players with 3+ steals. **Turtle/Thief** = one player who only "
           "guards-when-unprotected / only steals, in a normal office: share of wins vs fair (1.0) and how often they "
           "get a seat. **Balance** = weakest and strongest personality, win share vs fair, default office.\n"]
    for ph, desc, items in PHASES:
        out.append(f"\n## {ph}\n\n{desc}\n\n")
        out.append("| Config | Alive | Died | Back | Catch | Robs | Quiet | Coin | Thief seats | Turtle | Thief | Balance |\n")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for name, _ in items:
            r = by[name]
            out.append(
                f"| {name} | {r['survivors_end']:.1f} | {r['ever_bandit']:.1f} | {r['comebacks']:.1f} | "
                f"{fmt_pct(r['catch_rate'])} | {r['robberies_per_night']:.1f} | {r['quiet_nights']:.1f} | "
                f"{fmt_pct(r['coin_flip_finale'])} | {fmt_pct(r['extracted_heavy_thieves'])} | "
                f"{r['lone_turtle_winx']:.2f}x, {fmt_pct(r['lone_turtle_extract'])} | "
                f"{r['lone_always_steal_winx']:.2f}x, {fmt_pct(r['lone_always_steal_extract'])} | "
                f"{r['default_weakest']} / {r['default_strongest']} |\n")
    out.append("\n## Secret objective completion (default office)\n\n| Config | Beat @player | Robbed + extract | "
               "Steal 3 clean | Give away | Grudge |\n| --- | --- | --- | --- | --- | --- |\n")
    for name in ("v1_first_draft", "objectives_give3_rob2", "R1", "v2_current"):
        r = by[name]
        out.append(f"| {name} | " + " | ".join(fmt_pct(r[f'objective_{o}']) for o in S.OBJECTIVES) + " |\n")
    out.append("\n## Balance across office mixes (weakest / strongest personality, win share vs fair)\n\n"
               "| Config | Default office | Honest office | Cutthroat office |\n| --- | --- | --- | --- |\n")
    for name in ("v1_first_draft", "tuned_a_start7", "R1", "R1+guard_limit_3", "R1+limit_3+bounty = v2", "v2+steal_1"):
        r = by[name]
        out.append(f"| {name} | {r['default_weakest']} / {r['default_strongest']} | "
                   f"{r['honest_weakest']} / {r['honest_strongest']} | {r['cutthroat_weakest']} / {r['cutthroat_strongest']} |\n")
    with open(os.path.join(RESULTS, "experiments.md"), "w", encoding="utf-8") as f:
        f.write("".join(out))
    print(f"Wrote {len(rows)} configs to {RESULTS}/experiments.csv and experiments.md")


if __name__ == "__main__":
    main()
