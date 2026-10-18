"""Torch's sim colleagues: the balanced cast, legal moves, restart equivalence, reciprocity and radio.

    .venv/Scripts/python -I -m unittest discover -s bot/tests -t .
"""
import random
import re
import unittest
from collections import Counter

from bot.brain import RADIO_KEYS, RADIO_RATE, SimBrain, balanced_pick
from bot.game import RADIO_PHRASES, GameError, GameService
from bot.store import MemoryEventStore, MemoryIdentityStore, MemoryTextStore
from bot.tests.test_game import ALIASES, OFFICIAL
from engine.moves import validate
from simbrain import OFFICE_MIX

DAY = 300


def make(seed, sims=8, humans=0, cast="balanced", season=None, events="gentle", ranges=True, parts=None):
    """A started game: `humans` human seats then `sims` sims. parts = (store, ident, texts) to reuse (a restart)."""
    store, ident, texts = parts or (MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore())
    g = GameService(OFFICIAL, store, ident, texts, ALIASES, season or f"sims-{seed}", clock=lambda: 0)
    rng = random.Random(seed)
    for h in range(humans):
        g.join(f"human-{h}", rng=rng)
    if sims:
        g.gm_add_sims(sims, rng=rng, cast=cast)
    g.gm_start(day_seconds=DAY, news_delay=5, now=0, events=events, ranges=ranges)
    return g, (store, ident, texts)


def restart(parts):
    """A new GameService on the same files: what Torch does after a crash or a deploy."""
    store, ident, texts = parts
    season = next(r for r in store.load() if r["type"] == "start")["season"]
    return GameService(OFFICIAL, store, ident, texts, ALIASES, season, clock=lambda: 0)


class BalancedCast(unittest.TestCase):
    def test_eight_sims_are_all_eight_personalities_for_every_seed(self):
        for seed in range(300):
            g, _ = make(seed, sims=8, cast="balanced")
            self.assertEqual(sorted(g.personality.values()), sorted(OFFICE_MIX), seed)

    def test_no_repeat_before_every_personality_is_used_whatever_the_batches(self):
        for seed in range(100):
            rng, have = random.Random(seed), []
            for batch in (3, 1, 7, 5):                         # added in pieces, as /gm add-sims twice would
                for _ in range(batch):
                    have.append(balanced_pick(rng, have))
                    counts = Counter(have)
                    self.assertLessEqual(max(counts.values()) - min(counts[a] for a in OFFICE_MIX), 1, (seed, have))
            self.assertEqual(Counter(have), Counter({a: 2 for a in OFFICE_MIX}))      # 16 sims: exactly two of each

    def test_the_order_is_shuffled_not_fixed(self):
        orders = set()
        for seed in range(50):
            g, _ = make(seed, sims=8)
            orders.add(tuple(g.personality[pid] for pid in sorted(g.personality)))
        self.assertGreater(len(orders), 25)

    def test_office_cast_is_still_the_weighted_draw_and_often_has_no_saint(self):
        no_saint = sum("saint" not in make(seed, sims=8, cast="office")[0].personality.values() for seed in range(200))
        self.assertGreater(no_saint, 40)                       # 92% ** 8 = 51% of offices have no saint
        with self.assertRaises(ValueError):
            GameService(OFFICIAL, MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore(), ALIASES,
                        "x").gm_add_sims(2, cast="nope")

    def test_personality_is_stored_in_the_join_record(self):
        g, (store, _, _) = make(5)
        joins = [r for r in store.load() if r["type"] == "join"]
        self.assertEqual(sorted(r["personality"] for r in joins), sorted(OFFICE_MIX))


class AliasesAcrossSeasons(unittest.TestCase):
    def test_last_seasons_aliases_are_not_handed_out_while_others_are_free(self):
        last = set(ALIASES[:12])
        for seed in range(40):
            g = GameService(OFFICIAL, MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore(), ALIASES, "s",
                            clock=lambda: 0, avoid_aliases=last)
            rng = random.Random(seed)
            g.join("h", rng=rng)
            g.gm_add_sims(17, rng=rng)                         # 18 players, 18 fresh names exist
            used = {a for _, a, _, _ in g.joined}
            self.assertEqual(used & last, set(), seed)
            g.gm_add_sims(6, rng=rng)                          # fresh names run out: the old ones are used, not "full"
            self.assertEqual(len({a for _, a, _, _ in g.joined}), 24)


