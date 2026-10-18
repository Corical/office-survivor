"""The game core: one game's state, rebuilt from its event log, with no delivery, no clock and no wording of its own.

Torch (bot/game.py, GameService) and the live Godot rooms (arena/, coming) both run on this, so a night resolves the
same way whoever delivers it. Truth is the event log (EventStore); who-is-who lives in IdentityStore, radio text in
TextStore. On load the log is folded back into state and every stored night is re-resolved from its moves and seed; a
mismatch stops the game rather than letting it run on a state it can't reproduce.

What a front end adds through hooks (each a no-op here):
  _on_start(rec)                       read its own fields of the start record (Torch: the day schedule)
  _apply_extra(rec, replay)            record types the core doesn't know (Torch: news, sent)
  _private_for(events, p, before, n)   what one player is told about night n, stored in the night record
  _quit_extra(alias)                   extra fields for a quit record (Torch: the #news line)
"""
import hashlib
import logging
import random
import time
from collections import Counter
from dataclasses import fields, replace

from engine import ENGINE_VERSION, Rules, resolve_night
from engine import events as wild
from engine.deal import deal
from engine.finish import finish
from engine.moves import legal_moves, validate

from . import sims
from .brain import SimBrain, SimSeat

log = logging.getLogger("torch.game")

# Radio is fixed phrases so nobody can be recognised by their writing style (owner, 17 Oct 2026).
RADIO_PHRASES = {
    "saw": "I saw {a} sneaking around last night.",
    "trust": "Don't trust {a}.",
    "lying": "{a} is lying about their rations.",
    "guarding": "{a} is guarding. Don't waste your night on them.",
    "easy": "{a} looks like an easy target.",
    "innocent": "{a} is innocent. Leave them alone.",
    "watch": "Someone should watch {a}'s back tonight.",
    "me": "I'm innocent. Leave me alone.",
}

EVENT_MODES = {   # /gm start events:... ; "gentle" = events round 2's kindest design (docs/sim/results/events_sweep2.md)
    "off": {},
    "gentle": {"events_per_night": 1.0, "events_bias": "top", "events_rats_relative": True},
}


def night_seed(seed_key, night):
    return int(hashlib.sha256(f"{seed_key}:{night}".encode()).hexdigest()[:16], 16)


class GameError(Exception):
    """A player-facing refusal: the text is safe to show to the player who asked."""


class _EventCtx:
    """What engine/events.py needs from a game: the active players, rules, night, a seed, and two writers that turn
    every event and ration change into a record in the night's event list."""

    def __init__(self, players, rules, night, seed, emit):
        self.players, self.r, self.night, self.seed = players, rules, night, seed
        self.event_tally = Counter()
        self.L = emit
        self.ledger = lambda p, delta, reason, balance, detail="": emit(
            "ration", player=p.name, delta=delta, reason=reason, balance=balance, detail=detail)


