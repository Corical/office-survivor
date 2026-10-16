#!/usr/bin/env python3
"""
Survivors - office game simulator (phase-1 rules, no camps).

Simulates a Discord office of N players with different personalities and
runs the nightly rules: scavenge, steal, guard, investigate, gift, radio,
bandits, extraction and scoring.

Usage:
  python3 survivors_sim.py reel   [--seed 7]           one game as #news posts, with what really happened
  python3 survivors_sim.py batch  [--runs 100]          aggregate stats + automatic weak-spot flags
  python3 survivors_sim.py compare [--runs 300] baseline v1_original steal_1 guard_unlimited
                                                        rule variants side by side ('+' combines variants)
  python3 survivors_sim.py extremes [--runs 300]       everyone / one / a few players going ultra one direction
  python3 survivors_sim.py rules                         list rule knobs, variants and personalities

Options for any mode:
  --rules ../game.json         where the rules come from (this is the default; 'none' = built-in)
  --variant v1_original        apply a named variant on top (baseline = no changes)
  --set key=value              override one rule, e.g. --set start_rations=6 --set steal_amount=1
  --mix honest|cutthroat       try a different office personality mix
  --brain adaptive             players learn from what paid off (free, any scale)
  --brain jev [--smart 5]      Jev decides for all (or 5) players; needs TYPESAFE_API_KEY. Small runs only.
  --jev-mock                   test the Jev path offline; --max-calls caps spend (default 3000)

The simulated players follow fixed personalities; they don't learn or adapt
when the rules change. Treat the numbers as a stress test of the rules, not a
prediction of how real colleagues will play.

No dependencies beyond the Python standard library.
"""

import argparse
import json
import os
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, fields, replace

# --------------------------------------------------------------------------
# Rules (every knob the game exposes)
# --------------------------------------------------------------------------


@dataclass
class Rules:
    """Defaults = the rules doc as currently written (v2, tuned 16 Oct 2026)."""
    players: int = 15
    rounds: int = 10              # weekday nights
    start_rations: int = 7
    eat: int = 1                  # cost per night for survivors
    scavenge_min: int = 0
    scavenge_max: int = 2
    steal_amount: int = 2
    caught_penalty: int = 2       # a thief caught by a guard loses this
    guard_reward: int = 2         # a guard gains this per thief caught
    guard_income_max: int = 0     # guards still scavenge 0..this
    guard_nights: int = 2         # a guard stays up for this many nights
    guard_limit: int = 3          # max guards per player per game (0 = unlimited)
    guard_cooldown: int = 0       # nights you must wait after a guard ends before guarding again
    missed_scavenge_max: int = -1 # missed deadline scavenges 0..this (-1 = same as a normal scavenge)
    investigate_bounty: int = 1   # catching a thief by investigation exposes them and they pay this
    gift_bonus: int = 0           # extra rations the receiver gets on top of each gift
    winner_tiebreak: str = "kindness"  # tied top scores: "none" (shared win), "rations", or "kindness"
    tiebreak: str = "kindness"    # last-seat ties: "coin" or "kindness" (most given away, then fewest caught)
    give_goal: int = 3            # threshold for the give-away objective
    grudge_goal: str = "rob"      # "deny" (@player doesn't extract) or "rob" (rob @player N times)
    grudge_robs: int = 1          # N for the "rob" grudge objective
    robbed_goal: int = 1          # times robbed for the robbed-and-extract objective
    bandit_steal_amount: int = 1
    bandit_rejoin: int = 3        # a bandit with this many rations rejoins
    bandit_can_extract: bool = False
    seat_ratio: float = 1 / 3     # extraction seats as a share of players
    miss_scale: float = 1.0       # multiplies everyone's chance of missing the deadline
    pts_extract: int = 3
    pts_objective: int = 2
    pts_survive: int = 1


# Named rule sets. Each one changes the defaults above; join several with '+'.
VARIANTS = {
    "baseline": {},                                   # the rules doc as written (v2)
    "v1_original": {"start_rations": 5, "caught_penalty": 1, "guard_reward": 0, "guard_nights": 1,
                    "guard_limit": 0, "investigate_bounty": 0, "winner_tiebreak": "none",
                    "tiebreak": "coin", "give_goal": 5, "grudge_goal": "deny", "grudge_robs": 2,
                    "robbed_goal": 2, "bandit_steal_amount": 2},
    # single-knob experiments against v2
    "start_5": {"start_rations": 5},
    "start_9": {"start_rations": 9},
    "scavenge_0_3": {"scavenge_max": 3},
    "steal_1": {"steal_amount": 1, "bandit_steal_amount": 1},
    "bandit_steal_2": {"bandit_steal_amount": 2},
    "rejoin_5": {"bandit_rejoin": 5},
    "guard_1_night": {"guard_nights": 1},
    "guard_unlimited": {"guard_limit": 0},
    "guard_limit_4": {"guard_limit": 4},
    "guard_cooldown_1": {"guard_cooldown": 1},
    "guard_income": {"guard_income_max": 1},
    "catch_1": {"caught_penalty": 1, "guard_reward": 1},
    "catch_3": {"caught_penalty": 3, "guard_reward": 3},
    "no_bounty": {"investigate_bounty": 0},
    "coin_tiebreak": {"tiebreak": "coin", "winner_tiebreak": "none"},
    "missed_half": {"missed_scavenge_max": 1},
    "gift_bonus": {"gift_bonus": 1},
    "seats_quarter": {"seat_ratio": 0.25},
    # the first recommendation (before the guard loophole was found): v2 without the guard cap and bounty
    "r1_first_pick": {"guard_limit": 0, "investigate_bounty": 0},
}


def variant(name):
    """A named variant, or several joined with '+', e.g. start_7+guard_income."""
    out = {}
    for part in name.split("+"):
        if part not in VARIANTS:
            raise SystemExit(f"unknown variant '{part}'. Known: {', '.join(VARIANTS)}")
        out.update(VARIANTS[part])
    return out


# Office personality mixes, to check the findings hold for different crowds.
MIXES = {
    "default": None,  # uses OFFICE_MIX
    "honest": {"casual": 0.30, "farmer": 0.30, "opportunist": 0.08, "shark": 0.02,
               "paranoid": 0.10, "saint": 0.12, "detective": 0.05, "chaos": 0.03},
    "cutthroat": {"casual": 0.15, "farmer": 0.10, "opportunist": 0.30, "shark": 0.15,
                  "paranoid": 0.10, "saint": 0.03, "detective": 0.10, "chaos": 0.07},
}

KINDS = ("scavenge", "steal", "guard", "investigate", "gift")
LOG_FORMAT_VERSION = 1

# --------------------------------------------------------------------------
# Personalities. Weights are base odds for (scavenge, steal, guard, investigate, gift).
# --------------------------------------------------------------------------

ARCH = {
    "casual":      dict(w=(0.80, 0.05, 0.10, 0.00, 0.05), miss=0.35, final=0.2, radio=0.02,
                        desc="busy, often misses the deadline, mostly scavenges"),
    "farmer":      dict(w=(0.80, 0.03, 0.12, 0.02, 0.03), miss=0.08, final=0.3, radio=0.03,
                        desc="honest grinder"),
    "opportunist": dict(w=(0.55, 0.30, 0.10, 0.03, 0.02), miss=0.08, final=1.0, radio=0.10,
                        desc="steals when it looks safe"),
    "shark":       dict(w=(0.30, 0.60, 0.05, 0.05, 0.00), miss=0.05, final=1.0, radio=0.25,
                        desc="aggressive thief, frames others on radio"),
    "paranoid":    dict(w=(0.40, 0.05, 0.50, 0.05, 0.00), miss=0.05, final=0.2, radio=0.05,
                        desc="guards a lot"),
    "saint":       dict(w=(0.60, 0.00, 0.05, 0.05, 0.30), miss=0.08, final=0.0, radio=0.05,
                        desc="gives to people in trouble"),
    "detective":   dict(w=(0.45, 0.10, 0.10, 0.35, 0.00), miss=0.05, final=0.4, radio=0.60,
                        desc="investigates, exposes thieves on radio"),
    "chaos":       dict(w=(0.20, 0.20, 0.20, 0.20, 0.20), miss=0.10, final=0.5, radio=0.35,
                        desc="does whatever, spreads rumours"),
}

