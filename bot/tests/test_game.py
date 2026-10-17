"""Game service tests: a whole compressed game with sim colleagues, restart replay, deadline, privacy of replies.

    python -m unittest discover -s bot/tests -t .
"""
import random
import unittest

from bot.game import GameError, GameService
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from engine import Rules

ALIASES = [f"Alias{i:02d}" for i in range(30)]


def service(store=None, ident=None, texts=None):
    return GameService(Rules(), store or MemoryEventStore(), ident or MemoryIdentityStore(),
                       texts or MemoryTextStore(), ALIASES, "test-season", clock=lambda: 0)


class FullGame(unittest.TestCase):
    def test_compressed_game_with_sims_runs_to_the_reveal_and_replays(self):
        store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
        g = service(store, ident, texts)
        g.join("human-a", rng=random.Random(1))
        g.join("human-b", rng=random.Random(2))
        g.gm_add_sims(8, rng=random.Random(3))
        g.gm_start(day_seconds=300, news_delay=5, now=0)
        b_alias = ident.get("human-b")["alias"]
        for night in range(1, 11):
            g.submit("human-a", "steal", b_alias, at=night * 300 - 10)
            g.tick(now=night * 300 + 10)
        self.assertTrue(g.finished)
        self.assertTrue(any("helicopter" in g.outbox_text(i) for i in g.pending_outbox()))
        # restart: a fresh service on the same log rebuilds and re-resolves every night identically
        again = service(store, ident, texts)
        self.assertTrue(again.finished)
        self.assertEqual({p: (s.rations, s.bandit) for p, s in again.players.items()},
                         {p: (s.rations, s.bandit) for p, s in g.players.items()})

    def test_tampered_log_refuses_to_load(self):
        store = MemoryEventStore()
        g = service(store)
        g.gm_add_sims(4, rng=random.Random(1))
        g.gm_start(day_seconds=60, now=0)
        g.tick(now=61)
        night = next(r for r in store.records if r["type"] == "night")
        night["events"][0]["found" if "found" in night["events"][0] else "type"] = "tampered"
        with self.assertRaises(RuntimeError):
            service(store)


class Rules_(unittest.TestCase):
    def setUp(self):
        self.g = service()
        self.g.join("a", rng=random.Random(1))
        self.g.join("b", rng=random.Random(2))
        self.g.gm_start(day_seconds=300, now=0)

    def test_move_after_the_deadline_is_refused(self):
        with self.assertRaises(GameError):
            self.g.submit("a", "scavenge", at=300)
        self.g.submit("a", "scavenge", at=299.999)

    def test_illegal_move_is_refused_with_a_reason(self):
        me = self.g.identity.get("a")["alias"]
        with self.assertRaises(GameError) as e:
            self.g.submit("a", "steal", me, at=1)
        self.assertIn("yourself", str(e.exception))

    def test_tick_twice_resolves_once(self):
        self.g.tick(now=310)
        self.g.tick(now=310)
        self.assertEqual(sum(1 for r in self.g.store.records if r["type"] == "night"), 1)

    def test_news_intents_are_written_once_even_if_ticked_again(self):
        self.g.tick(now=310)
        self.g.tick(now=320)
        n = len([i for i in self.g.pending_outbox() if i["to"] == "news"])
        self.g.tick(now=330)
        self.assertEqual(len([i for i in self.g.pending_outbox() if i["to"] == "news"]), n)

    def test_radio_is_fixed_phrases_and_one_a_day(self):
        other = self.g.identity.get("b")["alias"]
        self.g.radio("a", "trust", other)
        self.assertEqual(self.g.texts.get(self.g.radio_pending[0]), f"Don't trust {other}.")
        with self.assertRaises(GameError):
            self.g.radio("a", "me")                       # one a day
        with self.assertRaises(GameError):
            self.g.radio("b", "trust")                    # needs a player
        with self.assertRaises(GameError):
            self.g.radio("b", "<script>")                 # only the fixed lines
        self.g.radio("b", "me")
        self.g.tick(now=310)
        self.g.tick(now=320)
        radio = [self.g.outbox_text(i) for i in self.g.pending_outbox() if i["to"] == "radio"]
        self.assertEqual(sorted(radio), sorted([f"Don't trust {other}.", "I'm innocent. Leave me alone."]))

    def test_player_list_never_offers_your_own_alias(self):
        me, other = self.g.identity.get("a")["alias"], self.g.identity.get("b")["alias"]
        self.assertNotIn(me, self.g.alias_list("a"))
        self.assertIn(other, self.g.alias_list("a"))
        self.assertIn(me, self.g.alias_list("b"))

    def test_night_labels_anchor_to_real_time(self):
        from bot.game import Schedule, night_label
        pilot = Schedule(start_ts=1792217089.8, day_seconds=300)          # 17 Oct 2026 08:04:49 SAST
        self.assertEqual(night_label(pilot, 6), "Night 6 (closes 08:34)")
        real = Schedule(start_ts=1791756000.0, day_seconds=86400)         # Mon 12 Oct 2026 00:00 SAST
        self.assertEqual(night_label(real, 1), "Night 1 (Mon)")            # closes at Tuesday 00:00: Monday's night
        self.assertEqual(night_label(real, 2), "Night 2 (Tue)")

    def test_join_closed_after_start(self):
        with self.assertRaises(GameError):
            self.g.join("late")

    def test_status_never_mentions_other_players_rations(self):
        other = self.g.identity.get("b")["alias"]
        self.assertNotIn(other, self.g.status("a").split("Secret goal")[0])


if __name__ == "__main__":
    unittest.main()
