"""Tests that try to break the wilderness-event hooks (storm, feast, idol) and the simulator's event phase.

    python -m unittest discover -s engine/tests -t .
"""
import os
import random
import sys
import unittest


class Variations(unittest.TestCase):
    """Owner: flavour must not read 'snake bite, snake bite'. Every variation before any repeat, same effect."""

    def test_no_variation_repeats_until_all_are_used(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docs", "sim"))
        import events as E
        for eid, options in E.VARIANTS.items():
            ev = E.BY_ID[eid]
            for seed in (1, 2, 99):
                seen = [E.flavour(ev, seed, k) for k in range(len(options))]
                self.assertEqual(len(set(seen)), len(options), f"{eid} repeated before using every variation")
                self.assertEqual(E.flavour(ev, seed, len(options)), seen[0])     # then the deck starts over

    def test_every_variation_states_the_same_effect_as_its_event(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docs", "sim"))
        import events as E
        for eid, options in E.VARIANTS.items():
            eff = E.BY_ID[eid]["effect"]
            tag = f"{'+' if eff['op'] == 'find' else '-'}{eff['amount']} ration"
            for _, text in options:
                self.assertIn(tag, text, f"{eid}: '{text}' doesn't say {tag}")
                self.assertIn("{who}", text)
from dataclasses import replace

from engine import PlayerState, Rules, resolve_night

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "sim"))
import events as W  # noqa: E402
import survivors_sim as S  # noqa: E402

CREATE = {"scavenge", "guard_income", "gift_bonus", "event_found"}
DESTROY = {"eat", "fine", "event_lost"}


def players(n=4, rations=7):
    return [PlayerState(pid=i, name=f"P{i}", rations=rations) for i in range(n)]


def night(ps, moves, rules=None, seed=1, n=1, flags=frozenset()):
    log, rng = [], random.Random(seed)
    res = resolve_night(ps, moves, rules or Rules(), rng, n, emit=lambda t, **f: log.append({"type": t, **f}),
                        flags=flags)
    return res, log, rng


def scav(ps):
    return {p.pid: ("scavenge", None, 0, False) for p in ps}


class Idol(unittest.TestCase):
    def test_idol_stops_every_thief_and_is_spent(self):
        ps = players()
        ps[0].idol = True
        moves = scav(ps)
        moves[1], moves[2] = ("steal", 0, 0, False), ("steal", 0, 0, False)
        moves[0] = ("scavenge", None, 0, False)
        res, log, _ = night(ps, moves, replace(Rules(), scavenge_max=0))
        self.assertEqual(ps[0].rations, 6)                     # only ate
        self.assertEqual((ps[1].rations, ps[2].rations), (6, 6))
        self.assertFalse(ps[0].idol)
        self.assertEqual(res.ev["idol_used"], 1)
        self.assertEqual(ps[1].steals_caught + ps[2].steals_caught, 0)   # no penalty, just nothing
        self.assertTrue(all(e["outcome"] == "empty" for e in log if e["type"] == "steal"))

    def test_second_theft_after_idol_works(self):
        ps = players()
        ps[0].idol = True
        r = replace(Rules(), scavenge_max=0)
        m = scav(ps)
        m[1] = ("steal", 0, 0, False)
        night(ps, m, r)
        m2 = scav(ps)
        m2[1] = ("steal", 0, 0, False)
        night(ps, m2, r, n=2)
        self.assertEqual(ps[0].rations, 7 - 1 - 2 - 1)         # eat, then robbed of 2, then eat

    def test_idol_not_spent_when_nobody_steals(self):
        ps = players()
        ps[0].idol = True
        night(ps, scav(ps))
        self.assertTrue(ps[0].idol)

    def test_guard_beats_idol_and_keeps_it(self):
        ps = players()
        ps[0].idol = True
        m = scav(ps)
        m[0] = ("guard", None, 0, False)
        m[1] = ("steal", 0, 0, False)
        res, _, _ = night(ps, m)
        self.assertEqual(res.ev["caught"], 1)
        self.assertTrue(ps[0].idol)                            # the guard did the work; the idol is still there

    def test_idol_with_empty_stash_is_still_spent_and_books_balance(self):
        ps = players()
        ps[0].idol, ps[0].rations = True, 1
        m = scav(ps)
        m[1] = ("steal", 0, 0, False)
        _, log, _ = night(ps, m, replace(Rules(), scavenge_max=0))
        net = sum(e["delta"] for e in log if e["type"] == "ration" and e["reason"] not in CREATE | DESTROY)
        self.assertEqual(net, 0)
        self.assertFalse(ps[0].idol)


