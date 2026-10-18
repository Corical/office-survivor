"""Behaviour lock for GameService: five seeded games, everything they write and say, compared byte for byte.

Recorded on the code BEFORE the GameCore extraction (plan: .local/.sisyphus/plans/godot-arena-platform.md, P1a), so any
refactor that changes a log record, a stored radio text, an identity entry or a single reply a player sees fails here.
The golden master cannot catch that: it runs the simulator, not GameService.

    python -m unittest bot.tests.test_core_fixtures          # check
    python -m bot.tests.test_core_fixtures --record          # re-record (only after a deliberate, explained change)
"""
import json
import os
import random
import sys
import unittest

from bot.game import GameError, GameService
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from engine import Rules

HERE = os.path.dirname(__file__)
FIXTURES = os.path.join(HERE, "core_fixtures")
ALIASES = [f"Alias{i:02d}" for i in range(30)]


def _official():
    from dataclasses import fields
    known = {f.name for f in fields(Rules)}
    with open(os.path.join(HERE, "..", "..", "docs", "game.json"), encoding="utf-8") as f:
        return Rules(**{k: v for k, v in json.load(f)["rules"].items() if k in known})


# name: (rules, humans, sims, cast, events, ranges, day_seconds, quit (human, night) or None, seed)
SCENARIOS = {
    "arena4_official_events_ranges": ("official", 1, 3, "balanced", "gentle", True, 300, None, 11),
    "office10_official_plain": ("official", 2, 8, "balanced", "off", False, 300, None, 22),
    "office15_quit_officecast": ("official", 3, 12, "office", "gentle", True, 300, (1, 4), 33),
    "humans4_default_rules_no_sims": ("default", 4, 0, "balanced", "off", False, 300, (3, 7), 44),
    "realdays6_official": ("official", 1, 5, "balanced", "gentle", True, 86400, None, 55),
}


def play(name):
    """Play one scenario through GameService's public surface and return everything observable."""
    rules_kind, humans, n_sims, cast, events, ranges, day, quit_at, seed = SCENARIOS[name]
    rules = _official() if rules_kind == "official" else Rules()
    store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
    mk = lambda: GameService(rules, store, ident, texts, ALIASES, f"fixture-{name}", clock=lambda: 0)  # noqa: E731
    g = mk()
    rng = random.Random(seed)
    out = []

    def say(tag, fn):
        try:
            out.append([tag, fn()])
        except GameError as e:
            out.append([tag, "GameError", str(e)])

    hk = [f"h{i}" for i in range(humans)]
    for k in hk:
        say(f"join {k}", lambda k=k: g.join(k, rng=random.Random(rng.random())))
    say("join again", lambda: g.join(hk[0]))
    say("status before start", lambda: g.status(hk[0]))
    if n_sims:
        say("add sims", lambda: g.gm_add_sims(n_sims, rng=random.Random(seed + 1), cast=cast))
    say("board before start", lambda: g.board())
    say("start", lambda: g.gm_start(day_seconds=day, news_delay=5, now=0, events=events, ranges=ranges))
    say("start twice", lambda: g.gm_start(day_seconds=day, now=0))
    quit_ids = set()
    for night in range(1, g.rules.rounds + 1):
        deadline = night * day
        say(f"n{night} board", lambda: g.board())
        for i, k in enumerate(hk):
            if quit_at and quit_at == (i, night):
                say(f"n{night} {k} quit", lambda k=k: g.quit(k))
                say(f"n{night} {k} quit again", lambda k=k: g.quit(k))
                quit_ids.add(k)
            if k in quit_ids:
                say(f"n{night} {k} menu after quit", lambda k=k: g.play_menu(k))
                continue
            say(f"n{night} {k} menu", lambda k=k: g.play_menu(k))
            say(f"n{night} {k} status", lambda k=k: g.status(k))
            say(f"n{night} {k} results", lambda k=k: g.results(k))
            if rng.random() < 0.15:
                continue                                    # misses the night: auto-scavenge
            for attempt in range(2 if rng.random() < 0.25 else 1):   # sometimes changes their mind
                try:
                    menu = g.play_menu(k)
                except GameError:
                    break
                kind = rng.choice(sorted(menu["moves"]))
                targets = menu["moves"][kind]
                tgt = rng.choice(targets) if targets else None
                amt = rng.choice(menu["gift_amounts"]) if kind == "gift" and menu["gift_amounts"] else 0
                say(f"n{night} {k} submit{attempt}", lambda k=k, kind=kind, tgt=tgt, amt=amt, a=attempt:
                    g.submit(k, kind, tgt, amt, at=deadline - 20 + a))
            if rng.random() < 0.1:
                me = ident.get(k)["alias"]
                say(f"n{night} {k} steal self", lambda k=k, me=me: g.submit(k, "steal", me, at=deadline - 5))
            if rng.random() < 0.35:
                rm = g.radio_menu(k)
                key, _ = rng.choice(rm["lines"])
                about = rng.choice(rm["about"]) if GameService.radio_needs_player(key) and rm["about"] else None
                say(f"n{night} {k} radio", lambda k=k, key=key, about=about: g.radio(k, key, about))
                say(f"n{night} {k} radio twice", lambda k=k, key=key, about=about: g.radio(k, key, about))
        say(f"n{night} who moved", lambda: g.gm_who_moved())
        g.tick(now=deadline + 1)                            # resolve
        if hk[0] not in quit_ids:
            say(f"n{night} late submit", lambda: g.submit(hk[0], "scavenge", at=deadline + 1))
        g.tick(now=deadline + 7)                            # news (and the finish after the last)
        for intent in g.pending_outbox():
            out.append([f"n{night} outbox", intent, g.outbox_text(intent)])
            g.mark_sent(intent["id"], ref=intent.get("ref"))
    say("finished", lambda: g.finished)
    say("reveal", lambda: g.reveal_data())
    say("menu after end", lambda: g.play_menu(hk[0]))
    again = mk()                                            # restart: rebuild from the log
    say("replayed state", lambda: {str(p): [s.rations, s.bandit] for p, s in sorted(again.players.items())})
    return {"log": store.records, "texts": texts.data, "identity": ident.data, "transcript": out}


