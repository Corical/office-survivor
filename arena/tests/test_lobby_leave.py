"""Giving a seat back in the lobby, written to break it: the pids must stay exactly 0..n-1 (the sim brain indexes lists by
pid), a leaver's token must never reach the person who got the seat, replay, a leave after the start, a crash between the
log line and the identity write, and whole 10-round games after leaves."""
import random
import unittest

from arena.room import FakeScheduler, RoomGame
from bot.core import GameError
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from bot.tests.test_core_fixtures import _official

from .test_room import ALIASES, S, pick_any, records


def make(salt="secret-salt", store=None, ident=None, texts=None, sched=None, settings=S):
    store, ident, texts = store or MemoryEventStore(), ident or MemoryIdentityStore(), texts or MemoryTextStore()
    sched = sched or FakeScheduler(0.0)
    return RoomGame(_official(), store, ident, texts, ALIASES, salt, sched, settings), (store, ident, texts), sched


def pids_of(g):
    return [j[0] for j in g.joined]


class GivingASeatBack(unittest.TestCase):
    def test_the_seat_is_free_the_identity_is_gone_and_the_log_says_so(self):
        g, (store, ident, _), _ = make()
        for k in ("u0", "u1", "u2"):
            g.add_human(k)
        g.leave_lobby("u1")
        self.assertEqual(pids_of(g), [0, 2])
        self.assertIsNone(ident.get("u1"))
        self.assertEqual(len(records(g, "left_lobby")), 1)

    def test_the_freed_pid_goes_to_the_next_person_and_the_leavers_token_does_not_come_with_it(self):
        g, (_, ident, _), _ = make()
        for k in ("u0", "u1", "u2"):
            g.add_human(k)
        old_alias = ident.get("u1")["alias"]
        g.leave_lobby("u1")
        g.add_human("u3")
        self.assertEqual(pids_of(g), [0, 1, 2], "the newcomer takes the free pid: pids stay 0..n-1")
        self.assertIsNone(ident.get("u1"), "the leaver's key must not resolve to the newcomer's seat")
        self.assertEqual(ident.get("u3")["pid"], 1)
        with self.assertRaises(GameError):
            g.leave_lobby("u1")                          # and the old key can not act as the newcomer
        self.assertEqual(pids_of(g), [0, 1, 2])
        self.assertTrue(old_alias)

    def test_a_long_random_walk_keeps_pids_unique_and_below_the_seat_count_and_the_start_makes_them_zero_to_three(self):
        """Before the start pids may have gaps (the bots fill them); each join takes the lowest free one; at the start the
        roster is exactly 0..3, which is what the engine needs. 400 random joins and leaves, several seeds."""
        for seed in range(8):
            rng = random.Random(seed)
            g, (_, ident, _), _ = make(salt=f"s{seed}")
            live = []
            for i in range(400):
                if live and (len(live) == 4 or rng.random() < 0.45):
                    g.leave_lobby(live.pop(rng.randrange(len(live))))
                else:
                    free = min(set(range(4)) - set(pids_of(g)))
                    g.add_human(f"u{seed}-{i}")
                    live.append(f"u{seed}-{i}")
                    self.assertEqual(ident.get(live[-1])["pid"], free, f"seed {seed} step {i}: not the lowest free pid")
                pids = pids_of(g)
                self.assertEqual(len(pids), len(set(pids)), "pids unique")
                self.assertTrue(all(0 <= p < 4 for p in pids), f"seed {seed} step {i}: {pids}")
                self.assertEqual(pids, sorted(pids), "joined stays in pid order")
                names = [j[1] for j in g.joined]
                self.assertEqual(len(names), len(set(names)), "aliases stay unique")
                for key in live:                         # every live key maps to the seat that carries its alias
                    me = ident.get(key)
                    self.assertEqual(next(j[1] for j in g.joined if j[0] == me["pid"]), me["alias"])
                self.assertEqual(len(ident.data), len(live), "no stale identity is left behind")
            if live:
                for p in pids_of(g):
                    g.connect(p)
                g.start()
                self.assertEqual(sorted(g.players), [0, 1, 2, 3], f"seed {seed}")

    def test_leaving_twice_or_as_a_stranger_is_refused_and_logs_nothing_more(self):
        g, _, _ = make()
        g.add_human("u0")
        g.add_human("u1")
        g.leave_lobby("u1")
        for who in ("u1", "never-joined"):
            with self.assertRaises(GameError):
                g.leave_lobby(who)
        self.assertEqual(len(records(g, "left_lobby")), 1)
        self.assertEqual(pids_of(g), [0])

    def test_after_the_start_it_is_refused_and_changes_nothing(self):
        g, (store, ident, _), _ = make()
        g.add_human("u0")
        g.connect(0)
        g.start()
        before = len(store.records)
        with self.assertRaises(GameError):
            g.leave_lobby("u0")
        self.assertEqual(len(store.records), before)
        self.assertIsNotNone(ident.get("u0"))

    def test_a_full_room_takes_a_newcomer_after_a_leave_and_then_refuses_the_next(self):
        g, _, _ = make()
        for k in ("u0", "u1", "u2", "u3"):
            g.add_human(k)
        with self.assertRaises(GameError):
            g.add_human("u4")
        g.leave_lobby("u2")
        g.add_human("u4")
        with self.assertRaises(GameError):
            g.add_human("u5")
        self.assertEqual(pids_of(g), [0, 1, 2, 3])

    def test_every_change_is_pushed_to_the_listeners(self):
        g, _, _ = make()
        seen = []
        g.listeners.append(seen.append)
        g.add_human("u0")
        g.leave_lobby("u0")
        self.assertIn("left_lobby", seen)

    def test_an_empty_lobby_can_not_start(self):
        g, _, _ = make()
        g.add_human("u0")
        g.leave_lobby("u0")
        with self.assertRaises(GameError):
            g.start()
        self.assertFalse(g.started)

    def test_the_roster_is_zero_to_three_with_the_bots_in_the_freed_places(self):
        g, _, _ = make()
        for k in ("u0", "u1", "u2"):
            g.add_human(k)
        g.leave_lobby("u1")
        for pid in pids_of(g):
            g.connect(pid)
        g.start()
        self.assertEqual(sorted(g.players), [0, 1, 2, 3])
        self.assertEqual(g.sims, {1, 3}, "the bots take the free pids: the freed 1 and the next, 3")
        self.assertEqual(g.humans(), [0, 2])