# Ultra one-direction players: they do the same thing every single night (bandits still have to steal).
PURE = {
    "always_guard":       dict(pure="guard", desc="guards every night, no matter what"),
    "turtle":             dict(pure="turtle", desc="guards whenever not already protected, scavenges otherwise"),
    "always_steal":       dict(pure="steal", desc="steals every night from whoever looks richest"),
    "always_scavenge":    dict(pure="scavenge", desc="scavenges every night, never anything else"),
    "always_gift":        dict(pure="gift", desc="gives 1 away every night it can afford to"),
    "always_investigate": dict(pure="investigate", desc="investigates every night"),
}
for _k, _v in PURE.items():
    ARCH[_k] = dict(w=(0, 0, 0, 0, 0), miss=0.0, final=0.0, radio=0.3, **_v)

# How often each personality shows up in a ~15-person office.
OFFICE_MIX = {"casual": 0.25, "farmer": 0.20, "opportunist": 0.15, "shark": 0.07,
              "paranoid": 0.10, "saint": 0.08, "detective": 0.08, "chaos": 0.07}

NAMES = ["RustyKettle", "QuietBadger", "SoggyBiscuit", "LuckyLantern", "GrumpyGecko", "VelvetMole",
         "DustyBoots", "NightOwl", "CrookedSpoon", "MuddyPaws", "SilentGoose", "BurntToast",
         "LooseCannon", "ColdCoffee", "SneakyPenguin", "WobblyTable", "HollowTin", "PaperTiger",
         "SaltyPretzel", "LazyRiver", "IronSpatula", "FoggyGlasses", "CleverCrow", "MissingSock"]  # aliases, as in the real game

OBJECTIVES = ("beat", "robbed2_extract", "steal3_clean", "give", "grudge")


def obj_text(o, rules, t="@player"):
    return {
        "beat": f"finish with more rations than {t}",
        "robbed2_extract": (f"get robbed at least {rules.robbed_goal}x and still extract"),
        "steal3_clean": "steal at least 3 times without ever being caught",
        "give": f"give away {rules.give_goal} rations over the game",
        "grudge": (f"make sure {t} doesn't extract" if rules.grudge_goal == "deny"
                   else f"successfully rob {t} at least {rules.grudge_robs}x"),
    }[o]

# --------------------------------------------------------------------------
# Game state
# --------------------------------------------------------------------------


@dataclass
class Player:
    pid: int
    name: str
    arch: str
    rations: int
    objective: str = ""
    obj_target: int = -1
    bandit: bool = False
    ever_bandit: bool = False
    caution: float = 1.0               # drops each time they get caught
    robbed_last: bool = False
    knows_robbed_by: set = field(default_factory=set)
    suspicion: dict = field(default_factory=lambda: defaultdict(float))
    # stats
    times_robbed: int = 0
    steals_ok: int = 0
    steals_caught: int = 0
    rations_stolen: int = 0
    gifted_out: int = 0
    deaths: int = 0
    comebacks: int = 0
    died_unrobbed: int = 0
    missed: int = 0
    grudge_hits: int = 0
    guard_until: int = 0
    guards_used: int = 0
    next_guard_night: int = 0
    actions: Counter = field(default_factory=Counter)
    notes: list = field(default_factory=list)       # what only this player knows (used by smart brains)


