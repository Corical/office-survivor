"""Tests that try to break Rules.investigate_find (an investigator also finds 0..N new rations, phase 6) and the
interaction with gifts, thefts, eating and bandits.

    python -m unittest discover -s engine/tests -t .
"""
import random
import unittest
from collections import Counter
from dataclasses import replace

from engine import PlayerState, Rules, resolve_night

CREATE = {"scavenge", "guard_income", "gift_bonus", "investigate_find"}
DESTROY = {"eat", "fine"}


def players(n=6, rations=7):
    return [PlayerState(pid=i, name=f"P{i}", rations=rations) for i in range(n)]


def night(ps, moves, r, seed=1, n=1, rng=None):
    events = []
    res = resolve_night(ps, moves, r, rng or random.Random(seed), n,
                        emit=lambda t, **f: events.append({"type": t, **f}))
    return res, events


def hold():
    return ("scavenge", None, 0, False)


def quiet():
    return ("guard", None, 0, False)


def steal(t):
    return ("steal", t, 0, False)


def inv(t):
    return ("investigate", t, 0, False)


def gift(t, a=1):
    return ("gift", t, a, False)


def find_lines(events):
    return [e for e in events if e["type"] == "ration" and e["reason"] == "investigate_find"]


class FindOff(unittest.TestCase):
    def test_nothing_found_and_no_dice_drawn_when_off(self):
        r = replace(Rules(), scavenge_max=0, eat=0)
        self.assertEqual(r.investigate_find, 0)
        for seed in range(50):
            ps = players()
            moves = {0: inv(1), 1: quiet(), 2: inv(3), 3: steal(4), 4: quiet(), 5: inv(0)}
            rng = random.Random(seed)
            res, ev = night(ps, moves, r, rng=rng)
            self.assertFalse(find_lines(ev))
            self.assertEqual(res.ev["investigate_find"], 0)
            # the only draw in this night is the single thief's share shuffle; a night with no thief draws nothing
            ps2 = players()
            rng2 = random.Random(seed)
            night(ps2, {0: inv(1), 1: quiet(), 2: inv(3), 3: quiet(), 4: quiet(), 5: inv(0)}, r, rng=rng2)
            self.assertEqual(rng2.getstate(), random.Random(seed).getstate(), "an investigation drew a die with the knob off")

    def test_one_die_per_investigator_when_on(self):
        r = replace(Rules(), scavenge_max=0, eat=0, investigate_find=2)
        seed = 9
        ps = players()
        rng = random.Random(seed)
        night(ps, {0: inv(1), 1: quiet(), 2: inv(3), 3: quiet(), 4: quiet(), 5: inv(0)}, r, rng=rng)
        ref = random.Random(seed)
        for _ in range(3):
            ref.randint(0, 2)
        self.assertEqual(rng.getstate(), ref.getstate())


