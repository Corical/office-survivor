"""Torch's game service: everything players and the Game Master can do in Discord's words, on top of the game core.

The rules, the log, replay, moves, quits, radio and the sims live in bot/core.py (GameCore), shared with the live
Godot rooms. This layer adds what is Torch's own: the compressed-day schedule, the wording of every reply, the
#news / #radio / DM lines, and the outbox. The service never talks to Discord: anything to send goes into the log as an
outbox intent ("post", "dm"), the adapter delivers it and reports back with `mark_sent`.
"""
import logging
import time
from dataclasses import dataclass

from engine.finish import goal_progress, objective_text
from engine.visibility import band_label, morning_board

from .core import EVENT_MODES, RADIO_PHRASES, GameCore, GameError, night_seed  # noqa: F401 (re-exported)

log = logging.getLogger("torch.game")


@dataclass
class Schedule:
    """When each round's deadline and news fall. Compressed: one day every `day_seconds` from the start."""
    start_ts: float
    day_seconds: float
    news_delay: float = 5.0

    def deadline(self, night):
        return self.start_ts + night * self.day_seconds

    def news_at(self, night):
        return self.deadline(night) + self.news_delay


SAST = __import__("datetime").timezone(__import__("datetime").timedelta(hours=2), "SAST")   # no daylight saving

FINAL_STRETCH = 3       # the last this-many nights get a countdown (owner, 17 Oct 2026)


def endgame_note(night, rounds):
    """'' early on; '⏳ 3 nights left' … '🚁 LAST NIGHT…' for the final stretch, counting the night itself."""
    left = rounds - night + 1
    if left <= 0 or left > FINAL_STRETCH:
        return ""
    if left == 1:
        return "🚁 **LAST NIGHT:** the helicopter comes after this. Seats go to the biggest stashes."
    return f"⏳ **{left} nights left**, then the helicopter."


def night_label(schedule, night, closed=False):
    """'Night 6 (closes 08:34)' while moves are open, 'Night 6 (closed 08:34)' in news and results after it;
    'Night 6 (Tue)' for real days. A real-world anchor for the number."""
    import datetime
    end = datetime.datetime.fromtimestamp(schedule.deadline(night), SAST)
    if schedule.day_seconds >= 20 * 3600:
        return f"Night {night} ({(end - datetime.timedelta(minutes=1)).strftime('%a')})"
    return f"Night {night} ({'closed' if closed else 'closes'} {end.strftime('%H:%M')})"


