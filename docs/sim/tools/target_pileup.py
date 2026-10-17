"""How unfair can goal dealing get? Counts how many Grudge/Beat goals point at the same player, per game.

    python tools/target_pileup.py [games]
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import survivors_sim as S  # noqa: E402

rules = S.load_game_rules(S.DEFAULT_GAME)[0]
games = int(sys.argv[1]) if len(sys.argv) > 1 else 300
worst = Counter()      # most goals aimed at one player in a game -> number of games
grudges = Counter()    # most *grudges* aimed at one player in a game
for seed in range(1, games + 1):
    g = S.Game(rules, seed)   # goals are dealt in __init__
    aimed = Counter(p.obj_target for p in g.players if p.objective in ("grudge", "beat"))
    gr = Counter(p.obj_target for p in g.players if p.objective == "grudge")
    worst[max(aimed.values(), default=0)] += 1
    grudges[max(gr.values(), default=0)] += 1
print(f"{games} games, {rules.players} players")
print("most Grudge+Beat goals aimed at one player:", {k: f"{v / games:.0%}" for k, v in sorted(worst.items())})
print("most Grudge goals aimed at one player:     ", {k: f"{v / games:.0%}" for k, v in sorted(grudges.items())})
