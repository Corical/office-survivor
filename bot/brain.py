"""The brain of Torch's sim colleagues: the simulator's own AI (docs/sim/simbrain.py), fed only what a player in that
seat could know, and rebuilt from the game log on every restart.

Restart determinism. Nothing here is persisted. The brain's beliefs are updated only inside GameService._resolve, which
runs exactly once per night both live and when the log is replayed, so a restarted Torch ends a replay holding exactly
the beliefs an uninterrupted one holds. Decisions use dice seeded per season and night (never kept in memory), and the
only state a decision changes is restored afterwards, so the same log always gives the same moves and radio.

What a sim knows: its own state, its own private night results (what it saw when investigating, who gave it food, who
it caught), and the public facts (robberies, catches, exposures, bandits, events) plus the morning ration ranges when
the game has them. It is never told who robbed it. It does not listen to #radio.
"""
import logging
import os
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "sim"))
import visibility as V  # noqa: E402
from simbrain import BeliefObserver, OFFICE_MIX, SimAI  # noqa: E402

from engine import PlayerState  # noqa: E402
from engine.moves import validate  # noqa: E402

log = logging.getLogger("torch.brain")

CASTS = ("balanced", "office")

# Chance that a sim of this personality posts a radio line on a given day (once it has something to say). One of each
# personality adds up to about 1.5 lines a night; change the numbers here to make #radio busier or quieter.
RADIO_RATE = {"casual": 0.03, "farmer": 0.08, "opportunist": 0.15, "shark": 0.40, "paranoid": 0.20,
              "saint": 0.20, "detective": 0.90, "chaos": 0.45}
RADIO_KEYS = ("saw", "trust", "lying", "guarding", "easy", "innocent", "watch", "me")   # = bot/game.py RADIO_PHRASES
NO_TARGET = ("me",)


def balanced_pick(rng, existing):
    """The next personality for a balanced cast: one of each before any repeats, the order shuffled, continuing the
    cycle when sims are added in several batches. `existing` is the personalities already in the game."""
    counts = Counter(existing)
    low = min(counts[a] for a in OFFICE_MIX)
    return rng.choice([a for a in OFFICE_MIX if counts[a] == low])


@dataclass
class SimSeat(PlayerState):
    """A seat with the AI's private beliefs on it. Humans' seats carry them too and never use them."""
    arch: str = ""
    caution: float = 1.0                                   # halves each time this seat is caught or exposed
    knows_robbed_by: set = field(default_factory=set)
    suspicion: dict = field(default_factory=lambda: defaultdict(float))
    saw_steals: list = field(default_factory=list)         # (night, thief pid, victim pid): theft this seat watched


class _Observer(BeliefObserver):
    def saw_theft(self, night, inv, tgt, victim, exposed_paid):
        inv.saw_steals.append((night, tgt.pid, victim))


class SimBrain(SimAI):
    def __init__(self, rules, seats, seed, ranges):
        self.r, self.seed = rules, seed
        self.seats = seats                                  # pid -> SimSeat (every seat, quitters included)
        self.players = [seats[k] for k in sorted(seats)]
        self.night, self.rng, self.quit_ids = 1, random.Random(0), frozenset()
        self.vis, self.edges = ("ranges" if ranges else "hidden"), V.BAND_EDGES
        self.ai_exposure = self.ai_quiet = True            # the quiet-moves sweep's AI: weighs finds, bonuses, give-back
        self.public_delta, self.public_susp = defaultdict(int), defaultdict(float)
        self.known_guard, self.gift_owed = {}, {}
        self.why, self._why, self._odds = {}, [], None
        self.mem = V.Memory(V.HumanMemory(), self)
        self.observer = _Observer(self)
        self.mem.morning()                                  # the first morning, as the simulator does

    def P(self, pid):
        return self.seats[pid]

    def others(self, p):
        return [q for q in self.players if q.pid != p.pid and q.pid not in self.quit_ids]

    # ---------------- after each night (inside GameService._resolve, live and replayed alike) ----------------
    def end_night(self, night, res):
        for victim in res.robbed_by:                        # victims guess at thieves from what the camp is saying
            v = self.P(victim)
            for q in self.players:
                if q.pid != victim:
                    v.suspicion[q.pid] += 0.3 * self.public_susp[q.pid]
        self.night = night + 1
        self.mem.morning()

    # ---------------- decisions ----------------
    def decide(self, p, active, night, rng, quit_ids):
        """A legal move for sim seat p tonight (auto-scavenge when it 'missed the deadline')."""
        self.night, self.rng, self.quit_ids = night, rng, frozenset(quit_ids)
        missed = p.missed
        try:
            move = self.choose(p)
        finally:
            p.missed = missed                               # decisions leave no trace; beliefs change only in _resolve
        if validate(active, p.pid, move, self.r, night, self.quit_ids) is None:
            return move
        log.warning("sim %d chose an illegal move %s on night %d; falling back", p.pid, move, night)
        targets = self.others(p)
        return ("steal", targets[0].pid, 0, False) if p.bandit and targets else ("scavenge", None, 0, False)

    def radio(self, p, night, rng, quit_ids):
        """(phrase key, alias pid or None) this sim posts for tonight's morning, or None. Decided from what it knew at
        the deadline. One roll is always drawn so the dice stream does not depend on which branch is taken."""
        self.night, self.rng, self.quit_ids = night, rng, frozenset(quit_ids)
        targets = self.others(p)
        roll = rng.random()
        if not targets:
            return None
        rate = RADIO_RATE.get(p.arch, 0)
        if p.arch == "detective":                           # says only what it watched happen
            seen = [(n, t) for n, t, _v in p.saw_steals if t in {q.pid for q in targets}]
            last = [t for n, t in seen if n == night - 1]
            if last and roll < rate:
                return "saw", rng.choice(last)
            if seen and roll < rate * 0.3:
                return "trust", seen[-1][1]
            return None
        if roll >= rate:
            return None
        rich = lambda: max(targets, key=lambda q: self.perceived(p, q)).pid         # noqa: E731
        poor = lambda: min(targets, key=lambda q: self.perceived(p, q)).pid         # noqa: E731
        robbed = [q.pid for q in targets if q.robbed_last]
        if p.arch == "shark":                               # frames the one with the most to lose
            return rng.choice(("trust", "lying")), rich()
        if p.arch == "opportunist":                         # a bluff to keep rivals off its own mark
            return "guarding", rich()
        if p.arch == "paranoid":
            return "me", None
        if p.arch == "saint":                               # stands up for the one in trouble
            return ("watch", rng.choice(robbed)) if robbed else ("innocent", poor())
        if p.arch == "farmer":
            return ("watch", rng.choice(robbed)) if robbed else ("me", None)
        if p.arch == "casual":
            return rng.choice((("me", None), ("innocent", rng.choice(targets).pid)))
        key = rng.choice(RADIO_KEYS)                        # chaos: anything, true or not
        return key, (None if key in NO_TARGET else rng.choice(targets).pid)