def _canon(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, sort_keys=True))


class CoreFixtures(unittest.TestCase):
    def test_every_scenario_matches_its_recording(self):
        for name in SCENARIOS:
            with self.subTest(name):
                with open(os.path.join(FIXTURES, f"{name}.json"), encoding="utf-8") as f:
                    want = json.load(f)
                got = _canon(play(name))
                for part in ("log", "texts", "identity", "transcript"):
                    self.assertEqual(got[part], want[part], f"{name}: {part} differs")

    def test_scenarios_actually_exercise_the_paths(self):
        """A fixture that never quits, never radios or never errors would lock nothing in: check it does."""
        seen = {"quit": 0, "radio": 0, "GameError": 0, "finish": 0, "sim": 0, "event": 0}
        for name in SCENARIOS:
            with open(os.path.join(FIXTURES, f"{name}.json"), encoding="utf-8") as f:
                data = json.load(f)
            types = [r["type"] for r in data["log"]]
            seen["quit"] += types.count("quit")
            seen["radio"] += types.count("radio")
            seen["finish"] += types.count("finish")
            seen["sim"] += sum(1 for r in data["log"] if r["type"] == "join" and r.get("sim"))
            seen["event"] += sum(1 for r in data["log"] if r["type"] == "night"
                                 for e in r["events"] if e["type"] == "event")
            seen["GameError"] += sum(1 for t in data["transcript"] if len(t) == 3 and t[1] == "GameError")
        self.assertEqual(seen["finish"], len(SCENARIOS))
        for k in ("quit", "radio", "GameError", "sim", "event"):
            self.assertGreater(seen[k], 0, k)


if __name__ == "__main__":
    if "--record" in sys.argv:
        os.makedirs(FIXTURES, exist_ok=True)
        for name in SCENARIOS:
            with open(os.path.join(FIXTURES, f"{name}.json"), "w", encoding="utf-8") as f:
                json.dump(_canon(play(name)), f, ensure_ascii=False, sort_keys=True, indent=0)
            print("recorded", name)
    else:
        unittest.main()