class LegalMoves(unittest.TestCase):
    def test_sims_never_make_an_illegal_move_with_the_official_rules(self):
        problems = []

        class Checked(GameService):
            def _resolve(self, night, moves):
                active = self._active()
                for pid, m in moves.items():
                    if pid not in self.sims:                  # a human who became a bandit is auto-scavenged: not the sims' concern
                        continue
                    why = validate(active, pid, m, self.rules, night, frozenset(self.quit_ids))
                    if why or m[1] == pid:
                        problems.append((self.season_id, night, pid, m, why))
                return super()._resolve(night, moves)

        for seed in range(150):
            store, ident, texts = MemoryEventStore(), MemoryIdentityStore(), MemoryTextStore()
            g = Checked(OFFICIAL, store, ident, texts, ALIASES, f"legal-{seed}", clock=lambda: 0)
            rng = random.Random(seed)
            g.join("h", rng=rng)
            g.join("quitter", rng=rng)
            g.gm_add_sims(6, rng=rng, cast="balanced" if seed % 2 else "office")
            g.gm_start(day_seconds=DAY, now=0, events="gentle", ranges=True)
            for night in range(1, OFFICIAL.rounds + 1):
                if night == 3:
                    g.quit("quitter")
                g.tick(now=night * DAY + 10)
            self.assertTrue(g.finished)
        self.assertEqual(problems, [])

    def test_a_sim_left_alone_after_everyone_else_quit_keeps_playing_to_the_end(self):
        """Found by the Arena fuzz test (18 Oct 2026): a sim that wanted to investigate with nobody left crashed the
        night (simbrain pick_investigate_target took max() of nothing). With nobody to target it must fall back."""
        for seed in range(30):
            g, _ = make(seed, sims=1, humans=1)
            g.quit("human-0")
            for night in range(1, 11):
                g.tick(now=night * DAY + 1)
                g.tick(now=night * DAY + 7)
            with self.subTest(seed=seed):
                self.assertTrue(g.finished)

    def test_no_sim_ever_targets_a_player_who_quit(self):
        for seed in range(60):
            g, (store, ident, _) = make(seed, sims=7, humans=1)
            for night in range(1, 11):
                if night == 2:
                    g.quit("human-0")
                g.tick(now=night * DAY + 10)
            for rec in store.load():
                if rec["type"] == "night" and rec["night"] >= 2:
                    for pid, m in rec["moves"].items():
                        self.assertNotEqual(m[1], 0, (seed, rec["night"], pid, m))

    def test_sim_beliefs_use_only_public_numbers(self):
        g, _ = make(1, ranges=False)
        brain, seat = g.brain, g.players[3]
        other = g.players[4]
        seat.rations = 1
        a = brain.fresh(seat)
        seat.rations = 40
        self.assertEqual(brain.fresh(seat), a)                 # hidden: the true count never reaches the AI
        self.assertEqual(brain.fresh(other), OFFICIAL.start_rations)
        g2, _ = make(1, ranges=True)
        s2 = g2.players[3]
        s2.rations = 8
        hi = g2.brain.fresh(s2)
        s2.rations = 9
        self.assertEqual(g2.brain.fresh(s2), hi)               # ranges: only the band shows, 8 and 9 look the same


class RestartEquivalence(unittest.TestCase):
    def _play(self, seed, restart_after=(), crash_window=None):
        g, parts = make(seed, sims=7, humans=1)
        target = g.alias_list("human-0")[0]
        for night in range(1, 11):
            try:
                g.submit("human-0", "steal" if night % 3 else "scavenge", target if night % 3 else None,
                         at=night * DAY - 10)
            except GameError:                                  # e.g. the human is a bandit tonight: it misses the deadline
                pass
            if crash_window == night:                          # radio written, night record not yet
                g._sim_radio(night)
                g = restart(parts)
            g.tick(now=night * DAY + 10)
            if night in restart_after:
                g = restart(parts)
        return g, parts[0].load()

    def test_restarts_midway_give_the_identical_log(self):
        for seed in range(25):
            _, whole = self._play(seed)
            _, cut = self._play(seed, restart_after=(2, 5, 6, 9))
            self.assertEqual(cut, whole, seed)

    def test_restart_between_the_sims_radio_and_the_night_record_repeats_nothing(self):
        for seed in range(25):
            _, whole = self._play(seed)
            for night in (1, 4, 8):
                _, cut = self._play(seed, crash_window=night)
                self.assertEqual(cut, whole, (seed, night))

    def test_a_brain_that_forgot_would_decide_differently(self):
        """Control for the tests above: they only mean something if the beliefs really steer the moves."""
        def moves(g, brain):
            rng = random.Random(5)
            return {p.pid: brain.decide(p, g._active(), 5, rng, g.quit_ids)
                    for p in g._active() if p.pid in g.sims}
        differs = same_as_rebuilt = 0
        for seed in range(25):
            g, parts = make(seed, sims=8)
            for night in range(1, 5):
                g.tick(now=night * DAY + 10)
            amnesiac = SimBrain(g.rules, g.players, 123, True)
            differs += moves(g, g.brain) != moves(g, amnesiac)
            same_as_rebuilt += moves(g, g.brain) == moves(restart(parts), restart(parts).brain)
        self.assertGreater(differs, 10)
        self.assertEqual(same_as_rebuilt, 25)


