"""Tests that try to break exposure_undo ("none" | "split" | "full"): an exposed thief gives the loot back.

    python -m unittest discover -s engine/tests -t .

All nights here use scavenge_max=0 and eat=0 unless a test says otherwise, so every ration is accounted for by
the ledger lines alone.
"""
import random
import unittest
from collections import defaultdict
from dataclasses import replace

from engine import Observer, PlayerState, Rules, resolve_night

CREATE = {"scavenge", "guard_income", "gift_bonus"}
DESTROY = {"eat", "fine"}


def rules(mode, bounty=1, **kw):
    return replace(Rules(), exposure_undo=mode, investigate_bounty=bounty, scavenge_max=0, eat=0, **kw)


def players(n=6, rations=7):
    return [PlayerState(pid=i, name=f"P{i}", rations=rations) for i in range(n)]


def night(ps, moves, r, seed=1, obs=None, n=1):
    events = []
    res = resolve_night(ps, moves, r, random.Random(seed), n,
                        emit=lambda t, **f: events.append({"type": t, **f}), obs=obs)
    return res, events


def hold(pid=None):
    return ("scavenge", None, 0, False)


def steal(t):
    return ("steal", t, 0, False)


def inv(t):
    return ("investigate", t, 0, False)


def got(ps):
    return [p.rations for p in ps]


def books(test, ps, start, events, r):
    """Transfers net to zero, nobody is negative, and every player's ledger explains their final count."""
    held = dict(start)
    net = 0
    for e in events:
        if e["type"] == "ration":
            held[e["player"]] += e["delta"]
            if e["reason"] not in CREATE | DESTROY:
                net += e["delta"]
    test.assertEqual(net, 0, "transfers between players must net to zero")
    for p in ps:
        test.assertGreaterEqual(p.rations, 0, p.name)
        test.assertEqual(held[p.name], p.rations, f"{p.name}: ledger does not explain the final count")


class Payouts(unittest.TestCase):
    def go(self, mode, bounty=1, moves=None, ps=None, **kw):
        ps = ps or players()
        start = {p.name: p.rations for p in ps}
        m = {p.pid: hold() for p in ps}
        m.update(moves or {0: steal(3), 1: inv(0)})
        r = rules(mode, bounty, **kw)
        res, events = night(ps, m, r)
        books(self, ps, start, events, r)
        return ps, res, events

    def test_none_is_todays_night_and_its_event_has_no_new_fields(self):
        ps, _, events = self.go("none")
        self.assertEqual(got(ps)[:4], [7 + 2 - 1, 7 + 1, 7, 7 - 2])        # theft stands, bounty 1
        ex = [e for e in events if e["type"] == "exposed"][0]
        self.assertNotIn("loot_back", ex)
        self.assertFalse([e for e in events if e.get("reason", "").startswith("exposed_")])

    def test_split_two_stolen_one_each_plus_bounty(self):
        ps, _, events = self.go("split")
        # thief 7+2 -1 to victim -1 to investigator -1 bounty; victim 7-2+1; investigator 7+1+1
        self.assertEqual(got(ps)[:4], [6, 9, 7, 6])
        reasons = {e["reason"] for e in events if e["type"] == "ration"}
        self.assertTrue({"exposed_return", "exposed_loot", "bounty_paid", "bounty_received"} <= reasons)

    def test_full_returns_everything_to_the_victim(self):
        ps, _, _ = self.go("full")
        self.assertEqual(got(ps)[:4], [7 + 2 - 2 - 1, 7 + 1, 7, 7])        # victim whole again, investigator +1

    def test_full_with_bounty_two(self):
        ps, _, _ = self.go("full", bounty=2)
        self.assertEqual(got(ps)[:4], [7 + 2 - 2 - 2, 7 + 2, 7, 7])

    def test_ledger_lines_come_in_loot_then_bounty_order(self):
        _, _, events = self.go("split")
        order = [e["reason"] for e in events if e["type"] == "ration" and e["delta"] < 0 and e["player"] == "P0"]
        out = [r for r in order if r.startswith("exposed") or r.startswith("bounty")]
        self.assertEqual(out, ["exposed_return", "exposed_loot", "bounty_paid"])

    def test_bounty_zero_still_exposes_and_returns_loot_when_undo_is_on(self):
        ps, res, _ = self.go("full", bounty=0)
        self.assertEqual(got(ps)[:4], [7, 7, 7, 7])
        self.assertEqual(res.ev["exposed"], 1)
        ps, res, _ = self.go("none", bounty=0)
        self.assertEqual(res.ev["exposed"], 0, "today: no bounty, no exposure")
        self.assertEqual(got(ps)[0], 9)

    def test_invalid_mode_is_refused_not_silently_none(self):
        with self.assertRaises(ValueError):
            Rules(exposure_undo="splt")