class Game:
    def __init__(self, rules: Rules, seed: int, mix=None, record=False, force=None, brain=None, smart=None,
                 log=False):
        self.r = rules
        self.brain = brain
        self.logging = log
        self.events = []                   # the replay log (see LOG_FORMAT.md); filled only when log=True
        self._seq = 0
        self.seed = seed
        self.public_log = []               # (night, line) for everything posted in #news and #radio
        self.rng = random.Random(seed)
        self.record = record
        self.night = 0
        self.log = []                      # per-night dicts for the reel
        self.public_delta = defaultdict(int)  # what the public can infer about rations
        self.public_susp = defaultdict(float)
        self.known_guard = {}              # pid -> last night they publicly caught someone
        mix = mix or OFFICE_MIX
        archs = self.rng.choices(list(mix), weights=list(mix.values()), k=rules.players)
        for i, arch in enumerate(force or []):
            archs[i] = arch                # forced personalities take the first seats
        names = self.rng.sample(NAMES, rules.players)
        self.players = [Player(i, names[i], archs[i], rules.start_rations) for i in range(rules.players)]
        for p in self.players:
            p.objective = self.rng.choice(OBJECTIVES)
            if p.objective in ("beat", "grudge"):
                p.obj_target = self.rng.choice([q.pid for q in self.players if q.pid != p.pid])
        self.night_stats = []
        n_smart = rules.players if smart is None else max(0, min(smart, rules.players))
        self.smart_ids = set(random.Random(seed * 7919 + 1).sample(range(rules.players), n_smart)) if brain else set()
        if self.logging:
            self.L("game_start", seed=seed, log_format=LOG_FORMAT_VERSION, rules=asdict(rules),
                   seats=max(1, round(rules.players * rules.seat_ratio)),
                   players=[{"id": p.pid, "name": p.name, "personality": p.arch, "start_rations": p.rations,
                             "smart": p.pid in self.smart_ids} for p in self.players])
            for p in self.players:
                tgt = self.P(p.obj_target).name if p.obj_target >= 0 else None
                self.L("objective", player=p.name, objective=p.objective, target=tgt,
                       text=obj_text(p.objective, rules, tgt or ""), visibility="private")

    # ---------------- helpers ----------------
    def L(self, _type, **fields_):
        """Append one event to the replay log."""
        if self.logging:
            self._seq += 1
            self.events.append({"seq": self._seq, "night": self.night, "type": _type, **fields_})

    def ledger(self, p, delta, reason, balance, **extra):
        self.L("ration", player=p.name, delta=delta, reason=reason, balance=balance, **extra)

    def P(self, pid):
        return self.players[pid]

    def perceived(self, viewer, q):
        """What `viewer` guesses q has: start minus publicly known losses, plus noise."""
        if q.bandit:
            base = 1
        else:
            base = self.r.start_rations + self.public_delta[q.pid]
        return base + self.rng.gauss(0, 1.5)

    def weighted(self, weights: dict):
        keys = [k for k, v in weights.items() if v > 0]
        if not keys:
            return "scavenge"
        return self.rng.choices(keys, weights=[weights[k] for k in keys])[0]

    # ---------------- decisions ----------------
    def can_guard(self, p):
        if p.guard_until >= self.night:
            return False                  # already protected tonight
        if self.r.guard_limit and p.guards_used >= self.r.guard_limit:
            return False
        return self.night >= p.next_guard_night

    # ---------------- what a player can do and knows (for smart brains) ----------------
    def options_for(self, p):
        r = self.r
        others = [q for q in self.players if q.pid != p.pid]
        opts = []
        if not p.bandit:
            opts.append(dict(key="scavenge", kind="scavenge", desc=f"Scavenge: find {r.scavenge_min} to {r.scavenge_max} rations at random. Safe, but you can be robbed."))
            if self.can_guard(p):
                left = (r.guard_limit - p.guards_used) if r.guard_limit else "unlimited"
                opts.append(dict(key="guard", kind="guard", desc=(
                    f"Guard: protected for {r.guard_nights} night(s); any thief who tries is named in #news and pays you "
                    f"{r.guard_reward}. You find no food tonight. Guards left: {left}.")))
        amt = r.bandit_steal_amount if p.bandit else r.steal_amount
        for q in others:
            status = "bandit" if q.bandit else f"robbed {q.times_robbed}x so far"
            opts.append(dict(key=f"steal:{q.name}", kind="steal", desc=(
                f"Steal from {q.name} ({status}): take up to {amt} rations anonymously. If they are guarding, "
                f"you are named and pay them {r.caught_penalty}.")))
        for q in others:
            opts.append(dict(key=f"investigate:{q.name}", kind="investigate", desc=(
                f"Investigate {q.name}: learn privately what they do tonight. If they steal, they are exposed and pay you "
                f"{r.investigate_bounty}. You find no food tonight.")))
        if not p.bandit and p.rations >= 2:
            g_amt = 2 if p.rations >= 7 else 1
            for q in others:
                opts.append(dict(key=f"gift:{q.name}", kind="gift", desc=f"Secretly give {q.name} {g_amt} ration(s)."))
        return opts

    def action_from_kind(self, p, kind):
        if kind == "steal":
            return ("steal", self.pick_steal_target(p), 0, False)
        if kind == "investigate":
            return ("investigate", self.pick_investigate_target(p), 0, False)
        if kind == "gift":
            tgt = self.pick_gift_target(p)
            if tgt is None or p.rations < 2:
                return ("scavenge", None, 0, False)
            return ("gift", tgt, 2 if p.rations >= 7 else 1, False)
        if kind == "guard" and not self.can_guard(p):
            return ("scavenge", None, 0, False)
        return (kind, None, 0, False)

    def action_from_key(self, p, key):
        kind, _, name = key.partition(":")
        if not name:
            return self.action_from_kind(p, kind)
        tgt = next(q.pid for q in self.players if q.name == name)
        if kind == "gift":
            return ("gift", tgt, 2 if p.rations >= 7 else 1, False)
        return (kind, tgt, 0, False)

    def observation(self, p):
        r = self.r
        seats = max(1, round(r.players * r.seat_ratio))
        tgt = self.P(p.obj_target).name if p.obj_target >= 0 else ""
        lines = [
            f"Survivors is a {r.rounds}-night office survival game with {r.players} colleagues. Everyone eats {r.eat} "
            f"ration a night; at 0 you become a bandit who can only steal or investigate and rejoins at {r.bandit_rejoin} "
            f"rations. After the last night the {seats} survivors with the most rations take a helicopter seat "
            f"({r.pts_extract} pts); completing your secret goal is worth {r.pts_objective} pts; most points wins. "
            f"Ties go to whoever gave away the most.",
            f"You are {p.name}. Personality: {ARCH[p.arch]['desc']}. Secret goal: {obj_text(p.objective, r, tgt)}.",
            f"It is night {self.night} of {r.rounds}. You have {p.rations} rations"
            + (" and you are a BANDIT." if p.bandit else ".")
            + (" You are protected by a guard tonight." if p.guard_until >= self.night else ""),
            "Your stealing so far: " + (f"{p.steals_ok} successful, {p.steals_caught} caught." if p.actions["steal"] else "none."),
        ]
        recent = [f"Night {n}: {line}" for n, line in self.public_log if n >= self.night - 4]
        lines.append("Public #news and #radio (last few nights): " + (" | ".join(recent) if recent else "nothing yet."))
        lines.append("What only you know: " + (" | ".join(p.notes[-8:]) if p.notes else "nothing yet."))
        return "\n".join(lines)

    def choose(self, p):
        a = ARCH[p.arch]
        final = self.night == self.r.rounds
        if not p.bandit and self.rng.random() < a["miss"] * self.r.miss_scale:
            p.missed += 1
            return ("scavenge", None, 0, True)

        if p.bandit:
            kind = "steal" if self.rng.random() < 0.85 else "investigate"
        elif a.get("pure"):
            kind = a["pure"]
            if kind == "turtle":
                kind = "guard" if self.can_guard(p) else "scavenge"
            elif kind == "guard" and not self.can_guard(p) and p.guard_until < self.night:
                kind = "scavenge"           # out of guards: forced to do something else
            if kind == "gift" and p.rations < 2:
                kind = "scavenge"
        else:
            w = dict(zip(KINDS, a["w"]))
            w["steal"] *= p.caution
            if p.robbed_last:
                w["guard"] += 0.5
                if p.arch == "detective":
                    w["investigate"] += 0.3
            revenge = [t for t in p.knows_robbed_by if not self.P(t).bandit]
            if revenge and p.arch != "saint":
                w["steal"] += 0.4
            if p.rations <= 2:
                w["steal"] += 0.25 * (p.arch != "saint")
                w["gift"] = 0
                w["guard"] *= 0.5
            if p.rations >= 8:
                w["guard"] += 0.15
            if final:
                w["steal"] += 0.6 * a["final"]
                w["guard"] += 0.3
                w["investigate"] = 0          # info is worthless on the last night
            if p.objective == "steal3_clean" and p.steals_ok < 3 and p.steals_caught == 0:
                w["steal"] += 0.2
            if p.objective == "give" and p.gifted_out < self.r.give_goal:
                w["gift"] += 0.25
            if p.objective == "grudge":
                if self.r.grudge_goal == "deny" and self.night >= self.r.rounds - 2:
                    w["steal"] += 0.3
                elif self.r.grudge_goal == "rob" and p.grudge_hits < self.r.grudge_robs:
                    w["steal"] += 0.2
            if p.rations <= 1:
                w["gift"] = 0
            if not self.can_guard(p):
                w["guard"] = 0               # protected already, out of guards, or cooling down
            kind = self.weighted(w)

        if kind == "steal":
            return ("steal", self.pick_steal_target(p), 0, False)
        if kind == "investigate":
            return ("investigate", self.pick_investigate_target(p), 0, False)
        if kind == "gift":
            tgt = self.pick_gift_target(p)
            if tgt is None:
                return ("scavenge", None, 0, False)
            amt = 2 if p.rations >= 7 else 1
            return ("gift", tgt, amt, False)
        return (kind, None, 0, False)

    def pick_steal_target(self, p):
        best, best_s = None, -1e9
        for q in self.players:
            if q.pid == p.pid:
                continue
            s = self.perceived(p, q)
            if q.pid in p.knows_robbed_by:
                s += 3
            if p.objective in ("beat", "grudge") and q.pid == p.obj_target:
                s += 2
            if q.pid in self.known_guard and self.night - self.known_guard[q.pid] <= 2:
                s -= 4
            if q.bandit:
                s -= 3
            s += p.suspicion[q.pid] * 0.5      # punish people you suspect
            if p.arch == "chaos":
                s = self.rng.random()
            if s > best_s:
                best, best_s = q.pid, s
        return best

    def pick_investigate_target(self, p):
        cands = [q for q in self.players if q.pid != p.pid]
        susp = [(p.suspicion[q.pid] + self.public_susp[q.pid] + self.rng.random(), q.pid) for q in cands]
        return max(susp)[1]

    def pick_gift_target(self, p):
        cands = [q for q in self.players if q.pid != p.pid]
        if not cands:
            return None
        # give to whoever looks worst off; bandits close to rejoining are attractive too
        scored = [(self.perceived(p, q) - (2 if q.robbed_last else 0), q.pid) for q in cands]
        return min(scored)[1]

    # ---------------- one night ----------------
    def play_night(self):
        self.night += 1
        r, rng = self.r, self.rng
        if not self.brain:
            acts = {p.pid: self.choose(p) for p in self.players}
        else:
            acts, waiting = {}, []
            for p in self.players:
                if p.pid not in self.smart_ids:
                    acts[p.pid] = self.choose(p)
                elif not p.bandit and rng.random() < ARCH[p.arch]["miss"] * r.miss_scale:
                    p.missed += 1                       # smart players still forget sometimes
                    acts[p.pid] = ("scavenge", None, 0, True)
                else:
                    waiting.append(p)
            if waiting:
                acts.update(self.brain.decide_many(self, waiting))
            acts = dict(sorted(acts.items()))
        start_bandit = {p.pid: p.bandit for p in self.players}
        if self.logging:
            last = getattr(self.brain, "last", {}) if self.brain else {}
            for pid, a in acts.items():
                p = self.P(pid)
                self.L("action", player=p.name, action=a[0], target=self.P(a[1]).name if a[1] is not None else None,
                       amount=a[2] or None, auto=bool(a[3]), as_bandit=p.bandit, rations_before=p.rations,
                       decided_by=(self.brain.name if pid in self.smart_ids else "rules"),
                       decision=last.get(pid), visibility="private")
        loss_items, gain_items = defaultdict(list), defaultdict(list)
        for p in self.players:
            p.actions[acts[p.pid][0]] += 1
            p.robbed_last = False
        start = {p.pid: p.rations for p in self.players}
        news, truth, radio = [], [], []
        ev = Counter()

        for pid, a in acts.items():
            if a[0] == "guard":
                gp = self.P(pid)
                if gp.guard_until < self.night:      # a fresh guard (not a wasted re-guard)
                    gp.guards_used += 1
                    gp.guard_until = self.night + r.guard_nights - 1
                    gp.next_guard_night = gp.guard_until + 1 + r.guard_cooldown
                    self.L("guard_up", player=gp.name, until_night=gp.guard_until, guards_used=gp.guards_used,
                           visibility="private")
                else:
                    self.L("guard_wasted", player=gp.name, protected_until=gp.guard_until, visibility="private")
        guards = {p.pid for p in self.players if p.guard_until >= self.night and not p.bandit}
        steals = defaultdict(list)
        for pid, a in acts.items():
            if a[0] == "steal" and a[1] is not None:
                steals[a[1]].append(pid)

        gains = defaultdict(int)
        losses = defaultdict(int)
        robbed_by = defaultdict(list)       # victim -> thieves who got something
        for tgt, thieves in steals.items():
            t = self.P(tgt)
            if tgt in guards:
                for th in thieves:
                    tp = self.P(th)
                    losses[th] += r.caught_penalty
                    gains[tgt] += r.guard_reward
                    loss_items[th].append(("caught_penalty", r.caught_penalty, t.name))
                    gain_items[tgt].append(("guard_reward", r.guard_reward, tp.name))
                    self.L("steal", thief=tp.name, target=t.name, outcome="caught", amount=0, visibility="public")
                    tp.steals_caught += 1
                    tp.caution *= 0.5
                    self.public_delta[th] -= r.caught_penalty
                    self.public_susp[th] += 2
                    self.known_guard[tgt] = self.night
                    ev["caught"] += 1
                    fine = (f"{tp.name} pays {t.name} {r.caught_penalty}." if r.guard_reward
                            else f"{tp.name} is fined {r.caught_penalty}.")
                    news.append(f"CAUGHT: {t.name} was guarding and caught {tp.name} red-handed. {fine}")
                    tp.notes.append(f"Night {self.night}: you tried to rob {t.name}, who was guarding. You paid {r.caught_penalty}.")
                    t.notes.append(f"Night {self.night}: your guard caught {tp.name}; they paid you {r.guard_reward}.")
                    truth.append(f"{tp.name} tried to rob {t.name} (guarded)")
                continue
            wants = [(th, r.bandit_steal_amount if self.P(th).bandit else r.steal_amount) for th in thieves]
            available = start[tgt]
            total_want = sum(w for _, w in wants)
            take = min(available, total_want)
            # split as evenly as possible, random order for remainders
            rng.shuffle(wants)
            shares = {th: 0 for th, _ in wants}
            left = take
            while left > 0:
                progressed = False
                for th, w in wants:
                    if left > 0 and shares[th] < w:
                        shares[th] += 1
                        left -= 1
                        progressed = True
                if not progressed:
                    break
            losses[tgt] += take
            if take > 0:
                loss_items[tgt].append(("robbed", take, ", ".join(self.P(th).name for th, g in shares.items() if g)))
            for th, got in shares.items():
                gains[th] += got
                tp = self.P(th)
                if got > 0:
                    gain_items[th].append(("stole", got, t.name))
                self.L("steal", thief=tp.name, target=t.name, outcome="success" if got else "empty", amount=got,
                       split_with=len(thieves) - 1, visibility="victim_sees_amount_only")
                if got > 0:
                    tp.steals_ok += 1
                    if tgt == tp.obj_target and tp.objective == "grudge":
                        tp.grudge_hits += 1
                    tp.rations_stolen += got
                    robbed_by[tgt].append(th)
                    tp.notes.append(f"Night {self.night}: you stole {got} from {t.name}.")
                else:
                    tp.notes.append(f"Night {self.night}: you tried to steal from {t.name} but got nothing.")
                truth.append(f"{tp.name} robbed {t.name} for {got}")
            if take > 0:
                t.times_robbed += 1
                t.robbed_last = True
                self.public_delta[tgt] -= take
                ev["robbed"] += 1
                who = "Someone" if len(thieves) == 1 else f"{len(thieves)} people"
                news.append(f"{who} hit {t.name} overnight. {t.name} is down {take}.")
                t.notes.append(f"Night {self.night}: someone stole {take} of your rations.")
            else:
                ev["empty_steal"] += 1
                news.append(f"Someone broke into {t.name}'s place and found nothing.")

        for pid, a in acts.items():
            p = self.P(pid)
            if a[0] == "scavenge" and not p.bandit:
                if a[3] and r.missed_scavenge_max >= 0:
                    gains[pid] += rng.randint(0, r.missed_scavenge_max)
                else:
                    gains[pid] += rng.randint(r.scavenge_min, r.scavenge_max)
                found = gains[pid] - sum(x[1] for x in gain_items[pid])
                gain_items[pid].append(("scavenge", found, "auto" if a[3] else ""))
                self.L("scavenge", player=p.name, found=found, auto=bool(a[3]), visibility="private")
                if self.brain:
                    p.notes.append(f"Night {self.night}: you scavenged and found {gains[pid]}.")
            elif a[0] == "guard" and not p.bandit and r.guard_income_max > 0:
                extra = rng.randint(0, r.guard_income_max)
                gains[pid] += extra
                gain_items[pid].append(("guard_income", extra, ""))

        for p in self.players:
            p.rations = max(0, start[p.pid] - losses[p.pid]) + gains[p.pid]
            if self.logging:                       # same result, written out item by item
                bal = start[p.pid]
                for reason, amt, detail in loss_items[p.pid]:
                    d = min(amt, bal)
                    bal -= d
                    extra = {"requested": amt} if d < amt else {}
                    self.ledger(p, -d, reason, bal, detail=detail, **extra)
                for reason, amt, detail in gain_items[p.pid]:
                    if amt:
                        bal += amt
                        self.ledger(p, amt, reason, bal, detail=detail)
                assert bal == p.rations, (p.name, bal, p.rations)

        # gifts (after steals, so a gift can't be stolen the same night)
        for pid, a in acts.items():
            if a[0] != "gift":
                continue
            giver, recv = self.P(pid), self.P(a[1])
            amt = min(a[2], max(0, giver.rations - 1))
            if amt <= 0:
                continue
            giver.rations -= amt
            recv.rations += amt + r.gift_bonus
            giver.gifted_out += amt
            self.L("gift", giver=giver.name, receiver=recv.name, amount=amt, visibility="giver_and_receiver")
            self.ledger(giver, -amt, "gift_out", giver.rations, detail=recv.name)
            self.ledger(recv, amt + r.gift_bonus, "gift_in", recv.rations, detail=giver.name)
            ev["gift"] += 1
            recv.notes.append(f"Night {self.night}: {giver.name} secretly gave you {amt}.")
            giver.notes.append(f"Night {self.night}: you gave {recv.name} {amt}.")
            truth.append(f"{giver.name} gave {recv.name} {amt}")

        # investigations and radio
        for pid, a in acts.items():
            if a[0] != "investigate":
                continue
            inv, tgt = self.P(pid), self.P(a[1])
            seen = acts[a[1]]
            did = {"steal": "stole from {}", "investigate": "investigated {}", "gift": "gave food to {}",
                   "guard": "guarded", "scavenge": "scavenged"}[seen[0]]
            inv.notes.append(f"Night {self.night}: you watched {tgt.name}: they "
                             + did.format(self.P(seen[1]).name if seen[1] is not None else "") + ".")
            self.L("investigate", investigator=inv.name, target=tgt.name, saw_action=seen[0],
                   saw_target=self.P(seen[1]).name if seen[1] is not None else None, visibility="private")
            if seen[0] == "steal" and seen[1] is not None:
                victim = seen[1]
                inv.suspicion[tgt.pid] += 2
                if victim == pid:
                    inv.knows_robbed_by.add(tgt.pid)
                if r.investigate_bounty > 0:
                    pay = min(r.investigate_bounty, tgt.rations)
                    tgt.rations -= pay
                    inv.rations += pay
                    self.L("exposed", thief=tgt.name, investigator=inv.name, victim=self.P(victim).name, paid=pay,
                           visibility="public_without_investigator")
                    self.ledger(tgt, -pay, "bounty_paid", tgt.rations, detail=inv.name)
                    self.ledger(inv, pay, "bounty_received", inv.rations, detail=tgt.name)
                    self.public_susp[tgt.pid] += 2
                    self.public_delta[tgt.pid] -= pay
                    ev["exposed"] += 1
                    news.append(f"EXPOSED: an investigator saw {tgt.name} rob {self.P(victim).name}. "
                                f"{tgt.name} pays them {pay}.")
                elif rng.random() < max(0.4, ARCH[inv.arch]["radio"]):
                    self.public_susp[tgt.pid] += 1.5
                    radio.append(f"\"I've got proof {tgt.name} went after {self.P(victim).name} last night.\"")
                    self.L("radio", author=inv.name, text=radio[-1], kind="accusation", true=True,
                           visibility="public_anonymous")
                    ev["radio_true"] += 1

        # eat, deaths, comebacks
        for p in self.players:
            was_bandit = p.bandit
            if not p.bandit:
                before = p.rations
                p.rations = max(0, p.rations - r.eat)
                if before != p.rations or before == 0:
                    self.ledger(p, p.rations - before, "eat", p.rations)
                if p.rations == 0:
                    self.L("became_bandit", player=p.name, visibility="public")
                    p.bandit = True
                    p.ever_bandit = True
                    p.deaths += 1
                    if p.times_robbed == 0:
                        p.died_unrobbed += 1
                    ev["death"] += 1
                    news.append(f"{p.name} ran out of food. {p.name} is back... as a bandit.")
                    p.notes.append(f"Night {self.night}: you ran out of food and became a bandit.")
            elif was_bandit and p.rations >= r.bandit_rejoin:
                p.bandit = False
                self.L("rejoined", player=p.name, rations=p.rations, visibility="public")
                p.comebacks += 1
                ev["comeback"] += 1
                news.append(f"Bandit {p.name} has scraped together enough to rejoin the survivors.")

        # victims guess at who robbed them using public suspicion
        for victim, thieves in robbed_by.items():
            v = self.P(victim)
            for q in self.players:
                if q.pid != victim:
                    v.suspicion[q.pid] += 0.3 * self.public_susp[q.pid]

        # rumours and framing
        for p in self.players:
            if p.arch in ("chaos", "shark") and rng.random() < ARCH[p.arch]["radio"] * 0.5:
                victim = rng.choice([q for q in self.players if q.pid != p.pid])
                self.public_susp[victim.pid] += 1
                radio.append(f"\"Just saying: {victim.name} has been very quiet. Too quiet.\"")
                self.L("radio", author=p.name, text=radio[-1], kind="rumour", true=False,
                       visibility="public_anonymous")
                truth.append(f"(radio rumour about {victim.name} came from {p.name})")
                ev["radio_false"] += 1

        self.public_log += [(self.night, line) for line in news + radio]
        if self.logging:
            self.L("news_post", channel="#news", lines=list(news), visibility="public")
            self.L("night_end", rations={p.name: p.rations for p in self.players},
                   bandits=sorted(p.name for p in self.players if p.bandit),
                   guarded_until={p.name: p.guard_until for p in self.players if p.guard_until >= self.night},
                   guards_used={p.name: p.guards_used for p in self.players})
        if self.brain:
            self.brain.after_night(self, acts, start, start_bandit)
        quiet = ev["robbed"] + ev["caught"] + ev["death"] + ev["comeback"] + ev["exposed"] == 0
        self.night_stats.append(dict(ev, quiet=quiet))
        if self.record:
            for pid, a in acts.items():
                if a[3]:
                    truth.append(f"{self.P(pid).name} missed the deadline (auto-scavenge)")
            if self.brain and getattr(self.brain, "last", None):
                for pid in sorted(self.brain.last):
                    truth.append(f"[{self.brain.name}] {self.P(pid).name} chose {self.brain.last[pid]}")
                self.brain.last = {}
            self.log.append(dict(night=self.night, news=news, radio=radio, truth=truth,
                                 standings=sorted(((p.rations, p.name, p.bandit) for p in self.players),
                                                  reverse=True)))

    # ---------------- end of game ----------------
    def finish(self):
        r, rng = self.r, self.rng
        seats = max(1, round(r.players * r.seat_ratio))
        eligible = [p for p in self.players if not p.bandit or r.bandit_can_extract]
        rng.shuffle(eligible)                          # coin flips for whatever is still tied
        if r.tiebreak == "kindness":
            key = lambda p: (p.rations, p.gifted_out, -p.steals_caught)
        else:
            key = lambda p: (p.rations,)
        eligible.sort(key=key, reverse=True)
        extracted = eligible[:seats]
        coin_flip = (len(eligible) > seats and key(eligible[seats - 1]) == key(eligible[seats]))
        ext_ids = {p.pid for p in extracted}

        for p in self.players:
            p.extracted = p.pid in ext_ids
            p.survived = not p.bandit
            o = p.objective
            if o == "beat":
                done = p.rations > self.P(p.obj_target).rations
            elif o == "robbed2_extract":
                done = p.times_robbed >= r.robbed_goal and p.extracted
            elif o == "steal3_clean":
                done = p.steals_ok >= 3 and p.steals_caught == 0
            elif o == "give":
                done = p.gifted_out >= r.give_goal
            elif r.grudge_goal == "deny":
                done = p.obj_target not in ext_ids
            else:  # rob
                done = p.grudge_hits >= r.grudge_robs
            p.obj_done = done
            p.score = (r.pts_extract if p.extracted else (r.pts_survive if p.survived else 0)) \
                + (r.pts_objective if done else 0)

        if self.logging:
            self.L("extraction", seats=seats, extracted=[p.name for p in extracted],
                   ranking=[{"player": p.name, "rations": p.rations, "gave_away": p.gifted_out} for p in eligible],
                   tiebreak=r.tiebreak, decided_by_coin_flip=coin_flip, visibility="public")
            for p in self.players:
                tgt = self.P(p.obj_target).name if p.obj_target >= 0 else ""
                self.L("result", player=p.name, rations=p.rations, survived=p.survived, extracted=p.extracted,
                       objective=obj_text(p.objective, r, tgt), objective_done=p.obj_done, score=p.score,
                       stole=p.rations_stolen, steals_ok=p.steals_ok, steals_caught=p.steals_caught,
                       times_robbed=p.times_robbed, gave_away=p.gifted_out, visibility="public_at_reveal")
        top = max(p.score for p in self.players)
        winners = [p for p in self.players if p.score == top]
        if r.winner_tiebreak != "none":
            wkey = (lambda p: (p.gifted_out, p.rations)) if r.winner_tiebreak == "kindness" else (lambda p: (p.rations,))
            best = max(wkey(p) for p in winners)
            winners = [p for p in winners if wkey(p) == best]
        self.L("game_end", winners=[p.name for p in winners], winner_tiebreak=r.winner_tiebreak, visibility="public")
        return dict(seats=seats, extracted=extracted, coin_flip=coin_flip, winners=winners,
                    cutoff=extracted[-1].rations if extracted else 0,
                    survivors=len(eligible))

    def run(self):
        for _ in range(self.r.rounds):
            self.play_night()
        return self.finish()


