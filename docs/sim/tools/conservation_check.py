"""How much food the engine creates from nothing: rations a guard receives that the caught thief never paid,
and thefts taken from a victim whose loss was capped. Current rules, logged games, single process."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import survivors_sim as S  # noqa: E402

rules = S.load_game_rules(S.DEFAULT_GAME)[0]
GAMES = 300
created, games_hit, caught_total, caught_short, total_in_play = 0, 0, 0, 0, 0
for seed in range(1, GAMES + 1):
    g = S.Game(rules, seed, log=True)
    g.run()
    made = 0
    for e in g.events:
        if e["type"] == "ration" and "requested" in e:
            made += e["requested"] - (-e["delta"])           # owed but not paid, yet credited to someone
            if e["reason"] == "caught_penalty":
                caught_short += 1
        if e["type"] == "steal" and e["outcome"] == "caught":
            caught_total += 1
    created += made
    games_hit += made > 0
    total_in_play += sum(p.rations for p in g.players)
print(f"{GAMES} games, current rules")
print(f"games where food was created from nothing: {games_hit} ({games_hit / GAMES:.0%})")
print(f"rations created per game: {created / GAMES:.2f}")
print(f"caught thieves who couldn't pay in full: {caught_short} of {caught_total} catches ({caught_short / max(1, caught_total):.0%})")
print(f"rations held by everyone at the end, per game: {total_in_play / GAMES:.1f}")
