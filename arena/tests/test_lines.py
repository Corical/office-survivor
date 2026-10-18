"""Line codes, rendered in English, are exactly Torch's lines: over many random games, every night, every player.

If a branch is added to bot/game.py news_lines / private_lines and not to arena/lines.py (or the other way round),
some game here renders differently and the test names the night and the player.
"""
import json
import random
import unittest

from arena.lines import JSON_PATH, LINES_EN, news_codes, private_codes, render
from bot.game import GameError, GameService, news_lines, private_lines
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from bot.tests.test_core_fixtures import _official

ALIASES = [f"Alias{i:02d}" for i in range(30)]
# Codes that random play cannot reach often enough to require here; each is checked by a hand-made case below.
RARE = set()


class Checking(GameService):
    """Torch, with every private line and every news post also produced from codes and compared."""
    seen = set()
    mismatches = []

    def _private_for(self, events, p, before, night):
        words = super()._private_for(events, p, before, night)
        codes = private_codes(events, p, before, night, self.rules.guard_nights)
        self.seen.update(c["code"] for c in codes)
        got = [render(c) for c in codes]
        if got != words:
            self.mismatches.append((self.season_id, night, p.name, words, got))
        return words

    def _post_news(self, night):
        rec = self._night_record(night)
        codes = news_codes(rec["events"])
        self.seen.update(c["code"] for c in codes)
        got = [render(c) for c in codes]
        if got != news_lines(rec["events"]):
            self.mismatches.append((self.season_id, night, "news", news_lines(rec["events"]), got))
        if not codes:
            self.seen.add("news_quiet")
        super()._post_news(night)


def play_random(seed, humans, events, rules):
    """A game of all-human seats making random legal moves (sims get no private lines, so humans cover more)."""
    rng = random.Random(seed)
    g = Checking(rules, MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore(), ALIASES, f"lines-{seed}",
                 clock=lambda: 0)
    keys = [f"h{i}" for i in range(humans)]
    for k in keys:
        g.join(k, rng=random.Random(rng.random()))
    g.gm_add_sims(rng.randint(0, 3), rng=random.Random(seed))
    g.gm_start(day_seconds=300, news_delay=5, now=0, events=events, ranges=rng.random() < 0.5)
    for night in range(1, g.rules.rounds + 1):
        for k in keys:
            if k in ("h3",) and night == 6 and seed % 4 == 0:
                g.quit(k)
            try:
                menu = g.play_menu(k)
            except GameError:
                continue
            if rng.random() < 0.1:
                continue
            kind = rng.choice(sorted(menu["moves"]))
            tgt = rng.choice(menu["moves"][kind]) if menu["moves"][kind] else None
            amt = rng.choice(menu["gift_amounts"]) if kind == "gift" and menu["gift_amounts"] else 0
            try:
                g.submit(k, kind, tgt, amt, at=night * 300 - 10)
            except GameError:
                pass
        g.tick(now=night * 300 + 1)
        g.tick(now=night * 300 + 7)


def play_random_game_keeping_logs(seed):
    """A finished all-human-plus-bots game with events on, for tests that read its night records."""
    from engine import Rules
    rng = random.Random(seed)
    g = Checking(_official(), MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore(), ALIASES, f"ev-{seed}",
                 clock=lambda: 0)
    for i in range(3):
        g.join(f"h{i}", rng=random.Random(rng.random()))
    g.gm_add_sims(3, rng=random.Random(seed))
    g.gm_start(day_seconds=300, news_delay=5, now=0, events="gentle", ranges=True)
    for night in range(1, g.rules.rounds + 1):
        g.tick(now=night * 300 + 1)
        g.tick(now=night * 300 + 7)
    return g


