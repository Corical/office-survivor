"""No view leaks what its seat may not know. Proven by non-interference, not by a list of forbidden words:
scramble every hidden fact about the OTHER seats, rebuild my view, and it must not change by a single byte.

Hidden from a seat during play: the others' picks, goals, private lines and exact rations (only the band is public
when ranges are on), which of them have locked (only the count is public), and which seats are bots.
"""
import copy
from dataclasses import replace
import json
import random
import unittest

from arena import views
from arena.room import FakeScheduler, RoomGame, RoomSettings
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from bot.tests.test_core_fixtures import _official
from engine.deal import GOALS
from engine.visibility import band_index

ALIASES = [f"Alias{i:02d}" for i in range(30)]
BAND_VALUES = {0: range(7, 20), 1: range(3, 7), 2: range(1, 3)}


def new_room(seed, humans, ranges):
    sched = FakeScheduler()
    g = RoomGame(_official(), MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore(), ALIASES,
                 f"leak-{seed}", sched, RoomSettings(ranges=ranges))
    for i in range(humans):
        g.add_human(f"u{i}")
        g.connect(i)
    g.start()
    return g, sched


def scramble(g, me, rng):
    """A copy of the room where everything `me` may not know about the others is different."""
    h = copy.deepcopy(g)
    others = [p for p in h._active() if p.pid != me]
    for q in others:
        if rng.random() < 0.5:
            h.moves.pop(q.pid, None)
        else:
            moves, amounts = h.legal_for(q.pid)
            kind = rng.choice(sorted(moves))
            tgt = rng.choice(moves[kind]) if moves[kind] else None
            tid = next((x.pid for x in h.players.values() if x.name == tgt), None)
            h.moves[q.pid] = (kind, tid, amounts[0] if kind == "gift" and amounts else 0, False)
        q.objective = rng.choice(GOALS)
        q.obj_target = rng.choice([x.pid for x in h.players.values() if x.pid != q.pid])
        if not q.bandit:
            q.rations = rng.choice(list(BAND_VALUES[band_index(q)]))
    # which others locked: same count, different seats
    locked_others = [q.pid for q in others if q.pid in h.locked]
    h.locked = {x for x in h.locked if x == me or x not in {q.pid for q in others}}
    h.locked |= set(rng.sample([q.pid for q in others], len(locked_others)))
    # which seats are bots
    h.sims = set(rng.sample([q.pid for q in others], rng.randint(0, len(others))))
    # the others' private lines in every stored night
    recs = []
    for r in h.store.records:
        if r["type"] == "night":
            r = copy.deepcopy(r)
            for k in list(r["private"]):
                if k != str(me):
                    r["private"][k] = [{"code": "now_have", "args": {"rations": rng.randint(0, 99)}}]
        recs.append(r)
    h.store.records = recs
    return h


