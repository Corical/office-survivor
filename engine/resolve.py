"""One night of Survivors, in the fixed phase order. Pure: no I/O, no clock, randomness only from the caller's rng.

Phases (see LOG_FORMAT.md and the rules doc):
  1. guards go up            2. thieves who hit a guard pay   3. other thefts, from a snapshot
  4. scavenging              5. gifts                         6. investigations and bounty
  7. eating, bandits, comebacks

`moves` maps player id -> (kind, target_id | None, amount, auto) with kind in scavenge/steal/guard/investigate/gift.
Every ration change is booked as an event through `emit`; food moves between players only as a transfer of what
the payer actually holds, and only scavenging (and rule-set bonuses) creates it.

`obs` is called at each point a caller may want to react (the simulator updates its AI players' beliefs there).
The engine never depends on what the observer does, except that an observer may draw from the same rng, so the
hooks sit exactly where the simulator drew before the engine was extracted.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field


class Observer:
    """No-op hooks. Override what you need."""

    def caught(self, night, thief, target, paid, to_guard): pass
    def stole(self, night, thief, target, got): pass
    def robbed(self, night, victim, take): pass
    def scavenged(self, night, player, found): pass
    def gifted(self, night, giver, receiver, amount): pass
    def restored(self, night, victim, thief, amount): pass     # an exposure gave `amount` of the loot back to the victim
    def investigated(self, night, investigator, target, seen, exposed_paid): pass
    def became_bandit(self, night, player): pass


@dataclass
class NightResult:
    start: dict                       # pid -> rations before the night
    news: list = field(default_factory=list)      # #news lines, in posting order
    truth: list = field(default_factory=list)     # what really happened (for the reveal)
    ev: Counter = field(default_factory=Counter)  # counts: caught, robbed, empty_steal, gift, exposed, death, comeback
    robbed_by: dict = field(default_factory=dict)  # victim pid -> thief pids who got something


def resolve_night(players, moves, r, rng, night, emit=lambda _type, **f: None, obs=None, flags=frozenset()):
    """`flags` is the camp-wide weather for tonight (wilderness events, default none): "storm" = nobody finds food
    scavenging, "feast" = nobody eats. A player may carry `idol` = True (set by an event): the next theft against
    them takes nothing. With no flags and no idols this is exactly the original night."""
    obs = obs or Observer()
    moves = dict(sorted(moves.items()))    # player-id order, never arrival order: same moves, same night
    P = {p.pid: p for p in players}

    def ledger(p, delta, reason, balance, **extra):
        emit("ration", player=p.name, delta=delta, reason=reason, balance=balance, **extra)

    for p in players:
        p.actions[moves[p.pid][0]] += 1
        p.robbed_last = False
    res = NightResult(start={p.pid: p.rations for p in players})
    news, truth, ev = res.news, res.truth, res.ev

    # 1. guards go up
    for pid, a in moves.items():
        if a[0] == "guard":
            gp = P[pid]
            if gp.guard_until < night:      # a fresh guard (not a wasted re-guard)
                gp.guards_used += 1
                gp.guard_until = night + r.guard_nights - 1
                gp.next_guard_night = gp.guard_until + 1 + r.guard_cooldown
                emit("guard_up", player=gp.name, until_night=gp.guard_until, guards_used=gp.guards_used,
                     visibility="private")
            else:
                emit("guard_wasted", player=gp.name, protected_until=gp.guard_until, visibility="private")
    guards = {p.pid for p in players if p.guard_until >= night and not p.bandit}
    steals = defaultdict(list)
    for pid, a in moves.items():
        if a[0] == "steal" and a[1] is not None:
            steals[a[1]].append(pid)

    bal = dict(res.start)

    def move(src, dst, amount, out_reason, in_reason):
        """Move up to `amount` from src to dst; both sides get exactly what moved. Returns what moved."""
        moved = min(amount, bal[src])
        if moved:
            bal[src] -= moved
            bal[dst] += moved
            ledger(P[src], -moved, out_reason, bal[src], detail=P[dst].name,
                   **({"requested": amount} if moved < amount else {}))
            ledger(P[dst], moved, in_reason, bal[dst], detail=P[src].name)
        return moved

    robbed_by = defaultdict(list)
    loot = {}        # thief pid -> (victim pid, rations they took tonight): what an exposure can still take back
    # 2. thieves who walked into a guard pay first, from what they actually hold; the guard receives what was paid,
    #    up to guard_reward, and anything above that is a fine that leaves the game
    for tgt, thieves in steals.items():
        if tgt not in guards:
            continue
        t = P[tgt]
        for th in thieves:
            tp = P[th]
            can_pay = min(r.caught_penalty, bal[th])
            to_guard = move(th, tgt, min(can_pay, r.guard_reward), "caught_penalty", "guard_reward")
            fined = can_pay - to_guard
            if fined:
                bal[th] -= fined
                ledger(tp, -fined, "fine", bal[th], detail=t.name)
            paid = to_guard + fined
            emit("steal", thief=tp.name, target=t.name, outcome="caught", amount=0, paid=paid, visibility="public")
            tp.steals_caught += 1
            ev["caught"] += 1
            fine = (f"{tp.name} pays {t.name} {to_guard}." if r.guard_reward else f"{tp.name} is fined {paid}.")
            news.append(f"CAUGHT: {t.name} was guarding and caught {tp.name} red-handed. {fine}")
            obs.caught(night, tp, t, paid, to_guard)
            truth.append(f"{tp.name} tried to rob {t.name} (guarded)")

    # 3. other thefts take from what each victim holds after step 2, fixed before any theft lands, so the order
    #    between thieves can't matter and tonight's loot can't be stolen again tonight
    can_lose = dict(bal)
    for tgt, thieves in steals.items():
        if tgt in guards:
            continue
        t = P[tgt]
        wants = [(th, r.bandit_steal_amount if P[th].bandit else r.steal_amount) for th in thieves]
        shielded = getattr(t, "idol", False)
        take = min(can_lose[tgt], sum(w for _, w in wants))
        if shielded:                       # a hidden idol: this night's thieves get nothing, and the idol is spent
            take = 0
            t.idol = False
            ev["idol_used"] += 1
            emit("event", event="idol_used", player=t.name, visibility="public")
            news.append(f"IDOL: someone tried to rob {t.name} and left with nothing. The idol is spent.")
        rng.shuffle(wants)                # split as evenly as possible, random order for remainders
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
        for th, got in shares.items():
            tp = P[th]
            if got > 0:
                moved = move(tgt, th, got, "robbed", "stole")
                assert moved == got, ("theft larger than the victim's start-of-step rations", t.name, got, moved)
            emit("steal", thief=tp.name, target=t.name, outcome="success" if got else "empty", amount=got,
                 split_with=len(thieves) - 1, visibility="victim_sees_amount_only")
            if got > 0:
                tp.steals_ok += 1
                if tp.steals_caught == 0:
                    tp.clean_steals += 1
                if tgt == tp.obj_target and tp.objective == "grudge":
                    tp.grudge_hits += 1
                tp.rations_stolen += got
                robbed_by[tgt].append(th)
                loot[th] = (tgt, got)
            obs.stole(night, tp, t, got)
            truth.append(f"{tp.name} robbed {t.name} for {got}")
        if take > 0:
            t.times_robbed += 1
            t.robbed_last = True
            ev["robbed"] += 1
            who = "Someone" if len(thieves) == 1 else f"{len(thieves)} people"
            news.append(f"{who} hit {t.name} overnight. {t.name} is down {take}.")
            obs.robbed(night, t, take)
        else:
            ev["empty_steal"] += 1
            if not shielded:
                news.append(f"Someone broke into {t.name}'s place and found nothing.")
    res.robbed_by = dict(robbed_by)

    # 4. scavenging (and guard income, where a rule set has it) is the only thing that creates food
    for pid, a in moves.items():
        p = P[pid]
        if a[0] == "scavenge" and not p.bandit:
            if a[3] and r.missed_scavenge_max >= 0:
                found = rng.randint(0, r.missed_scavenge_max)
            else:
                found = rng.randint(r.scavenge_min, r.scavenge_max)
            if "storm" in flags:           # the roll is still drawn, so the random stream matches a calm night
                ev["storm_lost"] += found
                found = 0
            bal[pid] += found
            emit("scavenge", player=p.name, found=found, auto=bool(a[3]), visibility="private")
            if found:
                ledger(p, found, "scavenge", bal[pid], detail="auto" if a[3] else "")
            obs.scavenged(night, p, found)
        elif a[0] == "guard" and not p.bandit and r.guard_income_max > 0:
            extra = rng.randint(0, r.guard_income_max)
            bal[pid] += extra
            if extra:
                ledger(p, extra, "guard_income", bal[pid], detail="")

    for p in players:
        p.rations = bal[p.pid]
        assert p.rations >= 0, (p.name, p.rations)

    # 5. gifts (after steals, so a gift can't be stolen the same night)
    for pid, a in moves.items():
        if a[0] != "gift":
            continue
        giver, recv = P[pid], P[a[1]]
        amt = min(a[2], max(0, giver.rations - 1))
        if amt <= 0:
            continue
        giver.rations -= amt
        recv.rations += amt
        giver.gifted_out += amt
        emit("gift", giver=giver.name, receiver=recv.name, amount=amt, visibility="giver_and_receiver")
        ledger(giver, -amt, "gift_out", giver.rations, detail=recv.name)
        ledger(recv, amt, "gift_in", recv.rations, detail=giver.name)
        if r.gift_bonus:                   # a rule-set bonus is new food, booked as such
            recv.rations += r.gift_bonus
            ledger(recv, r.gift_bonus, "gift_bonus", recv.rations, detail=giver.name)
        ev["gift"] += 1
        obs.gifted(night, giver, recv, amt)
        truth.append(f"{giver.name} gave {recv.name} {amt}")

    # 6. investigations and bounty
    for pid, a in moves.items():
        if a[0] != "investigate":
            continue
        inv, tgt = P[pid], P[a[1]]
        seen = moves[a[1]]
        emit("investigate", investigator=inv.name, target=tgt.name, saw_action=seen[0],
             saw_target=P[seen[1]].name if seen[1] is not None else None, visibility="private")
        exposed_paid = None
        undo = r.exposure_undo != "none"
        if seen[0] == "steal" and seen[1] is not None and (r.investigate_bounty > 0 or undo):
            victim = P[seen[1]]
            # An exposure takes back what this thief took tonight (only this thief's share, only once, and only
            # what they still hold: loot first, then the bounty). A thief who hit a guard or an idol took nothing.
            taken = loot.pop(tgt.pid, None) if undo else None
            back = min(taken[1], tgt.rations) if taken else 0
            to_victim = back if r.exposure_undo == "full" else (back + 1) // 2
            to_inv = back - to_victim
            pay = min(r.investigate_bounty, tgt.rations - back)
            if not undo:
                emit("exposed", thief=tgt.name, investigator=inv.name, victim=victim.name, paid=pay,
                     visibility="public_without_investigator")
            else:
                emit("exposed", thief=tgt.name, investigator=inv.name, victim=victim.name, paid=pay,
                     loot_back=back, to_victim=to_victim, to_investigator=to_inv,
                     visibility="public_without_investigator")
            transfers = [(pay, inv, "bounty_paid", "bounty_received")]
            if undo:                       # loot goes back before the bounty is paid
                transfers[:0] = [(to_victim, victim, "exposed_return", "exposed_return"),
                                 (to_inv, inv, "exposed_loot", "exposed_loot")]
            for amt, dst, out_reason, in_reason in transfers:
                if amt or not undo:        # today's books always carry the bounty line, even for 0
                    tgt.rations -= amt
                    dst.rations += amt
                    ledger(tgt, -amt, out_reason, tgt.rations, detail=dst.name)
                    ledger(dst, amt, in_reason, dst.rations, detail=tgt.name)
            ev["exposed"] += 1
            inv.exposures = getattr(inv, "exposures", 0) + 1
            if not undo:
                news.append(f"EXPOSED: an investigator saw {tgt.name} rob {victim.name}. {tgt.name} pays them {pay}.")
                exposed_paid = pay
            else:
                ev["exposed_undone"] += bool(back)
                news.append(f"EXPOSED: an investigator saw {tgt.name} rob {victim.name}. {tgt.name} hands back "
                            f"{back} and pays {pay}.")
                exposed_paid = back + pay
                if to_victim:
                    obs.restored(night, victim, tgt, to_victim)
        if r.investigate_find > 0:         # opt-in: watching also turns up new food, booked as such. The die is drawn
            found = rng.randint(0, r.investigate_find)     # for every investigator, and only when the knob is on
            if found:
                inv.rations += found
                ledger(inv, found, "investigate_find", inv.rations, detail="")
            ev["investigate_find"] += found
        obs.investigated(night, inv, tgt, seen, exposed_paid)

    # 7. eat, run out (bandit), come back
    for p in players:
        was_bandit = p.bandit
        if not p.bandit:
            before = p.rations
            eat = 0 if "feast" in flags else r.eat
            if eat == 0 and r.eat and before > 0:
                ev["feast_saved"] += r.eat
            p.rations = max(0, p.rations - eat)
            if before != p.rations or before == 0:
                ledger(p, p.rations - before, "eat", p.rations)
            if p.rations == 0:
                emit("became_bandit", player=p.name, visibility="public")
                p.bandit = True
                p.ever_bandit = True
                p.deaths += 1
                if p.times_robbed == 0:
                    p.died_unrobbed += 1
                ev["death"] += 1
                news.append(f"{p.name} ran out of food. {p.name} is back... as a bandit.")
                obs.became_bandit(night, p)
        elif was_bandit and p.rations >= r.bandit_rejoin:
            p.bandit = False
            emit("rejoined", player=p.name, rations=p.rations, visibility="public")
            p.comebacks += 1
            ev["comeback"] += 1
            news.append(f"Bandit {p.name} has scraped together enough to rejoin the survivors.")
    return res