class GameService(GameCore):
    def __init__(self, rules, store, identity, texts, aliases, season_id, clock=time.time, avoid_aliases=()):
        self.season_id = season_id            # Torch's seed key: never shown to players
        super().__init__(rules, store, identity, texts, aliases, season_id, clock=clock, avoid_aliases=avoid_aliases)

    # ---------------- state from the log: Torch's own parts ----------------
    def _reset(self):
        super()._reset()
        self.schedule = None
        self.news_posted = set()   # nights whose news intents exist
        self.intents, self.sent = {}, set()

    def _loaded(self):
        log.info("state rebuilt: started=%s night=%d players=%d pending_outbox=%d", self.started, self.night,
                 len(self.players) or len(self.joined), len(self.pending_outbox()))

    def _apply(self, rec, replay):
        for intent in rec.get("outbox", []):      # messages ride inside the record that causes them: one write
            self.intents[intent["id"]] = intent
        super()._apply(rec, replay)

    def _on_start(self, rec):
        self.schedule = Schedule(rec["start_ts"], rec["day_seconds"], rec["news_delay"])

    def _apply_extra(self, rec, replay):
        t = rec["type"]
        if t == "news":
            self.news_posted.add(rec["night"])
            self.radio_pending = []
        elif t == "sent":
            self.sent.add(rec["id"])

    def _private_for(self, events, p, before, night):
        return private_lines(events, p, before, night, self.rules.guard_nights)

    def _quit_extra(self, alias):
        return {"outbox": self._intents(("news", f"{alias} has left the game. Their food goes with them.", None))}

    def _intents(self, *msgs):
        """Outbox intents for (to, text, ref) tuples, numbered after those already known."""
        n = len(self.intents)
        return [{"id": f"o{n + i + 1}", "to": to, **({"text": text} if text else {}), **({"ref": ref} if ref else {})}
                for i, (to, text, ref) in enumerate(msgs)]

    # ---------------- player commands ----------------
    def join(self, user_key, sim=False, rng=None, personality=None):
        if self.started:
            raise GameError("The game has already started; joining is closed.")
        if self.identity.get(user_key):
            return f"You're already in as **{self.identity.get(user_key)['alias']}**."
        alias = self.add_player(user_key, sim=sim, rng=rng, personality=personality)
        return (f"You're in. Your secret alias is **{alias}**. Tell no one.")

    def submit(self, user_key, kind, target_alias=None, amount=0, at=None):
        if not self.started or self.finished:
            raise GameError("There's no round open right now.")
        pid, _ = self._who(user_key)
        night = self.night + 1
        at = self.clock() if at is None else at
        if at >= self.schedule.deadline(night):
            raise GameError("Tonight's deadline has passed; wait for the next round.")
        self.record_move(pid, kind, target_alias, amount, at)
        what = {"scavenge": "🥫 scavenge", "guard": "🛡️ guard", "steal": f"🥷 steal from {target_alias}",
                "investigate": f"🔍 investigate {target_alias}", "gift": f"🎁 give {target_alias} {amount}"}[kind]
        note = endgame_note(night, self.rules.rounds)
        return (f"{night_label(self.schedule, night)}: you'll {what}. You can change your mind until the deadline."
                + (f"\n{note}" if note else ""))

    def play_menu(self, user_key):
        """What /play offers this player right now: a header line and the legal moves with target aliases.
        {'header': str, 'moves': {kind: [aliases]}, 'gift_amounts': [ints]}"""
        if not self.started or self.finished:
            raise GameError("There's no round open right now.")
        pid, alias = self._who(user_key)
        if pid in self.quit_ids:
            raise GameError("You're not in this game.")
        night = self.night + 1
        p = self.players[pid]
        moves, amounts = self.legal_for(pid)
        state = "🏴‍☠️ bandit" if p.bandit else f"🥫 {p.rations} rations"
        note = endgame_note(night, self.rules.rounds)
        return {"header": f"**{night_label(self.schedule, night)}**: {alias}, {state}. What will you do tonight?"
                          + (f"\n{note}" if note else ""),
                "moves": moves, "gift_amounts": amounts, "radio": not self.radio_used(pid, night)}

    def board(self):
        """(key, text) for the live status board in #news, or None before anyone has joined. Public facts only.
        The key changes when the board's content does (start, each night, each news, the end); between those,
        Discord's own <t:…:R> timestamps keep the countdown ticking in every player's app."""
        if not self.joined:
            return None
        head = f"🔥 **Survivors** · {len(self.players) or len(self.joined)} players"
        if not self.started:
            return ("waiting", len(self.joined)), f"{head}\n⏳ Waiting for the Game Master to start. /join to play."
        n, rounds = self.night, self.rules.rounds
        posted = len(self.news_posted)
        key = (self.season_id, n, posted, self.finished)
        done = " ".join(str(i) for i in range(1, n + 1)) or "none"
        modes = " · ".join(m for m in ("🌴 Events on" if self.events_mode != "off" else "",
                                        "📊 Ranges on" if self.ranges else "") if m)
        if self.finished:
            return key, f"{head}\n🚁 **Game over.** The reveal is above. Thanks for playing."
        nxt = n + 1
        if nxt <= rounds:
            dl = int(self.schedule.deadline(nxt))
            now_line = f"🌙 **Night {nxt} of {rounds}** · moves close <t:{dl}:R> (<t:{dl}:t>) · tap 🎮 Play"
            note = endgame_note(nxt, rounds)
            now_line += f"\n{note}" if note else ""
        else:
            now_line = "🚁 The last night is over. The helicopter is coming…"
        return key, "\n".join(x for x in (head + (f" · {modes}" if modes else ""), now_line,
                                           f"✅ Nights done: {done}") if x)

    def radio_menu(self, user_key):
        """What the radio picker offers: the fixed lines, the aliases (never your own), and whether today's message
        is still unused. {'lines': [(key, text with '…')], 'about': [aliases], 'available': bool}"""
        if not self.started or self.finished:
            raise GameError("Radio opens when the game starts.")
        pid, _ = self._who(user_key)
        return {"lines": [(k, t.replace("{a}", "…")) for k, t in RADIO_PHRASES.items()],
                "about": self.alias_list(user_key), "available": not self.radio_used(pid)}

    def radio(self, user_key, phrase, about=None):
        self.record_radio(user_key, phrase, about)
        return "Your anonymous message goes out with the morning news."

    def status(self, user_key):
        pid, alias = self._who(user_key)
        if not self.started:
            return f"You're **{alias}**. The game hasn't started yet."
        p = self.players[pid]
        if pid in self.quit_ids:
            return "You've left the game."
        guards = f"{self.rules.guard_limit - p.guards_used} guards left" if self.rules.guard_limit else "guards unlimited"
        tgt = self.players[p.obj_target].name if p.obj_target >= 0 else ""
        move = self.moves.get(pid)
        tonight = ("not chosen yet (you'll scavenge if you forget)" if not move else
                   move[0] + (f" {self.players[move[1]].name}" if move[1] is not None else ""))
        band = band_label(self.players[p.obj_target]) if self.ranges and p.obj_target >= 0 else None
        state, how = goal_progress(p, list(self.players.values()), self.rules, frozenset(self.quit_ids), band)
        mark = {"done": "✅ **Goal met:**", "failed": "❌ **Goal lost:**", "open": "🎯 **Progress:**",
                "end": "⏳ **Progress:**"}[state]
        return (f"**{alias}**: 🥫 {p.rations} rations{' 🏴‍☠️ BANDIT' if p.bandit else ''}, 🛡️ {guards}"
                f"{', guarded tonight' if p.guard_until > self.night else ''}.\n"
                f"Secret goal: {objective_text(p.objective, self.rules, tgt)}.\n{mark} {how}.\nTonight: {tonight}."
                + (f"\nThe camp sees you as {band_label(p)}." if self.ranges else ""))

    def results(self, user_key):
        pid, _ = self._who(user_key)
        lines = self.last_private.get(pid)
        return "\n".join(lines) if lines else "Nothing to report yet."

    def quit(self, user_key):
        if not self.leave(user_key):
            return "You've already left."
        return "You've left the game. Thanks for playing."

    # ---------------- Game Master ----------------
    def gm_start(self, day_seconds, news_delay=5.0, now=None, events="off", ranges=False):
        if events not in EVENT_MODES:
            raise GameError(f"events must be one of: {', '.join(EVENT_MODES)}.")
        if self.started:
            raise GameError("Already started.")
        if len(self.joined) < 2:
            raise GameError("Need at least 2 players.")
        now = self.clock() if now is None else now

        def extra(roster):
            msgs = [("news", f"🔥 The game has begun: {len(roster)} survivors, {self.rules.rounds} rounds. "
                             f"Check /status for your secret goal. Choose a move before each deadline.", None)]
            msgs += [(f"dm:{c['pid']}", "🔥 The game has begun. Use /status any time to see your rations and your "
                                        "secret goal.", None) for c in roster if c["pid"] not in self.sims]
            if events != "off":
                msgs[0] = ("news", msgs[0][1] + " 🌴 Wilderness events are on: luck, good and bad, can strike anyone.",
                           None)
            if ranges:
                msgs[0] = ("news", msgs[0][1] + " 📊 Every morning #news shows everyone's ration range "
                                   "(🟢 7+ · 🟡 3-6 · 🔴 1-2 · 🏴‍☠️ bandit), never the exact count.", None)
            return {"start_ts": now, "day_seconds": day_seconds, "news_delay": news_delay, "season": self.season_id,
                    "outbox": self._intents(*msgs)}

        roster = self.start_game(events=events, ranges=ranges, extra=extra)
        log.info("game started: %d players, day=%ss", len(roster), day_seconds)

    # ---------------- the clock ----------------
    def tick(self, now=None):
        """Advance whatever is due: resolve the night at its deadline, post news, finish the game. Idempotent."""
        if not self.started or self.finished:
            return
        now = self.clock() if now is None else now
        nxt = self.night + 1
        if nxt <= self.rules.rounds and now >= self.schedule.deadline(nxt):
            self._resolve_due(nxt)
        if self.night and self.night not in self.news_posted and now >= self.schedule.news_at(self.night):
            self._post_news(self.night)
        if self.night == self.rules.rounds and self.night in self.news_posted and not self.finished:
            self._finish_game()

    def _post_news(self, night):
        rec = self._night_record(night)
        lines = news_lines(rec["events"]) or ["🌙 A quiet night. Nobody lost anything."]
        label = night_label(self.schedule, night, closed=True)
        body = f"📰 **News: {label}**\n" + "\n".join(f"- {l}" for l in lines)
        coming = endgame_note(night + 1, self.rules.rounds)        # about the night that opens now
        if coming:
            body += "\n\n" + coming.replace("**LAST NIGHT:**", "**Tonight is the LAST NIGHT:**")
        if self.ranges:          # the morning ration ranges: a band per player, never a count (engine/visibility.py)
            body += "\n\n📊 **Rations this morning**\n" + "\n".join(morning_board(self._active(), "ranges"))
        msgs = [("news", body, None)]
        msgs += [("radio", None, ref) for ref in self.radio_pending]
        msgs += [(f"dm:{pid}", f"🌙 **{label}**\n" + "\n".join(plines), None)
                 for pid, plines in rec["private"].items() if int(pid) not in self.quit_ids]
        self._append({"type": "news", "night": night, "outbox": self._intents(*msgs)})

    def _finish_game(self):
        events = self._run_finish()
        ext = next(e for e in events if e["type"] == "extraction")
        end = next(e for e in events if e["type"] == "game_end")
        results = sorted((e for e in events if e["type"] == "result"), key=lambda e: -e["score"])
        lines = [f"🚁 The helicopter takes {', '.join(ext['extracted'])}.",
                 f"🏆 Winner: {', '.join(end['winners'])}.", "", "**The reveal**"]
        for e in results:
            lines.append(f"- {e['player']}: {e['score']} pts, {e['rations']} rations, goal: {e['objective']} "
                         f"({'done' if e['objective_done'] else 'missed'}); stole {e['stole']}, robbed "
                         f"{e['times_robbed']}x, gave away {e['gave_away']}")
        intents = self._intents(("news", "\n".join(lines), None))
        intents[0]["image"] = "reveal"     # the adapter posts the reveal table as a picture, this text as fallback
        self._append({"type": "finish", "events": events, "outbox": intents})

    def reveal_data(self):
        """(rows, winners) for the reveal picture, from the finish record; None before the game ends."""
        from .reveal_image import rows_from_results
        rec = next((r for r in self.store.load() if r["type"] == "finish"), None)
        if rec is None:
            return None
        ext = next(e for e in rec["events"] if e["type"] == "extraction")["extracted"]
        end = next(e for e in rec["events"] if e["type"] == "game_end")
        return rows_from_results([e for e in rec["events"] if e["type"] == "result"], ext), end["winners"]

    def _night_record(self, night):
        for rec in self.store.load():
            if rec["type"] == "night" and rec["night"] == night:
                return rec
        raise RuntimeError(f"no record for night {night}")

    # ---------------- outbox ----------------
    def pending_outbox(self):
        return [i for rid, i in self.intents.items() if rid not in self.sent]

    def outbox_text(self, intent):
        return intent.get("text") or self.texts.get(intent.get("ref", "")) or ""

    def mark_sent(self, intent_id, ref=None):
        if intent_id not in self.sent:
            self._append({"type": "sent", "id": intent_id, **({"ref": ref} if ref else {})})


