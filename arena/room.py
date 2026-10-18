"""A live room: Survivors played in timed rounds with lock-in and early advance, on the shared game core.

Round life (all of it in the log, so a restart picks up exactly where it was):
  round_open {round, opened_at, deadline}      moves open; the deadline is stored, never recomputed
  move / lock {round, pid}                     pick freely; Lock makes it final (Arena-only rule, owner 18 Oct 2026)
  round_closed {round, reason, reveal_until}   reason: all_locked | timeout
  night                                        the core resolves it (one atomic record, as in Torch)
  continue {round, pid}                        a human is done reading; the reveal ends early when all are
  ... next round_open, or the finish record after the last round

Early advance: a round closes as soon as every *connected* human has locked. A human who has been disconnected for
longer than `grace` stops blocking. With no human connected the round waits for its timer, so an empty room cannot
race through the game. Bots lock after a seeded random delay, logged like a human's lock; when the last human locks,
any bot still open locks just before the close (a small timing hint remains: see docs/ARENA.md).

The dice come from `seed_key`, which the server keeps secret (never the join code).
"""
import logging
import random
from dataclasses import dataclass

from bot.core import GameCore, GameError, night_seed

from .lines import private_codes

log = logging.getLogger("arena.room")


@dataclass(frozen=True)
class RoomSettings:
    """Owner figures: 4 seats, 10 rounds (the rules), 180 s rounds. The rest are chosen defaults, not derived."""
    seats: int = 4
    timer: float = 180.0          # owner, 18 Oct 2026
    reveal: float = 20.0          # chosen default
    grace: float = 30.0           # chosen default: a disconnected player stops blocking early advance after this
    bot_lock_min: float = 5.0     # chosen default
    bot_lock_max: float = 60.0    # chosen default (capped below the timer)
    events: str = "gentle"
    ranges: bool = True


class FakeScheduler:
    """A clock and timers you drive by hand (tests). Same interface as AsyncioScheduler."""

    def __init__(self, t=0.0):
        self.t, self._q, self._n = float(t), [], 0

    def now(self):
        return self.t

    def call_at(self, when, fn):
        self._n += 1
        h = [when, self._n, fn, True]
        self._q.append(h)
        return h

    def cancel(self, h):
        if h:
            h[3] = False

    def advance(self, to):
        """Run every live timer due up to `to`, in time order (ties: the order they were set), then set the clock."""
        while True:
            due = sorted((h for h in self._q if h[3] and h[0] <= to), key=lambda h: (h[0], h[1]))
            if not due:
                break
            h = due[0]
            h[3] = False
            self.t = max(self.t, h[0])
            h[2]()
        self.t = max(self.t, to)
        self._q = [h for h in self._q if h[3]]


