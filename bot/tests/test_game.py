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

    def test_status_board_counts_down_to_the_right_deadline_and_changes_only_when_content_does(self):
        g = service()
        self.assertIsNone(g.board())                                     # nobody joined: no board
        g.join("a", rng=random.Random(1))
        self.assertIn("Waiting for the Game Master", g.board()[1])
        g.gm_add_sims(3, rng=random.Random(2))
        g.gm_start(day_seconds=300, now=1000, events="gentle", ranges=True)
        k1, t1 = g.board()
        self.assertIn("Night 1 of 10", t1)
        self.assertIn("<t:1300:R>", t1)                                  # Discord renders the live countdown
        self.assertIn("🌴 Events on", t1)
        self.assertIn("📊 Ranges on", t1)
        g.tick(now=1301)                                                 # night 1 resolved, news not out yet
        self.assertNotEqual(g.board()[0], k1)
        self.assertIn("<t:1600:R>", g.board()[1])                        # now counting down to night 2
        k2 = g.board()[0]
        g.tick(now=1302)                                                 # nothing new: same board, no repost
        self.assertEqual(g.board()[0], k2)
        g.tick(now=1320)                                                 # news posted: board moves under it
        self.assertNotEqual(g.board()[0], k2)
        for night in range(2, 11):
            g.tick(now=1000 + night * 300 + 30)
        g.tick(now=5000)
        self.assertTrue(g.finished)
        self.assertIn("Game over", g.board()[1])
        self.assertNotIn("<t:", g.board()[1])                            # no countdown to a deadline that's gone

    def test_goal_progress_never_promises_what_the_reveal_takes_away(self):
        """Over many games: 'met' mid-game must score as met at the end, 'lost' must never score; and the
        beat-someone goal must never show the target's exact rations."""
        from engine.finish import goal_progress
        checked = {"done": 0, "failed": 0}
        for seed in range(40):
            g = service()
            g.join("h", rng=random.Random(seed))
            g.gm_add_sims(9, rng=random.Random(seed + 100))
            g.gm_start(day_seconds=300, now=0, events="gentle" if seed % 2 else "off", ranges=bool(seed % 3))
            promised = {}
            for night in range(1, 11):
                g.tick(now=night * 300 + 10)
                for pid, p in g.players.items():
                    state, text = goal_progress(p, list(g.players.values()), g.rules, frozenset(g.quit_ids))
                    if state in ("done", "failed"):
                        promised.setdefault(pid, (state, night))
                    if p.objective == "beat":
                        tgt = g.players[p.obj_target]
                        self.assertNotIn(f"{tgt.name} has", text)
                        bare = text.replace(tgt.name, "").replace(f"you have {p.rations}", "")
                        self.assertFalse(any(ch.isdigit() for ch in bare),
                                         f"seed {seed}: beat-goal text shows a number beyond your own: {text!r}")
            g.tick(now=5000)
            self.assertTrue(g.finished)
            for pid, (state, night) in promised.items():
                p = g.players[pid]
                checked[state] += 1
                self.assertEqual(p.obj_done, state == "done",
                                 f"seed {seed}: {p.name} ({p.objective}) shown {state} on night {night}, "
                                 f"scored {p.obj_done} at the end")
        self.assertGreater(checked["done"], 10)            # the test must actually see both kinds
        self.assertGreater(checked["failed"], 3)

    def test_three_clean_steals_lock_the_goal_even_if_caught_later(self):
        """Owner's case: 3/3 clean steals, then caught on a later steal: the goal stays met, at the reveal too."""
        from engine import PlayerState, Rules, resolve_night
        from engine.finish import finish, goal_progress
        r = Rules()

        def game():
            ps = [PlayerState(pid=i, name=f"P{i}", rations=8) for i in range(4)]
            ps[0].objective, ps[0].obj_target = "steal3_clean", -1
            for q in ps[1:]:
                q.objective, q.obj_target = "give", -1
            return ps

        def night(ps, n, move0, guard_target=None):
            moves = {q.pid: ("guard", None, 0, False) if q.pid == guard_target else ("scavenge", None, 0, False)
                     for q in ps}
            moves[0] = move0
            resolve_night(ps, moves, r, random.Random(n), n)

        ps = game()                                            # 3 clean steals, then caught on night 4
        for n, victim in ((1, 1), (2, 2), (3, 3)):
            night(ps, n, ("steal", victim, 0, False))
        self.assertEqual(goal_progress(ps[0], ps, r)[0], "done")
        night(ps, 4, ("steal", 1, 0, False), guard_target=1)
        self.assertEqual(ps[0].steals_caught, 1)
        self.assertEqual(goal_progress(ps[0], ps, r)[0], "done")
        finish(ps, r, random.Random(0))
        self.assertTrue(ps[0].obj_done)

        ps = game()                                            # caught at 2: lost, even with 5 clean steals after
        night(ps, 1, ("steal", 1, 0, False))
        night(ps, 2, ("steal", 2, 0, False))
        night(ps, 3, ("steal", 3, 0, False), guard_target=3)
        for n in range(4, 9):
            night(ps, n, ("steal", 1 + n % 3, 0, False))
        self.assertGreaterEqual(ps[0].steals_ok, 3)
        self.assertEqual(goal_progress(ps[0], ps, r)[0], "failed")
        finish(ps, r, random.Random(0))
        self.assertFalse(ps[0].obj_done)

    def test_owners_night_5_dm_explains_every_ration(self):
        """Guard from the night before, no move chosen, a thief caught: the DM must say the guard was still up,
        the scavenge was automatic, what the thief paid, and the meal, so the numbers add up."""
        from engine import PlayerState, Rules, resolve_night
        r = Rules()
        ps = [PlayerState(pid=i, name=n, rations=5) for i, n in enumerate(("Me", "NightOwl", "C"))]
        ps[0].guard_until = 5                                  # guarded on night 4, covers night 5
        evs = []
        moves = {0: ("scavenge", None, 0, True), 1: ("steal", 0, 0, False), 2: ("scavenge", None, 0, False)}
        resolve_night(ps, moves, r, random.Random(3), 5, emit=lambda t, **f: evs.append({"type": t, **f}))
        dm = "\n".join(private_lines(evs, ps[0], 5, night=5, guard_nights=2))
        self.assertIn("Your guard (still up from night 4) caught NightOwl red-handed. They paid you", dm)
        evs4 = [{"type": "guard_up", "player": "Me", "until_night": 5}]
        self.assertIn("on guard for nights 4 and 5.", "\n".join(private_lines(evs4, ps[0], 5, night=4)))
        self.assertIn("scavenged automatically", dm)
        self.assertIn("You ate 1.", dm)
        paid = sum(e["delta"] for e in evs if e["type"] == "ration" and e["player"] == "Me" and e["reason"] == "guard_reward")
        found = next(e["found"] for e in evs if e["type"] == "scavenge" and e["player"] == "Me")
        self.assertEqual(5 + paid + found - 1, ps[0].rations)  # the DM's numbers add up to the total it shows
        self.assertIn(f"You now have {ps[0].rations} rations.", dm)

    def test_every_ration_change_in_a_night_is_mentioned_in_the_dm(self):
        reasons_to_words = {"guard_reward": "paid you", "eat": "You ate", "scavenge": "scavenged",
                            "stole": "You stole", "robbed": "stole", "gift_in": "gave you", "gift_out": "You gave",
                            "caught_penalty": "you were caught", "fine": "you were caught",
                            "event_found": "+", "event_lost": "-", "bounty_received": "paid you",
                            "bounty_paid": "EXPOSED", "gift_bonus": "gave you", "guard_income": "guard",
                            "exposed_return": "back", "exposed_loot": "back"}
        seen = set()
        for seed in range(25):
            g = service()
            g.join("h", rng=random.Random(seed))
            g.gm_add_sims(9, rng=random.Random(seed + 50))
            g.gm_start(day_seconds=300, now=0, events="gentle" if seed % 2 else "off")
            pick = random.Random(seed)
            for night in range(1, 11):
                menu = g.play_menu("h")["moves"]                  # the human plays too, or the DM is all autopilot
                kind = pick.choice([k for k in menu if k != "gift"] or ["scavenge"])
                g.submit("h", kind, pick.choice(menu[kind]) if menu[kind] else None, at=night * 300 - 5)
                g.tick(now=night * 300 + 10)
            for rec in g.store.records:
                if rec["type"] != "night":
                    continue
                for pid, lines in rec["private"].items():
                    name = g.players[int(pid)].name
                    dm = "\n".join(lines)
                    for e in rec["events"]:
                        if e["type"] == "ration" and e["player"] == name and e["delta"]:
                            word = reasons_to_words.get(e["reason"])
                            self.assertIsNotNone(word, f"unknown ration reason {e['reason']!r}: add it to the DM")
                            seen.add(e["reason"])
                            self.assertIn(word, dm, f"seed {seed} night {rec['night']}: {name}'s "
                                                    f"{e['reason']} {e['delta']:+} isn't in their DM:\n{dm}")
        self.assertTrue({"eat", "scavenge", "stole", "robbed"} <= seen, f"the games never produced: {seen}")

    def test_exposed_theft_is_returned_and_everyone_involved_is_told(self):
        from dataclasses import replace
        from engine import PlayerState, Rules, resolve_night
        r = replace(Rules(), exposure_undo="full")
        for seed in range(30):                                   # find a night where the thief lands the steal
            ps = [PlayerState(pid=i, name=n, rations=6) for i, n in enumerate(("Thief", "Victim", "Eye"))]
            evs = []
            moves = {0: ("steal", 1, 0, False), 1: ("scavenge", None, 0, False), 2: ("investigate", 0, 0, False)}
            resolve_night(ps, moves, r, random.Random(seed), 1, emit=lambda t, **f: evs.append({"type": t, **f}))
            exp = next(e for e in evs if e["type"] == "exposed")
            if exp.get("to_victim"):
                break
        self.assertEqual(exp["to_victim"], 2)
        self.assertIn("gives Victim back the 2 they stole", " ".join(news_lines(evs)))
        self.assertIn("gave back the 2 you stole", " ".join(private_lines(evs, ps[0], 6)))
        self.assertIn("You got your 2 back", " ".join(private_lines(evs, ps[1], 6)))
        self.assertIn("You exposed Thief", " ".join(private_lines(evs, ps[2], 6)))
        victim_booked = sum(e["delta"] for e in evs if e["type"] == "ration" and e["player"] == "Victim"
                            and e["reason"] in ("robbed", "exposed_return"))
        self.assertEqual(victim_booked, 0)                       # robbed 2, got 2 back: whole again

    def test_status_shows_goal_progress_and_a_quit_target_voids_it(self):
        g = service()
        g.join("a", rng=random.Random(1))
        g.join("b", rng=random.Random(2))
        g.join("c", rng=random.Random(3))
        g.gm_start(day_seconds=300, now=0)
        p = g.players[g.identity.get("a")["pid"]]
        p.objective, p.gifted_out = "give", 1
        self.assertIn(f"🎯 **Progress:** 1/{g.rules.give_goal} given", g.status("a"))
        p.gifted_out = g.rules.give_goal
        self.assertIn("✅ **Goal met:**", g.status("a"))
        p.objective, p.steals_ok, p.steals_caught = "steal3_clean", 3, 1
        self.assertIn("❌ **Goal lost:**", g.status("a"))
        p.objective = "grudge"
        p.obj_target = g.identity.get("b")["pid"]
        g.quit("b")
        self.assertIn("❌ **Goal lost:** your target left the game", g.status("a"))

    def test_the_last_three_nights_count_down_everywhere(self):
        g = service()
        g.join("a", rng=random.Random(1))
        g.gm_add_sims(3, rng=random.Random(2))
        g.gm_start(day_seconds=300, now=0)
        expect = {7: None, 8: "3 nights left", 9: "2 nights left", 10: "LAST NIGHT"}
        for night in range(1, 11):
            reply = g.submit("a", "scavenge", at=night * 300 - 20)
            header = g.play_menu("a")["header"]
            board = g.board()[1]
            want = expect.get(night)
            for where, text in (("reply", reply), ("/play", header), ("board", board)):
                if want:
                    self.assertIn(want, text, f"night {night} {where}")
                else:
                    self.assertNotIn("nights left", text, f"night {night} {where}")
                    self.assertNotIn("LAST NIGHT", text, f"night {night} {where}")
            g.tick(now=night * 300 + 1)
            g.tick(now=night * 300 + 10)
            news = next(g.outbox_text(i) for i in g.pending_outbox()
                        if i["to"] == "news" and f"News: Night {night} " in g.outbox_text(i))
            nxt = expect.get(night + 1)
            if nxt:
                self.assertIn(nxt, news, f"news after night {night} must warn about night {night + 1}")
            else:
                self.assertNotIn("nights left", news)
                self.assertNotIn("LAST NIGHT", news)
        self.assertIn("Tonight is the LAST NIGHT", next(g.outbox_text(i) for i in g.pending_outbox()
                                                        if "News: Night 9 " in g.outbox_text(i)))

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
