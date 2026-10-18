"""The Arena server: rooms over WebSocket, one JSON object per frame (protocol: docs/arena/GODOT_FOUNDATION.md).

    python -m arena.server --data DIR [--host 127.0.0.1] [--port 8765]

Each room lives in DIR/rooms/<CODE>/: room.json (code and the secret dice salt; never sent to a client), log.jsonl
(the event log), identity.json (seat keys: the SHA-256 of each seat token, never the token itself) and texts.json.
On start every room is loaded from disk and its timers re-armed. The server is the only writer; one asyncio loop runs
everything, so a room never sees two actions at once.

A seat is known from its connection only: no message carries a seat or player id. A second connection with the same
token takes the seat over (newest wins, the old one is told why); takeovers are rate-limited.
"""
import argparse
import asyncio
import hashlib
import json
import logging
import os
import secrets
import shutil
import time
import unicodedata

from bot.core import GameError
from bot.store import IdentityStore, JsonlEventStore, TextStore
from bot.config import game_settings

from . import views
from .room import RoomGame, RoomSettings

log = logging.getLogger("arena.server")

PROTO, MIN_PROTO = 1, 1
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"        # no I or O: read aloud across a room without confusion
MAX_MESSAGE = 4096                               # bytes; a real message is under 200
TAKEOVERS_PER_MINUTE = 5                         # chosen default
NAME_MAX = 24                                    # characters of a camp's label (the client's request)
LIST_INTERVAL = 1.0                              # seconds between list_rooms from one connection (the client's suggestion)
FEATURES = ["list_rooms"]                        # advertised in hello_ok so a client need not guess
# WebSocket close codes the client reads (the 4000s are ours). Godot's WebSocketPeer drops a message that arrives in the
# same poll as the close frame, so every terminal message is followed by a short pause and only then the close.
# 4001 (seat gone) is NOT used: a dead seat is a plain error and the connection stays open to create or join a room.
CLOSE_UPGRADE_REQUIRED = 4002
CLOSE_TAKEN_OVER = 4003
CLOSE_KICKED = 4004
CLOSE_PAUSE = 0.25                              # chosen default (seconds)


