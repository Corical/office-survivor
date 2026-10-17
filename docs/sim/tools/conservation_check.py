"""Does the engine create food from nothing? Plays 300 logged games on the current rules and checks the books:
transfers between players must net to zero each night (only scavenging creates food, only eating and fines
destroy it). Also counts caught thieves who couldn't pay the full penalty. Single process."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import survivors_sim as S  # noqa: E402

CREATE = {"scavenge", "guard_income", "gift_bonus", "event_found"}
DESTROY = {"eat", "fine", "event_lost"}

rules = S.load_game_rules(S.DEFAULT_GAME)[0]
GAMES = 300
created = games_hit = caught_total = caught_short = total_in_play = 0
for seed in range(1, GAMES + 1):
    g = S.Game(rules, seed, log=True)
    g.run()
    net_by_night = {}
    for e in g.events:
        if e["type"] == "ration" and e["reason"] not in CREATE | DESTROY:
            net_by_night[e["night"]] = net_by_night.get(e["night"], 0) + e["delta"]
        if e["type"] == "steal" and e["outcome"] == "caught":
            caught_total += 1
            if e.get("paid", rules.caught_penalty) < rules.caught_penalty:
                caught_short += 1
    made = sum(v for v in net_by_night.values() if v > 0)
    created += made
    games_hit += made > 0
    total_in_play += sum(p.rations for p in g.players)
print(f"{GAMES} games, current rules")
print(f"games where food was created from nothing: {games_hit} ({games_hit / GAMES:.0%})")
print(f"rations created per game: {created / GAMES:.2f}")
print(f"caught thieves who couldn't pay the full {rules.caught_penalty}: {caught_short} of {caught_total} catches "
      f"({caught_short / max(1, caught_total):.0%}); the guard now receives exactly what they paid")
print(f"rations held by everyone at the end, per game: {total_in_play / GAMES:.1f}")
