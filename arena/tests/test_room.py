"""A live room's rounds, written to break it: races, stale timers, double taps, disconnects, crashes and restarts."""
import random
import unittest

from arena.room import FakeScheduler, RoomGame, RoomSettings
from bot.core import GameError
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from bot.tests.test_core_fixtures import _official

ALIASES = [f"Alias{i:02d}" for i in range(30)]
S = RoomSettings()                     # 180 s rounds, 20 s reveal, 30 s grace, bots lock at 5..60 s


def room(store=None, ident=None, texts=None, t=0.0, settings=S, sched=None):
    sched = sched or FakeScheduler(t)
    g = RoomGame(_official(), store or MemoryEventStore(), ident or MemoryIdentityStore(),
                 texts or MemoryTextStore(), ALIASES, "secret-salt", sched, settings)
    return g, sched


def seated(humans=1, settings=S):
    store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
    g, sched = room(store, ident, texts, settings=settings)
    pids = []
    for i in range(humans):
        g.add_human(f"u{i}")
        pids.append(ident.get(f"u{i}")["pid"])
    for p in pids:
        g.connect(p)
    g.start()
    return g, sched, pids, (store, ident, texts)


def records(g, t):
    return [r for r in g.store.records if r["type"] == t]


def pick_any(g, pid):
    moves, amounts = g.legal_for(pid)
    kind = "scavenge" if "scavenge" in moves else sorted(moves)[0]
    tgt = moves[kind][0] if moves[kind] else None
    g.pick(pid, kind, tgt, amounts[0] if kind == "gift" else 0)


class Lifecycle(unittest.TestCase):
    def test_bots_fill_the_room_to_four_and_round_one_opens(self):
        g, sched, pids, _ = seated(1)
        self.assertEqual(len(g.players), 4)
        self.assertEqual(len(g.sims), 3)
        self.assertEqual(g.phase, "round")
        self.assertEqual(records(g, "round_open")[0]["deadline"], 180.0)

    def test_everyone_locking_fast_ends_each_round_early_and_the_game_finishes(self):
        g, sched, pids, _ = seated(2)
        for n in range(1, 11):
            for p in pids:
                if p not in g.quit_ids:
                    pick_any(g, p)
            sched.advance(sched.now() + 1)
            for p in pids:
                g.lock(p)
            self.assertEqual(g.close_reason, "all_locked", f"round {n}")
            for p in pids:
                g.continue_(p)
        self.assertTrue(g.finished)
        self.assertEqual(len(records(g, "night")), 10)
        self.assertEqual(len(records(g, "finish")), 1)
        self.assertLess(sched.now(), 10 * 180, "early advance should beat ten full timers")

    def test_nobody_locking_runs_on_the_timer_and_missed_moves_auto_scavenge(self):
        g, sched, pids, _ = seated(1)
        sched.advance(180)
        self.assertEqual(g.close_reason, "timeout")
        night = records(g, "night")[0]
        self.assertEqual(night["moves"][str(pids[0])][0], "scavenge")
        self.assertTrue(night["moves"][str(pids[0])][3], "auto flag: the player never chose")

    def test_an_unlocked_pick_still_counts_at_the_timer(self):
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "guard")
        sched.advance(180)
        self.assertEqual(records(g, "night")[0]["moves"][str(pids[0])][:2], ["guard", None])

    def test_full_game_on_timers_alone_finishes(self):
        g, sched, pids, _ = seated(1)
        sched.advance(10 * (180 + 20) + 5)
        self.assertTrue(g.finished)
        self.assertEqual([r["reason"] for r in records(g, "round_closed")], ["timeout"] * 10)


class LockRules(unittest.TestCase):
    def test_lock_without_a_pick_is_refused(self):
        g, _, pids, _ = seated(2)
        with self.assertRaisesRegex(GameError, "Pick a move"):
            g.lock(pids[0])

    def test_pick_after_lock_and_double_lock_are_refused_and_change_nothing(self):
        g, _, pids, _ = seated(2)
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])
        before = list(g.store.records)
        with self.assertRaisesRegex(GameError, "locked in"):
            g.pick(pids[0], "guard")
        with self.assertRaisesRegex(GameError, "already locked"):
            g.lock(pids[0])
        self.assertEqual(g.store.records, before)
        self.assertEqual(g.moves[pids[0]][0], "scavenge")

    def test_changing_your_mind_before_lock_keeps_the_last_pick(self):
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "guard")
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])
        self.assertEqual(records(g, "night")[0]["moves"][str(pids[0])][0], "scavenge")

    def test_actions_in_the_wrong_phase_are_refused(self):
        g, sched, pids, _ = seated(1)
        with self.assertRaises(GameError):
            g.continue_(pids[0])                      # no reveal yet
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])
        self.assertEqual(g.phase, "reveal")
        with self.assertRaises(GameError):
            g.pick(pids[0], "guard")
        with self.assertRaises(GameError):
            g.lock(pids[0])

    def test_lobby_refuses_a_fifth_human_and_a_second_start(self):
        g, _ = room()
        for i in range(4):
            g.add_human(f"u{i}")
        with self.assertRaisesRegex(GameError, "full"):
            g.add_human("u4")
        g.start()
        with self.assertRaises(GameError):
            g.start()
        self.assertEqual(len(g.sims), 0, "a full room needs no bots")