# --------------------------------------------------------------------------
# Reel: one game, told the way #news would tell it
# --------------------------------------------------------------------------


def reel(rules, seed, truth=True, mix=None, brain_factory=None, smart=None, log_path=None):
    g = Game(rules, seed, mix=mix, record=True, brain=brain_factory() if brain_factory else None, smart=smart,
             log=bool(log_path))
    res = g.run()
    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            for e in g.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"SURVIVORS - simulated game (seed {seed}, {rules.players} players, {rules.rounds} nights)\n")
    print("Cast:")
    for p in sorted(g.players, key=lambda p: p.name):
        tgt = g.P(p.obj_target).name if p.obj_target >= 0 else ""
        print(f"  {p.name:<9} {p.arch:<12} secret goal: {obj_text(p.objective, g.r, tgt)}")
    for n in g.log:
        print(f"\n=== NIGHT {n['night']} - #news, 07:30 ===")
        for line in n["news"] or ["A quiet night. Nobody lost anything. Suspicious."]:
            print(f"  - {line}")
        for line in n["radio"]:
            print(f"  #radio: {line}")
        if truth:
            print("  [behind the scenes]")
            for line in n["truth"] or ["nothing happened"]:
                print(f"    {line}")
            st = ", ".join(f"{name} {r}{'(B)' if b else ''}" for r, name, b in n["standings"])
            print(f"    rations: {st}")
    print("\n=== EXTRACTION ===")
    print(f"  {res['seats']} seats. On the chopper: " +
          ", ".join(f"{p.name} ({p.rations})" for p in res["extracted"]))
    if res["coin_flip"]:
        print("  The last seat came down to a coin flip.")
    print("\n=== THE REVEAL ===")
    for p in sorted(g.players, key=lambda p: -p.score):
        tgt = g.P(p.obj_target).name if p.obj_target >= 0 else ""
        status = "extracted" if p.extracted else ("survived" if p.survived else "bandit")
        print(f"  {p.score} pts  {p.name:<9} {p.arch:<12} {status:<10} rations {p.rations:<3}"
              f" stole {p.rations_stolen} ({p.steals_ok} ok / {p.steals_caught} caught), robbed {p.times_robbed}x,"
              f" goal {'DONE' if p.obj_done else 'failed'}: {obj_text(p.objective, g.r, tgt)}")
    print(f"\n  Winner(s): {', '.join(p.name for p in res['winners'])}")