# ---------------- what players are told ----------------
def news_lines(events):
    """The public #news lines for a night, in the engine's order, from its events."""
    out, wild_lines = [], []
    robbed = {}
    idol = {e["player"] for e in events if e["type"] == "event" and e.get("event") == "idol_used"}
    for e in events:
        if e["type"] == "event" and e.get("line"):          # a wilderness event (happens first, so listed first)
            wild_lines.append(e["line"])
        elif e["type"] == "event" and e.get("event") == "idol_used":
            out.append(f"🗿 Someone tried to rob {e['player']} and left empty-handed: {e['player']} had a hidden idol.")
        elif e["type"] == "steal" and e["target"] in idol and e["outcome"] in ("success", "empty"):
            continue                                       # the idol line above says it all
        elif e["type"] == "steal" and e["outcome"] == "caught":
            out.append(f"🚨 CAUGHT: {e['target']} was guarding and caught {e['thief']} red-handed. "
                       f"{e['thief']} paid {e['paid']}.")
        elif e["type"] == "steal" and e["outcome"] in ("success", "empty"):
            robbed.setdefault(e["target"], []).append(e["amount"])
        elif e["type"] == "exposed":
            back = f" and gives {e['victim']} back the {e['to_victim']} they stole" if e.get("to_victim") else ""
            out.append(f"🕵️ EXPOSED: an investigator saw {e['thief']} rob {e['victim']}. "
                       f"{e['thief']} pays them {e['paid']}{back}.")
        elif e["type"] == "became_bandit":
            out.append(f"🏴‍☠️ {e['player']} ran out of food. {e['player']} is back... as a bandit.")
        elif e["type"] == "rejoined":
            out.append(f"🎉 Bandit {e['player']} has scraped together enough to rejoin the survivors.")
    for victim, amounts in robbed.items():
        total = sum(amounts)
        who = "Someone" if len(amounts) == 1 else f"{len(amounts)} people"
        out.insert(0, f"🥷 {who} hit {victim} overnight. {victim} is down {total}." if total
                   else f"🥷 Someone broke into {victim}'s place and found nothing.")
    return wild_lines + out


