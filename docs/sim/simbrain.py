"""The simulated players' brain: personalities, the move chooser, target picking and belief updates.

One implementation, two hosts: the simulator (survivors_sim.Game) and Torch's sim colleagues (bot/brain.py). The code
here only READS what the host offers and writes only to the AI's own beliefs, so the rules never see it.

A host is anything with these attributes (see Game.__init__ and bot/brain.py SimBrain for the two real ones):
    r (Rules)      night (the night being decided)      rng (the dice for this decision)
    players        every seat; P(pid) -> seat           others(p) -> the seats p may target
    public_delta / public_susp / known_guard / gift_owed     what the camp has been told (dicts keyed by pid)
    vis / edges    "hidden" | "ranges" | "exact" and the band edges   mem (Memory or None)   ai_exposure / ai_quiet
    why (dict)     scratch for the replay log
and every seat has: pid name arch rations bandit objective obj_target caution robbed_last knows_robbed_by suspicion
clean_steals steals_caught gifted_out grudge_hits guard_until guards_used next_guard_night missed.

Nothing is drawn from the rng except by the methods below, and in a fixed order, so the same host state and the same
rng give the same decision.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import visibility as V  # noqa: E402

from engine import Observer  # noqa: E402  (docs/sim/visibility.py puts the repo root on sys.path)

KINDS = ("scavenge", "steal", "guard", "investigate", "gift")
AI_BASE_PAYOUT = 1        # an exposure paid the investigator 1 (the bounty) before exposure_undo existed

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


class SimAI:
    """Mixin: how an AI player chooses a move. Game (the simulator) and SimBrain (Torch) both inherit it."""

    # ---------------- helpers ----------------
    def others(self, p):
        """The seats `p` may target: everyone else. A host with players who have left overrides this."""
        return [q for q in self.players if q.pid != p.pid]

    def fresh(self, q):
        """What the information on offer says q holds, before judgement noise. hidden: start minus publicly known
        losses (a bandit counts as 1). ranges: that guess pulled into q's posted band, so the exact count never
        reaches the AI. exact: the true count."""
        if self.vis == "exact":
            return float(q.rations)
        if q.bandit:
            return 1
        guess = self.r.start_rations + self.public_delta[q.pid]
        if self.vis == "ranges":
            lo, hi = V.band_bounds(V.band_index(q, self.edges), self.edges)
            return min(max(guess, lo), hi)
        return guess

    def perceived(self, viewer, q):
        """What `viewer` guesses q has: the information on offer (remembered, for human-memory players) plus noise."""
        base = self.mem.est[viewer.pid][q.pid] if self.mem else self.fresh(q)
        sd = V.NOISE_SD[self.vis]
        return base + (self.rng.gauss(0, sd) if sd else self.rng.random() * V.EXACT_TIE_JITTER)

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

    def choose(self, p):
        """The rules brain's move, plus why: the reasons and odds are kept for the replay log (no extra dice rolls)."""
        self._why, self._odds = [], None
        act = self._choose(p)
        self.why[p.pid] = {"reasons": self._why, "odds": self._odds}
        return act

    def _choose(self, p):
        a = ARCH[p.arch]
        why = self._why
        final = self.night == self.r.rounds
        if not p.bandit and self.rng.random() < a["miss"] * self.r.miss_scale:
            p.missed += 1
            why.append(f"missed the deadline (a {p.arch} misses {a['miss'] * self.r.miss_scale:.0%} of nights), "
                       "so the bot scavenged for them")
            return ("scavenge", None, 0, True)

        if p.bandit:
            kind = "steal" if self.rng.random() < 0.85 else "investigate"
            self._odds = {"steal": 0.85, "investigate": 0.15}
            why.append("a bandit can only steal (85%) or investigate (15%)")
        elif a.get("pure"):
            kind = a["pure"]
            why.append(f"test player: {a['desc']}")
            if kind == "turtle":
                kind = "guard" if self.can_guard(p) else "scavenge"
            elif kind == "guard" and not self.can_guard(p) and p.guard_until < self.night:
                kind = "scavenge"           # out of guards: forced to do something else
                why.append("out of guards, so scavenged")
            if kind == "gift" and p.rations < 2:
                kind = "scavenge"
                why.append("too little food to give, so scavenged")
        else:
            w = dict(zip(KINDS, a["w"]))
            why.append(f"{p.arch}: {a['desc']}")
            if self.ai_exposure and self.invest_payout() > 0:
                w["investigate"] *= self.invest_payout() / AI_BASE_PAYOUT
                if self.invest_payout() != AI_BASE_PAYOUT:
                    why.append(f"an exposure pays the investigator {self.invest_payout()} (today {AI_BASE_PAYOUT}), "
                               "so investigating is weighed up or down by that ratio")
            if self.ai_quiet:
                # opt-in, AI only (identical in every sweep row; does nothing while investigate_find and gift_bonus are 0
                # and nobody has gifted yet). Investigating is weighed up by its expected find over today's payout of 1;
                # gifting by what the receiver gets over what the giver pays; and a player who was given food by an
                # alias and has not returned it is likelier to give back (+0.25).
                if self.r.investigate_find:
                    w["investigate"] *= (AI_BASE_PAYOUT + self.r.investigate_find / 2) / AI_BASE_PAYOUT
                    why.append(f"watching also finds 0..{self.r.investigate_find} food, so investigating is weighed up")
                g_amt = 2 if p.rations >= 7 else 1
                if self.r.gift_bonus:
                    w["gift"] *= (g_amt + self.r.gift_bonus) / g_amt
                    why.append(f"a gift gives the receiver {self.r.gift_bonus} extra, so gifting is weighed up")
                if self.owed_to(p):
                    w["gift"] += 0.25
                    why.append("was given food and has not returned it: likelier to give back")
            w["steal"] *= p.caution
            if p.caution < 1:
                why.append(f"has been caught before, so stealing odds are cut to {p.caution:.0%} of normal")
            if p.robbed_last:
                w["guard"] += 0.5
                why.append("robbed last night, so more likely to guard")
                if p.arch == "detective":
                    w["investigate"] += 0.3
                    why.append("detective who was robbed: wants to find out who")
            revenge = [t for t in p.knows_robbed_by if not self.P(t).bandit]
            if revenge and p.arch != "saint":
                w["steal"] += 0.4
                why.append("knows who robbed them (" + ", ".join(self.P(t).name for t in revenge) + "): wants revenge")
            if p.rations <= 2:
                w["steal"] += 0.25 * (p.arch != "saint")
                w["gift"] = 0
                w["guard"] *= 0.5
                why.append(f"only {p.rations} rations left: desperate, no gifts"
                           + (", more stealing" if p.arch != "saint" else ""))
            if p.rations >= 8:
                w["guard"] += 0.15
                why.append(f"{p.rations} rations: protecting the stash")
            if final:
                w["steal"] += 0.6 * a["final"]
                w["guard"] += 0.3
                w["investigate"] = 0          # info is worthless on the last night
                why.append("last night: grab or protect a seat, information is worthless now")
            if p.objective == "steal3_clean" and p.clean_steals < 3 and p.steals_caught == 0:
                w["steal"] += 0.2
                why.append(f"secret goal (steal 3 times clean, {p.steals_ok} so far) nudges toward stealing")
            if p.objective == "give" and p.gifted_out < self.r.give_goal:
                w["gift"] += 0.25
                why.append(f"secret goal (give away {self.r.give_goal}, {p.gifted_out} so far) nudges toward gifting")
            if p.objective == "grudge":
                if self.r.grudge_goal == "deny" and self.night >= self.r.rounds - 2:
                    w["steal"] += 0.3
                    why.append("secret goal (stop " + self.P(p.obj_target).name + " extracting) nudges toward stealing")
                elif self.r.grudge_goal == "rob" and p.grudge_hits < self.r.grudge_robs:
                    w["steal"] += 0.2
                    why.append("secret goal (rob " + self.P(p.obj_target).name + ") nudges toward stealing")
            if p.rations <= 1:
                w["gift"] = 0
            if not self.can_guard(p):
                if p.guard_until >= self.night:
                    why.append(f"already protected until night {p.guard_until}, so no new guard")
                elif self.r.guard_limit and p.guards_used >= self.r.guard_limit:
                    why.append(f"used all {self.r.guard_limit} guards")
                w["guard"] = 0               # protected already, out of guards, or cooling down
            total = sum(v for v in w.values() if v > 0)
            self._odds = {k: round(v / total, 3) for k, v in w.items() if v > 0} if total else {}
            kind = self.weighted(w)
            if self._odds.get(kind):
                why.append(f"rolled {kind} (a {self._odds[kind]:.0%} chance)")

        if kind == "steal":
            return ("steal", self.pick_steal_target(p), 0, False)
        if kind == "investigate":
            return ("investigate", self.pick_investigate_target(p), 0, False)
        if kind == "gift":
            tgt = self.pick_gift_target(p)
            if tgt is None:
                why.append("nobody to give to, so scavenged")
                return ("scavenge", None, 0, False)
            amt = 2 if p.rations >= 7 else 1
            return ("gift", tgt, amt, False)
        return (kind, None, 0, False)

    def owed_to(self, p):
        """Players who gave `p` food that `p` has not given back, oldest first (AI memory, only kept when ai_quiet)."""
        return [q for q in self.gift_owed.get(p.pid, []) if not self.P(q).bandit]

    def invest_payout(self):
        """What one exposure pays the investigator, for a typical theft of steal_amount: the bounty, plus their half
        of the loot when the rules split it (the victim gets the larger half)."""
        r = self.r
        share = (r.steal_amount // 2) if r.exposure_undo == "split" else 0
        return r.investigate_bounty + share

    def pick_steal_target(self, p):
        best, best_s, best_info = None, -1e9, None
        for q in self.others(p):
            s = self.perceived(p, q)
            guess = s
            flags = []
            if q.pid in p.knows_robbed_by:
                s += 3
                flags.append("revenge: they robbed you")
            if p.objective in ("beat", "grudge") and q.pid == p.obj_target:
                s += 2
                flags.append("your secret-goal target")
            if (q.pid in self.mem.guard_seen[p.pid]) if self.mem else \
                    (q.pid in self.known_guard and self.night - self.known_guard[q.pid] <= 2):
                s -= 4
            if q.bandit:
                s -= 3
            if p.suspicion[q.pid] > 0:
                flags.append("you suspect them")
            s += p.suspicion[q.pid] * 0.5      # punish people you suspect
            if p.arch == "chaos":
                s = self.rng.random()
            if s > best_s:
                best, best_s, best_info = q.pid, s, (guess, flags)
        if best is not None:
            if p.arch == "chaos":
                self._why.append(f"picked {self.P(best).name} at random (chaos)")
            else:
                guess, flags = best_info
                self._why.append(f"picked {self.P(best).name}: looked like they had about {max(0, round(guess))} rations"
                                 + ("; " + "; ".join(flags) if flags else ""))
        return best

    def pick_investigate_target(self, p):
        cands = self.others(p)
        susp = [(p.suspicion[q.pid] + self.public_susp[q.pid] + self.rng.random(), q.pid) for q in cands]
        top = max(susp)
        q = self.P(top[1])
        known = p.suspicion[q.pid] + self.public_susp[q.pid]
        self._why.append(f"watched {q.name}: " + ("top suspect (named in #news or #radio, or seen stealing)"
                                                  if known > 0 else "a hunch, nobody stood out"))
        return top[1]

    def pick_gift_target(self, p):
        cands = self.others(p)
        if not cands:
            return None
        # give to whoever looks worst off; bandits close to rejoining are attractive too
        if self.ai_quiet:                  # pay back the most recent giver first
            owed = self.owed_to(p)
            if owed:
                q = self.P(owed[-1])
                self._why.append(f"gave to {q.name}: they gave to you")
                return q.pid
        scored = [(self.perceived(p, q) - (2 if q.robbed_last else 0), q.pid) for q in cands]
        low = min(scored)
        q = self.P(low[1])
        self._why.append(f"gave to {q.name}: looked worst off" + (" (robbed last night)" if q.robbed_last else ""))
        return low[1]


class BeliefObserver(Observer):
    """What AI players believe and remember, updated at the points the engine calls. Shared by the simulator (which adds
    a diary and radio on top, see survivors_sim.SimObserver) and Torch. `g` is the host (see the module docstring)."""

    def __init__(self, g):
        self.g = g

    def caught(self, night, tp, t, paid, to_guard):
        g = self.g
        tp.caution *= 0.5
        g.public_delta[tp.pid] -= paid
        g.public_susp[tp.pid] += 2
        g.known_guard[t.pid] = night
        if g.mem:
            g.mem.touch(tp.pid, t.pid)
            g.mem.touch(t.pid, tp.pid)

    def stole(self, night, tp, t, got):
        if self.g.mem:
            self.g.mem.touch(tp.pid, t.pid)

    def robbed(self, night, t, take):
        self.g.public_delta[t.pid] -= take

    def gifted(self, night, giver, recv, amt):
        if self.g.mem:
            self.g.mem.touch(giver.pid, recv.pid)
            self.g.mem.touch(recv.pid, giver.pid)
        if self.g.ai_quiet:                # the receiver now owes the giver; a gift back clears what the giver owed them
            owed = self.g.gift_owed
            owed[giver.pid] = [x for x in owed.get(giver.pid, []) if x != recv.pid]
            owed.setdefault(recv.pid, [])
            owed[recv.pid] = [x for x in owed[recv.pid] if x != giver.pid] + [giver.pid]

    def restored(self, night, victim, thief, amount):
        self.g.public_delta[victim.pid] += amount          # the EXPOSED line in #news says the loot went back

    def investigated(self, night, inv, tgt, seen, exposed_paid):
        g = self.g
        if g.mem:
            g.mem.touch(inv.pid, tgt.pid)
        if seen[0] != "steal" or seen[1] is None:
            return
        victim = seen[1]
        inv.suspicion[tgt.pid] += 2
        if victim == inv.pid:
            inv.knows_robbed_by.add(tgt.pid)
        self.saw_theft(night, inv, tgt, victim, exposed_paid)
        if exposed_paid is not None:
            g.public_susp[tgt.pid] += 2
            g.public_delta[tgt.pid] -= exposed_paid
            if g.ai_exposure:
                tgt.caution *= 0.5
        else:
            self.unexposed_theft(night, inv, tgt, victim)

    # extension points: the investigator saw `tgt` rob `victim` (always), and the theft was not exposed (no payout)
    def saw_theft(self, night, inv, tgt, victim, exposed_paid): pass
    def unexposed_theft(self, night, inv, tgt, victim): pass