class GameCore:
    def __init__(self, rules: Rules, store, identity, texts, aliases, seed_key, clock=time.time, avoid_aliases=()):
        """`seed_key` drives every die of the game. It must be secret from the players wherever they could learn it
        (Torch: the season id, never shown; a live room: a server-only salt, never the join code)."""
        self.rules, self.store, self.identity, self.texts = rules, store, identity, texts
        self.aliases, self.seed_key, self.clock = list(aliases), seed_key, clock
        self.avoid_aliases = set(avoid_aliases)    # last season's aliases: handed out only when nothing else is free
        self._reset()
        self._load()

    # ---------------- state from the log ----------------
    def _reset(self):
        self.players = {}          # pid -> PlayerState (after start)
        self.joined = []           # [(pid, alias, sim, personality)] before start
        self.started = False
        self.finished = False
        self.night = 0             # last resolved night
        self.moves = {}            # pid -> move for night+1
        self.radio_pending = []    # text refs to post with the next news
        self.quit_ids = set()
        self.event_counts = Counter()  # wilderness events so far this game, for the no-repeat story decks
        self.events_mode, self.ranges = "off", False
        self.personality = {}      # pid -> personality for sims
        self.sims = set()
        self.last_private = {}     # pid -> what that player was told about the last resolved night
        self.brain = None          # the sims' beliefs (bot/brain.py): rebuilt from the log, never saved

    def _load(self):
        for rec in self.store.load():
            self._apply(rec, replay=True)
        self._loaded()

    def _loaded(self):
        log.info("state rebuilt: started=%s night=%d players=%d", self.started, self.night,
                 len(self.players) or len(self.joined))

    def _append(self, rec):
        self.store.append(rec)
        self._apply(rec, replay=False)

    def _apply(self, rec, replay):
        t = rec["type"]
        if t == "join":
            self.joined.append((rec["pid"], rec["alias"], rec.get("sim", False), rec.get("personality")))
            if rec.get("sim"):
                self.sims.add(rec["pid"])
                self.personality[rec["pid"]] = rec["personality"]
        elif t == "start":
            self.started = True
            self._on_start(rec)
            # A game is played and replayed under the rules it STARTED with, never today's: a rule change between
            # restarts must not rewrite (or refuse to load) a game already in progress. Fields newer than the log
            # take their defaults, which is what that game ran on.
            known = {f.name for f in fields(Rules)}
            self.rules = Rules(**{k: v for k, v in rec.get("rules", {}).items() if k in known}) \
                if rec.get("rules") else self.rules
            self.events_mode = rec.get("events", "off")            # older logs have no key: events off
            self.ranges = rec.get("ranges", False)                  # morning ration ranges
            self.rules = replace(self.rules, **EVENT_MODES[self.events_mode])
            for c in rec["roster"]:
                self.players[c["pid"]] = SimSeat(pid=c["pid"], name=c["alias"], rations=self.rules.start_rations,
                                                 objective=c["objective"], obj_target=c["target"],
                                                 arch=self.personality.get(c["pid"], ""))
            if self.sims:
                self.brain = SimBrain(self.rules, self.players, night_seed(self.seed_key, -2), self.ranges)
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
        elif t == "finish":
            if replay:
                self._run_finish(check=rec["events"])
            self.finished = True
        else:
            self._apply_extra(rec, replay)

    # ---------------- hooks for a front end ----------------
    def _on_start(self, rec):
        pass

    def _apply_extra(self, rec, replay):
        pass

    def _private_for(self, events, p, before, night):
        return []

    def _quit_extra(self, alias):
        return {}

    # ---------------- resolution ----------------
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
            ctx = _EventCtx(self._active(), self.rules, night, self.seed_key, emit)
            if self.brain:
                ctx.public_delta = self.brain.public_delta     # public event finds and losses reach the sims' beliefs
            ctx.event_tally.update(self.event_counts)          # earlier nights count, so story decks don't restart
            flags, lines = wild.run_night_events(ctx, wild.rng_for(self.seed_key, night))
            public = [e for e in events if e["type"] == "event" and e["visibility"] == "public"]
            for e, line in zip(public, lines):   # each public event wrote one news line, in the same order
                e["line"] = line
        res = resolve_night(self._active(), moves, self.rules, random.Random(night_seed(self.seed_key, night)), night,
                            emit=emit, flags=flags, obs=self.brain.observer if self.brain else None)
        if self.brain:       # live and replayed nights both pass here exactly once: that is how a restart rebuilds it
            self.brain.end_night(night, res)
        return events

    def _run_finish(self, check=None):
        events = []
        finish(list(self.players.values()), self.rules, random.Random(night_seed(self.seed_key, 0)),
               emit=lambda _t, **f: events.append({"type": _t, **f}), quit_ids=frozenset(self.quit_ids))
        if check is not None and events != check:
            raise RuntimeError("the final scoring does not replay")
        return events

    def _sim_radio(self, night):
        """The sims' radio for day `night`, decided at the deadline from what each knew then, so it goes out with this
        morning's news like any player's. Its own dice (seed and night), so it never moves a sim's choice. Safe to
        run again after a crash: every sim is decided again identically and one that already has a line today is skipped."""
        rng = random.Random(night_seed(self.seed_key, night) ^ 0x7AD10)
        quit_ids = frozenset(self.quit_ids)
        for p in self._active():
            if p.pid not in self.sims:
                continue
            pick = self.brain.radio(p, night, rng, quit_ids)
            if pick and not any(r.startswith(f"r{night}-{p.pid}-") for r in self.radio_pending):
                self._post_radio(p.pid, pick[0], pick[1])

    def _resolve_due(self, night):
        rng = random.Random(night_seed(self.seed_key, night) ^ 0x51A5)
        active = self._active()
        moves = {}
        for p in active:
            m = self.moves.get(p.pid)
            if m is not None and validate(active, p.pid, m, self.rules, night, frozenset(self.quit_ids)) is None:
                moves[p.pid] = m
            elif p.pid in self.sims:
                moves[p.pid] = self.brain.decide(p, active, night, rng, self.quit_ids)
            else:
                moves[p.pid] = ("scavenge", None, 0, True)      # missed the deadline (or the move went stale)
        if self.brain:
            self._sim_radio(night)          # before the night record: a crash between the two is repaired on the retry
        before = {pid: (p.rations, p.bandit) for pid, p in self.players.items()}
        events = self._resolve(night, moves)
        private = {pid: self._private_for(events, self.players[pid], before[pid], night)
                   for pid in moves if pid not in self.sims}
        self._append({"type": "night", "night": night, "seed": night_seed(self.seed_key, night),
                      "moves": {str(k): list(v) for k, v in moves.items()}, "events": events,
                      "private": {str(k): v for k, v in private.items()}})
        log.info("night %d resolved: %d moves, %d events", night, len(moves), len(events))

    # ---------------- lookups ----------------
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

    def alias_list(self, user_key=None):
        """Aliases still in the game, alphabetical (never join order: that would hint at who is who), without the
        asking player's own alias: you can't target yourself, so you shouldn't be offered."""
        me = (self.identity.get(user_key) or {}).get("pid") if user_key else None
        return sorted(p.name for pid, p in self.players.items() if pid not in self.quit_ids and pid != me)

    def legal_for(self, pid):
        """The legal moves for `pid` tonight: ({kind: [target aliases, alphabetical]}, [gift amounts])."""
        night = self.night + 1
        legal = legal_moves(self._active(), pid, self.rules, night, frozenset(self.quit_ids))
        amounts = legal.pop("gift_amounts", [])
        return {k: sorted(self.players[t].name for t in v) for k, v in legal.items()}, amounts

    def radio_used(self, pid, night=None):
        night = self.night + 1 if night is None else night
        return any(r.startswith(f"r{night}-{pid}-") for r in self.radio_pending)

    # ---------------- actions ----------------
    def add_player(self, user_key, sim=False, rng=None, personality=None):
        """Seat a new player with a fresh secret alias; returns the alias."""
        if self.started:
            raise GameError("The game has already started; joining is closed.")
        taken = {a for _, a, _, _ in self.joined}
        free = [a for a in self.aliases if a not in taken]
        free = [a for a in free if a not in self.avoid_aliases] or free      # a fresh name if there is one
        if not free:
            raise GameError("The game is full.")
        rng = rng or random.Random()
        alias = rng.choice(free)
        pid = len(self.joined)
        personality = (personality or sims.pick_personality(rng)) if sim else None
        self.identity.put(user_key, pid, alias, sim=sim)
        self._append({"type": "join", "pid": pid, "alias": alias, "sim": sim, **({"personality": personality} if sim else {})})
        log.info("join pid=%d sim=%s", pid, sim)
        return alias

    def join(self, user_key, sim=False, rng=None, personality=None):
        return self.add_player(user_key, sim=sim, rng=rng, personality=personality)

    def record_move(self, pid, kind, target_alias=None, amount=0, at=None):
        """Validate and log tonight's move for `pid` (the last valid one counts). Returns (night, move)."""
        night = self.night + 1
        target = self._pid_by_alias(target_alias) if target_alias else None
        move = (kind, target, int(amount or 0), False)
        why = validate(self._active(), pid, move, self.rules, night, frozenset(self.quit_ids))
        if why:
            raise GameError(why)
        self._append({"type": "move", "night": night, "pid": pid, "move": list(move), "at": at})
        log.info("move night=%d pid=%d kind=%s", night, pid, kind)
        return night, move

    @staticmethod
    def radio_needs_player(phrase):
        return "{a}" in RADIO_PHRASES.get(phrase, "")

    def record_radio(self, user_key, phrase, about=None):
        """Validate and store one anonymous radio line for the next news."""
        pid, _ = self._who(user_key)
        if not self.started or self.finished:
            raise GameError("Radio opens when the game starts.")
        if phrase not in RADIO_PHRASES:
            raise GameError("Pick one of the radio lines.")
        needs_player = "{a}" in RADIO_PHRASES[phrase]
        if needs_player and not about:
            raise GameError("Pick who it's about.")
        about_pid = self._pid_by_alias(about) if needs_player else None
        if self.radio_used(pid):
            raise GameError("One radio message a day. Yours goes out with the morning news.")
        self._post_radio(pid, phrase, about_pid)

    def _post_radio(self, pid, phrase, about_pid):
        """The one way a radio line is stored, for players and sims alike: text to the text store, a record in the
        log, posted with the next morning news."""
        text = RADIO_PHRASES[phrase].format(a=self.players[about_pid].name if about_pid is not None else "")
        ref = f"r{self.night + 1}-{pid}-{len(self.radio_pending)}"
        self.texts.put(ref, text)
        self._append({"type": "radio", "ref": ref, "night": self.night + 1})

    def leave(self, user_key):
        """Leave the game for good. Returns False if this player had already left."""
        pid, alias = self._who(user_key)
        if pid in self.quit_ids:
            return False
        self._append({"type": "quit", "pid": pid, "night": self.night + 1, **self._quit_extra(alias)})
        return True

    def gm_add_sims(self, n, rng=None, cast="balanced"):
        """Add n sims. cast "balanced": one of each of the eight personalities before any repeats (continuing the cycle
        across batches); "office": each drawn from the simulator's office mix (a saint is only 8%)."""
        if cast not in sims.CASTS:
            raise ValueError(f"cast must be one of {sims.CASTS}, not {cast!r}")
        rng = rng or random.Random()
        out = []
        for _ in range(n):
            pick = sims.balanced_pick(rng, self.personality.values()) if cast == "balanced" else None
            out.append(self.join(f"sim:{len(self.joined)}", sim=True, rng=rng, personality=pick))
        return out

    def start_game(self, events="off", ranges=False, extra=None):
        """Deal the goals and log the start record (plus a front end's own `extra` fields). Returns the roster."""
        if events not in EVENT_MODES:
            raise GameError(f"events must be one of: {', '.join(EVENT_MODES)}.")
        if self.started:
            raise GameError("Already started.")
        if len(self.joined) < 2:
            raise GameError("Need at least 2 players.")
        hand = deal([pid for pid, _, _, _ in self.joined], random.Random(night_seed(self.seed_key, -1)))
        roster = [{"pid": pid, "alias": alias, "objective": hand[pid][0], "target": hand[pid][1]}
                  for pid, alias, _, _ in self.joined]
        extra = extra(roster) if callable(extra) else dict(extra or {})
        self._append({**extra, "type": "start", "events": events, "ranges": bool(ranges), "roster": roster,
                      "engine_version": ENGINE_VERSION, "rules": {**vars(self.rules), "players": len(roster)}})
        log.info("game started: %d players", len(roster))
        return roster

    def gm_who_moved(self):
        """Who has chosen tonight (never anyone's rations). Sims are left out: they decide at the deadline."""
        done = [p.name for pid, p in sorted(self.players.items()) if pid in self.moves and pid not in self.sims]
        waiting = [p.name for pid, p in sorted(self.players.items())
                   if pid not in self.moves and pid not in self.sims and pid not in self.quit_ids]
        return done, waiting
