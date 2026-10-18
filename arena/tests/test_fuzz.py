"""Random everything: actions in any order, at any time, legal or not. A room must never crash and must always end.

The count of games is chosen (300), not derived; each runs in milliseconds on the fake clock.
"""
import random
import unittest

from arena.room import FakeScheduler, RoomGame, RoomSettings
from bot.core import GameError
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from bot.tests.test_core_fixtures import _official

ALIASES = [f"Alias{i:02d}" for i in range(30)]
KINDS = ("scavenge", "steal", "guard", "investigate", "gift", "teleport", "")


class Fuzz(unittest.TestCase):
    def test_random_actions_never_crash_and_every_game_ends(self):
        for seed in range(300):
            rng = random.Random(seed)
            store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
            sched = FakeScheduler()
            make = lambda: RoomGame(_official(), store, ident, texts, ALIASES, f"fuzz-{seed}", sched,   # noqa: E731
                                    RoomSettings(ranges=rng.random() < 0.5))
            g = make()
            humans = rng.randint(1, 4)
            for i in range(humans):
                g.add_human(f"u{i}")
            g.start()
            steps = 0
            while not g.finished:
                steps += 1
                self.assertLess(steps, 5000, f"seed {seed}: the game did not end")
                pid = rng.randrange(humans)
                act = rng.random()
                try:
                    if act < 0.3:
                        names = [p.name for p in g.players.values()] + ["Nobody", ""]
                        g.pick(pid, rng.choice(KINDS), rng.choice(names) if rng.random() < 0.7 else None,
                               rng.choice([0, 1, 2, -1, 99]))
                    elif act < 0.45:
                        g.lock(pid)
                    elif act < 0.55:
                        g.continue_(pid)
                    elif act < 0.62:
                        g.connect(pid)
                    elif act < 0.69:
                        g.disconnect(pid)
                    elif act < 0.71:
                        g.leave_seat(f"u{pid}")
                    elif act < 0.73:
                        g.record_radio(f"u{pid}", rng.choice(["me", "trust", "nonsense"]),
                                       rng.choice([p.name for p in g.players.values()]))
                    elif act < 0.75:
                        sched._q = []                     # the old process dies, and its timers with it
                        g = make()                        # the server restarts on the same log
                    else:
                        sched.advance(sched.now() + rng.choice([0, 0.5, 5, 40, 200]))
                except GameError:
                    pass
            nights = [r["night"] for r in store.records if r["type"] == "night"]
            self.assertEqual(nights, list(range(1, 11)), f"seed {seed}: each night exactly once, in order")
            self.assertEqual(sum(r["type"] == "finish" for r in store.records), 1)


class Quarantine(unittest.TestCase):
    def test_a_room_whose_log_will_not_load_is_skipped_and_the_others_load(self):
        import json
        import os
        import shutil
        import tempfile
        from arena.server import Server
        data = tempfile.mkdtemp(prefix="arena-q-")
        try:
            s = Server(data, scheduler=FakeScheduler())
            s.load()
            for code in ("GOOD", "BADD"):
                from arena.server import Room
                room = Room(code, os.path.join(data, "rooms", code), s.sched, RoomSettings())
                room.game.add_human("t:x")
                room.game.start()
            with open(os.path.join(data, "rooms", "BADD", "log.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"type": "night", "night": 1, "moves": {}, "events": [{"type": "forged"}],
                                    "private": {}, "seed": 0}) + "\n")
            s2 = Server(data, scheduler=FakeScheduler())
            with self.assertLogs("arena.server", level="ERROR"):
                s2.load()
            self.assertEqual(sorted(s2.rooms), ["GOOD"])
        finally:
            shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
