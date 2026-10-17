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
        weather = {"storm": "Nobody finds any food tonight.", "feast": "Nobody eats tonight."}
        for eid, options in E.VARIANTS.items():
            eff = E.BY_ID[eid]["effect"]
            if eff["op"] == "flag":                 # camp weather: names nobody, must say what it does
                for _, text in options:
                    self.assertIn(weather[eff["flag"]], text, f"{eid}: '{text}' doesn't say what it does")
                    self.assertNotIn("{who}", text)
                continue
            tag = f"{'+' if eff['op'] == 'find' else '-'}{eff['amount']} ration"
            for _, text in options:
                self.assertIn(tag, text, f"{eid}: '{text}' doesn't say {tag}")
                self.assertIn("{who}", text)
from dataclasses import replace

from engine import PlayerState, Rules, resolve_night

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "sim"))
import events as W  # noqa: E402
import survivors_sim as S  # noqa: E402

CREATE = {"scavenge", "guard_income", "gift_bonus", "investigate_find", "event_found"}
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


def set_rations(g, values, bandits=()):
    """Give players 0..n-1 these rations; pids in `bandits` become bandits."""
    for p, v in zip(g.players, values):
        p.rations = v
        p.bandit = p.pid in bandits


def losses(g, ev_id, tries, seed=0):
    """Apply one event `tries` times to a fresh copy of the same rations. Returns the list of per-player changes."""
    start = [p.rations for p in g.players]
    out = []
    for k in range(tries):
        for p, v in zip(g.players, start):
            p.rations = v
        W._apply(g, W.BY_ID[ev_id], random.Random(seed * 1000 + k), set(), [])
        out.append([p.rations - v for p, v in zip(g.players, start)])
    for p, v in zip(g.players, start):
        p.rations = v                      # leave the camp as it was found
    return out


class Round2Variants(unittest.TestCase):
    def test_new_negative_events_have_at_least_four_variants_with_who(self):
        for eid in ("raid", "rats_top"):
            self.assertGreaterEqual(len(W.VARIANTS[eid]), 4, eid)
            for _, text in W.VARIANTS[eid]:
                self.assertIn("{who}", text)
                self.assertIn("-2 rations" if eid == "raid" else "-1 ration", text)


class Raid(unittest.TestCase):
    def test_raid_never_takes_the_last_ration_or_makes_a_bandit(self):
        g = sim_game(1, events_per_night=1.0, events_raid=1.0)
        g.night = 1
        for values in ([1] * 15, [2] * 15, [3] * 15, [1, 2, 3, 4] * 3 + [9, 9, 1], list(range(1, 16))):
            set_rations(g, values)
            for delta in losses(g, "raid", 60):
                self.assertTrue(all(v + d >= 1 for v, d in zip(values, delta)), values)
        self.assertFalse([p for p in g.players if p.bandit])

    def test_raid_takes_exactly_two_and_only_from_the_top_quarter(self):
        g = sim_game(1, events_per_night=1.0, events_raid=1.0)
        g.night = 1
        values = list(range(1, 16))                          # 15 players: 75th percentile is the 12th value, 12
        set_rations(g, values)
        hit = set()
        for delta in losses(g, "raid", 300):
            taken = [(i, d) for i, d in enumerate(delta) if d]
            self.assertEqual(len(taken), 1)
            self.assertEqual(taken[0][1], -2)
            hit.add(values[taken[0][0]])
        self.assertEqual(hit, {12, 13, 14, 15})              # all four of them get hit sometimes, nobody else

    def test_raid_fizzles_when_nobody_in_the_top_quarter_has_three(self):
        g = sim_game(1, events_per_night=1.0, events_raid=1.0)
        g.night = 1
        set_rations(g, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2])     # the top quarter holds 2: a raid would hit 1
        W._apply(g, W.BY_ID["raid"], random.Random(0), set(), [])
        self.assertEqual(g.event_tally["fizzled"], 1)
        self.assertEqual(g.event_tally["lost"], 0)

    def test_raid_ignores_bandits_even_when_they_are_the_richest(self):
        g = sim_game(1, events_per_night=1.0, events_raid=1.0)
        g.night = 1
        set_rations(g, [30, 30, 30] + [5] * 12, bandits={0, 1, 2})
        for delta in losses(g, "raid", 100):
            self.assertEqual(delta[:3], [0, 0, 0])
            self.assertEqual(sum(delta), -2)

    def test_raid_with_everyone_tied_hits_exactly_one_player_for_two(self):
        g = sim_game(1, events_per_night=1.0, events_raid=1.0)
        g.night = 1
        set_rations(g, [5] * 15)
        for delta in losses(g, "raid", 50):
            self.assertEqual(sorted(delta)[0], -2)
            self.assertEqual(sum(delta), -2)

    def test_raid_in_a_one_player_game(self):
        g = sim_game(1, events_per_night=1.0, events_raid=1.0, players=1)
        g.night = 1
        set_rations(g, [7])
        W._apply(g, W.BY_ID["raid"], random.Random(0), set(), [])
        self.assertEqual(g.players[0].rations, 5)
        set_rations(g, [2])
        W._apply(g, W.BY_ID["raid"], random.Random(0), set(), [])
        self.assertEqual(g.players[0].rations, 2)            # would leave 0: fizzles instead

    def test_raid_is_never_drawn_when_the_knob_is_off(self):
        for seed in range(40):
            g = sim_game(seed, events_per_night=4.0)
            g.run()
            self.assertFalse([e for e in g.events if e["type"] == "event" and e["event"] in ("raid", "rats_top")])

    def test_raid_is_drawn_when_the_knob_is_on(self):
        n = 0
        for seed in range(30):
            g = sim_game(seed, events_per_night=3.0, events_raid=4.0)
            g.run()
            n += sum(1 for e in g.events if e["type"] == "event" and e["event"] == "raid")
        self.assertGreater(n, 0)