# --------------------------------------------------------------------------
# Batch: many games, aggregate stats, flags
# --------------------------------------------------------------------------


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def simulate(rules, runs, seed=1, mix=None, force=None, brain_factory=None, smart=None):
    M = defaultdict(list)
    F = defaultdict(list)                  # stats for forced (ultra) players
    arch_score = defaultdict(list)
    arch_extract = defaultdict(list)
    arch_win = Counter()
    arch_count = Counter()
    obj = defaultdict(list)
    for i in range(runs):
        g = Game(rules, seed + i, mix=mix, force=force,
                 brain=brain_factory() if brain_factory else None, smart=smart)
        res = g.run()
        ps = g.players
        nf = len(force or [])
        if nf:
            forced, rest = ps[:nf], ps[nf:]
            win_ids = {w.pid for w in res["winners"]}
            F["win"].append(sum(1 / len(res["winners"]) for p in forced if p.pid in win_ids) / nf)
            F["extract"].append(statistics.mean(1 if p.extracted else 0 for p in forced))
            F["survive"].append(statistics.mean(1 if p.survived else 0 for p in forced))
            F["ever_bandit"].append(statistics.mean(1 if p.ever_bandit else 0 for p in forced))
            F["score"].append(statistics.mean(p.score for p in forced))
            F["rations"].append(statistics.mean(p.rations for p in forced))
            if rest:
                F["rest_score"].append(statistics.mean(p.score for p in rest))
                F["rest_survive"].append(statistics.mean(1 if p.survived else 0 for p in rest))
        steals_ok = sum(p.steals_ok for p in ps)
        caught = sum(p.steals_caught for p in ps)
        attempts = sum(p.actions["steal"] for p in ps)
        rations_end = [p.rations for p in ps if not p.bandit]
        M["survivors_end"].append(sum(not p.bandit for p in ps))
        M["bandits_end"].append(sum(p.bandit for p in ps))
        M["ever_bandit"].append(sum(p.ever_bandit for p in ps))
        M["comebacks"].append(sum(p.comebacks for p in ps))
        M["died_never_robbed"].append(sum(p.died_unrobbed for p in ps))
        M["steal_attempts"].append(attempts)
        M["catch_rate"].append(caught / attempts if attempts else 0)
        M["empty_steals"].append(sum(n.get("empty_steal", 0) for n in g.night_stats))
        M["quiet_nights"].append(sum(n["quiet"] for n in g.night_stats))
        M["robberies_per_night"].append(statistics.mean(n.get("robbed", 0) for n in g.night_stats))
        M["max_rations"].append(max(p.rations for p in ps))
        M["median_rations_survivors"].append(statistics.median(rations_end) if rations_end else 0)
        M["extraction_cutoff"].append(res["cutoff"])
        M["coin_flip_finale"].append(1 if res["coin_flip"] else 0)
        M["seats_unfilled"].append(max(0, res["seats"] - res["survivors"]))
        M["deaths_final_night"].append(g.night_stats[-1].get("death", 0))
        M["first_death_night"].append(next((n + 1 for n, s in enumerate(g.night_stats) if s.get("death")),
                                          rules.rounds + 1))
        thief_ext = sum(1 for p in res["extracted"] if p.steals_ok >= 3)
        M["extracted_heavy_thieves"].append(thief_ext / max(1, len(res["extracted"])))
        M["winners_per_game"].append(len(res["winners"]))
        for p in ps:
            arch_score[p.arch].append(p.score)
            arch_extract[p.arch].append(1 if p.extracted else 0)
            arch_count[p.arch] += 1
            obj[p.objective].append(1 if p.obj_done else 0)
        for w in res["winners"]:
            arch_win[w.arch] += 1 / len(res["winners"])
    return dict(M=M, F=F, arch_score=arch_score, arch_extract=arch_extract, arch_win=arch_win,
                arch_count=arch_count, obj=obj, runs=runs)


