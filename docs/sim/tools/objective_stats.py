"""How each secret goal plays out: how often it's completed, and what it does to the player's seat and score.

    python tools/objective_stats.py [games]
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import survivors_sim as S  # noqa: E402

rules = S.load_game_rules(S.DEFAULT_GAME)[0]
games = int(sys.argv[1]) if len(sys.argv) > 1 else 300
t = defaultdict(lambda: defaultdict(int))
for seed in range(1, games + 1):
    g = S.Game(rules, seed)
    g.run()
    for p in g.players:
        o = p.objective if p.objective != "grudge" else f"grudge ({rules.grudge_goal})"
        t[o]["n"] += 1
        t[o]["done"] += p.obj_done
        t[o]["seat"] += p.extracted
        t[o]["seat_when_done"] += p.extracted and p.obj_done
        t[o]["score"] += p.score
print(f"{games} games, {rules.players} players each")
print(f"{'goal':22} {'players':>7} {'done':>6} {'seat':>6} {'seat if done':>12} {'avg score':>9}")
for o, v in sorted(t.items(), key=lambda kv: -kv[1]["done"] / kv[1]["n"]):
    d = v["done"]
    print(f"{o:22} {v['n']:7} {d / v['n']:6.0%} {v['seat'] / v['n']:6.0%} "
          f"{(v['seat_when_done'] / d if d else 0):12.0%} {v['score'] / v['n']:9.2f}")