class TopBias(unittest.TestCase):
    def setUp(self):
        self.g = sim_game(1, events_per_night=1.0, events_bias="top", events_raid=1.0)
        self.g.night = 1

    def test_bad_events_only_hit_the_top_third_and_good_only_the_bottom_third(self):
        values = list(range(1, 16))                          # thirds of 15: bottom 1-5, top 11-15
        set_rations(self.g, values)
        for ev_id, lo_ok in (("snake", False), ("rain", False), ("raid", False), ("bananas", True), ("cache", True)):
            seen = set()
            for delta in losses(self.g, ev_id, 200):
                idx = [i for i, d in enumerate(delta) if d]
                self.assertEqual(len(idx), 1, ev_id)
                seen.add(values[idx[0]])
            ok = {1, 2, 3, 4, 5} if lo_ok else ({12, 13, 14, 15} if ev_id == "raid" else {11, 12, 13, 14, 15})
            self.assertTrue(seen <= ok, (ev_id, seen))
            self.assertGreaterEqual(len(seen), 3, ev_id)     # and it really spreads over the whole third

    def test_top_bias_never_hits_a_bandit(self):
        set_rations(self.g, [40, 40, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], bandits={0, 1})
        for ev_id in ("snake", "rain", "bananas", "idol", "shelter", "raid", "cache"):
            for delta in losses(self.g, ev_id, 60):
                self.assertEqual(delta[:2], [0, 0], ev_id)
        self.assertTrue(self.g.players[0].bandit and self.g.players[1].bandit)

    def test_top_bias_never_creates_a_bandit(self):
        for seed in range(80):
            g = sim_game(seed, events_per_night=5.0, events_bias="top", events_raid=3.0, events_rats_relative=True)
            for _ in range(g.r.rounds):
                g.night += 1
                bandits = {p.pid for p in g.players if p.bandit}
                for p in g.players:
                    p.rations = min(p.rations, 1 + (p.pid % 4))
                W.run_night_events(g, W.rng_for(g.seed, g.night))
                self.assertEqual({p.pid for p in g.players if p.bandit}, bandits)
                self.assertTrue(all(p.rations >= 1 for p in g.players if not p.bandit))

    def test_bad_event_fizzles_instead_of_hitting_outside_the_top_when_the_top_is_ineligible(self):
        set_rations(self.g, list(range(1, 16)))
        for p in self.g.players:
            p.guard_until = 0
        self.g.players[0].guard_until = 99                   # only the poorest player is guarding
        W._apply(self.g, W.BY_ID["shelter"], random.Random(0), set(), [])
        self.assertEqual(self.g.event_tally["fizzled"], 1)
        self.assertEqual(self.g.players[0].guard_until, 99)  # the poor player's guard survives

    def test_good_event_falls_back_when_the_whole_bottom_third_has_idols(self):
        set_rations(self.g, list(range(1, 16)))
        for p in self.g.players[:5]:
            p.idol = True
        W._apply(self.g, W.BY_ID["idol"], random.Random(0), set(), [])
        self.assertEqual(sum(p.idol for p in self.g.players), 6)

    def test_everyone_tied_everyone_is_top_and_bottom(self):
        set_rations(self.g, [6] * 15)
        for ev_id in ("snake", "bananas"):
            seen = {i for delta in losses(self.g, ev_id, 200) for i, d in enumerate(delta) if d}
            self.assertGreater(len(seen), 8, ev_id)

    def test_one_player_game(self):
        g = sim_game(1, events_per_night=1.0, events_bias="top", players=1)
        g.night = 1
        set_rations(g, [7])
        W._apply(g, W.BY_ID["snake"], random.Random(0), set(), [])
        W._apply(g, W.BY_ID["bananas"], random.Random(0), set(), [])
        self.assertEqual(g.players[0].rations, 7)

    def test_two_player_game_thirds(self):
        g = sim_game(1, events_per_night=1.0, events_bias="top", players=2)
        g.night = 1
        set_rations(g, [3, 9])
        for delta in losses(g, "snake", 50):
            self.assertEqual(delta, [0, -1])
        for delta in losses(g, "bananas", 50):
            self.assertEqual(delta, [1, 0])


