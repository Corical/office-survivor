"""Game service tests: a whole compressed game with sim colleagues, restart replay, deadline, privacy of replies.

    python -m unittest discover -s bot/tests -t .
"""
import random
import unittest

from bot.game import GameError, GameService, news_lines, private_lines
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from engine import Rules

ALIASES = [f"Alias{i:02d}" for i in range(30)]


def service(store=None, ident=None, texts=None):
    return GameService(Rules(), store or MemoryEventStore(), ident or MemoryIdentityStore(),
                       texts or MemoryTextStore(), ALIASES, "test-season", clock=lambda: 0)


class FullGame(unittest.TestCase):
    def test_compressed_game_with_sims_runs_to_the_reveal_and_replays(self):
        store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
        g = service(store, ident, texts)
        g.join("human-a", rng=random.Random(1))
        g.join("human-b", rng=random.Random(2))
        g.gm_add_sims(8, rng=random.Random(3))
        g.gm_start(day_seconds=300, news_delay=5, now=0)
        b_alias = ident.get("human-b")["alias"]
        for night in range(1, 11):
            g.submit("human-a", "steal", b_alias, at=night * 300 - 10)
            g.tick(now=night * 300 + 10)
        self.assertTrue(g.finished)
        self.assertTrue(any("helicopter" in g.outbox_text(i) for i in g.pending_outbox()))
        # restart: a fresh service on the same log rebuilds and re-resolves every night identically
        again = service(store, ident, texts)
        self.assertTrue(again.finished)
        self.assertEqual({p: (s.rations, s.bandit) for p, s in again.players.items()},
                         {p: (s.rations, s.bandit) for p, s in g.players.items()})

    def test_reveal_picture_is_built_from_the_finish_record(self):
        from bot.reveal_image import awards, render
        g = service()
        self.assertIsNone(g.reveal_data())                       # nothing to show before the end
        g.join("a", rng=random.Random(1))
        g.gm_add_sims(6, rng=random.Random(3))
        g.gm_start(day_seconds=300, now=0)
        for night in range(1, 11):
            g.tick(now=night * 300 + 10)
        rows, winners = g.reveal_data()
        self.assertEqual(len(rows), 7)
        self.assertEqual([r["score"] for r in rows], sorted((r["score"] for r in rows), reverse=True))
        self.assertTrue(set(winners) <= {r["player"] for r in rows})
        self.assertTrue(render(rows, winners).startswith(b"\x89PNG"))
        intent = next(i for i in g.pending_outbox() if i.get("image") == "reveal")
        head = g.outbox_text(intent).split("\n\n**The reveal**")[0]
        self.assertIn("helicopter", head)
        self.assertFalse(any(r["player"] + ":" in head for r in rows))   # per-player lines live in the picture

    def test_awards_share_ties_and_say_nobody_for_zero(self):
        from bot.reveal_image import awards
        rows = [{"player": n, "stole": s, "times_robbed": 1, "gave_away": 0, "rations": 3} for n, s in (("A", 2), ("B", 2))]
        got = {t: (who, top) for t, who, top in awards(rows)}
        self.assertEqual(got["Biggest thief"], ("A, B", 2))
        self.assertEqual(got["Most generous"], ("nobody", 0))

    def test_events_game_books_every_ration_and_replays_identically(self):
        store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
        g = service(store, ident, texts)
        g.join("human", rng=random.Random(1))
        g.gm_add_sims(9, rng=random.Random(3))
        g.gm_start(day_seconds=300, now=0, events="gentle")
        start = {pid: p.rations for pid, p in g.players.items()}
        for night in range(1, 11):
            g.tick(now=night * 300 + 10)
        self.assertTrue(g.finished)
        nights = [r for r in store.records if r["type"] == "night"]
        evs = [e for r in nights for e in r["events"]]
        self.assertGreater(sum(1 for e in evs if e["type"] == "event"), 3)          # events actually happened
        lines = [l for r in nights for l in news_lines(r["events"])]
        self.assertTrue(any(e.get("line") in lines for e in evs if e["type"] == "event" and e.get("line")))
        # the books: every ration change, events included, is a ration line (quitters aside, none here)
        for pid, p in g.players.items():
            booked = sum(e["delta"] for e in evs if e["type"] == "ration" and e["player"] == p.name)
            self.assertEqual(start[pid] + booked, p.rations, f"{p.name}: unbooked change")
        again = service(store, ident, texts)                                       # restart: replay re-checks
        self.assertEqual({p: s.rations for p, s in again.players.items()}, {p: s.rations for p, s in g.players.items()})
        self.assertEqual(again.events_mode, "gentle")
        # story decks run across the whole game: no event line repeats until its deck is used up
        from engine.events import VARIANTS
        seen = {}
        for e in evs:
            if e["type"] == "event" and e.get("line") and e["event"] in VARIANTS:
                seen.setdefault(e["event"], []).append(e["line"].split(" ", 1)[1].replace(e.get("player", ""), "{who}"))
        for eid, used in seen.items():
            first = used[:len(VARIANTS[eid])]
            self.assertEqual(len(first), len(set(first)), f"{eid} repeated a story before using its whole deck")

    def test_events_off_by_default_and_old_logs_without_the_key_load(self):
        store = MemoryEventStore()
        g = service(store)
        g.gm_add_sims(4, rng=random.Random(1))
        g.gm_start(day_seconds=60, now=0)
        g.tick(now=61)
        self.assertFalse(any(e["type"] == "event" for r in store.records if r["type"] == "night" for e in r["events"]))
        for r in store.records:
            r.pop("events", None) if r["type"] == "start" else None
        self.assertEqual(service(store).events_mode, "off")
        with self.assertRaises(GameError):
            service().gm_start(day_seconds=60, now=0, events="chaos")

    def test_morning_ranges_put_every_active_player_in_their_true_band_once(self):
        from engine.visibility import BAND_LABELS, band_index
        g = service()
        g.join("human", rng=random.Random(1))
        g.gm_add_sims(9, rng=random.Random(3))
        g.gm_start(day_seconds=300, now=0, ranges=True)
        g.quit("human") if hasattr(g, "quit") else None
        for night in range(1, 11):
            g.tick(now=night * 300 + 10)
            news = [g.outbox_text(i) for i in g.pending_outbox() if i["to"] == "news" and f"Night {night} " in g.outbox_text(i)]
            if not news:
                continue
            board = news[0].split("📊 **Rations this morning**\n")[1].split("\n")
            placed = {}
            for line in board:
                label, names = line.split(": ", 1)
                for n in names.split(", "):
                    self.assertNotIn(n, placed, f"night {night}: {n} listed twice")
                    placed[n] = label
            active = [p for pid, p in g.players.items() if pid not in g.quit_ids]
            self.assertEqual(set(placed), {p.name for p in active}, f"night {night}: wrong roster on the board")
            for p in active:                                  # bandits under the flag even when holding food
                self.assertEqual(placed[p.name], BAND_LABELS[band_index(p)], f"night {night}: {p.name} misplaced")

    def test_ranges_off_by_default_and_status_shows_your_band_only_when_on(self):
        g = service()
        g.join("a", rng=random.Random(1))
        g.join("b", rng=random.Random(2))
        g.gm_start(day_seconds=300, now=0)
        g.tick(now=310)
        g.tick(now=320)
        self.assertFalse(any("Rations this morning" in g.outbox_text(i) for i in g.pending_outbox()))
        self.assertNotIn("camp sees you", g.status("a"))
        h = service()
        h.join("a", rng=random.Random(1))
        h.join("b", rng=random.Random(2))
        h.gm_start(day_seconds=300, now=0, ranges=True)
        from engine.visibility import band_label
        p = h.players[h.identity.get("a")["pid"]]
        for rations, bandit in ((9, False), (4, False), (1, False), (2, True)):
            p.rations, p.bandit = rations, bandit
            self.assertIn(f"The camp sees you as {band_label(p)}.", h.status("a"))
        self.assertIn("🏴‍☠️ bandit", h.status("a"))                       # a bandit with food is still a bandit

    def test_idol_stories_reach_news_thief_and_holder(self):
        from types import SimpleNamespace
        evs = [{"type": "event", "event": "idol", "scope": "player", "player": "Holder", "visibility": "private"},
               {"type": "event", "event": "idol_used", "player": "Holder", "visibility": "public"},
               {"type": "steal", "thief": "Thief", "target": "Holder", "outcome": "empty", "amount": 0, "split_with": 0}]
        news = " ".join(news_lines(evs))
        self.assertIn("hidden idol", news)
        self.assertNotIn("found nothing", news)                  # the idol line replaces the empty-break-in line
        self.assertNotIn("found a hidden idol", news)            # finding it stays secret
        holder = " ".join(private_lines(evs, SimpleNamespace(name="Holder", rations=4), 4))
        self.assertIn("found a hidden idol", holder)
        self.assertIn("idol saved you", holder)
        thief = " ".join(private_lines(evs, SimpleNamespace(name="Thief", rations=3), 3))
        self.assertIn("had a hidden idol", thief)
        self.assertNotIn("beat you to it", thief)

    def test_tampered_log_refuses_to_load(self):
        store = MemoryEventStore()
        g = service(store)
        g.gm_add_sims(4, rng=random.Random(1))
        g.gm_start(day_seconds=60, now=0)
        g.tick(now=61)
        night = next(r for r in store.records if r["type"] == "night")
        night["events"][0]["found" if "found" in night["events"][0] else "type"] = "tampered"
        with self.assertRaises(RuntimeError):
            service(store)


