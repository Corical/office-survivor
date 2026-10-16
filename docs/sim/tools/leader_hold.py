"""How often does whoever leads after night N go on to take a seat / win? Current rules, 1000 games."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import survivors_sim as S  # noqa: E402

rules = S.load_game_rules(S.DEFAULT_GAME)[0]
GAMES = 1000
for check in (3, 5, 7):
    seat = win = n = survivors_seat = 0
    for seed in range(1, GAMES + 1):
        g = S.Game(rules, seed)
        for _ in range(check):
            g.play_night()
        alive = [p for p in g.players if not p.bandit]
        top = max(p.rations for p in alive)
        leaders = {p.pid for p in alive if p.rations == top}
        for _ in range(rules.rounds - check):
            g.play_night()
        res = g.finish()
        ext = {p.pid for p in res["extracted"]}
        wins = {p.pid for p in res["winners"]}
        seat += len(leaders & ext) / len(leaders)
        win += len(leaders & wins) / len(leaders)
        survivors_seat += res["seats"] / max(1, len([p for p in alive]))
        n += 1
    print(f"leader after night {check}: takes a seat {seat / n:.0%}, wins {win / n:.0%} "
          f"(a random player wins {1 / rules.players:.0%}; seats per player alive then: {survivors_seat / n:.0%})")