class RatsRelative(unittest.TestCase):
    def setUp(self):
        self.g = sim_game(1, events_per_night=1.0, events_rats_relative=True)
        self.g.night = 1

    def test_taxes_exactly_those_within_one_of_the_richest(self):
        set_rations(self.g, [10, 9, 8, 10, 3, 9, 1] + [5] * 8)
        [delta] = losses(self.g, "rats_top", 1)
        self.assertEqual(delta[:7], [-1, -1, 0, -1, 0, -1, 0])
        self.assertEqual(sum(delta), -4)

    def test_works_when_nobody_reaches_seven(self):
        set_rations(self.g, [4, 3, 2, 1] + [1] * 11)
        [delta] = losses(self.g, "rats_top", 1)
        self.assertEqual(delta[:4], [-1, -1, 0, 0])

    def test_all_tied_taxes_everyone_once(self):
        set_rations(self.g, [6] * 15)
        [delta] = losses(self.g, "rats_top", 1)
        self.assertEqual(delta, [-1] * 15)

    def test_everyone_at_the_floor_fizzles(self):
        set_rations(self.g, [1] * 15)
        news = []
        W._apply(self.g, W.BY_ID["rats_top"], random.Random(0), set(), news)
        self.assertEqual(news, [])
        self.assertEqual(self.g.event_tally["fizzled"], 1)
        self.assertTrue(all(p.rations == 1 and not p.bandit for p in self.g.players))

    def test_a_rich_bandit_does_not_set_the_bar_and_is_not_taxed(self):
        set_rations(self.g, [50, 6, 5, 4] + [1] * 11, bandits={0})
        [delta] = losses(self.g, "rats_top", 1)
        self.assertEqual(delta[:4], [0, -1, -1, 0])

    def test_one_player_game(self):
        g = sim_game(1, events_per_night=1.0, events_rats_relative=True, players=1)
        g.night = 1
        set_rations(g, [4])
        W._apply(g, W.BY_ID["rats_top"], random.Random(0), set(), [])
        self.assertEqual(g.players[0].rations, 3)
        set_rations(g, [1])
        W._apply(g, W.BY_ID["rats_top"], random.Random(0), set(), [])
        self.assertEqual(g.players[0].rations, 1)

    def test_news_names_the_people_taxed(self):
        set_rations(self.g, [9, 9, 9] + [2] * 12)
        news = []
        W._apply(self.g, W.BY_ID["rats_top"], random.Random(0), set(), news)
        names = [p.name for p in self.g.players[:3]]
        self.assertTrue(all(n in news[0] for n in names), news)

    def test_the_old_rats_step_aside_and_come_back(self):
        on, off = sim_game(1, events_rats_relative=True).r, sim_game(1).r
        self.assertEqual(W._weight(W.BY_ID["rats"], on), 0)
        self.assertGreater(W._weight(W.BY_ID["rats_top"], on), 0)
        self.assertGreater(W._weight(W.BY_ID["rats"], off), 0)
        self.assertEqual(W._weight(W.BY_ID["rats_top"], off), 0)

    def test_old_fixed_rats_unchanged(self):
        g = sim_game(1, events_per_night=1.0)
        g.night = 1
        set_rations(g, [7, 6, 12] + [3] * 12)
        [delta] = losses(g, "rats", 1)
        self.assertEqual(delta[:3], [-1, 0, -1])


class Round2Books(unittest.TestCase):
    def test_books_balance_with_every_round_two_knob_on(self):
        for bias in ("random", "trailing", "top"):
            for seed in range(40):
                g = sim_game(seed, events_per_night=4.0, events_bias=bias, events_raid=4.0, events_rats_relative=True)
                g.run()
                by_night, start = {}, {p.name: S.Rules().start_rations for p in g.players}
                for e in g.events:
                    if e["type"] == "ration":
                        start[e["player"]] += e["delta"]
                        if e["reason"] not in CREATE | DESTROY:
                            by_night[e["night"]] = by_night.get(e["night"], 0) + e["delta"]
                self.assertTrue(all(v == 0 for v in by_night.values()), (bias, seed))
                self.assertEqual(start, {p.name: p.rations for p in g.players}, (bias, seed))

    def test_off_means_off_even_with_round_two_knobs_set(self):
        g = sim_game(1, events_raid=5.0, events_rats_relative=True, events_bias="top")
        g.run()
        self.assertFalse([e for e in g.events if e["type"] == "event"])
        for k in ("events_per_night", "events_bias", "events_raid", "events_rats_relative"):
            self.assertNotIn(k, g.events[0]["rules"])


if __name__ == "__main__":
    unittest.main()
