"""Torch's game service: everything players and the Game Master can do, independent of Discord.

Truth is the event log (EventStore). Who-is-who lives in IdentityStore, radio text in TextStore. The service never
talks to Discord: anything to send goes into the log as an outbox intent ("post", "dm"), the adapter delivers it and
reports back with `mark_sent`. On load the log is folded back into state and every stored night is re-resolved from
its moves and seed; a mismatch stops the bot rather than letting it run on a state it can't reproduce.
"""
import hashlib
import logging
import random
import time
from collections import Counter
from dataclasses import dataclass, replace

from engine import ENGINE_VERSION, PlayerState, Rules, resolve_night
from engine import events as wild
from engine.deal import deal
from engine.finish import finish, objective_text
from engine.moves import can_guard, legal_moves, validate

from . import sims

log = logging.getLogger("torch.game")
# Radio is fixed phrases so nobody can be recognised by their writing style (owner, 17 Oct 2026).
RADIO_PHRASES = {
    "saw": "I saw {a} sneaking around last night.",
    "trust": "Don't trust {a}.",
    "lying": "{a} is lying about their rations.",
    "guarding": "{a} is guarding. Don't waste your night on them.",
    "easy": "{a} looks like an easy target.",
    "innocent": "{a} is innocent. Leave them alone.",
    "me": "I'm innocent. Leave me alone.",
}


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


EVENT_MODES = {   # /gm start events:... ; "gentle" = events round 2's kindest design (docs/sim/results/events_sweep2.md)
    "off": {},
    "gentle": {"events_per_night": 1.0, "events_bias": "top", "events_rats_relative": True},
}


class _EventCtx:
    """What engine/events.py needs from a game, for Torch: the active players, rules, night, a seed, and two writers
    that turn every event and ration change into a record in the night's event list."""

    def __init__(self, players, rules, night, seed, emit):
        self.players, self.r, self.night, self.seed = players, rules, night, seed
        self.event_tally = Counter()
        self.L = emit
        self.ledger = lambda p, delta, reason, balance, detail="": emit(
            "ration", player=p.name, delta=delta, reason=reason, balance=balance, detail=detail)


def night_label(schedule, night, closed=False):
    """'Night 6 (closes 08:34)' while moves are open, 'Night 6 (closed 08:34)' in news and results after it;
    'Night 6 (Tue)' for real days. A real-world anchor for the number."""
    import datetime
    end = datetime.datetime.fromtimestamp(schedule.deadline(night), SAST)
    if schedule.day_seconds >= 20 * 3600:
        return f"Night {night} ({(end - datetime.timedelta(minutes=1)).strftime('%a')})"
    return f"Night {night} ({'closed' if closed else 'closes'} {end.strftime('%H:%M')})"


def night_seed(season_id, night):
    return int(hashlib.sha256(f"{season_id}:{night}".encode()).hexdigest()[:16], 16)


class GameError(Exception):
    """A player-facing refusal: the text is safe to show to the player who asked."""