LABELS = [
    ("survivors_end", "Survivors at the end"),
    ("bandits_end", "Bandits at the end"),
    ("ever_bandit", "Players who were ever a bandit"),
    ("comebacks", "Bandit comebacks"),
    ("died_never_robbed", "Died without ever being robbed"),
    ("first_death_night", "First death on night"),
    ("steal_attempts", "Steal attempts per game"),
    ("catch_rate", "Share of steals caught by a guard"),
    ("empty_steals", "Steals that found nothing"),
    ("robberies_per_night", "Robberies per night"),
    ("quiet_nights", "Quiet nights (no robbery/catch/death)"),
    ("max_rations", "Richest player's rations"),
    ("median_rations_survivors", "Median survivor rations"),
    ("extraction_cutoff", "Rations needed for the last seat"),
    ("coin_flip_finale", "Last seat decided by coin flip"),
    ("seats_unfilled", "Empty seats on the chopper"),
    ("deaths_final_night", "Deaths on the final night"),
    ("extracted_heavy_thieves", "Share of seats won by heavy thieves (3+ steals)"),
    ("winners_per_game", "Joint winners per game"),
]


def fmt(v):
    return f"{v:.2f}" if isinstance(v, float) and abs(v) < 10 else f"{v:.1f}"


def report(rules, runs, seed, mix=None, brain_factory=None, smart=None):
    S = simulate(rules, runs, seed, mix, None, brain_factory, smart)
    M = S["M"]
    print(f"SURVIVORS - {runs} simulated games, {rules.players} players, {rules.rounds} nights")
    changed = {f.name: getattr(rules, f.name) for f in fields(Rules) if getattr(rules, f.name) != getattr(Rules(), f.name)}
    print(f"Rules changed from default: {changed or 'none'}\n")
    print(f"{'Metric':<50}{'mean':>8}{'p10':>8}{'p90':>8}")
    for k, label in LABELS:
        xs = M[k]
        print(f"{label:<50}{fmt(statistics.mean(xs)):>8}{fmt(pct(xs, .1)):>8}{fmt(pct(xs, .9)):>8}")

    total_players = sum(S["arch_count"].values())
    print(f"\n{'Personality':<13}{'share':>7}{'avg pts':>9}{'extract':>9}{'win share':>11}  ")
    for a in sorted(ARCH, key=lambda a: -statistics.mean(S["arch_score"][a]) if S["arch_score"][a] else 0):
        if not S["arch_count"][a]:
            continue
        share = S["arch_count"][a] / total_players
        print(f"{a:<13}{share:>7.0%}{statistics.mean(S['arch_score'][a]):>9.2f}"
              f"{statistics.mean(S['arch_extract'][a]):>9.0%}{S['arch_win'][a] / runs:>11.0%}")

    print(f"\n{'Secret objective':<50}{'completed':>10}")
    for o in OBJECTIVES:
        print(f"{obj_text(o, rules):<50}{statistics.mean(S['obj'][o]):>10.0%}")

    print("\nFlags:")
    flags = flag_issues(S, rules)
    for f in flags or ["nothing obviously broken"]:
        print(f"  - {f}")
    return S