class Rules_(unittest.TestCase):
    def setUp(self):
        self.g = service()
        self.g.join("a", rng=random.Random(1))
        self.g.join("b", rng=random.Random(2))
        self.g.gm_start(day_seconds=300, now=0)

    def test_move_after_the_deadline_is_refused(self):
        with self.assertRaises(GameError):
            self.g.submit("a", "scavenge", at=300)
        self.g.submit("a", "scavenge", at=299.999)

    def test_illegal_move_is_refused_with_a_reason(self):
        me = self.g.identity.get("a")["alias"]
        with self.assertRaises(GameError) as e:
            self.g.submit("a", "steal", me, at=1)
        self.assertIn("yourself", str(e.exception))

    def test_tick_twice_resolves_once(self):
        self.g.tick(now=310)
        self.g.tick(now=310)
        self.assertEqual(sum(1 for r in self.g.store.records if r["type"] == "night"), 1)

    def test_news_intents_are_written_once_even_if_ticked_again(self):
        self.g.tick(now=310)
        self.g.tick(now=320)
        n = len([i for i in self.g.pending_outbox() if i["to"] == "news"])
        self.g.tick(now=330)
        self.assertEqual(len([i for i in self.g.pending_outbox() if i["to"] == "news"]), n)

    def test_radio_is_fixed_phrases_and_one_a_day(self):
        other = self.g.identity.get("b")["alias"]
        self.g.radio("a", "trust", other)
        self.assertEqual(self.g.texts.get(self.g.radio_pending[0]), f"Don't trust {other}.")
        with self.assertRaises(GameError):
            self.g.radio("a", "me")                       # one a day
        with self.assertRaises(GameError):
            self.g.radio("b", "trust")                    # needs a player
        with self.assertRaises(GameError):
            self.g.radio("b", "<script>")                 # only the fixed lines
        self.g.radio("b", "me")
        self.g.tick(now=310)
        self.g.tick(now=320)
        radio = [self.g.outbox_text(i) for i in self.g.pending_outbox() if i["to"] == "radio"]
        self.assertEqual(sorted(radio), sorted([f"Don't trust {other}.", "I'm innocent. Leave me alone."]))

    def test_player_list_never_offers_your_own_alias(self):
        me, other = self.g.identity.get("a")["alias"], self.g.identity.get("b")["alias"]
        self.assertNotIn(me, self.g.alias_list("a"))
        self.assertIn(other, self.g.alias_list("a"))
        self.assertIn(me, self.g.alias_list("b"))

    def test_night_labels_anchor_to_real_time(self):
        from bot.game import Schedule, night_label
        pilot = Schedule(start_ts=1792217089.8, day_seconds=300)          # 17 Oct 2026 08:04:49 SAST
        self.assertEqual(night_label(pilot, 6), "Night 6 (closes 08:34)")
        self.assertEqual(night_label(pilot, 6, closed=True), "Night 6 (closed 08:34)")
        # news and night DMs go out after the deadline, so they say 'closed'; the move reply says 'closes'
        self.g.tick(now=310)
        self.g.tick(now=320)
        posted = [t for t in (self.g.outbox_text(i) for i in self.g.pending_outbox()) if "Night 1" in t]
        self.assertEqual(len(posted), 3)                                  # #news + a DM for each of the 2 players
        self.assertTrue(all("(closed " in t and "(closes " not in t for t in posted))
        self.assertIn("(closes ", self.g.submit("a", "scavenge", at=330))
        real = Schedule(start_ts=1791756000.0, day_seconds=86400)         # Mon 12 Oct 2026 00:00 SAST
        self.assertEqual(night_label(real, 1), "Night 1 (Mon)")            # closes at Tuesday 00:00: Monday's night
        self.assertEqual(night_label(real, 2), "Night 2 (Tue)")

    def test_play_menu_offers_only_what_the_server_accepts(self):
        me, other = self.g.identity.get("a")["alias"], self.g.identity.get("b")["alias"]
        m = self.g.play_menu("a")
        self.assertEqual(set(m["moves"]), {"scavenge", "guard", "steal", "investigate", "gift"})
        self.assertNotIn(me, m["moves"]["steal"])
        # every offered move is accepted by submit
        for kind, targets in m["moves"].items():
            for t in targets or [None]:
                self.g.submit("a", kind, t, m["gift_amounts"][0] if kind == "gift" else 0, at=1)
        # a bandit is offered steal and investigate only, and no guard after guards run out
        p = self.g.players[self.g.identity.get("a")["pid"]]
        p.bandit = True
        self.assertEqual(set(self.g.play_menu("a")["moves"]), {"steal", "investigate"})
        p.bandit, p.guards_used = False, self.g.rules.guard_limit
        self.assertNotIn("guard", self.g.play_menu("a")["moves"])
        p.rations = 1                                     # can't gift: must keep 1
        self.assertNotIn("gift", self.g.play_menu("a")["moves"])
        p.rations = 2
        self.assertEqual(self.g.play_menu("a")["gift_amounts"], [1])
        self.assertIn(other, self.g.play_menu("a")["moves"]["gift"])

    def test_radio_menu_matches_what_radio_accepts_and_tracks_the_daily_message(self):
        me, other = self.g.identity.get("a")["alias"], self.g.identity.get("b")["alias"]
        m = self.g.radio_menu("a")
        self.assertTrue(m["available"] and self.g.play_menu("a")["radio"])
        self.assertNotIn(me, m["about"])
        self.assertFalse(any("{a}" in t for _, t in m["lines"]))          # placeholders shown as '…'
        phrase = next(k for k, _ in m["lines"] if GameService.radio_needs_player(k))
        self.g.radio("a", phrase, m["about"][0])
        self.assertFalse(self.g.radio_menu("a")["available"])           # one a day: the button goes away
        self.assertFalse(self.g.play_menu("a")["radio"])
        self.assertTrue(self.g.radio_menu("b")["available"])            # other players unaffected
        self.g.tick(now=310)
        self.assertTrue(self.g.radio_menu("a")["available"])            # a new day, a new message
        self.assertEqual(other, m["about"][0])

    def test_play_menu_refused_before_start_and_for_strangers(self):
        g = service()
        g.join("x", rng=random.Random(5))
        with self.assertRaises(GameError):
            g.play_menu("x")
        with self.assertRaises(GameError):
            self.g.play_menu("nobody")

    def test_unlucky_thief_learns_someone_beat_them_to_it(self):
        from types import SimpleNamespace
        from bot.game import private_lines
        p = SimpleNamespace(name="Unlucky", rations=3)
        shared = [{"type": "steal", "thief": "Unlucky", "target": "Wobbly", "outcome": "empty", "amount": 0, "split_with": 1}]
        alone = [{"type": "steal", "thief": "Unlucky", "target": "Wobbly", "outcome": "empty", "amount": 0, "split_with": 0}]
        self.assertIn("someone beat you to it", " ".join(private_lines(shared, p, 3)))
        self.assertIn("found nothing", " ".join(private_lines(alone, p, 3)))
        self.assertNotIn("beat you", " ".join(private_lines(alone, p, 3)))

    def test_join_closed_after_start(self):
        with self.assertRaises(GameError):
            self.g.join("late")

    def test_status_never_mentions_other_players_rations(self):
        other = self.g.identity.get("b")["alias"]
        self.assertNotIn(other, self.g.status("a").split("Secret goal")[0])


if __name__ == "__main__":
    unittest.main()