class GameService:
    def __init__(self, rules: Rules, store, identity, texts, aliases, season_id, clock=time.time):
        self.rules, self.store, self.identity, self.texts = rules, store, identity, texts
        self.aliases, self.season_id, self.clock = list(aliases), season_id, clock
        self._reset()
        self._load()

    # ---------------- state from the log ----------------
    def _reset(self):
        self.players = {}          # pid -> PlayerState (after start)
        self.joined = []           # [(pid, alias, sim, personality)] before start
        self.started = False
        self.finished = False
        self.schedule = None
        self.night = 0             # last resolved night
        self.moves = {}            # pid -> move for night+1
        self.radio_pending = []    # text refs to post with the next news
        self.quit_ids = set()
        self.event_counts = Counter()  # wilderness events so far this game, for the no-repeat story decks
        self.personality = {}      # pid -> personality for sims
        self.sims = set()
        self.news_posted = set()   # nights whose news intents exist
        self.intents, self.sent = {}, set()
        self.last_private = {}     # pid -> [lines] from the last resolved night

    def _load(self):
        for rec in self.store.load():
            self._apply(rec, replay=True)
        log.info("state rebuilt: started=%s night=%d players=%d pending_outbox=%d", self.started, self.night,
                 len(self.players) or len(self.joined), len(self.pending_outbox()))

    def _append(self, rec):
        self.store.append(rec)
        self._apply(rec, replay=False)

    def _apply(self, rec, replay):
        t = rec["type"]
        for intent in rec.get("outbox", []):      # messages ride inside the record that causes them: one write
            self.intents[intent["id"]] = intent
        if t == "join":
            self.joined.append((rec["pid"], rec["alias"], rec.get("sim", False), rec.get("personality")))
            if rec.get("sim"):
                self.sims.add(rec["pid"])
                self.personality[rec["pid"]] = rec["personality"]
        elif t == "start":
            self.started = True
            self.schedule = Schedule(rec["start_ts"], rec["day_seconds"], rec["news_delay"])
            self.events_mode = rec.get("events", "off")            # older logs have no key: events off
            self.rules = replace(self.rules, **EVENT_MODES[self.events_mode])
            for c in rec["roster"]:
                self.players[c["pid"]] = PlayerState(pid=c["pid"], name=c["alias"], rations=self.rules.start_rations,
                                                     objective=c["objective"], obj_target=c["target"])
        elif t == "move":
            if rec["night"] == self.night + 1:
                self.moves[rec["pid"]] = tuple(rec["move"])
        elif t == "quit":
            self.quit_ids.add(rec["pid"])
            if rec["pid"] in self.players:
                self.players[rec["pid"]].rations = 0     # owner decision: a quitter's food leaves the game
            self.moves.pop(rec["pid"], None)
        elif t == "radio":
            self.radio_pending.append(rec["ref"])
        elif t == "night":
            if replay:
                self._replay_night(rec)
            self.night = rec["night"]
            self.moves = {}
            self.last_private = {int(k): v for k, v in rec["private"].items()}
            self.event_counts.update(e["event"] for e in rec["events"] if e["type"] == "event" and "scope" in e)
        elif t == "news":
            self.news_posted.add(rec["night"])
            self.radio_pending = []
        elif t == "sent":
            self.sent.add(rec["id"])
        elif t == "finish":
            if replay:
                self._run_finish(check=rec["events"])
            self.finished = True

    def _replay_night(self, rec):
        events = self._resolve(rec["night"], {int(k): tuple(v) for k, v in rec["moves"].items()})
        if events != rec["events"]:
            raise RuntimeError(f"night {rec['night']} does not replay: the log and the engine disagree")

    def _active(self):
        return [p for pid, p in sorted(self.players.items()) if pid not in self.quit_ids]

    def _resolve(self, night, moves):
        events = []
        emit = lambda _t, **f: events.append({"type": _t, **f})    # noqa: E731
        flags = frozenset()
        if self.rules.events_per_night > 0:      # wilderness events first, from their own dice (engine/events.py)
            ctx = _EventCtx(self._active(), self.rules, night, self.season_id, emit)
            ctx.event_tally.update(self.event_counts)          # earlier nights count, so story decks don't restart
            flags, lines = wild.run_night_events(ctx, wild.rng_for(self.season_id, night))
            public = [e for e in events if e["type"] == "event" and e["visibility"] == "public"]
            for e, line in zip(public, lines):   # each public event wrote one #news line, in the same order
                e["line"] = line
        resolve_night(self._active(), moves, self.rules, random.Random(night_seed(self.season_id, night)), night,
                      emit=emit, flags=flags)
        return events

    def _run_finish(self, check=None):
        events = []
        finish(list(self.players.values()), self.rules, random.Random(night_seed(self.season_id, 0)),
               emit=lambda _t, **f: events.append({"type": _t, **f}), quit_ids=frozenset(self.quit_ids))
        if check is not None and events != check:
            raise RuntimeError("the final scoring does not replay")
        return events

    # ---------------- helpers ----------------
    def _who(self, user_key):
        ident = self.identity.get(user_key)
        if not ident:
            raise GameError("You haven't joined. Use /join.")
        return ident["pid"], ident["alias"]

    def _pid_by_alias(self, alias):
        for pid, p in self.players.items():
            if p.name.lower() == (alias or "").strip().lower():
                return pid
        raise GameError(f"There's no player called '{alias}'.")

    def _intents(self, *msgs):
        """Outbox intents for (to, text, ref) tuples, numbered after those already known."""
        n = len(self.intents)
        return [{"id": f"o{n + i + 1}", "to": to, **({"text": text} if text else {}), **({"ref": ref} if ref else {})}
                for i, (to, text, ref) in enumerate(msgs)]

    def alias_list(self, user_key=None):
        """Aliases still in the game, alphabetical (never join order: that would hint at who is who), without the
        asking player's own alias: you can't target yourself, so you shouldn't be offered."""
        me = (self.identity.get(user_key) or {}).get("pid") if user_key else None
        return sorted(p.name for pid, p in self.players.items() if pid not in self.quit_ids and pid != me)

    # ---------------- player commands ----------------
    def join(self, user_key, sim=False, rng=None):
        if self.started:
            raise GameError("The game has already started; joining is closed.")
        if self.identity.get(user_key):
            return f"You're already in as **{self.identity.get(user_key)['alias']}**."
        taken = {a for _, a, _, _ in self.joined}
        free = [a for a in self.aliases if a not in taken]
        if not free:
            raise GameError("The game is full.")
        rng = rng or random.Random()
        alias = rng.choice(free)
        pid = len(self.joined)
        personality = sims.pick_personality(rng) if sim else None
        self.identity.put(user_key, pid, alias, sim=sim)
        self._append({"type": "join", "pid": pid, "alias": alias, "sim": sim, **({"personality": personality} if sim else {})})
        log.info("join pid=%d sim=%s", pid, sim)
        return (f"You're in. Your secret alias is **{alias}**. Tell no one.")

    def submit(self, user_key, kind, target_alias=None, amount=0, at=None):
        if not self.started or self.finished:
            raise GameError("There's no round open right now.")
        pid, _ = self._who(user_key)
        night = self.night + 1
        at = self.clock() if at is None else at
        if at >= self.schedule.deadline(night):
            raise GameError("Tonight's deadline has passed; wait for the next round.")
        target = self._pid_by_alias(target_alias) if target_alias else None
        move = (kind, target, int(amount or 0), False)
        why = validate(self._active(), pid, move, self.rules, night, frozenset(self.quit_ids))
        if why:
            raise GameError(why)
        self._append({"type": "move", "night": night, "pid": pid, "move": list(move), "at": at})
        log.info("move night=%d pid=%d kind=%s", night, pid, kind)
        what = {"scavenge": "🥫 scavenge", "guard": "🛡️ guard", "steal": f"🥷 steal from {target_alias}",
                "investigate": f"🔍 investigate {target_alias}", "gift": f"🎁 give {target_alias} {amount}"}[kind]
        return f"{night_label(self.schedule, night)}: you'll {what}. You can change your mind until the deadline."

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
        legal = legal_moves(self._active(), pid, self.rules, night, frozenset(self.quit_ids))
        amounts = legal.pop("gift_amounts", [])
        moves = {k: sorted(self.players[t].name for t in v) for k, v in legal.items()}
        state = "🏴‍☠️ bandit" if p.bandit else f"🥫 {p.rations} rations"
        radio_free = not any(r.startswith(f"r{night}-{pid}-") for r in self.radio_pending)
        return {"header": f"**{night_label(self.schedule, night)}**: {alias}, {state}. What will you do tonight?",
                "moves": moves, "gift_amounts": amounts, "radio": radio_free}

    def radio_menu(self, user_key):
        """What the radio picker offers: the fixed lines, the aliases (never your own), and whether today's message
        is still unused. {'lines': [(key, text with '…')], 'about': [aliases], 'available': bool}"""
        if not self.started or self.finished:
            raise GameError("Radio opens when the game starts.")
        pid, _ = self._who(user_key)
        used = any(r.startswith(f"r{self.night + 1}-{pid}-") for r in self.radio_pending)
        return {"lines": [(k, t.replace("{a}", "…")) for k, t in RADIO_PHRASES.items()],
                "about": self.alias_list(user_key), "available": not used}

    @staticmethod
    def radio_needs_player(phrase):
        return "{a}" in RADIO_PHRASES.get(phrase, "")

    def radio(self, user_key, phrase, about=None):
        pid, _ = self._who(user_key)
        if not self.started or self.finished:
            raise GameError("Radio opens when the game starts.")
        if phrase not in RADIO_PHRASES:
            raise GameError("Pick one of the radio lines.")
        needs_player = "{a}" in RADIO_PHRASES[phrase]
        if needs_player and not about:
            raise GameError("Pick who it's about.")
        text = RADIO_PHRASES[phrase].format(a=self.players[self._pid_by_alias(about)].name if needs_player else "")
        if any(r.startswith(f"r{self.night + 1}-{pid}-") for r in self.radio_pending):
            raise GameError("One radio message a day. Yours goes out with the morning news.")
        ref = f"r{self.night + 1}-{pid}-{len(self.radio_pending)}"
        self.texts.put(ref, text)
        self._append({"type": "radio", "ref": ref, "night": self.night + 1})
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
        return (f"**{alias}**: 🥫 {p.rations} rations{' 🏴‍☠️ BANDIT' if p.bandit else ''}, 🛡️ {guards}"
                f"{', guarded tonight' if p.guard_until > self.night else ''}.\n"
                f"Secret goal: {objective_text(p.objective, self.rules, tgt)}.\nTonight: {tonight}.")

    def results(self, user_key):
        pid, _ = self._who(user_key)
        lines = self.last_private.get(pid)
        return "\n".join(lines) if lines else "Nothing to report yet."

    def quit(self, user_key):
        pid, alias = self._who(user_key)
        if pid in self.quit_ids:
            return "You've already left."
        self._append({"type": "quit", "pid": pid, "night": self.night + 1,
                      "outbox": self._intents(("news", f"{alias} has left the game. Their food goes with them.", None))})
        return "You've left the game. Thanks for playing."

    # ---------------- Game Master ----------------
    def gm_add_sims(self, n, rng=None):
        rng = rng or random.Random()
        return [self.join(f"sim:{len(self.joined)}", sim=True, rng=rng) for _ in range(n)]

    def gm_start(self, day_seconds, news_delay=5.0, now=None, events="off"):
        if events not in EVENT_MODES:
            raise GameError(f"events must be one of: {', '.join(EVENT_MODES)}.")
        if self.started:
            raise GameError("Already started.")
        if len(self.joined) < 2:
            raise GameError("Need at least 2 players.")
        now = self.clock() if now is None else now
        hand = deal([pid for pid, _, _, _ in self.joined], random.Random(night_seed(self.season_id, -1)))
        roster = [{"pid": pid, "alias": alias, "objective": hand[pid][0], "target": hand[pid][1]}
                  for pid, alias, _, _ in self.joined]
        msgs = [("news", f"🔥 The game has begun: {len(roster)} survivors, {self.rules.rounds} rounds. "
                         f"Check /status for your secret goal. Choose a move before each deadline.", None)]
        msgs += [(f"dm:{c['pid']}", "🔥 The game has begun. Use /status any time to see your rations and your "
                                    "secret goal.", None) for c in roster if c["pid"] not in self.sims]
        if events != "off":
            msgs[0] = ("news", msgs[0][1] + " 🌴 Wilderness events are on: luck, good and bad, can strike anyone.", None)
        self._append({"type": "start", "start_ts": now, "day_seconds": day_seconds, "news_delay": news_delay,
                      "events": events,
                      "roster": roster, "engine_version": ENGINE_VERSION, "season": self.season_id,
                      "rules": {**vars(self.rules), "players": len(roster)}, "outbox": self._intents(*msgs)})
        log.info("game started: %d players, day=%ss", len(roster), day_seconds)

    def gm_who_moved(self):
        """Who has chosen tonight (never anyone's rations)."""
        done = [p.name for pid, p in sorted(self.players.items()) if pid in self.moves and pid not in self.sims]
        waiting = [p.name for pid, p in sorted(self.players.items())
                   if pid not in self.moves and pid not in self.sims and pid not in self.quit_ids]
        return done, waiting

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

    def _resolve_due(self, night):
        rng = random.Random(night_seed(self.season_id, night) ^ 0x51A5)
        active = self._active()
        moves = {}
        for p in active:
            m = self.moves.get(p.pid)
            if m is not None and validate(active, p.pid, m, self.rules, night, frozenset(self.quit_ids)) is None:
                moves[p.pid] = m
            elif p.pid in self.sims:
                moves[p.pid] = sims.decide(p, self.personality[p.pid], active, self.rules, night, rng,
                                           frozenset(self.quit_ids)) or ("scavenge", None, 0, True)
            else:
                moves[p.pid] = ("scavenge", None, 0, True)      # missed the deadline (or the move went stale)
        before = {pid: (p.rations, p.bandit) for pid, p in self.players.items()}
        events = self._resolve(night, moves)
        private = {pid: private_lines(events, self.players[pid], before[pid])
                   for pid in moves if pid not in self.sims}
        self._append({"type": "night", "night": night, "seed": night_seed(self.season_id, night),
                      "moves": {str(k): list(v) for k, v in moves.items()}, "events": events,
                      "private": {str(k): v for k, v in private.items()}})
        log.info("night %d resolved: %d moves, %d events", night, len(moves), len(events))

    def _post_news(self, night):
        rec = self._night_record(night)
        lines = news_lines(rec["events"]) or ["🌙 A quiet night. Nobody lost anything."]
        label = night_label(self.schedule, night, closed=True)
        msgs = [("news", f"📰 **News: {label}**\n" + "\n".join(f"- {l}" for l in lines), None)]
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
            out.append(f"🕵️ EXPOSED: an investigator saw {e['thief']} rob {e['victim']}. {e['thief']} pays them {e['paid']}.")
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