class Races(unittest.TestCase):
    def test_timer_and_last_lock_in_the_same_instant_resolve_exactly_once(self):
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "scavenge")
        sched.advance(180)                            # the timer fires at 180
        with self.assertRaises(GameError):
            g.lock(pids[0])                           # a lock arriving at 180 is too late
        self.assertEqual(len(records(g, "night")), 1)
        self.assertEqual(len(records(g, "round_closed")), 1)

    def test_a_stale_timer_after_early_close_does_nothing(self):
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])                               # round 1 closes at t=0
        g.continue_(pids[0])                          # round 2 opens at t=0, deadline 180
        sched.advance(180)                            # round 1's old timer (180) and round 2's timer both due
        self.assertEqual([r["round"] for r in records(g, "round_closed")], [1, 2])
        self.assertEqual(len(records(g, "night")), 2)

    def test_closing_a_round_leaves_none_of_its_timers_live(self):
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])
        live = [h for h in sched._q if h[3]]
        self.assertEqual(len(live), 1, "only the reveal timer is left")

    def test_a_timer_that_slips_past_cancellation_still_does_nothing(self):
        """Second layer: even if an old round's callback ran, it must not touch the new round."""
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])
        g.continue_(pids[0])                          # round 2 is open
        before = list(g.store.records)
        g._timeout(1)
        for pid in g.sims:
            g._bot_lock(1, pid)
        self.assertEqual(g.store.records, before)
        self.assertEqual(g.phase, "round")

    def test_bot_lock_timers_from_a_closed_round_never_lock_the_next_round(self):
        g, sched, pids, _ = seated(1)
        g.pick(pids[0], "scavenge")
        g.lock(pids[0])
        g.continue_(pids[0])
        sched.advance(61)                             # every round-1 bot timer would have fired by now
        r2 = [r for r in records(g, "lock") if r["round"] == 2]
        self.assertEqual(sorted(r["pid"] for r in r2), sorted(g._bot_lock_times(2)),
                         "only round 2's own bot timers lock round 2")


class Presence(unittest.TestCase):
    def test_a_disconnected_player_blocks_until_the_grace_then_stops_blocking(self):
        g, sched, (a, b), _ = seated(2)
        g.disconnect(b)
        g.pick(a, "scavenge")
        g.lock(a)
        self.assertEqual(g.phase, "round", "b is inside the grace period: still waited for")
        sched.advance(S.grace + 0.01)
        self.assertEqual(g.close_reason, "all_locked")

    def test_an_empty_room_waits_for_the_timer(self):
        g, sched, (a,), _ = seated(1)
        g.disconnect(a)
        sched.advance(S.grace + 5)
        self.assertEqual(g.phase, "round", "nobody connected: no early advance")
        sched.advance(180)
        self.assertEqual(g.close_reason, "timeout")

    def test_lock_then_disconnect_keeps_the_lock(self):
        g, sched, (a, b), _ = seated(2)
        g.pick(a, "guard")
        g.lock(a)
        g.disconnect(a)
        g.pick(b, "scavenge")
        g.lock(b)
        self.assertEqual(records(g, "night")[0]["moves"][str(a)][0], "guard")

    def test_leaving_mid_round_unblocks_the_others(self):
        g, sched, (a, b), _ = seated(2)
        g.pick(a, "scavenge")
        g.lock(a)
        self.assertEqual(g.phase, "round")
        g.leave_seat("u1")
        self.assertEqual(g.close_reason, "all_locked")


class Bots(unittest.TestCase):
    def test_bots_lock_like_people_every_round(self):
        g, sched, pids, _ = seated(1)
        sched.advance(10 * (180 + 20) + 5)
        for n in range(1, 11):
            locked = {r["pid"] for r in records(g, "lock") if r["round"] == n}
            self.assertEqual(locked, set(g.sims), f"round {n}: every bot locked")

    def test_bot_lock_times_are_inside_the_round_and_differ_between_rounds(self):
        g, sched, pids, _ = seated(1)
        t1 = g._bot_lock_times(1)
        self.assertTrue(all(S.bot_lock_min <= t <= S.bot_lock_max for t in t1.values()))
        sched.advance(200)
        self.assertNotEqual(sorted(g._bot_lock_times(2).values()), sorted(t + 200 for t in t1.values()))


