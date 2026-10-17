"""Adversarial tests for ration visibility and human memory (docs/sim/visibility.py).

The two promises: (1) the information only reaches the AI, never the rules; (2) the defaults are today's game.
Everything below tries to break one of them: leak an exact number through a band, change a night's outcome through
what players believe, make a "forgetful" player equal a perfect one for the wrong reason, or let memory disturb the
dice that the engine and the AI share.
"""
import os
import random
import sys
import unittest
from dataclasses import fields

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "sim"))
import survivors_sim as S  # noqa: E402
import visibility as V  # noqa: E402
from engine import Rules  # noqa: E402

RULES = S.load_game_rules(S.DEFAULT_GAME)[0]
FORGET_NOTHING = dict(k=99, guard_forget=0.0)       # follows everybody, never forgets a guard: should equal a perfect reader


def game(seed=1, **kw):
    return S.Game(RULES, seed, **kw)


def log_of(seed, **kw):
    g = game(seed, log=True, **kw)
    g.run()
    return g.events


class Scripted(S.Game):
    """Players choose from their own dice, ignoring beliefs entirely: any change in the log is the rules' doing."""

    def choose(self, p):
        r = random.Random(self.seed * 1000 + self.night * 50 + p.pid)
        others = [q.pid for q in self.players if q.pid != p.pid]
        kind = r.choice(["steal", "steal", "scavenge", "investigate", "guard"])
        if kind == "steal":
            return ("steal", r.choice(others), 0, False)
        if kind == "investigate":
            return ("investigate", r.choice(others), 0, False)
        if kind == "guard" and not p.bandit and self.can_guard(p):
            return ("guard", None, 0, False)
        return ("scavenge", None, 0, False)


class Defaults(unittest.TestCase):
    def test_nothing_new_in_the_rules(self):
        names = {f.name for f in fields(Rules)}
        self.assertFalse({"vis", "visibility", "memory", "edges"} & names)   # information is not a rule knob

    def test_default_game_is_hidden_and_bot_accurate(self):
        g = game()
        self.assertEqual((g.vis, g.mem), ("hidden", None))

    def test_unknown_visibility_is_refused(self):
        with self.assertRaises(ValueError):
            game(vis="rations")

    def test_same_moves_same_night_whatever_players_are_told(self):
        """The engine must not care what anyone believes: scripted moves give byte-identical logs in all modes."""
        for seed in (1, 2, 3):
            ref = None
            for vis in V.VISIBILITIES:
                for mem in (None, V.HumanMemory(), V.HumanMemory(k=0, random_slots=0, decay=1.0)):
                    g = Scripted(RULES, seed, log=True, vis=vis, memory=mem)
                    g.run()
                    ref = ref or g.events
                    self.assertEqual(g.events, ref, (seed, vis, mem))


class Bands(unittest.TestCase):
    def setUp(self):
        self.g = game()

    def band(self, rations, bandit=False):
        q = self.g.P(1)
        q.rations, q.bandit = rations, bandit
        return V.band_index(q)

    def test_edges_belong_to_the_richer_band(self):
        self.assertEqual([self.band(r) for r in (1, 2, 3, 6, 7, 30)], [2, 2, 1, 1, 0, 0])

    def test_bandit_is_a_bandit_whatever_it_holds(self):
        self.assertEqual([self.band(r, True) for r in (0, 1, 2, 5, 9)], [3] * 5)

    def test_survivor_on_zero_is_not_shown_as_a_bandit_before_the_rules_make_it_one(self):
        self.assertEqual(self.band(0), 2)         # unreachable in play; must not crash or index past the labels

    def test_bounds_tile_the_range_without_gaps_or_overlap(self):
        spans = [V.band_bounds(i) for i in range(4)]
        self.assertEqual(spans, [(7, 10), (3, 6), (1, 2), (0, 0)])
        for r in range(1, 40):
            q = self.g.P(2)
            q.rations, q.bandit = r, False
            lo, hi = V.band_bounds(V.band_index(q))
            if V.band_index(q) != 0:
                self.assertTrue(lo <= r <= hi, r)


