"""Tests that try to break the engine: bookkeeping, ordering, illegal moves and the edge cases of each phase.

    python -m unittest discover -s engine/tests -t .
"""
import random
import unittest
from collections import Counter
from dataclasses import replace

from engine import PlayerState, Rules, resolve_night
from engine.finish import finish
from engine.moves import validate

CREATE = {"scavenge", "guard_income", "gift_bonus", "investigate_find"}
DESTROY = {"eat", "fine"}


def players(n=6, rations=7):
    return [PlayerState(pid=i, name=f"P{i}", rations=rations) for i in range(n)]


def run_night(ps, moves, rules=None, seed=1, night=1):
    events = []
    res = resolve_night(ps, moves, rules or Rules(), random.Random(seed), night,
                        emit=lambda t, **f: events.append({"type": t, **f}))
    return res, events


def all_scavenge(ps):
    return {p.pid: ("scavenge", None, 0, False) for p in ps}


class Conservation(unittest.TestCase):
    """Food only appears through scavenging (and rule bonuses) and only vanishes through eating and fines."""

    VARIANTS = [{}, {"gift_bonus": 1}, {"guard_income_max": 1}, {"caught_penalty": 3, "guard_reward": 1},
                {"investigate_bounty": 0}, {"steal_amount": 3}, {"caught_penalty": 1, "guard_reward": 2}]

    def test_every_night_balances_under_random_moves(self):
        for vi, v in enumerate(self.VARIANTS):
            rules = replace(Rules(), **v)
            rng = random.Random(vi)
            for game in range(40):
                ps = players(8, rations=rng.randint(0, 9))
                for night in range(1, 11):
                    moves = {}
                    for p in ps:
                        kind = rng.choice(["scavenge", "steal", "guard", "investigate", "gift"])
                        others = [q.pid for q in ps if q.pid != p.pid]
                        tgt = rng.choice(others) if kind in ("steal", "investigate", "gift") else None
                        moves[p.pid] = (kind, tgt, rng.choice([1, 2]) if kind == "gift" else 0, False)
                    before = sum(p.rations for p in ps)
                    _, events = run_night(ps, moves, rules, seed=game * 100 + night, night=night)
                    rations = [e for e in events if e["type"] == "ration"]
                    made = sum(e["delta"] for e in rations if e["reason"] in CREATE)
                    lost = sum(e["delta"] for e in rations if e["reason"] in DESTROY)
                    moved = sum(e["delta"] for e in rations if e["reason"] not in CREATE | DESTROY)
                    after = sum(p.rations for p in ps)
                    self.assertEqual(moved, 0, f"transfers must net to zero (variant {v}, night {night})")
                    self.assertEqual(after, before + made + lost, f"books don't balance (variant {v})")
                    self.assertTrue(all(p.rations >= 0 for p in ps))


class Ordering(unittest.TestCase):
    def test_submission_order_cannot_change_the_night(self):
        base = players(6)
        moves = {0: ("steal", 3, 0, False), 1: ("steal", 3, 0, False), 2: ("investigate", 0, 0, False),
                 3: ("scavenge", None, 0, False), 4: ("gift", 3, 2, False), 5: ("guard", None, 0, False)}
        results = set()
        for perm in range(20):
            ps = players(6)
            items = list(moves.items())
            random.Random(perm).shuffle(items)
            _, events = run_night(ps, dict(items), seed=42)
            results.add(repr(events))
        self.assertEqual(len(results), 1, "the same moves in a different order gave a different night")


class Phases(unittest.TestCase):
    def test_caught_thief_with_nothing_pays_nothing_and_guard_gets_nothing(self):
        ps = players(2)
        ps[0].rations = 0
        ps[1].guard_until = 1
        res, events = run_night(ps, {0: ("steal", 1, 0, False), 1: ("guard", None, 0, False)})
        steal = [e for e in events if e["type"] == "steal"][0]
        self.assertEqual((steal["outcome"], steal["paid"]), ("caught", 0))
        self.assertFalse([e for e in events if e["type"] == "ration" and e["reason"] == "guard_reward"])

    def test_two_thieves_split_what_the_victim_has(self):
        ps = players(3)
        ps[2].rations = 3                  # wants 2 + 2 = 4, only 3 there
        res, events = run_night(ps, {0: ("steal", 2, 0, False), 1: ("steal", 2, 0, False),
                                     2: ("scavenge", None, 0, False)})
        got = sorted(e["amount"] for e in events if e["type"] == "steal")
        self.assertEqual(got, [1, 2])
        self.assertEqual(res.ev["robbed"], 1)

    def test_loot_from_tonight_cannot_be_stolen_again_tonight(self):
        ps = players(3)
        ps[0].rations = 0
        _, events = run_night(ps, {0: ("steal", 1, 0, False), 1: ("steal", 0, 0, False),
                                   2: ("scavenge", None, 0, False)})
        from_zero = [e for e in events if e["type"] == "steal" and e["target"] == "P0"][0]
        self.assertEqual(from_zero["amount"], 0, "P0 started with nothing, so nothing can be taken from P0")

    def test_two_investigators_on_one_thief_both_paid_current_rule(self):
        """Open owner decision: today both are paid. This pins the behaviour so a change is deliberate."""
        ps = players(4)
        _, events = run_night(ps, {0: ("steal", 3, 0, False), 1: ("investigate", 0, 0, False),
                                   2: ("investigate", 0, 0, False), 3: ("scavenge", None, 0, False)})
        self.assertEqual(len([e for e in events if e["type"] == "exposed"]), 2)

    def test_gift_never_takes_the_last_ration(self):
        ps = players(2, rations=2)
        ps[0].rations = 1
        _, events = run_night(ps, {0: ("gift", 1, 2, False), 1: ("scavenge", None, 0, False)})
        self.assertFalse([e for e in events if e["type"] == "gift"])

    def test_bandit_does_not_eat_and_rejoins_at_three_keeping_them(self):
        r = Rules()
        ps = players(2)
        ps[0].bandit, ps[0].rations = True, 2
        ps[1].rations = 9
        run_night(ps, {0: ("steal", 1, 0, False), 1: ("scavenge", None, 0, False)}, r)
        self.assertFalse(ps[0].bandit, "a bandit at 2 who steals 1 reaches 3 and rejoins")
        self.assertEqual(ps[0].rations, 3, "rejoining keeps the food; no meal is eaten that night")

    def test_running_out_makes_a_bandit(self):
        ps = players(2, rations=1)
        r = replace(Rules(), scavenge_max=0)
        res, _ = run_night(ps, all_scavenge(ps), r)
        self.assertTrue(all(p.bandit for p in ps))
        self.assertEqual(res.ev["death"], 2)