class Restart(unittest.TestCase):
    @staticmethod
    def _round(g, sched, pids, rng):
        """One round of a fixed script: some pick, all who picked lock after 30 s, then run to the next round."""
        assert g.phase == "round"
        for p in pids:
            if rng.random() < 0.7:
                pick_any(g, p)
        sched.advance(sched.now() + 30)
        for p in pids:
            if p in g.moves and g.phase == "round":
                g.lock(p)
        if g.phase == "round":
            sched.advance(g.deadline)
        sched.advance(g.reveal_until)

    def test_a_restart_mid_game_gives_the_same_game_as_no_restart(self):
        g1, s1, p1, _ = seated(2)
        rng = random.Random(5)
        for _ in range(10):
            self._round(g1, s1, p1, rng)
        self.assertTrue(g1.finished)
        g2, s2, p2, (store, ident, texts) = seated(2)
        rng = random.Random(5)
        for _ in range(3):
            self._round(g2, s2, p2, rng)
        g3, s3 = room(store, ident, texts, sched=FakeScheduler(s2.now()))    # the server came back
        for p in p2:
            g3.connect(p)
        for _ in range(7):
            self._round(g3, s3, p2, rng)
        self.assertTrue(g3.finished)
        self.assertEqual(records(g3, "finish")[0]["events"], records(g1, "finish")[0]["events"])

    def test_restart_after_the_deadline_passed_closes_the_round_on_load(self):
        g, sched, pids, (store, ident, texts) = seated(1)
        g2, s2 = room(store, ident, texts, t=500)      # down through the whole round
        self.assertEqual(g2.close_reason, "timeout")
        self.assertEqual(len(records(g2, "night")), 1)

    def _crash_after_close(self, keep_radio):
        """Close round 1 (with bot radio lines written before the night), then lose the tail of the log."""
        for seed in range(40):                           # find a game where a bot posts radio on night 1
            store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
            sched = FakeScheduler()
            g = RoomGame(_official(), store, ident, texts, ALIASES, f"salt-{seed}", sched, S)
            g.add_human("u0")
            g.connect(0)
            g.start()
            g.pick(0, "scavenge")
            g.lock(0)
            closed = max(i for i, r in enumerate(store.records) if r["type"] == "round_closed")
            night_i = next(i for i, r in enumerate(store.records) if r["type"] == "night")
            if night_i > closed + 1:
                break
        else:
            self.fail("no seed gave a bot radio line on night 1")
        full = list(store.records)
        lost = store.records[night_i]
        radios = [r for r in store.records[closed + 1:night_i] if r["type"] == "radio"]
        store.records = store.records[:night_i if keep_radio else closed + 1]
        g2 = RoomGame(_official(), store, ident, texts, ALIASES, f"salt-{seed}", FakeScheduler(1), S)
        return g2, lost, radios, full

    def test_crash_after_round_closed_before_any_radio_is_repaired_on_load(self):
        g2, lost, radios, full = self._crash_after_close(keep_radio=False)
        self.assertTrue(radios)
        self.assertEqual(records(g2, "night")[0]["events"], lost["events"], "the repaired night is the same night")
        self.assertEqual(records(g2, "radio"), radios, "the bots' radio is written again, identically")

    def test_crash_between_the_radio_lines_and_the_night_repairs_without_double_radio(self):
        g2, lost, radios, full = self._crash_after_close(keep_radio=True)
        self.assertTrue(radios)
        self.assertEqual(records(g2, "night")[0]["events"], lost["events"])
        self.assertEqual(records(g2, "radio"), radios, "no radio line twice")

    def test_crash_between_start_and_round_one_opens_round_one_on_load(self):
        g, sched, pids, (store, ident, texts) = seated(1)
        cut = next(i for i, r in enumerate(store.records) if r["type"] == "round_open")
        store.records = store.records[:cut]
        g2, _ = room(store, ident, texts, t=3)
        self.assertEqual(g2.phase, "round")
        self.assertEqual(g2.round, 1)

    def test_settings_come_from_the_start_record_not_the_constructor(self):
        g, sched, pids, (store, ident, texts) = seated(1, settings=RoomSettings(timer=60))
        g2, _ = room(store, ident, texts, t=1, settings=RoomSettings(timer=999))
        self.assertEqual(g2.settings.timer, 60)


if __name__ == "__main__":
    unittest.main()
