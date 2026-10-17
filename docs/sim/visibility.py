"""What the simulated players are TOLD about each other's rations, and how well they REMEMBER it. Opt-in; both are
information given to the AI's decisions only. Nothing here touches engine/ or the rules: the night resolves exactly as
before, whatever the players believe.

Visibility (what the camp is shown each morning):
    hidden   today: nobody sees rations; players only infer from #news (start + the losses the news reported)
    ranges   each morning every player's band is posted: well fed / getting by / starving / bandit
    exact    each morning every player's true ration count is posted

Memory (how much of that a player actually keeps in their head):
    None     "bot-accurate" (today): every player reads and remembers everything, every night
    Human    limited attention, fading estimates, forgotten guards. All the knobs are in HumanMemory below.

How a belief is built (survivors_sim.Game.perceived, one function for every combination):
    fresh(q)   what the information source says about q:
                   hidden: start rations + the public losses/finds  (a bandit counts as 1)
                   ranges: that same guess, pulled into q's posted band      (never sees the exact number)
                   exact : q's true rations
    belief(v,q) = fresh(q)                                    bot-accurate
                = a remembered estimate that is refreshed to fresh(q) when v is paying attention to q, and otherwise
                  slides toward the camp average (human)
    then a little judgement noise on top (NOISE_SD per visibility).
"""
import random
from dataclasses import dataclass

VISIBILITIES = ("hidden", "ranges", "exact")

# Band edges: the lowest ration count in each band, richest first. Below the last edge a survivor cannot exist (0 =
# bandit). (7, 3, 1) is the owner's proposal: well fed 7+, getting by 3-6, starving 1-2, bandit 0.
BAND_EDGES = (7, 3, 1)
BAND_LABELS = ("🟢 well fed", "🟡 getting by", "🔴 starving", "🏴‍☠️ bandit")
OPEN_TOP_SPAN = 3        # the top band has no ceiling; the AI reads "7+" as 7 to 10
# Judgement noise added to a belief, in rations (1 sd). Hidden is a guess from the news; a posted band or number
# leaves less to guess.
NOISE_SD = {"hidden": 1.5, "ranges": 1.0, "exact": 0.0}
EXACT_TIE_JITTER = 0.01  # breaks ties between equal true counts fairly instead of always picking the lowest seat


def band_index(q, edges=BAND_EDGES):
    """0 = richest band ... len(edges)-1 = poorest survivors, len(edges) = bandit. A bandit is a bandit whatever it holds."""
    if q.bandit:
        return len(edges)
    for i, lo in enumerate(edges):
        if q.rations >= lo:
            return i
    return len(edges) - 1            # a survivor on 0 is converted to a bandit before anyone can see it


def band_bounds(i, edges=BAND_EDGES):
    """(low, high) rations a player in band i can hold, as the AI reads it; the top band is read as lo..lo+OPEN_TOP_SPAN."""
    if i >= len(edges):
        return 0, 0
    lo = edges[i]
    hi = lo + OPEN_TOP_SPAN if i == 0 else edges[i - 1] - 1
    return lo, hi


def band_label(q, edges=BAND_EDGES):
    return BAND_LABELS[min(band_index(q, edges), len(BAND_LABELS) - 1)] if len(edges) == 3 else \
        f"band {band_index(q, edges)}"


def morning_board(players, vis, edges=BAND_EDGES):
    """The post a bot would put up each morning. Ranges: the player order inside a band is alphabetical so the post
    cannot leak a ranking; exact: richest first. Hidden: None."""
    if vis == "hidden":
        return None
    if vis == "exact":
        return [f"{p.name}: {'bandit, ' if p.bandit else ''}{p.rations}" for p in sorted(players, key=lambda p: (-p.rations, p.name))]
    lines = []
    for i in range(len(edges) + 1):
        names = sorted(p.name for p in players if band_index(p, edges) == i)
        if names:
            lines.append(f"{BAND_LABELS[i] if len(edges) == 3 else 'band ' + str(i)}: " + ", ".join(names))
    return lines


@dataclass
class HumanMemory:
    """Limited-memory players. All the parameters live here (the sweep uses the defaults).

    k                players each player follows closely. Each morning their followed set is rebuilt: the k - random_slots
                     players they dealt with most recently (robbed, tried to rob, were caught by, investigated, gave to,
                     received from, or learned had robbed them), topped up with random others.
    random_slots     how many of the k seats are random (the rest go to interaction), so people also notice strangers.
    decay            per night without new info, an estimate closes this share of its gap to the camp average
                     (0.4 = about 2-3 nights to forget). New info = followed, or named in last night's news
                     (robbed, caught, exposed, died, rejoined, event).
    guard_forget     chance a player forgets that someone recently caught a thief, even if they follow them.
                     Guards of players they do NOT follow are never remembered (unless it was in last night's news).
    """
    k: int = 3
    random_slots: int = 1
    decay: float = 0.4
    guard_forget: float = 0.25


class Memory:
    """Per-game state for HumanMemory. Uses its OWN random stream, so turning memory on never reorders the dice that
    decide scavenging, stealing and everything the engine rolls."""

    def __init__(self, cfg: HumanMemory, game):
        self.cfg, self.g = cfg, game
        self.rng = random.Random(game.seed * 7919 + 13)
        n = game.r.players
        self.est = {v: {q: float(game.r.start_rations) for q in range(n) if q != v} for v in range(n)}
        self.recent = {v: [] for v in range(n)}          # most recent interactions first
        self.tracked = {v: set() for v in range(n)}
        self.guard_seen = {v: set() for v in range(n)}
        self._pd = dict.fromkeys(range(n), 0)
        self._bandit = {p.pid: p.bandit for p in game.players}

    def touch(self, v, q):
        """v dealt with q (any direction)."""
        if v == q:
            return
        lst = self.recent[v]
        if q in lst:
            lst.remove(q)
        lst.insert(0, q)
        del lst[12:]

    def morning(self):
        """Rebuild attention, refresh or fade every estimate, decide which guards are remembered. Called once per
        night, after the wilderness and before anyone chooses."""
        g, cfg = self.g, self.cfg
        n = g.r.players
        news_ids = {q for q in range(n) if g.public_delta[q] != self._pd[q] or g.P(q).bandit != self._bandit[q]}
        self._pd = {q: g.public_delta[q] for q in range(n)}
        self._bandit = {p.pid: p.bandit for p in g.players}
        fresh = {q: g.fresh(g.P(q)) for q in range(n)}
        alive = [fresh[q] for q in range(n) if not g.P(q).bandit] or [float(g.r.start_rations)]
        avg = sum(alive) / len(alive)
        for v in range(n):
            others = [q for q in range(n) if q != v]
            keep = max(0, cfg.k - cfg.random_slots)
            tracked = list(self.recent[v][:keep])
            pool = [q for q in others if q not in tracked]
            self.rng.shuffle(pool)
            tracked += pool[:max(0, cfg.k - len(tracked))]
            self.tracked[v] = set(tracked)
            for q in others:
                if q in self.tracked[v] or q in news_ids:
                    self.est[v][q] = fresh[q]
                else:
                    self.est[v][q] += (avg - self.est[v][q]) * cfg.decay
            seen = set()
            for q, night in g.known_guard.items():
                if q == v or g.night - night > 2:
                    continue
                if (q in self.tracked[v] or night == g.night - 1) and self.rng.random() >= cfg.guard_forget:
                    seen.add(q)
            self.guard_seen[v] = seen