class FindOn(unittest.TestCase):
    def test_range_is_uniform_zero_to_max_and_booked(self):
        for top in (1, 2, 3):
            r = replace(Rules(), scavenge_max=0, eat=0, investigate_find=top)
            seen = Counter()
            for seed in range(600):
                ps = players(2)
                res, ev = night(ps, {0: inv(1), 1: hold()}, r, seed=seed)
                n = sum(e["delta"] for e in find_lines(ev))
                self.assertEqual(ps[0].rations, 7 + n)
                self.assertEqual(ps[1].rations, 7)
                self.assertEqual(res.ev["investigate_find"], n)
                seen[n] += 1
            self.assertEqual(set(seen), set(range(top + 1)), "every value 0..max must occur")
            for v in range(top + 1):
                self.assertGreater(seen[v], 600 / (top + 1) * 0.6, f"value {v} is under-represented: {seen}")

    def test_only_investigators_find_food(self):
        r = replace(Rules(), scavenge_max=0, eat=0, investigate_find=2)
        for seed in range(100):
            ps = players()
            res, ev = night(ps, {0: inv(1), 1: steal(2), 2: hold(), 3: ("guard", None, 0, False), 4: gift(5), 5: hold()}, r, seed=seed)
            self.assertTrue(all(e["player"] == "P0" for e in find_lines(ev)))

    def test_bandit_investigator_finds_food_and_can_rejoin_next_night(self):
        r = replace(Rules(), scavenge_max=0, investigate_find=2)
        got_any = False
        for seed in range(200):
            ps = players(3, rations=7)
            ps[0].rations, ps[0].bandit, ps[0].ever_bandit = 2, True, True
            night(ps, {0: inv(1), 1: hold(), 2: hold()}, r, seed=seed)
            self.assertGreaterEqual(ps[0].rations, 2)
            self.assertLessEqual(ps[0].rations, 4)
            self.assertEqual(ps[0].bandit, ps[0].rations < r.bandit_rejoin)     # rejoins at 3+, no eating for a bandit
            got_any |= ps[0].rations > 2
        self.assertTrue(got_any)

    def test_found_food_is_after_thefts_so_it_cannot_be_stolen_that_night(self):
        r = replace(Rules(), scavenge_max=0, eat=0, investigate_find=2)
        for seed in range(100):
            ps = players(3, rations=1)
            ps[1].rations = 5
            # P0 investigates P2; P1 steals from P0 who holds 1: the thief can only ever get that 1
            res, ev = night(ps, {0: inv(2), 1: steal(0), 2: hold()}, r, seed=seed)
            stole = sum(e["delta"] for e in ev if e["type"] == "ration" and e["reason"] == "stole")
            self.assertEqual(stole, 1)
            f = sum(e["delta"] for e in find_lines(ev))
            self.assertEqual(ps[0].rations, 0 + f)       # lost the 1, kept everything found afterwards

    def test_found_food_comes_after_gifts_and_before_eating(self):
        r = replace(Rules(), scavenge_max=0, investigate_find=2)    # eat = 1
        survived = starved = 0
        for seed in range(300):
            ps = players(3, rations=7)
            ps[0].rations = 1
            res, ev = night(ps, {0: inv(1), 1: gift(0, 2), 2: hold()}, r, seed=seed)
            f = sum(e["delta"] for e in find_lines(ev))
            self.assertEqual(ps[0].rations, 1 + 2 + f - 1)         # gift arrives, find arrives, then eats once
            self.assertFalse(ps[0].bandit)
        for seed in range(300):
            ps = players(2, rations=7)
            ps[0].rations = 1
            res, ev = night(ps, {0: inv(1), 1: hold()}, r, seed=seed)
            f = sum(e["delta"] for e in find_lines(ev))
            self.assertEqual(ps[0].bandit, f == 0, "finding food must save a 1-ration investigator from eating down to 0")
            survived += f > 0
            starved += f == 0
        self.assertTrue(survived and starved)

    def test_giver_keeps_one_even_with_find_on(self):
        r = replace(Rules(), scavenge_max=0, eat=0, investigate_find=2, gift_bonus=1)
        ps = players(3, rations=2)
        night(ps, {0: gift(1, 2), 1: inv(2), 2: hold()}, r)
        self.assertEqual(ps[0].rations, 1)

    def test_books_balance_over_random_nights(self):
        variants = [dict(), dict(exposure_undo="full"), dict(exposure_undo="split", investigate_bounty=2),
                    dict(exposure_undo="full", gift_bonus=1)]
        for var in variants:
            for top in (1, 2):
                r = replace(Rules(), investigate_find=top, **var)
                rng = random.Random(3)
                ps = players(10, rations=4)
                for n in range(1, 41):
                    start = {p.name: p.rations for p in ps}
                    moves = {}
                    for p in ps:
                        kind = rng.choice(["scavenge", "steal", "guard", "investigate", "gift", "investigate"])
                        if p.bandit and kind in ("scavenge", "guard", "gift"):
                            kind = "steal"
                        t = rng.choice([q.pid for q in ps if q.pid != p.pid])
                        moves[p.pid] = (kind, t if kind in ("steal", "investigate", "gift") else None, rng.choice([1, 2]), False)
                    res, ev = night(ps, moves, r, rng=rng, n=n)
                    net, held = 0, dict(start)
                    for e in ev:
                        if e["type"] == "ration":
                            held[e["player"]] += e["delta"]
                            if e["reason"] not in CREATE | DESTROY:
                                net += e["delta"]
                    self.assertEqual(net, 0, ("unbooked food", var, top, n))
                    for p in ps:
                        self.assertEqual(held[p.name], p.rations, (p.name, var, top, n))
                        self.assertGreaterEqual(p.rations, 0)


if __name__ == "__main__":
    unittest.main()