class Coded(GameError):
    """A refusal with its own error code, so a client can tell "forget your seat" from "that move is not allowed"."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _game():
    """The official rules and alias pool, from docs/game.json (the same reader as Torch)."""
    rules, aliases, _ = game_settings()
    return rules, aliases


class AsyncioScheduler:
    """Wall-clock time and asyncio timers, behind the same interface as FakeScheduler."""

    def __init__(self, loop=None):
        self.loop = loop

    def now(self):
        return time.time()

    def call_at(self, when, fn):
        loop = self.loop or asyncio.get_event_loop()
        return loop.call_later(max(0.0, when - time.time()), fn)

    def cancel(self, h):
        if h:
            h.cancel()


def token_key(token):
    return "t:" + hashlib.sha256(token.encode()).hexdigest()


def clean_name(raw):
    """A camp label that is safe to show: text only, no control or invisible characters, one line, NAME_MAX long.
    Anything that is not a string becomes empty (no label). Lone surrogates are dropped too: they cannot be sent."""
    if not isinstance(raw, str):
        return ""
    spaced = "".join(" " if c.isspace() else c for c in raw)
    kept = "".join(c for c in spaced if unicodedata.category(c)[0] != "C")
    return " ".join(kept.split())[:NAME_MAX].strip()


class Room:
    """One room on disk plus its live connections."""

    def __init__(self, code, path, scheduler, settings, salt=None, visibility="public", name=""):
        self.code, self.path = code, path
        os.makedirs(path, exist_ok=True)
        meta = os.path.join(path, "room.json")
        if os.path.exists(meta):
            with open(meta, encoding="utf-8") as f:
                info = json.load(f)
            salt, self.created = info["salt"], info.get("created", os.path.getmtime(meta))
            self.visibility, self.name = info.get("visibility", "public"), clean_name(info.get("name", ""))
        else:
            salt = salt or secrets.token_hex(16)
            self.created, self.visibility, self.name = time.time(), visibility, name
            with open(meta, "w", encoding="utf-8") as f:
                json.dump({"code": code, "salt": salt, "created": self.created, "visibility": visibility,
                           "name": name}, f)
            try:
                os.chmod(meta, 0o600)
            except OSError:
                pass
        self.identity = IdentityStore(os.path.join(path, "identity.json"))
        rules, aliases = _game()
        self.game = RoomGame(rules, JsonlEventStore(os.path.join(path, "log.jsonl")), self.identity,
                             TextStore(os.path.join(path, "texts.json")), aliases, salt, scheduler, settings)
        self.conns = {}                  # pid -> websocket
        self.takeovers = {}              # pid -> [times]
        self.game.listeners.append(self._on_change)

    def _on_change(self, what):
        try:
            asyncio.get_running_loop()
        except RuntimeError:             # loading or a tool outside the server loop: nobody to push to
            return
        asyncio.ensure_future(self.push_all())

    def host_pid(self):
        """The lowest connected human seat runs the lobby (so a lost host is replaced by the next one)."""
        here = sorted(p for p in self.conns)
        return here[0] if here else None

    def message_for(self, pid):
        if self.game.phase == "lobby":
            return views.lobby(self.game, pid, self.code, pid == self.host_pid())
        return views.view_for(self.game, pid)

    async def push(self, pid):
        ws = self.conns.get(pid)
        if ws is not None:
            try:
                await ws.send(json.dumps(self.message_for(pid), ensure_ascii=False))
            except Exception as e:           # a dead socket is cleaned up by its own handler
                log.info("push to room=%s failed: %s", self.code, type(e).__name__)

    async def push_all(self):
        for pid in list(self.conns):
            await self.push(pid)


class Server:
    def __init__(self, data_dir, settings=RoomSettings(), scheduler=None, max_rooms=20):
        self.data, self.settings, self.max_rooms = data_dir, settings, max_rooms
        self.sched = scheduler or AsyncioScheduler()
        self.rooms = {}                 # code -> Room
        self.by_token = {}              # token key -> code
        self.list_at = {}               # connection -> when it last asked for the room list

    def open_rooms(self):
        """Camps a stranger could still join: public, still in the lobby, a seat free, someone connected. Newest first.
        No aliases, no seat order: the same rule as the lobby message."""
        now = time.time()
        found = []
        for room in self.rooms.values():
            g = room.game
            if (room.visibility != "public" or g.started or room.host_pid() is None
                    or len(g.joined) >= g.settings.seats):
                continue
            found.append((room.created, room.code, {"code": room.code, "seats_taken": len(g.joined),
                                                    "seats_total": g.settings.seats,
                                                    "age_s": max(0, int(now - room.created)), "name": room.name}))
        found.sort(key=lambda f: (-f[0], f[1]))
        return [f[2] for f in found[:self.max_rooms]]

    def _drop_room(self, room):
        """Delete a lobby that everyone left (nothing has been played, so nothing is lost)."""
        self.rooms.pop(room.code, None)
        for key in [k for k, c in self.by_token.items() if c == room.code]:
            del self.by_token[key]
        shutil.rmtree(room.path, ignore_errors=True)
        log.info("room %s was left empty in the lobby and deleted", room.code)

    def load(self):
        base = os.path.join(self.data, "rooms")
        os.makedirs(base, exist_ok=True)
        for code in sorted(os.listdir(base)):
            try:
                room = Room(code, os.path.join(base, code), self.sched, self.settings)
            except Exception:
                log.exception("room %s does not load; quarantined, other rooms keep running", code)
                continue
            self.rooms[code] = room
            for key in room.identity.data:
                if key.startswith("t:"):
                    self.by_token[key] = code
        log.info("loaded %d rooms", len(self.rooms))

    def _new_code(self):
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
            if code not in self.rooms:
                return code

    # ---------------- one connection ----------------
    async def handle(self, ws):
        seat = None                     # (room, pid) once seated
        try:
            if not await self._hello(ws):
                return
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    if not isinstance(msg, dict) or not isinstance(msg.get("t"), str):
                        raise ValueError
                except ValueError:
                    await self._error(ws, "bad_message", "Messages are JSON objects with a \"t\".")
                    continue
                if seat and seat[0].conns.get(seat[1]) is not ws:
                    continue            # the seat moved to another device: this connection is only waiting to be closed
                try:
                    seat = await self._dispatch(ws, msg, seat)
                except GameError as e:
                    await self._error(ws, getattr(e, "code", "refused"), str(e))
                except Exception:
                    log.exception("message %s failed", msg.get("t"))
                    await self._error(ws, "server_error", "Something went wrong on the server.")
        except Exception as e:
            from websockets.exceptions import ConnectionClosed
            if not isinstance(e, ConnectionClosed):
                raise
            log.info("connection closed: %s", e)            # a dropped phone, or a frame over the size limit
        finally:
            self.list_at.pop(ws, None)
            if seat:
                room, pid = seat
                if room.conns.get(pid) is ws:
                    del room.conns[pid]
                    room.game.disconnect(pid)
                    await room.push_all()

    async def _hello(self, ws):
        try:
            msg = json.loads(await ws.recv())
        except Exception:
            return False
        if not isinstance(msg, dict) or msg.get("t") != "hello":
            await self._error(ws, "hello_first", "Send hello first.")
            return False
        proto = msg.get("proto")
        if not isinstance(proto, int) or proto < MIN_PROTO:
            await ws.send(json.dumps({"t": "upgrade_required", "min_proto": MIN_PROTO,
                                      "message": "Please update the app to play."}))
            await self._close_after_pause(ws, CLOSE_UPGRADE_REQUIRED, "upgrade_required")
            return False
        await ws.send(json.dumps({"t": "hello_ok", "proto": PROTO, "features": FEATURES}))
        return True

    async def _error(self, ws, code, message):
        await ws.send(json.dumps({"t": "error", "code": code, "message": message}, ensure_ascii=False))

    async def _close_after_pause(self, ws, code, reason):
        """Close with our code once the client has had a poll or two to read the message sent just before."""
        try:
            await asyncio.sleep(CLOSE_PAUSE)
            await ws.close(code, reason)
        except Exception:                   # already gone
            pass

    async def _seat(self, ws, room, pid, token):
        old = room.conns.get(pid)
        if old is not None and old is not ws:
            now = time.time()
            recent = [t for t in room.takeovers.get(pid, []) if now - t < 60]
            if len(recent) >= TAKEOVERS_PER_MINUTE:
                raise GameError("Too many reconnects; wait a minute.")
            room.takeovers[pid] = recent + [now]
            room.conns[pid] = ws            # from here the old connection no longer holds the seat (see handle)
            try:
                await self._error(old, "taken_over", "This seat was opened on another device.")
            except Exception:
                pass
            asyncio.ensure_future(self._close_after_pause(old, CLOSE_TAKEN_OVER, "taken_over"))
        room.conns[pid] = ws
        room.game.connect(pid)
        alias = next(a for p, a, _, _ in room.game.joined if p == pid)      # pids have gaps once a seat is given back
        await ws.send(json.dumps({"t": "seat", "token": token, "room_code": room.code, "alias": alias,
                                  "host": pid == room.host_pid()}, ensure_ascii=False))
        await room.push_all()
        return room, pid

    async def _dispatch(self, ws, msg, seat):
        t = msg["t"]
        if t == "list_rooms":
            now = time.time()
            if now - self.list_at.get(ws, -LIST_INTERVAL) < LIST_INTERVAL:
                raise Coded("rate_limited", "Too many room lists; wait a second.")
            self.list_at[ws] = now
            await ws.send(json.dumps({"t": "rooms", "rooms": self.open_rooms()}, ensure_ascii=False))
            return seat
        if t == "create_room":
            if seat:
                raise GameError("You're already in a room.")
            visibility = msg.get("visibility", "public")
            if visibility not in ("public", "private"):         # strict: a typo must not publish a private camp
                raise GameError("Visibility must be public or private.")
            if len(self.rooms) >= self.max_rooms:
                raise GameError("The server is full; try again later.")
            code = self._new_code()
            room = Room(code, os.path.join(self.data, "rooms", code), self.sched, self.settings,
                        visibility=visibility, name=clean_name(msg.get("name")))
            self.rooms[code] = room
            return await self._join(ws, room)
        if t == "join_room":
            if seat:
                raise GameError("You're already in a room.")
            room = self.rooms.get(str(msg.get("code", "")).strip().upper())
            if room is None:
                raise Coded("room_gone", "There's no room with that code.")
            if room.game.started:
                raise Coded("room_started", "That game has already started.")
            if len(room.game.joined) >= room.game.settings.seats:
                raise Coded("room_full", "The room is full.")
            return await self._join(ws, room)
        if t == "resume":
            key = token_key(str(msg.get("token", "")))
            code = self.by_token.get(key)
            ident = self.rooms[code].identity.get(key) if code in self.rooms else None
            if ident is None:
                raise Coded("seat_gone", "That seat no longer exists.")
            return await self._seat(ws, self.rooms[code], ident["pid"], msg["token"])
        if seat is None:
            raise GameError("Join or create a room first.")
        room, pid = seat
        g = room.game
        if t == "start":
            if pid != room.host_pid():
                raise GameError("Only the host can start.")
            g.start()
        elif t == "pick":
            amount = msg.get("amount", 0)
            if not isinstance(amount, int):
                raise GameError("Amount must be a whole number.")
            g.pick(pid, str(msg.get("kind", "")), msg.get("target") or None, amount)
        elif t == "lock":
            g.lock(pid)
        elif t == "radio":
            g.record_radio(room.identity.key_for(pid), str(msg.get("phrase", "")), msg.get("about") or None)
            await room.push(pid)
        elif t == "continue":
            g.continue_(pid)
        elif t == "kick":
            if g.started:
                raise GameError("Kicking is only possible in the lobby.")
            if pid != room.host_pid():
                raise GameError("Only the host can kick.")
            target = next((j[0] for j in g.joined if views.seat_handle(g, j[0]) == msg.get("seat")), None)
            if target is None:
                raise GameError("That seat is not in the room any more.")
            if target == pid:
                raise GameError("You can't kick yourself; use leave.")
            key = room.identity.key_for(target)
            gone = room.conns.pop(target, None)         # from here the target's connection no longer holds the seat
            g.leave_lobby(key, kicked=True)
            self.by_token.pop(key, None)
            if gone is not None:
                try:
                    await self._error(gone, "kicked", "The host removed you from this camp.")
                except Exception:
                    pass
                asyncio.ensure_future(self._close_after_pause(gone, CLOSE_KICKED, "kicked"))
            await room.push_all()
            return seat
        elif t == "leave":
            key = room.identity.key_for(pid)
            if g.started:
                g.leave_seat(key)
                room.conns.pop(pid, None)
                g.disconnect(pid)           # not here any more: after the grace, the round stops waiting for this seat
            else:
                room.conns.pop(pid, None)   # the seat goes back to the room: the token dies, the pid is never reused
                g.leave_lobby(key)
                self.by_token.pop(key, None)
            await room.push_all()
            if not g.started and not g.joined:
                self._drop_room(room)       # nobody left in the lobby: nothing to keep
            return None
        else:
            raise GameError(f"Unknown message type '{t}'.")
        await room.push(pid)
        return seat

    async def _join(self, ws, room):
        token = secrets.token_urlsafe(24)
        key = token_key(token)
        room.game.add_human(key)
        self.by_token[key] = room.code
        log.info("seat taken in room %s (%d/%d)", room.code, len(room.game.joined), room.game.settings.seats)
        return await self._seat(ws, room, room.identity.get(key)["pid"], token)


async def serve(data_dir, host="127.0.0.1", port=8765, settings=RoomSettings(), ready=None):
    from websockets.asyncio.server import serve as ws_serve
    server = Server(data_dir, settings, AsyncioScheduler(asyncio.get_running_loop()))
    server.load()
    async with ws_serve(server.handle, host, port, max_size=MAX_MESSAGE) as s:
        port = s.sockets[0].getsockname()[1]
        log.info("arena listening on %s:%d", host, port)
        if ready:
            ready(server, port)
        await asyncio.Future()


def main():
    ap = argparse.ArgumentParser(description="Survivors Arena server")
    ap.add_argument("--data", default=os.environ.get("ARENA_DATA", "arena-data"))
    ap.add_argument("--host", default=os.environ.get("ARENA_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("ARENA_PORT", "8765")))
    ap.add_argument("--timer", type=float, default=float(os.environ.get("ARENA_TIMER", "180")))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(serve(a.data, a.host, a.port, RoomSettings(timer=a.timer)))


if __name__ == "__main__":
    main()