def private_lines(events, p, before):
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
        elif t == "steal" and e["thief"] == me and e["target"] in idol:
            out.append(f"🗿 {e['target']} had a hidden idol. You got nothing.")
        elif t == "scavenge" and e["player"] == me:
            out.append(f"🥫 You scavenged and found {e['found']}.")
        elif t == "guard_up" and e["player"] == me:
            out.append(f"🛡️ You're on guard: protected tonight and through night {e['until_night']}.")
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
            out.append(f"🚨 Your guard caught {e['thief']} red-handed.")
        elif t == "investigate" and e["investigator"] == me:
            saw = e["saw_action"] + (f" ({e['saw_target']})" if e["saw_target"] else "")
            out.append(f"🔍 You watched {e['target']}: they chose {saw}.")
        elif t == "exposed" and e["investigator"] == me:
            out.append(f"🕵️ You exposed {e['thief']}; they paid you {e['paid']}.")
        elif t == "gift" and e["giver"] == me:
            out.append(f"🎁 You gave {e['receiver']} {e['amount']}.")
        elif t == "gift" and e["receiver"] == me:
            out.append(f"🎁 {e['giver']} secretly gave you {e['amount']}.")
        elif t == "became_bandit" and e["player"] == me:
            out.append("🏴‍☠️ You ran out of food. You're a bandit now: steal or investigate until you get back to 3.")
        elif t == "rejoined" and e["player"] == me:
            out.append("🎉 You've scraped together enough to rejoin the survivors.")
    out.append(f"🥫 You now have {p.rations} rations.")
    return out