class ThiefCannotPayMore(unittest.TestCase):
    def test_thief_holding_exactly_the_loot_pays_loot_and_no_bounty(self):
        """P0 holds 1, steals 2 from P3, but P4 takes 1 from P0 the same night: P0 ends on 2 = the loot, 0 spare."""
        ps = players(6)
        ps[0].rations = 1
        start = {p.name: p.rations for p in ps}
        r = rules("split")
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(3), 4: steal(0), 1: inv(0)})
        _, events = night(ps, m, r)
        books(self, ps, start, events, r)
        ex = [e for e in events if e["type"] == "exposed"][0]
        self.assertEqual((ex["loot_back"], ex["paid"]), (2, 0))
        self.assertEqual(ps[0].rations, 0)
        self.assertEqual(ps[1].rations, 7 + 1, "investigator gets the floor half and no bounty")
        self.assertFalse([e for e in events if e.get("reason") == "bounty_paid" and e["delta"] != 0])

    def test_partial_loot_is_taken_loot_first_and_bounty_gets_nothing(self):
        """Same setup but the loot cannot all come back: not possible to hold less than the loot in one night, so
        pin the cap itself: nothing the thief does not hold is ever moved."""
        for mode in ("split", "full"):
            for bounty in (1, 5):
                ps = players(6)
                ps[0].rations = 1
                start = {p.name: p.rations for p in ps}
                r = rules(mode, bounty)
                m = {p.pid: hold() for p in ps}
                m.update({0: steal(3), 4: steal(0), 1: inv(0)})
                _, events = night(ps, m, r)
                books(self, ps, start, events, r)
                self.assertEqual(ps[0].rations, 0, (mode, bounty))

    def test_bandit_thief_stealing_one(self):
        """A bandit on 0 steals 1. Split: the victim gets the rounded-up half (all of it), the investigator the
        rest (nothing), and the bandit has nothing left for a bounty."""
        ps = players(5)
        ps[0].bandit, ps[0].rations = True, 0
        start = {p.name: p.rations for p in ps}
        r = rules("split")
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(3), 1: inv(0)})
        _, events = night(ps, m, r)
        books(self, ps, start, events, r)
        self.assertEqual(got(ps)[:4], [0, 7, 7, 7], "theft fully undone, bandit back to 0")
        ex = [e for e in events if e["type"] == "exposed"][0]
        self.assertEqual((ex["loot_back"], ex["to_victim"], ex["to_investigator"], ex["paid"]), (1, 1, 0, 0))

    def test_bandit_thief_full_return_with_bounty(self):
        ps = players(5)
        ps[0].bandit, ps[0].rations = True, 0
        start = {p.name: p.rations for p in ps}
        r = rules("full", bounty=2)
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(3), 1: inv(0)})
        _, events = night(ps, m, r)
        books(self, ps, start, events, r)
        self.assertEqual(got(ps)[:4], [0, 7, 7, 7])