class Reciprocity(unittest.TestCase):
    def test_a_gift_makes_the_receiver_likelier_to_give_back(self):
        back = ctrl = 0
        n = 400
        for seed in range(n):
            for gifted in (True, False):
                g, (store, _, _) = make(seed, sims=8, humans=1, events="off")
                farmer = next(pid for pid, a in g.personality.items() if a == "farmer")
                alias = g.players[farmer].name
                if gifted:
                    g.submit("human-0", "gift", alias, 2, at=DAY - 10)
                else:
                    g.submit("human-0", "scavenge", at=DAY - 10)
                g.tick(now=DAY + 10)
                g.tick(now=2 * DAY + 10)
                night2 = next(r for r in store.load() if r["type"] == "night" and r["night"] == 2)
                m = night2["moves"][str(farmer)]
                hit = m[0] == "gift" and m[1] == 0
                if gifted:
                    back += hit
                else:
                    ctrl += hit
        self.assertGreater(back, 3 * ctrl + 20, (back, ctrl))   # farmer: gift weight 0.03 -> about 0.28 with the give-back


class SimRadio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = []
        for seed in range(400):
            g, (store, ident, texts) = make(seed, sims=8)
            for night in range(1, 11):
                g.tick(now=night * DAY + 10)
            cls.games.append((g, store.load(), texts))

    def lines(self):
        """(game, its log, night, author pid, text) for every radio line."""
        for g, recs, texts in self.games:
            for r in recs:
                if r["type"] == "radio":
                    night, pid = map(int, re.match(r"r(\d+)-(\d+)-", r["ref"]).groups())
                    yield g, recs, night, pid, texts.get(r["ref"])

    def test_at_most_one_line_per_sim_per_day_and_only_fixed_phrases(self):
        templates = [re.compile("^" + re.escape(t).replace(r"\{a\}", "(.+)") + "$") for t in RADIO_PHRASES.values()]
        per = Counter()
        for g, recs, night, pid, text in self.lines():
            per[(id(g), night, pid)] += 1
            self.assertTrue(any(t.match(text) for t in templates), text)
        self.assertTrue(per)
        self.assertEqual(max(per.values()), 1)

    def test_a_line_that_names_someone_never_names_its_author(self):
        for g, recs, night, pid, text in self.lines():
            self.assertNotIn(g.players[pid].name, re.sub(r"^I'm innocent.*", "", text), text)

    def test_every_line_is_posted_with_that_mornings_news_and_replays_without_change(self):
        g, recs, texts = self.games[0]
        refs = [r["ref"] for r in recs if r["type"] == "radio"]
        posted = [i["ref"] for r in recs if r["type"] == "news" for i in r["outbox"] if i["to"] == "radio"]
        self.assertEqual(sorted(refs), sorted(posted))

    def test_rate_is_bounded_and_not_silent(self):
        total = sum(1 for _ in self.lines())
        per_night = total / len(self.games) / 10
        self.assertTrue(0.6 <= per_night <= 3.0, per_night)
        worst = Counter()
        for g, recs, night, pid, text in self.lines():
            worst[(id(g), night)] += 1
        self.assertLessEqual(max(worst.values()), 8)           # eight sims, one line each at most

    def test_personalities_talk_in_character(self):
        allowed = {"shark": {"trust", "lying"}, "opportunist": {"guarding"}, "paranoid": {"me"},
                   "saint": {"watch", "innocent"}, "farmer": {"watch", "me"}, "casual": {"me", "innocent"},
                   "detective": {"saw", "trust"}, "chaos": set(RADIO_KEYS)}
        pattern = {k: re.compile("^" + re.escape(t).replace(r"\{a\}", "(.+)") + "$") for k, t in RADIO_PHRASES.items()}
        seen = Counter()
        for g, recs, night, pid, text in self.lines():
            arch = g.personality[pid]
            key = next(k for k, pat in pattern.items() if pat.match(text))
            self.assertIn(key, allowed[arch], (arch, text))
            seen[arch] += 1
        self.assertEqual(set(seen) - set(RADIO_RATE), set())
        self.assertGreater(len(seen), 5)

    def test_a_detective_only_names_someone_it_actually_watched_steal(self):
        checked = 0
        for g, recs, night, pid, text in self.lines():
            if g.personality[pid] != "detective":
                continue
            who = g.players[pid].name
            m = re.match(r"I saw (.+) sneaking around last night\.$", text) or re.match(r"Don't trust (.+)\.$", text)
            self.assertIsNotNone(m, text)
            nights = [r for r in recs if r["type"] == "night" and r["night"] < night]
            if text.startswith("I saw"):
                nights = [r for r in nights if r["night"] == night - 1]
            saw = [e for r in nights for e in r["events"]
                   if e["type"] == "investigate" and e["investigator"] == who and e["target"] == m.group(1)
                   and e["saw_action"] == "steal"]
            self.assertTrue(saw, (who, text, night))
            checked += 1
        self.assertGreater(checked, 5)


if __name__ == "__main__":
    unittest.main()
