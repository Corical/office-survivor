#!/usr/bin/env python3
"""
Sanity checks for the simulator engine. Run after any change to survivors_sim.py:

  python3 sim/check_invariants.py

Plays 300 games on each of several rule sets and asserts: nobody goes below 0
rations, a survivor at 0 is always a bandit, bandits never extract, seats never
go to someone with fewer rations than a player left behind, and every score
matches its parts.
"""
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survivors_sim as S  # noqa: E402

CONFIGS = ["baseline", "v1_original", "v1_original+gift_bonus+missed_half",
           "guard_unlimited+steal_1", "r1_first_pick", "catch_3+guard_cooldown_1"]

# Food may only enter or leave the game through these. Every other ration movement is a transfer between
# players and must net to exactly zero each night: nobody can be paid what somebody else didn't give.
CREATE = {"scavenge", "guard_income", "gift_bonus"}
DESTROY = {"eat", "fine"}


def check_conservation(name, seed, events):
    by_night = {}
    for e in events:
        if e["type"] == "ration" and e["reason"] not in CREATE | DESTROY:
            by_night[e["night"]] = by_night.get(e["night"], 0) + e["delta"]
    for night, net in by_night.items():
        assert net == 0, (name, seed, f"night {night}: transfers between players net to {net:+d}, food created or lost")

for name in CONFIGS:
    rules = replace(S.Rules(), **S.variant(name))
    for seed in range(300):
        g = S.Game(rules, seed, log=seed < 60)     # logged games also check the ration ledger adds up
        for _ in range(rules.rounds):
            g.play_night()
            for p in g.players:
                assert p.rations >= 0, (name, seed, p.name, "negative rations")
                assert p.bandit or p.rations > 0, (name, seed, p.name, "survivor at 0 rations")
        res = g.finish()
        if g.logging:
            check_conservation(name, seed, g.events)
        assert len(res["extracted"]) <= res["seats"], (name, seed, "too many seats")
        assert all(not p.bandit for p in res["extracted"]), (name, seed, "bandit extracted")
        left = [p for p in g.players if not p.bandit and p not in res["extracted"]]
        if res["extracted"] and left:
            assert max(p.rations for p in left) <= min(p.rations for p in res["extracted"]), \
                (name, seed, "seat went to a lower ration count")
        for p in g.players:
            base = rules.pts_extract if p.extracted else (rules.pts_survive if p.survived else 0)
            assert p.score == base + (rules.pts_objective if p.obj_done else 0), (name, seed, p.name, "score")
    print(f"ok  {name}")
print("all invariants hold")