def flag_issues(S, rules):
    M, out = S["M"], []
    mean = lambda k: statistics.mean(M[k])
    if mean("catch_rate") < 0.12:
        out.append(f"Guards rarely catch anyone ({mean('catch_rate'):.0%} of steals). Stealing is close to free.")
    if mean("catch_rate") > 0.40:
        out.append(f"Guards catch {mean('catch_rate'):.0%} of steals. Stealing may feel pointless.")
    if mean("quiet_nights") > rules.rounds * 0.2:
        out.append(f"{mean('quiet_nights'):.1f} quiet nights per game. Not enough news.")
    if mean("died_never_robbed") > 1:
        out.append(f"{mean('died_never_robbed'):.1f} players per game die without ever being robbed "
                   "(pure bad luck or forgetting). That feels unfair.")
    if mean("seats_unfilled") > 0.2:
        out.append("The chopper often leaves with empty seats: too many bandits at the end.")
    if mean("coin_flip_finale") > 0.35:
        out.append(f"The last seat is a coin flip in {mean('coin_flip_finale'):.0%} of games. Rations are too bunched.")
    if mean("bandits_end") > rules.players * 0.4:
        out.append(f"{mean('bandits_end'):.1f} of {rules.players} end as bandits. The economy is too harsh.")
    if mean("ever_bandit") < 1:
        out.append("Almost nobody ever dies. Too safe: no stakes.")
    if mean("comebacks") < 0.5 and mean("ever_bandit") >= 2:
        out.append("Bandits almost never come back. The dead are just out.")
    if mean("extracted_heavy_thieves") > 0.5:
        out.append(f"{mean('extracted_heavy_thieves'):.0%} of seats go to heavy thieves. Crime pays too well.")
    total = sum(S["arch_count"].values())
    for a, n in S["arch_count"].items():
        share = n / total
        win = S["arch_win"][a] / S["runs"]
        if share > 0.04 and win > 2.2 * share:
            out.append(f"'{a}' players win {win:.0%} of games while being {share:.0%} of the office. Dominant strategy?")
        if share > 0.08 and win < 0.35 * share:
            out.append(f"'{a}' players almost never win ({win:.0%} vs {share:.0%} of the office).")
    for o in OBJECTIVES:
        rate = statistics.mean(S["obj"][o])
        if rate > 0.75:
            out.append(f"Objective '{obj_text(o, rules)}' is too easy ({rate:.0%}).")
        if rate < 0.12:
            out.append(f"Objective '{obj_text(o, rules)}' is nearly impossible ({rate:.0%}).")
    return out


COMPARE_KEYS = [
    ("survivors_end", "Survivors"), ("ever_bandit", "Ever bandit"), ("comebacks", "Comebacks"),
    ("died_never_robbed", "Unrobbed deaths"), ("catch_rate", "Catch rate"),
    ("robberies_per_night", "Robberies/night"), ("quiet_nights", "Quiet nights"),
    ("coin_flip_finale", "Coin-flip finale"), ("seats_unfilled", "Empty seats"),
    ("extracted_heavy_thieves", "Thief seat share"),
]


def compare(base_rules, names, runs, seed, mix=None):
    results = {}
    for n in names:
        rules = replace(base_rules, **variant(n))
        S = simulate(rules, runs, seed, mix)
        results[n] = S
    col = 14
    print(f"{runs} games per variant\n")
    print(f"{'':<20}" + "".join(f"{n[:col - 1]:>{col}}" for n in names))
    for k, label in COMPARE_KEYS:
        print(f"{label:<20}" + "".join(f"{fmt(statistics.mean(results[n]['M'][k])):>{col}}" for n in names))
    print("\nWin share by personality")
    for a in ARCH:
        if not any(results[n]["arch_count"][a] for n in names):
            continue
        row = []
        for n in names:
            S = results[n]
            row.append(f"{S['arch_win'][a] / S['runs']:>{col}.0%}")
        print(f"{a:<20}" + "".join(row))
    return results


# --------------------------------------------------------------------------
# Extremes: what happens when people go ultra one direction
# --------------------------------------------------------------------------

EXTREME_TYPES = ["always_guard", "turtle", "always_steal", "always_scavenge", "always_gift", "always_investigate"]


