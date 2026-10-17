"""History and Hall of Fame: aliases tie back to people only for finished seasons, sims are left out, awards are
praise only and shared on ties, and a period filter really filters.

    python -m unittest discover -s bot/tests -t .
"""
import json
import os
import random
import tempfile
import unittest

from bot import hall
from bot.game import GameService
from bot.store import JsonlEventStore, IdentityStore, TextStore
from engine import Rules

ALIASES = [f"Alias{i:02d}" for i in range(30)]


def play(folder, humans, seed, finish=True, start_ts=0):
    os.makedirs(folder, exist_ok=True)
    g = GameService(Rules(), JsonlEventStore(os.path.join(folder, "season.jsonl")),
                    IdentityStore(os.path.join(folder, "identity.json")), TextStore(os.path.join(folder, "texts.json")),
                    ALIASES, f"s{seed}", clock=lambda: start_ts)
    for n, h in enumerate(humans):
        g.join(h, rng=random.Random(seed * 10 + n))
    g.gm_add_sims(6, rng=random.Random(seed))
    g.gm_start(day_seconds=300, now=start_ts)
    for night in range(1, 11 if finish else 4):
        for h in humans:
            menu = g.play_menu(h)["moves"]
            kind = random.Random(seed + night).choice([k for k in menu if k != "gift"])
            g.submit(h, kind, menu[kind][0] if menu[kind] else None, at=start_ts + night * 300 - 5)
        g.tick(now=start_ts + night * 300 + 10)
    if finish:
        g.tick(now=start_ts + 5000)
    return g


class Hall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # two finished archived seasons, and a current season still running
        self.g1 = play(os.path.join(self.tmp, "archive-1"), ["alice", "bob"], 1, start_ts=1000)
        self.g2 = play(os.path.join(self.tmp, "archive-2"), ["alice", "carol"], 2, start_ts=90000)
        self.live = play(self.tmp, ["alice", "bob"], 3, finish=False, start_ts=200000)

    def test_only_finished_seasons_link_aliases_to_people(self):
        seasons = hall.load_seasons(self.tmp)
        self.assertEqual(len(seasons), 2)                        # the running season is not there
        live_alias = self.live.identity.get("alice")["alias"]
        self.assertNotIn(live_alias, [r["alias"] for r in hall.history(seasons, "alice")
                                      if r["season"] == "s3"])
        self.assertEqual({r["season"] for r in hall.history(seasons, "alice")}, {"s1", "s2"})
        self.assertEqual([r["alias"] for r in hall.history(seasons, "alice")],
                         [self.g2.identity.get("alice")["alias"], self.g1.identity.get("alice")["alias"]])

    def test_sims_are_not_people(self):
        keys = {r["key"] for s in hall.load_seasons(self.tmp) for r in s}
        self.assertEqual(keys, {"alice", "bob", "carol"})

    def test_totals_match_the_reveal_and_the_period_filter_filters(self):
        seasons = hall.load_seasons(self.tmp)
        t = hall.totals(seasons)
        self.assertEqual(t["alice"]["games"], 2)
        a1 = self.g1.players[self.g1.identity.get("alice")["pid"]]
        a2 = self.g2.players[self.g2.identity.get("alice")["pid"]]
        self.assertEqual(t["alice"]["points"], a1.score + a2.score)
        self.assertEqual(t["alice"]["stolen"], a1.rations_stolen + a2.rations_stolen)
        recent = hall.totals(seasons, since=50000)              # only season 2
        self.assertEqual(recent["alice"]["games"], 1)
        self.assertNotIn("bob", recent)

    def test_awards_are_praise_only_shared_on_ties_and_skip_zeros(self):
        tot = {"a": dict.fromkeys(hall.TOTALS, 0), "b": dict.fromkeys(hall.TOTALS, 0)}
        tot["a"].update(games=2, won=1, stolen=4, given=0)
        tot["b"].update(games=2, won=1, stolen=2, given=0)
        aw = {meaning: (keys, v) for _, _, meaning, keys, v in hall.hall_of_fame(tot)}
        self.assertEqual(aw["most wins"], (["a", "b"], 1))
        self.assertEqual(aw["most rations stolen"], (["a"], 4))
        self.assertNotIn("most rations given away", aw)                  # nobody gave: no award, no "0" winner
        titles = " ".join(aw).lower()
        for banned in ("robbed", "bandit", "caught", "victim", "starv"):
            self.assertNotIn(banned, titles)

    def test_a_torn_last_line_does_not_crash_the_hall(self):
        with open(os.path.join(self.tmp, "season.jsonl"), "a", encoding="utf-8") as f:
            f.write('{"type": "mov')
        self.assertEqual(len(hall.load_seasons(self.tmp)), 2)


if __name__ == "__main__":
    unittest.main()