def dump(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


class NonInterference(unittest.TestCase):
    def test_scrambling_the_others_never_changes_my_view(self):
        checked = 0
        for seed in range(30):
            rng = random.Random(seed)
            g, sched = new_room(seed, humans=1 + seed % 4, ranges=seed % 2 == 0)
            humans = list(range(1 + seed % 4))
            while not g.finished:
                if g.phase == "round":
                    for p in humans:
                        if rng.random() < 0.6:
                            moves, amounts = g.legal_for(p)
                            kind = rng.choice(sorted(moves))
                            tgt = rng.choice(moves[kind]) if moves[kind] else None
                            g.pick(p, kind, tgt, amounts[0] if kind == "gift" and amounts else 0)
                            if rng.random() < 0.5:
                                g.lock(p)
                    sched.advance(sched.now() + rng.choice([3, 30, 70]))
                for me in humans:
                    if g.phase in ("round", "reveal"):
                        mine = dump(views.view_for(g, me))
                        for k in range(3):
                            self.assertEqual(dump(views.view_for(scramble(g, me, random.Random(k)), me)), mine,
                                             f"seed {seed} phase {g.phase} round {g.round} seat {me}")
                            checked += 1
                if g.phase == "round":
                    sched.advance(g.deadline)
                elif g.phase == "reveal":
                    sched.advance(g.reveal_until)
        self.assertGreater(checked, 1000)

    def test_the_scramble_really_changes_things_a_view_must_hide(self):
        """Guard against a scramble that changes nothing (the test above would pass vacuously)."""
        g, sched = new_room(1, humans=2, ranges=True)
        g.pick(1, "guard")
        h = scramble(g, 0, random.Random(3))
        self.assertNotEqual((h.moves, h.sims, [p.objective for p in h.players.values()]),
                            (g.moves, g.sims, [p.objective for p in g.players.values()]))

    def test_a_view_that_peeks_is_caught(self):
        """Mutation check of the test itself: a view leaking one hidden fact must fail non-interference."""
        g, sched = new_room(2, humans=1, ranges=True)
        leaky = lambda g, me: {**views.round_view(g, me), "x": sorted(g.sims)}     # noqa: E731
        diffs = sum(dump(leaky(scramble(g, 0, random.Random(k)), 0)) != dump(leaky(g, 0)) for k in range(5))
        self.assertGreater(diffs, 0)


class GoalLines(unittest.TestCase):
    def test_a_goal_and_its_progress_travel_as_lines_that_render_to_their_english(self):
        """Client request 4: `line` (code + values) and `text` are the same words, for every seat in every game."""
        from arena.lines import ALL_EN, render
        seen = set()
        for seed in range(40):
            rng = random.Random(seed)
            g, sched = new_room(seed, humans=1 + seed % 4, ranges=seed % 2 == 0)
            humans = list(range(1 + seed % 4))
            while not g.finished:
                if g.phase == "round":
                    for me in humans:
                        v = views.round_view(g, me)["me"]
                        for part in (v["goal"], v["goal_progress"]):
                            self.assertIn(part["line"]["code"], ALL_EN)
                            self.assertEqual(render(part["line"]), part["text"], f"seed {seed} seat {me}")
                            seen.add(part["line"]["code"])
                        moves, amounts = g.legal_for(me)
                        if rng.random() < 0.7:
                            kind = rng.choice(sorted(moves))
                            tgt = rng.choice(moves[kind]) if moves[kind] else None
                            g.pick(me, kind, tgt, amounts[0] if kind == "gift" and amounts else 0)
                    sched.advance(g.deadline)
                else:
                    sched.advance(g.reveal_until)
            for res in views.end_view(g, 0)["results"]:
                self.assertEqual(render(res["goal"]["line"]), res["goal"]["text"])
        goals = {c for c in seen if c.startswith("goal_")}
        # The goal deck is dealt in order, one card per seat: with 4 seats only the first four goal types exist.
        # (grudge and detective need 5+ seats: a design fact the owner has been told, pinned here.)
        self.assertEqual(goals, {"goal_beat", "goal_robbed2_extract", "goal_steal3_clean", "goal_give"})

    def test_all_six_goals_render_when_forced_even_the_two_a_four_seat_room_never_deals(self):
        from arena.lines import render
        from engine.deal import GOALS as ALL_GOALS
        g, sched = new_room(5, humans=1, ranges=True)
        p = g.players[0]
        for goal in ALL_GOALS:
            for grudge_goal in ("rob", "deny"):
                g.rules = replace(g.rules, grudge_goal=grudge_goal)
                p.objective, p.obj_target = goal, (1 if goal in ("beat", "grudge") else -1)
                v = views.round_view(g, 0)["me"]
                self.assertEqual(render(v["goal"]["line"]), v["goal"]["text"], goal)
                self.assertEqual(render(v["goal_progress"]["line"]), v["goal_progress"]["text"], goal)
                p.obj_target = 1 if goal in ("beat", "grudge") else -1
        g.quit_ids.add(1)                                   # a hunter whose target left
        p.objective, p.obj_target = "beat", 1
        v = views.round_view(g, 0)["me"]
        self.assertEqual(v["goal_progress"]["line"]["code"], "progress_target_left")
        self.assertEqual(v["goal_progress"]["state"], "failed")

    def test_goal_lines_use_the_players_own_numbers_and_the_targets_alias_not_its_rations(self):
        g, sched = new_room(3, humans=1, ranges=True)
        v = views.round_view(g, 0)["me"]
        text = json.dumps(v)
        target = g.players[g.players[0].obj_target].name if g.players[0].obj_target >= 0 else None
        for q in g.players.values():
            if q.pid != 0:
                self.assertNotIn(f"{q.name} has {q.rations}", text)
        if target:
            self.assertIn(target, text)


class NewsOrder(unittest.TestCase):
    def test_public_news_does_not_depend_on_the_order_the_engine_resolved_seats_in(self):
        """The engine resolves seats in seat order and humans take the low seats, so the order of the public lines would
        tell a watcher which seats are people. Shuffle each real night's events: the reveal's news must not move."""
        compared = 0
        for seed in range(25):
            rng = random.Random(seed)
            g, sched = new_room(seed, humans=1 + seed % 3, ranges=True)
            while not g.finished:
                if g.phase == "round":
                    sched.advance(g.deadline)
                    continue
                rec = g.night_record(g.closed)
                if len(views.news_codes(rec["events"])) >= 2:
                    base = views.reveal_view(g, 0)["news"]
                    for k in range(4):
                        events = list(rec["events"])
                        random.Random(seed * 10 + k).shuffle(events)
                        original = g.night_record
                        g.night_record = lambda n, e=events, r=rec: {**r, "events": e}
                        try:
                            self.assertEqual(views.reveal_view(g, 0)["news"], base, f"seed {seed} round {g.closed}")
                        finally:
                            g.night_record = original
                        compared += 1
                sched.advance(g.reveal_until)
        self.assertGreater(compared, 20, "too few nights with two or more public lines to mean anything")


class Shape(unittest.TestCase):
    def test_no_view_carries_internal_ids_or_bot_markers(self):
        bad = {"pid", "sim", "sims", "personality", "arch", "seed", "seed_key", "season", "token", "ref"}
        g, sched = new_room(4, humans=2, ranges=True)
        seen = []
        while not g.finished:
            for me in (0, 1):
                seen.append(views.view_for(g, me))
            sched.advance(g.deadline if g.phase == "round" else g.reveal_until)
        seen.append(views.view_for(g, 0))

        def keys(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from keys(v)
            elif isinstance(o, list):
                for v in o:
                    yield from keys(v)
        found = {k for v in seen for k in keys(v)} & bad
        self.assertEqual(found, set())
        self.assertEqual({v["t"] for v in seen}, {"round", "reveal", "end"})

    def test_radio_in_a_reveal_is_ordered_by_wording_not_by_who_sent_it_when(self):
        for seed in range(60):
            g, sched = new_room(seed, humans=1, ranges=False)
            g.record_radio("u0", "me")                      # the human posts first, during the round
            sched.advance(g.deadline)                       # bots post theirs at the close
            radio = views.reveal_view(g, 0)["radio"]
            if len(radio) > 1:
                texts = [g.texts.get(r) for r in g.radio_pending if r.startswith("r1-")]
                self.assertEqual([views._radio_line(t) for t in sorted(texts)], radio)
                self.assertNotEqual(sorted(texts), texts, "send order differs from the order shown") \
                    if sorted(texts) != texts else None
                return
        self.fail("no seed gave a bot radio line next to the human's")

    def test_every_radio_text_parses_back_to_its_phrase(self):
        for key, text in views.RADIO_PHRASES.items():
            line = text.format(a="Alias07")
            got = views._radio_line(line)
            self.assertEqual(got["phrase"], key)
            self.assertEqual(got["about"], "Alias07" if "{a}" in text else None)


if __name__ == "__main__":
    unittest.main()