class RangesNeverLeak(unittest.TestCase):
    def test_belief_depends_on_the_band_not_the_count(self):
        """Same public history, different true counts inside one band: the AI's belief must be identical."""
        for lo, hi in ((7, 30), (3, 6), (1, 2)):
            seen = set()
            for rations in range(lo, hi + 1):
                g = game(vis="ranges")
                q = g.P(4)
                q.rations = rations
                g.public_delta[4] = -2
                g.rng = random.Random(99)
                seen.add(g.perceived(g.P(0), q))
            self.assertEqual(len(seen), 1, (lo, hi, seen))

    def test_belief_stays_inside_the_band_before_noise(self):
        for rations in range(1, 25):
            for delta in (-6, 0, 6):                       # even a badly wrong public guess is pulled into the band
                g = game(vis="ranges")
                q = g.P(4)
                q.rations = rations
                g.public_delta[4] = delta
                lo, hi = V.band_bounds(V.band_index(q))
                self.assertTrue(lo <= g.fresh(q) <= hi, (rations, delta, g.fresh(q)))

    def test_hidden_belief_ignores_true_rations(self):
        beliefs = set()
        for rations in (1, 5, 20):
            g = game()
            g.P(4).rations = rations
            g.rng = random.Random(3)
            beliefs.add(g.perceived(g.P(0), g.P(4)))
        self.assertEqual(len(beliefs), 1)

    def test_the_morning_post_is_the_same_for_two_hidden_states_inside_a_band(self):
        a, b = game(), game()
        for g, extra in ((a, 0), (b, 3)):
            g.P(0).rations, g.P(1).rations, g.P(2).rations = 8 + extra, 4, 1
            g.P(3).rations, g.P(3).bandit = 0, True
        self.assertEqual(V.morning_board(a.players, "ranges"), V.morning_board(b.players, "ranges"))
        self.assertNotEqual(V.morning_board(a.players, "exact"), V.morning_board(b.players, "exact"))
        self.assertIsNone(V.morning_board(a.players, "hidden"))

    def test_the_post_does_not_rank_players_inside_a_band(self):
        g = game()
        for p, r in zip(g.players, [12, 11, 10, 9, 8, 7] + [5] * 9):
            p.rations = r
        for line in V.morning_board(g.players, "ranges"):
            names = line.split(": ", 1)[1].split(", ")
            self.assertEqual(names, sorted(names))


class Exact(unittest.TestCase):
    def test_belief_is_the_truth_with_only_a_tie_break(self):
        g = game(vis="exact")
        for rations, bandit in ((12, False), (1, False), (2, True), (0, True)):
            q = g.P(5)
            q.rations, q.bandit = rations, bandit
            b = g.perceived(g.P(0), q)
            self.assertTrue(rations <= b < rations + V.EXACT_TIE_JITTER + 1e-9, (rations, b))

    def test_equal_counts_are_not_always_won_by_the_lowest_seat(self):
        picks = set()
        for seed in range(30):
            g = game(seed, vis="exact")
            for p in g.players:
                p.rations = 7
            picks.add(g.pick_steal_target(g.P(0)) if g.P(0).arch != "chaos" else 1)
        self.assertGreater(len(picks), 1)


class HumanMemoryEqualsPerfectWhenItCanFollowEveryone(unittest.TestCase):
    def test_full_games_match_byte_for_byte(self):
        for vis in V.VISIBILITIES:
            for seed in (1, 2, 3, 4, 5):
                self.assertEqual(log_of(seed, vis=vis, memory=V.HumanMemory(**FORGET_NOTHING)),
                                 log_of(seed, vis=vis), (vis, seed))

    def test_it_is_not_equal_for_free_a_small_attention_span_changes_play(self):
        differ = sum(log_of(s, vis="exact", memory=V.HumanMemory(k=1, random_slots=1)) != log_of(s, vis="exact")
                     for s in range(1, 6))
        self.assertGreaterEqual(differ, 4)

    def test_forgetting_guards_alone_breaks_the_equality(self):
        cfg = V.HumanMemory(k=99, guard_forget=1.0)
        differ = sum(log_of(s, memory=cfg) != log_of(s) for s in range(1, 9))
        self.assertGreater(differ, 0)