class Weather(unittest.TestCase):
    def test_storm_finds_nothing_but_draws_the_same_dice(self):
        a, b = players(), players()
        r = replace(Rules(), scavenge_min=1, scavenge_max=2)
        _, log_calm, rng_calm = night(a, scav(a), r, seed=5)
        res, log_storm, rng_storm = night(b, scav(b), r, seed=5, flags=frozenset({"storm"}))
        self.assertEqual(rng_calm.getstate(), rng_storm.getstate())        # stream position identical
        self.assertTrue(all(p.rations == 6 for p in b))                    # only ate
        self.assertFalse([e for e in log_storm if e.get("reason") == "scavenge"])
        self.assertEqual(res.ev["storm_lost"], sum(p.rations - 6 for p in a))

    def test_storm_does_not_stop_stealing_or_gifts(self):
        ps = players()
        m = scav(ps)
        m[1] = ("steal", 0, 0, False)
        night(ps, m, replace(Rules(), scavenge_max=0), flags=frozenset({"storm"}))
        self.assertEqual(ps[1].rations, 7 + 2 - 1)

    def test_feast_nobody_eats_and_no_eat_lines(self):
        ps = players()
        res, log, _ = night(ps, scav(ps), replace(Rules(), scavenge_max=0), flags=frozenset({"feast"}))
        self.assertTrue(all(p.rations == 7 for p in ps))
        self.assertFalse([e for e in log if e.get("reason") == "eat"])
        self.assertEqual(res.ev["feast_saved"], 4)

    def test_feast_does_not_save_someone_robbed_to_zero(self):
        ps = players()
        ps[0].rations = 2
        m = scav(ps)
        m[1], m[2] = ("steal", 0, 0, False), ("steal", 0, 0, False)
        night(ps, m, replace(Rules(), scavenge_max=0), flags=frozenset({"feast"}))
        self.assertTrue(ps[0].bandit)

    def test_storm_and_feast_together(self):
        ps = players()
        night(ps, scav(ps), flags=frozenset({"storm", "feast"}))
        self.assertTrue(all(p.rations == 7 for p in ps))

    def test_no_flags_is_the_old_night(self):
        a, b = players(), players()
        _, la, ra = night(a, scav(a), seed=9)
        _, lb, rb = night(b, scav(b), seed=9, flags=frozenset())
        self.assertEqual(la, lb)
        self.assertEqual(ra.getstate(), rb.getstate())


def sim_game(seed=1, **over):
    return S.Game(replace(S.Rules(), **over), seed, log=True)