class SeveralThieves(unittest.TestCase):
    def test_only_the_exposed_thiefs_share_is_undone(self):
        for mode in ("split", "full"):
            ps = players(6)
            start = {p.name: p.rations for p in ps}
            r = rules(mode)
            m = {p.pid: hold() for p in ps}
            m.update({0: steal(3), 1: steal(3), 2: inv(0)})
            res, events = night(ps, m, r)
            books(self, ps, start, events, r)
            share = {e["thief"]: e["amount"] for e in events if e["type"] == "steal"}
            self.assertEqual(share, {"P0": 2, "P1": 2})
            self.assertEqual(ps[1].rations, 7 + 2, f"{mode}: the unexposed thief keeps everything")
            back = 2 if mode == "full" else 1
            self.assertEqual(ps[3].rations, 7 - 4 + (2 if mode == "full" else 1), mode)
            self.assertEqual(ps[0].rations, 7 + 2 - 2 - 1 if mode == "full" else 7 + 2 - 1 - 1 - 1)
            self.assertEqual(back, [e for e in events if e["type"] == "exposed"][0]["to_victim"])

    def test_uneven_split_returns_exactly_the_exposed_thiefs_own_amount(self):
        """Victim holds 3, two thieves want 2 each: shares are 2 and 1 in a seed-dependent order."""
        for seed in range(12):
            for who in (0, 1):
                ps = players(6)
                ps[3].rations = 3
                start = {p.name: p.rations for p in ps}
                r = rules("full")
                m = {p.pid: hold() for p in ps}
                m.update({0: steal(3), 1: steal(3), 2: inv(who)})
                _, events = night(ps, m, r, seed=seed)
                books(self, ps, start, events, r)
                share = {e["thief"]: e["amount"] for e in events if e["type"] == "steal"}
                self.assertEqual(sum(share.values()), 3)
                mine = share[f"P{who}"]
                other = share[f"P{1 - who}"]
                self.assertEqual(ps[3].rations, 3 - 3 + mine, "victim gets back only the exposed share")
                self.assertEqual(ps[1 - who].rations, 7 + other, "the other thief is untouched")

    def test_second_investigator_on_the_same_thief_gets_the_bounty_but_no_second_loot(self):
        for mode in ("split", "full"):
            ps = players(5)
            start = {p.name: p.rations for p in ps}
            r = rules(mode)
            m = {p.pid: hold() for p in ps}
            m.update({0: steal(3), 1: inv(0), 2: inv(0)})
            _, events = night(ps, m, r)
            books(self, ps, start, events, r)
            self.assertEqual(len([e for e in events if e["type"] == "exposed"]), 2)
            self.assertEqual(sum(e["loot_back"] for e in events if e["type"] == "exposed"), 2,
                             "the loot can only be taken back once")
            self.assertEqual(ps[2].rations, 7 + 1, "second investigator: bounty only")
            self.assertEqual(ps[0].rations, 7 + 2 - 2 - 1 - 1 if mode == "full" else 7 + 2 - 1 - 1 - 1 - 1)

    def test_investigator_is_the_victim(self):
        ps = players(4)
        start = {p.name: p.rations for p in ps}
        r = rules("split")
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(1), 1: inv(0)})
        _, events = night(ps, m, r)
        books(self, ps, start, events, r)
        self.assertEqual(ps[1].rations, 7 - 2 + 1 + 1 + 1, "robbed 2, gets 1 + 1 back and the bounty")
        self.assertEqual(ps[0].rations, 6)


class NothingToTakeBack(unittest.TestCase):
    def test_thief_who_hit_a_guard_is_exposed_for_the_bounty_only(self):
        for mode in ("split", "full"):
            ps = players(5)
            start = {p.name: p.rations for p in ps}
            r = rules(mode)
            m = {p.pid: hold() for p in ps}
            m.update({0: steal(3), 3: ("guard", None, 0, False), 1: inv(0)})
            _, events = night(ps, m, r)
            books(self, ps, start, events, r)
            ex = [e for e in events if e["type"] == "exposed"][0]
            self.assertEqual((ex["loot_back"], ex["to_victim"], ex["to_investigator"]), (0, 0, 0))
            self.assertEqual(ps[0].rations, 7 - 2 - 1, "caught penalty 2 then the bounty; no loot to return")
            self.assertEqual(ps[3].rations, 7 + 2, "the guard keeps what the thief paid")

    def test_idol_victim_means_no_loot_to_return(self):
        ps = players(5)
        ps[3].idol = True
        start = {p.name: p.rations for p in ps}
        r = rules("full")
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(3), 1: inv(0)})
        _, events = night(ps, m, r)
        books(self, ps, start, events, r)
        self.assertEqual(ps[3].rations, 7)
        self.assertEqual([e for e in events if e["type"] == "exposed"][0]["loot_back"], 0)
        self.assertEqual(ps[0].rations, 6)

    def test_empty_theft_from_a_player_with_nothing(self):
        ps = players(5)
        ps[3].rations = 0
        ps[3].bandit = True
        start = {p.name: p.rations for p in ps}
        r = rules("split")
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(3), 1: inv(0)})
        _, events = night(ps, m, r)
        books(self, ps, start, events, r)
        self.assertEqual(got(ps)[:2], [6, 8], "nothing taken, nothing returned, bounty only")

    def test_investigating_a_guard_or_a_scavenger_does_nothing(self):
        for target_move in (("guard", None, 0, False), hold()):
            ps = players(4)
            start = {p.name: p.rations for p in ps}
            r = rules("split")
            m = {p.pid: hold() for p in ps}
            m.update({0: target_move, 1: inv(0)})
            res, events = night(ps, m, r)
            books(self, ps, start, events, r)
            self.assertEqual(res.ev["exposed"], 0)
            self.assertEqual(got(ps), [7, 7, 7, 7])

    def test_investigating_someone_who_investigates_or_gifts_exposes_nobody(self):
        ps = players(4)
        r = rules("full")
        m = {p.pid: hold() for p in ps}
        m.update({0: inv(2), 1: inv(0), 2: ("gift", 3, 1, False)})
        res, _ = night(ps, m, r)
        self.assertEqual(res.ev["exposed"], 0)