class RoomGame(GameCore):
    def __init__(self, rules, store, identity, texts, aliases, seed_key, scheduler, settings=RoomSettings()):
        self.sched, self.settings = scheduler, settings
        self.present = set()          # pids with a live connection (transport state, never logged)
        self.gone_since = {}          # pid -> when they disconnected
        self._timers = []
        self.listeners = []           # fn(event_name) called after any state change (the server pushes views)
        super().__init__(rules, store, identity, texts, aliases, seed_key, clock=scheduler.now)
        seats = {j[0]: j[1] for j in self.joined}
        for key, ident in list(self.identity.data.items()):      # a crash between the log line and the identity write
            if not ident.get("sim") and seats.get(ident["pid"]) != ident["alias"]:
                self.identity.remove(key)
        self._rearm()

    # ---------------- state from the log ----------------
    def _reset(self):
        super()._reset()
        self.round = 0                # the round whose round_open is the latest
        self.opened_at = self.deadline = None
        self.locked = set()           # pids locked in the open round
        self.closed = 0               # the latest round with a round_closed
        self.close_reason = None
        self.reveal_until = None
        self.continued = set()

    def _on_start(self, rec):
        a = rec.get("arena", {})
        self.settings = RoomSettings(**{**vars(self.settings), **a}) if a else self.settings

    def _apply_extra(self, rec, replay):
        t = rec["type"]
        if t == "left_lobby":
            self.joined = [j for j in self.joined if j[0] != rec["pid"]]     # the pid is free again: the next join takes it
        elif t == "round_open":
            self.round, self.opened_at, self.deadline = rec["round"], rec["opened_at"], rec["deadline"]
            self.locked, self.continued, self.close_reason, self.reveal_until = set(), set(), None, None
        elif t == "lock" and rec["round"] == self.round:
            self.locked.add(rec["pid"])
        elif t == "round_closed":
            self.closed, self.close_reason, self.reveal_until = rec["round"], rec["reason"], rec["reveal_until"]
        elif t == "continue" and rec["round"] == self.closed:
            self.continued.add(rec["pid"])

    def _private_for(self, events, p, before, night):
        return private_codes(events, p, before, night, self.rules.guard_nights)

    # ---------------- phase ----------------
    @property
    def phase(self):
        if self.finished:
            return "end"
        if not self.started:
            return "lobby"
        if self.round and self.closed < self.round:
            return "round"
        return "reveal"

    def night_record(self, n):
        return next(r for r in self.store.load() if r["type"] == "night" and r["night"] == n)

    def humans(self):
        return [p.pid for p in self._active() if p.pid not in self.sims]

    def _changed(self, what):
        for fn in list(self.listeners):
            fn(what)

    # ---------------- lobby ----------------
    def add_human(self, user_key):
        if len(self.joined) >= self.settings.seats:
            raise GameError("The room is full.")
        # aliases come from the room's secret dice too: unpredictable to players, reproducible for the server
        return self.add_player(user_key, rng=random.Random(night_seed(self.seed_key, -4) + len(self.joined)))

    def start(self):
        if self.started:
            raise GameError("Already started.")
        if not self.joined:
            raise GameError("Need at least one player.")
        free = self.settings.seats - len(self.joined)
        if free > 0:
            self.gm_add_sims(free, rng=random.Random(night_seed(self.seed_key, -3)), cast="balanced")
        self.start_game(events=self.settings.events, ranges=self.settings.ranges,
                        extra={"arena": {k: v for k, v in vars(self.settings).items()}})
        self._open_round(1)

    # ---------------- rounds ----------------
    def _open_round(self, n):
        now = self.sched.now()
        self._append({"type": "round_open", "round": n, "opened_at": now, "deadline": now + self.settings.timer})
        log.info("round %d open, deadline in %ss", n, self.settings.timer)
        self._arm_round()
        self._changed("round_open")

    def _bot_lock_times(self, n):
        """When each bot locks in round n: seeded, so a restart puts them back at the same moments."""
        rng = random.Random(night_seed(self.seed_key, n) ^ 0xB07)
        hi = min(self.settings.bot_lock_max, self.settings.timer * 0.9)
        lo = min(self.settings.bot_lock_min, hi)
        return {pid: self.opened_at + rng.uniform(lo, hi) for pid in sorted(self.sims) if pid not in self.quit_ids}

    def _clear_timers(self):
        for h in self._timers:
            self.sched.cancel(h)
        self._timers = []

    def _arm_round(self):
        self._clear_timers()
        n = self.round
        self._timers.append(self.sched.call_at(self.deadline, lambda: self._timeout(n)))
        for pid, at in self._bot_lock_times(n).items():
            if pid not in self.locked:
                self._timers.append(self.sched.call_at(at, lambda pid=pid: self._bot_lock(n, pid)))

    def _bot_lock(self, n, pid):
        if self.phase != "round" or self.round != n or pid in self.locked:
            return                                   # a stale timer: that round is gone
        self._append({"type": "lock", "round": n, "pid": pid})
        self._changed("lock")
        self._check_advance()

    def _timeout(self, n):
        if self.phase != "round" or self.round != n:
            return
        self._close(n, "timeout")

    def pick(self, pid, kind, target=None, amount=0):
        if self.phase != "round":
            raise GameError("There's no round open right now.")
        if pid in self.quit_ids:
            raise GameError("You're not in this game.")
        if pid in self.locked:
            raise GameError("You've locked in. Your move is final this round.")
        self.record_move(pid, kind, target, amount, at=self.sched.now())
        self._changed("pick")

    def lock(self, pid):
        if self.phase != "round":
            raise GameError("There's no round open right now.")
        if pid in self.quit_ids:
            raise GameError("You're not in this game.")
        if pid in self.locked:
            raise GameError("You've already locked in.")
        if pid not in self.moves:
            raise GameError("Pick a move before you lock in.")
        self._append({"type": "lock", "round": self.round, "pid": pid})
        self._changed("lock")
        self._check_advance()

    def _blocking(self):
        """Humans the round still waits for: connected and not locked, or disconnected within the grace period."""
        now = self.sched.now()
        out = []
        for pid in self.humans():
            if pid in self.locked:
                continue
            if pid in self.present or now - self.gone_since.get(pid, -1e18) < self.settings.grace:
                out.append(pid)
        return out

    def _check_advance(self):
        if self.phase != "round":
            return
        if not (self.present & set(self.humans())):
            return                                   # nobody here: wait for the timer
        if self._blocking():
            return
        n = self.round
        for pid in sorted(self.sims):                # bots still open lock just before the close
            if pid not in self.locked and pid not in self.quit_ids:
                self._append({"type": "lock", "round": n, "pid": pid})
        self._close(n, "all_locked")

    def _close(self, n, reason):
        self._clear_timers()
        until = self.sched.now() + self.settings.reveal
        self._append({"type": "round_closed", "round": n, "reason": reason, "reveal_until": until})
        log.info("round %d closed: %s", n, reason)
        self._resolve_due(n)
        self._arm_reveal()
        self._changed("round_closed")

    # ---------------- reveal ----------------
    def _arm_reveal(self):
        self._clear_timers()
        n = self.closed
        self._timers.append(self.sched.call_at(self.reveal_until, lambda: self._end_reveal(n)))

    def continue_(self, pid):
        if self.phase != "reveal":
            raise GameError("Nothing to continue from.")
        if pid in self.continued:
            return
        self._append({"type": "continue", "round": self.closed, "pid": pid})
        here = self.present & set(self.humans())
        if here and here <= self.continued:
            self._end_reveal(self.closed)
        else:
            self._changed("continue")

    def _end_reveal(self, n):
        if self.phase != "reveal" or self.closed != n:
            return
        self._clear_timers()
        if n >= self.rules.rounds:
            self._append({"type": "finish", "events": self._run_finish()})
            log.info("game finished")
            self._changed("finish")
        else:
            self._open_round(n + 1)

    # ---------------- presence and leaving ----------------
    def connect(self, pid):
        self.present.add(pid)
        self.gone_since.pop(pid, None)

    def disconnect(self, pid):
        self.present.discard(pid)
        self.gone_since[pid] = self.sched.now()
        if self.phase == "round":                    # after the grace this player stops blocking: look again then
            n = self.round
            self._timers.append(self.sched.call_at(self.sched.now() + self.settings.grace,
                                                   lambda: self.round == n and self._check_advance()))
            self._check_advance()

    def leave_seat(self, user_key):
        pid, _ = self._who(user_key)
        if not self.started:
            raise GameError("You can only leave a game that has started.")
        if self.leave(user_key):
            self.present.discard(pid)
            self._changed("quit")
            self._check_advance()

    def leave_lobby(self, user_key, kicked=False):
        """Give the seat back before the game starts: the seat is free for someone else and the token is dead.
        `kicked` only records that the host removed them (the log tells the two apart); the effect is the same."""
        pid, _ = self._who(user_key)
        if self.started:
            raise GameError("The game has started; use leave to quit it for good.")
        self._append({"type": "left_lobby", "pid": pid, **({"kicked": True} if kicked else {})})
        self.identity.remove(user_key)
        self.present.discard(pid)
        self.gone_since.pop(pid, None)
        self._changed("left_lobby")

    # ---------------- restart ----------------
    def _rearm(self):
        """After loading the log: put the timers back, and finish anything a crash interrupted."""
        if not self.started or self.finished:
            return
        if self.round == 0:                          # crashed between the start record and round 1
            self._open_round(1)
            return
        if self.closed > self.night:                 # closed but never resolved: resolve now (deterministic)
            self._resolve_due(self.closed)
        if self.phase == "round":
            if self.sched.now() >= self.deadline:
                self._close(self.round, "timeout")
            else:
                self._arm_round()
        elif self.phase == "reveal":
            if self.sched.now() >= self.reveal_until:
                self._end_reveal(self.closed)
            else:
                self._arm_reveal()