class EventPhase(unittest.TestCase):
    def test_main_stream_untouched_by_events(self):
        g = sim_game(events_per_night=3.0)
        g.night = 1
        before = g.rng.getstate()
        for n in range(1, 40):
            g.night = n
            W.run_night_events(g, W.rng_for(g.seed, n))
        self.assertEqual(g.rng.getstate(), before)

    def test_same_seed_same_events_and_nights_differ(self):
        def trace(seed):
            g = sim_game(seed, events_per_night=2.0)
            g.run()
            return [(e["night"], e["event"], e.get("player")) for e in g.events if e["type"] == "event"]
        self.assertEqual(trace(3), trace(3))
        self.assertNotEqual(trace(3), trace(4))

    def test_bad_events_never_create_a_bandit_or_go_below_one(self):
        for bias in ("random", "trailing"):
            for seed in range(150):
                g = sim_game(seed, events_per_night=6.0, events_bias=bias)
                for _ in range(g.r.rounds):
                    g.night += 1
                    bandits = {p.pid for p in g.players if p.bandit}
                    for p in g.players:
                        p.rations = min(p.rations, 1 + (p.pid % 3))     # crowd the floor on purpose
                    W.run_night_events(g, W.rng_for(g.seed, g.night))
                    self.assertEqual({p.pid for p in g.players if p.bandit}, bandits)
                    self.assertTrue(all(p.rations >= 1 for p in g.players if not p.bandit), (bias, seed))

    def test_everyone_at_the_floor_makes_player_losses_fizzle(self):
        g = sim_game(1, events_per_night=1.0)
        g.night = 1
        for p in g.players:
            p.rations = 1
        for ev_id in ("snake", "rain"):
            W._apply(g, W.BY_ID[ev_id], random.Random(0), set(), [])
        self.assertEqual(g.event_tally["fizzled"], 2)
        self.assertTrue(all(p.rations == 1 for p in g.players))

    def test_trailing_bias_really_leans(self):
        g = sim_game(1, events_per_night=1.0, events_bias="trailing")
        g.night = 1
        for p in g.players:
            p.rations = 3 if p.pid < 5 else (7 if p.pid < 10 else 12)   # 5 poor, 5 at the median (7), 5 rich
        rng, poor_good, poor_bad, n = random.Random(1), 0, 0, 4000
        for _ in range(n):
            poor_good += W._pick(g, W.BY_ID["bananas"], g.players, rng).pid < 5
            poor_bad += W._pick(g, W.BY_ID["snake"], g.players, rng).pid < 5
        # strictly below / above the median is favoured 3:1; players exactly at the median get weight 1 either way
        self.assertAlmostEqual(poor_good / n, 15 / 25, delta=0.03)
        self.assertAlmostEqual(poor_bad / n, 5 / 25, delta=0.03)

    def test_unknown_bias_is_refused(self):
        g = sim_game(1, events_per_night=1.0, events_bias="sideways")
        g.night = 1
        with self.assertRaises(ValueError):
            W._pick(g, W.BY_ID["bananas"], g.players, random.Random(0))

    def test_books_balance_with_events_on_every_event_type(self):
        for bias in ("random", "trailing"):
            for seed in range(60):
                g = sim_game(seed, events_per_night=4.0, events_bias=bias)
                g.run()
                by_night, start = {}, {p.name: S.Rules().start_rations for p in g.players}
                for e in g.events:
                    if e["type"] == "ration":
                        start[e["player"]] += e["delta"]
                        if e["reason"] not in CREATE | DESTROY:
                            by_night[e["night"]] = by_night.get(e["night"], 0) + e["delta"]
                self.assertTrue(all(v == 0 for v in by_night.values()), (bias, seed, by_night))
                self.assertEqual(start, {p.name: p.rations for p in g.players}, (bias, seed))

    def test_off_means_off(self):
        g = sim_game(1)
        g.run()
        self.assertFalse([e for e in g.events if e["type"] == "event"])
        self.assertNotIn("events_per_night", g.events[0]["rules"])

    def test_every_library_entry_is_well_formed(self):
        ids = [e["id"] for e in W.EVENTS]
        self.assertEqual(len(ids), len(set(ids)))
        for e in W.EVENTS:
            self.assertGreater(e["weight"], 0)
            self.assertIn(e["scope"], ("player", "camp"))
            self.assertIn(e["effect"]["op"], ("find", "lose", "idol", "drop_guard", "tax", "flag"))
            if e["public"]:
                e["text"].format(who="X")


if __name__ == "__main__":
    unittest.main()