def private_lines(events, p, before, night=None, guard_nights=2):
    """What one player is told privately about their night."""
    me, out = p.name, []
    idol = {e["player"] for e in events if e["type"] == "event" and e.get("event") == "idol_used"}
    for e in events:
        t = e["type"]
        if t == "event" and e.get("player") == me:
            if e.get("event") == "idol":
                out.append("🗿 You found a hidden idol. The next person to rob you gets nothing. Tell no one.")
            elif e.get("event") == "idol_used":
                out.append("🗿 Your idol saved you: a thief left with nothing. The idol is spent.")
            elif e.get("line"):
                out.append(e["line"])
        elif t == "event" and e.get("scope") == "camp" and e.get("line") and any(
                x["type"] == "ration" and x["player"] == me and x.get("detail") == e["event"] for x in events):
            out.append(e["line"])                       # e.g. rats taxed your stash: say so, not just a lower total
        elif t == "steal" and e["thief"] == me and e["target"] in idol:
            out.append(f"🗿 {e['target']} had a hidden idol. You got nothing.")
        elif t == "scavenge" and e["player"] == me:
            out.append(f"🥫 You didn't choose a move, so you scavenged automatically and found {e['found']}."
                       if e.get("auto") else f"🥫 You scavenged and found {e['found']}.")
        elif t == "guard_up" and e["player"] == me:
            first = night if night else e["until_night"]
            span = (f"night {first}" if first == e["until_night"]
                    else f"nights {first}" + "".join(f", {n}" for n in range(first + 1, e["until_night"]))
                    + f" and {e['until_night']}")
            out.append(f"🛡️ You're on guard for {span}.")
        elif t == "steal" and e["thief"] == me:
            if e["outcome"] == "success":
                out.append(f"🥷 You stole {e['amount']} from {e['target']}.")
            elif e["outcome"] == "empty":
                out.append(f"🥷 You broke into {e['target']}'s place, but someone beat you to it."
                           if e.get("split_with") else f"🥷 You broke into {e['target']}'s place and found nothing.")
            else:
                out.append(f"🚨 {e['target']} was guarding: you were caught and paid {e['paid']}.")
        elif t == "steal" and e["target"] == me and e["outcome"] == "success":
            out.append(f"🥷 Someone stole {e['amount']} from you.")
        elif t == "steal" and e["target"] == me and e["outcome"] == "caught":
            got = sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me
                      and x["reason"] == "guard_reward" and x.get("detail") == e["thief"])
            fresh = any(x["type"] == "guard_up" and x["player"] == me for x in events)
            whose = ("Your guard" if fresh or not night
                     else f"Your guard (still up from night {p.guard_until - guard_nights + 1})")
            out.append(f"🚨 {whose} caught {e['thief']} red-handed. They paid you {got}." if got
                       else f"🚨 {whose} caught {e['thief']} red-handed, but they had nothing to pay you.")
        elif t == "investigate" and e["investigator"] == me:
            saw = e["saw_action"] + (f" ({e['saw_target']})" if e["saw_target"] else "")
            out.append(f"🔍 You watched {e['target']}: they chose {saw}.")
            found = sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me
                        and x["reason"] == "investigate_find")
            if found:
                out.append(f"🔍 While watching, you found {found} ration{'s' if found > 1 else ''}.")
        elif t == "exposed" and e["investigator"] == me:
            out.append(f"🕵️ You exposed {e['thief']}; they paid you {e['paid']}.")
            if e["victim"] == me and e.get("to_victim"):      # you watched your own thief: the loot comes back to you
                out.append(f"🕵️ You also got your {e['to_victim']} back from {e['thief']}, who robbed you.")
        elif t == "exposed" and e["thief"] == me:
            back = f" and gave back the {e['to_victim']} you stole" if e.get("to_victim") else ""
            out.append(f"🕵️ EXPOSED: an investigator saw you rob {e['victim']}. You paid them {e['paid']}{back}.")
        elif t == "exposed" and e["victim"] == me and e.get("to_victim"):
            out.append(f"🕵️ An investigator caught the thief who robbed you: {e['thief']}. "
                       f"You got your {e['to_victim']} back.")
        elif t == "gift" and e["giver"] == me:
            out.append(f"🎁 You gave {e['receiver']} {e['amount']}.")
        elif t == "gift" and e["receiver"] == me:
            bonus = sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me
                        and x["reason"] == "gift_bonus" and x.get("detail") == e["giver"])
            out.append(f"🎁 {e['giver']} secretly gave you {e['amount']}"
                       + (f", and gifts grow: you got {e['amount'] + bonus}." if bonus else "."))
        elif t == "became_bandit" and e["player"] == me:
            out.append("🏴‍☠️ You ran out of food. You're a bandit now: steal or investigate until you get back to 3.")
        elif t == "rejoined" and e["player"] == me:
            out.append("🎉 You've scraped together enough to rejoin the survivors.")
    ate = -sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me and x["reason"] == "eat")
    if ate:
        out.append(f"🍽️ You ate {ate}.")
    elif any(e["type"] == "event" and e.get("event") == "feast" for e in events) and not p.bandit:
        out.append("🍽️ Feast night: you ate for free.")
    out.append(f"🥫 You now have {p.rations} rations.")
    return out