class HumanMemoryMechanics(unittest.TestCase):
    def fade_game(self, **cfg):
        g = game(vis="exact", memory=V.HumanMemory(**cfg))
        g.night = 1
        return g

    def test_estimates_fade_toward_the_camp_average_without_news(self):
        g = self.fade_game(k=99)
        g.P(3).rations = 21
        g.mem.morning()                                 # everyone is following everyone: the 21 is read fresh
        self.assertEqual(g.mem.est[0][3], 21.0)
        g.mem.cfg.k, g.mem.cfg.random_slots = 0, 0      # ...then attention drops to nobody and nothing is in the news
        avg = (14 * 7 + 21) / 15
        gaps = []
        for _ in range(5):
            g.mem.morning()
            gaps.append(g.mem.est[0][3] - avg)
        self.assertTrue(all(a > b > 0 for a, b in zip(gaps, gaps[1:])), gaps)
        self.assertLess(gaps[-1], 0.1 * (21 - avg))

    def test_news_about_a_player_refreshes_even_a_stranger(self):
        g = self.fade_game(k=0, random_slots=0, decay=1.0)
        g.mem.morning()
        g.P(3).rations = 2
        g.public_delta[3] -= 5
        g.mem.morning()
        self.assertEqual(g.mem.est[0][3], 2.0)
        g.P(3).rations = 11                            # silent change: no news, nobody follows them -> still stale
        g.mem.morning()
        self.assertNotEqual(g.mem.est[0][3], 11.0)

    def test_followed_players_are_always_read_fresh(self):
        g = self.fade_game(k=99)
        g.P(3).rations = 13
        g.mem.morning()
        self.assertEqual(g.mem.est[0][3], 13.0)

    def test_attention_is_exactly_k_never_self_most_recent_first(self):
        g = self.fade_game(k=3, random_slots=1)
        for q in (5, 6, 7, 8):
            g.mem.touch(0, q)                          # 8 is the most recent
        g.mem.touch(0, 0)                              # dealing with yourself is ignored
        g.mem.morning()
        t = g.mem.tracked[0]
        self.assertEqual(len(t), 3)
        self.assertNotIn(0, t)
        self.assertTrue({8, 7} <= t)                   # two interaction seats go to the latest two
        self.assertEqual(len(t - {7, 8}), 1)           # the one remaining seat is the random one

    def test_a_player_who_has_dealt_with_nobody_still_follows_k_strangers(self):
        g = self.fade_game(k=4)
        g.mem.morning()
        self.assertTrue(all(len(g.mem.tracked[v]) == 4 for v in range(15)))

    def test_guards_of_strangers_are_forgotten_but_last_nights_news_is_not(self):
        g = self.fade_game(k=0, random_slots=0, guard_forget=0.0)
        g.night = 5
        g.known_guard.update({3: 4, 6: 3, 9: 2})       # caught thieves last night / 2 nights ago / 3 nights ago
        g.mem.morning()
        self.assertEqual(g.mem.guard_seen[0], {3})     # only last night's headline; the older ones faded for a stranger

    def test_followed_guards_last_two_nights_then_expire(self):
        g = self.fade_game(k=99, guard_forget=0.0)
        g.night = 5
        g.known_guard.update({3: 4, 6: 3, 9: 2})
        g.mem.morning()
        self.assertEqual(g.mem.guard_seen[0], {3, 6})  # the original rule: within 2 nights

    def test_forgetfulness_one_means_no_guard_is_ever_remembered(self):
        g = self.fade_game(k=99, guard_forget=1.0)
        g.night = 5
        g.known_guard.update({3: 4, 6: 3})
        g.mem.morning()
        self.assertTrue(all(not g.mem.guard_seen[v] for v in range(15)))

    def test_memory_does_not_touch_the_shared_dice(self):
        g = self.fade_game(k=3)
        before = g.rng.getstate()
        for _ in range(4):
            g.mem.morning()
        self.assertEqual(g.rng.getstate(), before)

    def test_a_viewer_can_be_wrong_in_both_directions(self):
        """Forgetting is not a one-way bias toward 'poor': a stale estimate of a now-poor player reads as richer."""
        g = self.fade_game(k=0, random_slots=0, decay=0.4)
        g.mem.morning()
        g.P(3).rations = 1                              # silently drops (no news yet)
        g.mem.morning()
        self.assertGreater(g.mem.est[0][3], 2.0)
        g.P(4).rations = 20
        g.mem.morning()
        self.assertLess(g.mem.est[0][4], 20.0)


class BooksStillBalance(unittest.TestCase):
    def test_every_combination_conserves_food(self):
        create = {"scavenge", "guard_income", "gift_bonus", "investigate_find", "event_found"}
        destroy = {"eat", "fine", "event_lost"}
        for vis in V.VISIBILITIES:
            for mem in (None, V.HumanMemory()):
                for seed in (1, 2, 3):
                    g = game(seed, log=True, vis=vis, memory=mem)
                    g.run()
                    held = {p.name: RULES.start_rations for p in g.players}
                    net = {}
                    for e in g.events:
                        if e["type"] == "ration":
                            held[e["player"]] += e["delta"]
                            if e["reason"] not in create | destroy:
                                net[e["night"]] = net.get(e["night"], 0) + e["delta"]
                    self.assertTrue(all(v == 0 for v in net.values()), (vis, mem, seed))
                    self.assertTrue(all(held[p.name] == p.rations for p in g.players), (vis, mem, seed))


if __name__ == "__main__":
    unittest.main()