class LinesMatchTorch(unittest.TestCase):
    def test_codes_render_to_torchs_exact_words(self):
        Checking.seen, Checking.mismatches = set(), []
        from dataclasses import replace
        from engine import Rules
        rules = [_official(), Rules(), replace(_official(), guard_nights=1)]   # 1-night guards reach "guard_up_1"
        for seed in range(120):
            r = rules[seed % 3]
            play_random(seed, humans=4 + seed % 5, events="gentle" if seed % 3 else "off", rules=r)
        if Checking.mismatches:
            sid, night, who, want, got = Checking.mismatches[0]
            self.fail(f"{len(Checking.mismatches)} mismatches; first: {sid} night {night} {who}\n"
                      f" torch: {want}\n codes: {got}")
        unreached = set(LINES_EN) - Checking.seen - RARE
        self.assertEqual(unreached, set(), "codes no random game produced: add a hand-made case or play more")

    def test_hand_made_cases_for_each_branch(self):
        """Branches random play rarely hits, built directly: each compared with Torch's words."""
        from engine import PlayerState
        me = PlayerState(pid=0, name="Me", rations=4, objective="beat", obj_target=1)
        me.guard_until = 5
        cases = [
            [{"type": "steal", "thief": "T", "target": "Me", "outcome": "caught", "amount": 0, "paid": 0},
             {"type": "ration", "player": "Me", "delta": 2, "reason": "guard_reward", "balance": 6, "detail": "T"}],
            [{"type": "steal", "thief": "T", "target": "Me", "outcome": "caught", "amount": 0, "paid": 0}],
            [{"type": "investigate", "investigator": "Me", "target": "X", "saw_action": "steal", "saw_target": "Me"},
             {"type": "ration", "player": "Me", "delta": 1, "reason": "investigate_find", "balance": 5, "detail": ""}],
            [{"type": "exposed", "investigator": "Me", "thief": "T", "victim": "Me", "paid": 2, "to_victim": 3}],
            [{"type": "exposed", "investigator": "I", "thief": "Me", "victim": "V", "paid": 2, "to_victim": 0}],
            [{"type": "gift", "giver": "G", "receiver": "Me", "amount": 2},
             {"type": "ration", "player": "Me", "delta": 1, "reason": "gift_bonus", "balance": 7, "detail": "G"}],
            [{"type": "guard_up", "player": "Me", "until_night": 5}],
            [{"type": "event", "event": "feast", "scope": "camp", "visibility": "public", "line": "A feast!"}],
            [{"type": "event", "event": "idol", "player": "Me", "visibility": "private"}],
        ]
        for night in (None, 3, 4):
            for ev in cases:
                with self.subTest(night=night, ev=ev[0]["type"]):
                    self.assertEqual([render(c) for c in private_codes(ev, me, (4, False), night, 2)],
                                     private_lines(ev, me, (4, False), night, 2))

    def test_event_lines_carry_the_event_id_scope_and_player_beside_the_sentence(self):
        """Client request 3 (18 Oct 2026): a theme with its own words for an event needs the id; the sentence stays as
        the fallback. The story variant is not in the engine's log, so it is not sent (see ARENA.md)."""
        from engine.events import EVENTS
        ids = {e["id"] for e in EVENTS}
        seen = {"camp": 0, "player": 0}
        for seed in range(60):
            Checking.seen, Checking.mismatches = set(), []
            g = play_random_game_keeping_logs(seed)
            for rec in g.store.records:
                if rec["type"] != "night":
                    continue
                public = [e for e in rec["events"] if e["type"] == "event" and e.get("line")]
                lines = [c for c in news_codes(rec["events"]) if c["code"] == "event"]
                self.assertEqual(len(lines), len(public), f"seed {seed}: one event line per public event")
                for line, ev in zip(lines, public):
                    a = line["args"]
                    self.assertIn(a["event"], ids)
                    self.assertEqual(a["event"], ev["event"])
                    self.assertEqual(a["scope"], ev["scope"])
                    self.assertEqual(a["line"], ev["line"])
                    if ev["scope"] == "player":
                        self.assertEqual(a["who"], ev["player"])
                    else:
                        self.assertNotIn("who", a)
                    seen[ev["scope"]] += 1
        self.assertGreater(seen["camp"], 0)
        self.assertGreater(seen["player"], 0)

    def test_json_for_the_client_equals_the_table(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.assertEqual(json.load(f), LINES_EN, "run: python -m arena.lines  (rewrites arena/lines_en.json)")

    def test_every_template_names_only_args_its_code_gets(self):
        """A template with a {name} no code ever fills would crash a client at render time."""
        import string
        for code, text in LINES_EN.items():
            names = {f for _, f, _, _ in string.Formatter().parse(text) if f}
            with self.subTest(code=code):
                self.assertTrue(all(n.isidentifier() for n in names))


if __name__ == "__main__":
    unittest.main()