class Validation(unittest.TestCase):
    def setUp(self):
        self.r = Rules()
        self.ps = players(4)

    def check(self, pid, move, night=1, **kw):
        return validate(self.ps, pid, move, self.r, night, **kw)

    def test_legal_moves_pass(self):
        for m in [("scavenge", None, 0, False), ("steal", 1, 0, False), ("guard", None, 0, False),
                  ("investigate", 2, 0, False), ("gift", 3, 2, False)]:
            self.assertIsNone(self.check(0, m), m)

    def test_illegal_moves_are_refused(self):
        cases = [(("steal", 0, 0, False), "yourself"), (("gift", 1, 0, False), "1 or 2"),
                 (("gift", 1, 3, False), "1 or 2"), (("steal", 9, 0, False), "still in the game"),
                 (("dance", None, 0, False), "Unknown"), (("scavenge", 1, 0, False), "doesn't take a target"),
                 (("steal", None, 0, False), "still in the game"), (("guard", None, 2, False), "amount")]
        for move, why in cases:
            self.assertIn(why, self.check(0, move) or "", move)

    def test_gift_must_leave_one(self):
        self.ps[0].rations = 2
        self.assertIn("at least 1", self.check(0, ("gift", 1, 2, False)))
        self.assertIsNone(self.check(0, ("gift", 1, 1, False)))

    def test_bandit_can_only_steal_or_investigate(self):
        self.ps[0].bandit = True
        for kind, tgt, amt in [("scavenge", None, 0), ("guard", None, 0), ("gift", 1, 1)]:
            self.assertIn("Bandits", self.check(0, (kind, tgt, amt, False)))
        self.assertIsNone(self.check(0, ("steal", 1, 0, False)))

    def test_guard_limit_exactly_three(self):
        p = self.ps[0]
        p.guards_used = 2
        self.assertIsNone(self.check(0, ("guard", None, 0, False), night=5))
        p.guards_used = 3
        self.assertIn("all 3", self.check(0, ("guard", None, 0, False), night=5))

    def test_already_protected_tonight(self):
        self.ps[0].guard_until = 2
        self.assertIn("already protected", self.check(0, ("guard", None, 0, False), night=2))

    def test_quitters_are_out_and_untargetable(self):
        self.assertIn("not in this game", self.check(1, ("scavenge", None, 0, False), quit_ids={1}))
        self.assertIn("still in the game", self.check(0, ("steal", 1, 0, False), quit_ids={1}))


class Deal(unittest.TestCase):
    def test_fair_deal_across_roster_sizes(self):
        from engine.deal import GOALS, TARGETED, deal
        for n in range(3, 21):
            for seed in range(60):
                hand = deal(range(n), random.Random(seed))
                targets = [t for g, t in hand.values() if g in TARGETED]
                self.assertEqual(len(targets), len(set(targets)), f"n={n} seed={seed}: someone targeted twice")
                for p, (g, t) in hand.items():
                    self.assertEqual(g in TARGETED, t >= 0)
                    self.assertNotEqual(p, t, "self-target")
                    if t >= 0 and hand[t][0] in TARGETED:
                        self.assertNotEqual(hand[t][1], p, f"n={n} seed={seed}: mutual pair {p}<->{t}")
                counts = Counter(g for g, _ in hand.values())
                full = [counts.get(g, 0) for g in GOALS]
                self.assertLessEqual(max(full) - min(full), 1, f"n={n}: goal types uneven {counts}")

    def test_detective_scores_after_one_exposure(self):
        ps = players(3)
        ps[1].objective = "detective"
        for p in (ps[0], ps[2]):
            p.objective = "give"
        run_night(ps, {0: ("steal", 2, 0, False), 1: ("investigate", 0, 0, False), 2: ("scavenge", None, 0, False)})
        self.assertEqual(ps[1].exposures, 1)
        finish(ps, Rules(), random.Random(1))
        self.assertTrue(ps[1].obj_done)


class Finish(unittest.TestCase):
    def test_seats_come_from_the_roster_not_the_rules(self):
        ps = players(11)
        for i, p in enumerate(ps):
            p.objective = "give"
        res = finish(ps, Rules(players=15), random.Random(1))
        self.assertEqual(res["seats"], 4, "11 players x 1/3 = 4 seats, not 15 x 1/3 = 5")

    def test_goal_aimed_at_a_quitter_is_void(self):
        ps = players(3)
        ps[0].objective, ps[0].obj_target = "beat", 1
        ps[1].rations = 0
        for p in ps[1:]:
            p.objective = "give"
        finish(ps, Rules(), random.Random(1), quit_ids={1})
        self.assertFalse(ps[0].obj_done)


if __name__ == "__main__":
    unittest.main()