class Replay(unittest.TestCase):
    def test_a_reload_gives_the_same_room_and_the_next_join_still_takes_the_free_pid(self):
        g, (store, ident, texts), sched = make()
        for k in ("u0", "u1", "u2"):
            g.add_human(k)
        g.leave_lobby("u1")
        g2, _, _ = make(store=store, ident=ident, texts=texts, sched=sched)
        self.assertEqual(g2.joined, g.joined)
        g2.add_human("u3")
        self.assertEqual(pids_of(g2), [0, 1, 2])

    def test_a_pid_given_back_and_handed_out_again_replays_in_order(self):
        g, (store, ident, texts), sched = make()
        for k in ("u0", "u1"):
            g.add_human(k)
        g.leave_lobby("u0")
        g.add_human("u2")                                 # takes pid 0 again
        g.leave_lobby("u1")
        g.add_human("u3")                                 # takes pid 1 again
        g2, _, _ = make(store=store, ident=ident, texts=texts, sched=sched)
        self.assertEqual(g2.joined, g.joined)
        self.assertEqual(pids_of(g2), [0, 1])

    def test_an_identity_left_behind_by_a_crash_is_cleaned_on_load(self):
        """Crash between the log line and the identity write: the log says u1 left, the identity file still has u1."""
        g, (store, ident, texts), sched = make()
        for k in ("u0", "u1"):
            g.add_human(k)
        snapshot = {k: dict(v) for k, v in ident.data.items()}
        g.leave_lobby("u1")
        ident.data.clear()
        ident.data.update(snapshot)                       # the write that never happened
        g2, _, _ = make(store=store, ident=ident, texts=texts, sched=sched)
        self.assertIsNone(ident.get("u1"))
        self.assertIsNotNone(ident.get("u0"))
        self.assertEqual(pids_of(g2), [0])

    def test_a_stale_identity_on_a_pid_someone_else_now_holds_is_removed_not_inherited(self):
        """Same pid, different alias: the stale key must not be able to act as the new holder."""
        g, (store, ident, texts), sched = make()
        for k in ("u0", "u1"):
            g.add_human(k)
        stale = dict(ident.get("u1"))
        g.leave_lobby("u1")
        g.add_human("u2")                                 # takes pid 1
        ident.data["u1"] = {**stale, "alias": "SomeoneElse"}
        g2, _, _ = make(store=store, ident=ident, texts=texts, sched=sched)
        self.assertIsNone(ident.get("u1"))
        self.assertEqual(ident.get("u2")["pid"], 1)


