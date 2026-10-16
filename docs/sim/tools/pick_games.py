"""Scan seeds, pick a typical game and a dramatic game, write their replay logs."""
import json
import os
import sys

SIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(SIM, "results", "replays")
sys.path.insert(0, SIM)
import survivors_sim as S  # noqa: E402

rules = S.load_game_rules(S.DEFAULT_GAME)[0]
rows = []
for seed in range(1, 301):
    g = S.Game(rules, seed)
    res = g.run()
    ev = {k: sum(n.get(k, 0) for n in g.night_stats) for k in ("caught", "exposed", "comeback", "death", "robbed", "gift")}
    rows.append(dict(seed=seed, alive=sum(not p.bandit for p in g.players), coin=res["coin_flip"], **ev))

# typical: close to the 100-game averages (alive 10.9, robberies ~19, deaths ~5) and shows each mechanic once
def typical_dist(r):
    return abs(r["alive"] - 11) * 2 + abs(r["robbed"] - 19) / 3 + abs(r["death"] - 5) \
        + (0 if r["caught"] >= 1 else 5) + (0 if r["exposed"] >= 1 else 5) + (0 if r["comeback"] >= 1 else 5) \
        + (0 if r["gift"] >= 1 else 5)
typical = min(rows, key=typical_dist)
drama = max((r for r in rows if r["seed"] != typical["seed"]),
            key=lambda r: r["caught"] * 2 + r["exposed"] * 2 + r["comeback"] * 2 + r["coin"] * 3)
print("typical", typical)
print("drama  ", drama)
for label, r in (("typical", typical), ("drama", drama)):
    g = S.Game(rules, r["seed"], log=True)
    g.run()
    with open(os.path.join(OUT, f"game_{label}_seed{r['seed']}.jsonl"), "w", encoding="utf-8") as f:
        for e in g.events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