class Hooks(unittest.TestCase):
    def test_restored_hook_fires_once_with_the_victims_amount_and_only_in_undo_modes(self):
        seen = []

        class Obs(Observer):
            def restored(self, night, victim, thief, amount):
                seen.append((victim.name, thief.name, amount))

        for mode, want in (("none", []), ("split", [("P3", "P0", 1)]), ("full", [("P3", "P0", 2)])):
            seen.clear()
            ps = players(5)
            m = {p.pid: hold() for p in ps}
            m.update({0: steal(3), 1: inv(0)})
            night(ps, m, rules(mode), obs=Obs())
            self.assertEqual(seen, want, mode)

    def test_exposed_paid_reported_to_the_observer_is_everything_the_thief_handed_over(self):
        seen = []

        class Obs(Observer):
            def investigated(self, night, inv, tgt, seen_move, exposed_paid):
                seen.append(exposed_paid)

        ps = players(5)
        m = {p.pid: hold() for p in ps}
        m.update({0: steal(3), 1: inv(0)})
        night(ps, m, rules("full"), obs=Obs())
        self.assertEqual(seen, [3], "2 of loot + the bounty of 1")


class Randomised(unittest.TestCase):
    def test_every_night_balances_under_random_moves_in_every_mode(self):
        for mi, (mode, bounty) in enumerate([("split", 1), ("full", 1), ("full", 2), ("split", 0), ("split", 3)]):
            r = replace(Rules(), exposure_undo=mode, investigate_bounty=bounty)
            rng = random.Random(mi)
            for game in range(60):
                ps = players(8, rations=rng.randint(0, 9))
                for p in ps:
                    p.bandit = p.rations == 0
                for nt in range(1, 11):
                    moves = {}
                    for p in ps:
                        kind = rng.choice(["scavenge", "steal", "steal", "guard", "investigate", "investigate", "gift"])
                        others = [q.pid for q in ps if q.pid != p.pid]
                        tgt = rng.choice(others) if kind in ("steal", "investigate", "gift") else None
                        moves[p.pid] = (kind, tgt, rng.choice([1, 2]) if kind == "gift" else 0, False)
                    start = {p.name: p.rations for p in ps}
                    before = sum(p.rations for p in ps)
                    _, events = night(ps, moves, r, seed=game * 100 + nt, n=nt)
                    rat = [e for e in events if e["type"] == "ration"]
                    made = sum(e["delta"] for e in rat if e["reason"] in CREATE)
                    lost = sum(e["delta"] for e in rat if e["reason"] in DESTROY)
                    books(self, ps, start, events, r)
                    self.assertEqual(sum(p.rations for p in ps), before + made + lost, (mode, bounty, game, nt))
                    for e in events:
                        if e["type"] == "exposed":
                            self.assertEqual(e["to_victim"] + e["to_investigator"], e["loot_back"])
                            self.assertGreaterEqual(e["to_victim"], e["to_investigator"])
                    # food in exposed_* lines only ever moves from the thief
                    for e in rat:
                        if e["reason"] in ("exposed_return", "exposed_loot"):
                            self.assertTrue(e["delta"] != 0)


if __name__ == "__main__":
    unittest.main()