class WholeGamesAfterLeaves(unittest.TestCase):
    """Whole games after leaves, which an earlier design (a pid counter) broke: the sim brain indexes by pid."""

    @staticmethod
    def _play(g, sched, humans, rounds=10):
        for n in range(1, rounds + 1):
            for p in humans:
                pick_any(g, p)
            sched.advance(sched.now() + 1)
            for p in humans:
                g.lock(p)
            for p in humans:
                g.continue_(p)

    SHAPES = {
        "swap-two": (["a", "b", "c", "d"], ["b", "c"], ["e", "f"]),
        "most-leave": (["a", "b", "c"], ["a", "b"], []),
        "first-leaves": (["a", "b", "c"], ["a"], []),
        "leave-and-rejoin-same-slot": (["a", "b"], ["a"], ["c"]),
        "all-leave-then-one-joins": (["a", "b"], ["a", "b"], ["c"]),
    }

    def _scenario(self, salt, shape):
        joins, leaves, rejoins = self.SHAPES[shape]
        g, mem, sched = make(salt=salt)
        for k in joins:
            g.add_human(k)
        for k in leaves:
            g.leave_lobby(k)
        for k in rejoins:
            g.add_human(k)
        humans = pids_of(g)
        for p in humans:
            g.connect(p)
        g.start()
        return g, mem, sched, humans

    def test_ten_rounds_finish_and_a_restart_replays_to_the_same_game(self):
        for shape in self.SHAPES:
            for salt in ("s1", "s2", "s3", "s4", "s5", "s6"):
                with self.subTest(shape=shape, salt=salt):
                    g, (store, ident, texts), sched, humans = self._scenario(salt, shape)
                    self.assertEqual(sorted(g.players), [0, 1, 2, 3])
                    self._play(g, sched, humans)
                    self.assertTrue(g.finished)
                    self.assertEqual(len(records(g, "night")), 10)
                    g2, _, _ = make(salt=salt, store=store, ident=ident, texts=texts, sched=sched)
                    self.assertTrue(g2.finished)
                    self.assertEqual({p: s.rations for p, s in g2.players.items()},
                                     {p: s.rations for p, s in g.players.items()})
                    self.assertEqual(g2.joined, g.joined)

    def test_a_mid_game_restart_after_leaves_gives_the_same_game(self):
        g, (store, ident, texts), sched, humans = self._scenario("s1", "swap-two")
        self._play(g, sched, humans, rounds=3)
        g2, _, _ = make(salt="s1", store=store, ident=ident, texts=texts, sched=sched)
        self.assertEqual(g2.round, g.round)
        self.assertEqual({p: s.rations for p, s in g2.players.items()}, {p: s.rations for p, s in g.players.items()})

    def test_a_steal_by_alias_hits_exactly_that_alias_after_a_leave(self):
        g, _, _, humans = self._scenario("s2", "first-leaves")
        me = humans[0]
        moves, _ = g.legal_for(me)
        self.assertEqual(len(moves["steal"]), 3, "steal is offered against the other three")
        for target in moves["steal"]:
            g.pick(me, "steal", target, 0)
            self.assertEqual(g.players[g.moves[me][1]].name, target)
        self.assertNotIn(g.players[me].name, moves["steal"], "never offered yourself")


if __name__ == "__main__":
    unittest.main()