def extremes(rules, runs, seed, mix=None):
    n = rules.players
    mean = statistics.mean
    print(f"EXTREMES - {runs} games per scenario, {n} players")
    changed = {f.name: getattr(rules, f.name) for f in fields(Rules) if getattr(rules, f.name) != getattr(Rules(), f.name)}
    print(f"Rules changed from default: {changed or 'none'}")

    print("\n1) THE WHOLE OFFICE GOES ULTRA (all players play the same way)")
    head = ["Survivors", "Ever bandit", "1st death", "Robs/night", "Catch rate", "Quiet nights", "Seat cutoff", "Empty seats"]
    keys = ["survivors_end", "ever_bandit", "first_death_night", "robberies_per_night", "catch_rate",
            "quiet_nights", "extraction_cutoff", "seats_unfilled"]
    print(f"{'':<20}" + "".join(f"{h:>13}" for h in head))
    rows = [("normal office", None)] + [(t, [t] * n) for t in EXTREME_TYPES]
    for label, force in rows:
        S = simulate(rules, runs, seed, mix, force)
        print(f"{label:<20}" + "".join(f"{fmt(mean(S['M'][k])):>13}" for k in keys))

    fair = 1 / n
    for k in (1, 3, 5):
        who = "ONE PLAYER GOES" if k == 1 else f"{k} PLAYERS GO"
        print(f"\n{2 if k == 1 else (3 if k == 3 else 4)}) {who} ULTRA in a normal office "
              f"(fair win share per player = {fair:.1%})")
        print(f"{'':<20}{'Win share':>11}{'vs fair':>9}{'Extract':>9}{'Survive':>9}{'Ever died':>11}"
              f"{'Avg pts':>9}{'Others pts':>12}{'Robs/night':>12}")
        for t in ["(normal player)"] + EXTREME_TYPES:
            if t == "(normal player)":
                S = simulate(rules, runs, seed, mix, None)
                # average over all players in a normal office
                tot_players = runs * n
                win = 1 / n
                ext = sum(sum(v) for v in S["arch_extract"].values()) / tot_players
                score = sum(sum(v) for v in S["arch_score"].values()) / tot_players
                print(f"{t:<20}{win:>11.1%}{1:>9.2f}{ext:>9.0%}{'':>9}{'':>11}{score:>9.2f}{'':>12}"
                      f"{fmt(mean(S['M']['robberies_per_night'])):>12}")
                continue
            S = simulate(rules, runs, seed, mix, [t] * k)
            F = S["F"]
            win = mean(F["win"])
            print(f"{t:<20}{win:>11.1%}{win / fair:>9.2f}{mean(F['extract']):>9.0%}{mean(F['survive']):>9.0%}"
                  f"{mean(F['ever_bandit']):>11.0%}{mean(F['score']):>9.2f}{mean(F['rest_score']):>12.2f}"
                  f"{fmt(mean(S['M']['robberies_per_night'])):>12}")


# --------------------------------------------------------------------------


DEFAULT_GAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game.json")


def load_game_rules(path):
    """Rules from the shared game.json (its "rules" block). Unknown keys are ignored with a note."""
    if not path or path == "none" or not os.path.exists(path):
        return Rules(), "built-in defaults"
    with open(path, encoding="utf-8") as f:
        game = json.load(f)
    known = {f.name for f in fields(Rules)}
    block = game.get("rules", {})
    extra = sorted(set(block) - known)
    if extra:
        print(f"(game.json keys not used by the simulator: {', '.join(extra)})")
    defaults = Rules()
    picked = {}
    for k, v in block.items():
        if k not in known:
            continue
        d = getattr(defaults, k)
        if isinstance(d, float) and isinstance(v, (int, float)) and abs(d - v) < 1e-6:
            v = d                                   # 0.3333333333 in JSON means 1/3
        picked[k] = v
    return replace(defaults, **picked), \
        f"{os.path.normpath(path)} ({game.get('version', 'no version')})"


def parse_sets(base, sets):
    kw = {}
    types = {f.name: f.type for f in fields(Rules)}
    for s in sets or []:
        k, v = s.split("=", 1)
        if k not in types:
            raise SystemExit(f"unknown rule '{k}'. Run: survivors_sim.py rules")
        t = getattr(base, k)
        kw[k] = (v.lower() in ("1", "true", "yes")) if isinstance(t, bool) else type(t)(v)
    return replace(base, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["reel", "batch", "compare", "extremes", "rules"])
    ap.add_argument("variants", nargs="*", help="variant names for compare mode")
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--variant", default="baseline", help="start from a named variant (combine with +)")
    ap.add_argument("--mix", default="default", choices=list(MIXES), help="office personality mix")
    ap.add_argument("--set", action="append", metavar="KEY=VALUE")
    ap.add_argument("--no-truth", action="store_true", help="reel: hide the behind-the-scenes lines")
    ap.add_argument("--rules", default=DEFAULT_GAME,
                    help="game.json to read rules from (default: ../game.json; 'none' = built-in defaults)")
    ap.add_argument("--brain", default="rules", choices=["rules", "adaptive", "jev"],
                    help="how players decide: fixed personality odds (rules), learn from payoffs (adaptive), or Jev")
    ap.add_argument("--smart", type=int, default=None, help="how many players use --brain (default: all)")
    ap.add_argument("--jev-model", default="jev-latest")
    ap.add_argument("--jev-mock", action="store_true", help="test the Jev path offline with a fake model")
    ap.add_argument("--jev-argmax", action="store_true", help="always take Jev's top choice instead of sampling")
    ap.add_argument("--max-calls", type=int, default=3000, help="hard cap on Jev calls per command")
    ap.add_argument("--log", metavar="FILE.jsonl", help="reel: write the full replay log (see LOG_FORMAT.md)")
    a = ap.parse_args()

    base, source = load_game_rules(a.rules)
    print(f"Rules from: {source}")
    rules = parse_sets(replace(base, **variant(a.variant)), a.set)
    mix = MIXES[a.mix]
    factory = None
    if a.brain != "rules":
        import brains
        factory = brains.make_brain_factory(a.brain, ARCH, model=a.jev_model, mock=a.jev_mock,
                                            max_calls=a.max_calls, sample=not a.jev_argmax) \
            if a.brain == "jev" else brains.make_brain_factory(a.brain, ARCH)
        who = "all players" if a.smart is None else f"{a.smart} of {rules.players} players"
        print(f"Brain: {a.brain} for {who}")
        if a.mode not in ("reel", "batch"):
            raise SystemExit("--brain works with reel and batch.")
        if a.brain == "jev" and a.mode == "batch" and not a.jev_mock:
            est = a.runs * rules.rounds * (rules.players if a.smart is None else a.smart)
            print(f"Up to {est:,} Jev calls (cap {a.max_calls:,}).")
    if a.mode == "rules":
        for f in fields(Rules):
            print(f"  {f.name:<22} {getattr(rules, f.name)}")
        print("\nVariants: " + ", ".join(f"{k} {v}" for k, v in VARIANTS.items()))
        print("\nPersonalities:")
        for k, v in ARCH.items():
            share = f"{OFFICE_MIX[k]:.0%} of office" if k in OFFICE_MIX else "test only"
            print(f"  {k:<19} {share:<14} {v['desc']}")
    elif a.mode == "reel":
        reel(rules, a.seed, truth=not a.no_truth, mix=mix, brain_factory=factory, smart=a.smart, log_path=a.log)
        if a.log:
            print(f"\nReplay log written to {a.log}")
    elif a.mode == "batch":
        report(rules, a.runs, a.seed, mix, factory, a.smart)
    elif a.mode == "extremes":
        extremes(rules, a.runs, a.seed, mix)
    else:
        compare(rules, a.variants or list(VARIANTS), a.runs, a.seed, mix)
    if factory is not None and hasattr(factory, "shared"):
        print("\n" + factory.shared.report())


if __name__ == "__main__":
    main()
