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
import time

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


class Room:
    """One room on disk plus its live connections."""

    def __init__(self, code, path, scheduler, settings, salt=None):
        self.code, self.path = code, path
        os.makedirs(path, exist_ok=True)
        meta = os.path.join(path, "room.json")
        if os.path.exists(meta):
            with open(meta, encoding="utf-8") as f:
                salt = json.load(f)["salt"]
        else:
            salt = salt or secrets.token_hex(16)
            with open(meta, "w", encoding="utf-8") as f:
                json.dump({"code": code, "salt": salt, "created": time.time()}, f)
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
        self.game.listeners.append(lambda what: asyncio.ensure_future(self.push_all()))

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
                try:
                    seat = await self._dispatch(ws, msg, seat)
                except GameError as e:
                    await self._error(ws, "refused", str(e))
                except Exception:
                    log.exception("message %s failed", msg.get("t"))
                    await self._error(ws, "server_error", "Something went wrong on the server.")
        except Exception as e:
            from websockets.exceptions import ConnectionClosed
            if not isinstance(e, ConnectionClosed):
                raise
            log.info("connection closed: %s", e)            # a dropped phone, or a frame over the size limit
        finally:
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
            return False
        await ws.send(json.dumps({"t": "hello_ok", "proto": PROTO}))
        return True

    async def _error(self, ws, code, message):
        await ws.send(json.dumps({"t": "error", "code": code, "message": message}, ensure_ascii=False))

    async def _seat(self, ws, room, pid, token):
        old = room.conns.get(pid)
        if old is not None and old is not ws:
            now = time.time()
            recent = [t for t in room.takeovers.get(pid, []) if now - t < 60]
            if len(recent) >= TAKEOVERS_PER_MINUTE:
                raise GameError("Too many reconnects; wait a minute.")
            room.takeovers[pid] = recent + [now]
            try:
                await self._error(old, "taken_over", "This seat was opened on another device.")
                await old.close()
            except Exception:
                pass
        room.conns[pid] = ws
        room.game.connect(pid)
        alias = room.game.joined[pid][1]
        await ws.send(json.dumps({"t": "seat", "token": token, "room_code": room.code, "alias": alias,
                                  "host": pid == room.host_pid()}, ensure_ascii=False))
        await room.push_all()
        return room, pid

    async def _dispatch(self, ws, msg, seat):
        t = msg["t"]
        if t == "create_room":
            if seat:
                raise GameError("You're already in a room.")
            if len(self.rooms) >= self.max_rooms:
                raise GameError("The server is full; try again later.")
            code = self._new_code()
            room = Room(code, os.path.join(self.data, "rooms", code), self.sched, self.settings)
            self.rooms[code] = room
            return await self._join(ws, room)
        if t == "join_room":
            if seat:
                raise GameError("You're already in a room.")
            room = self.rooms.get(str(msg.get("code", "")).strip().upper())
            if room is None:
                raise GameError("There's no room with that code.")
            if room.game.started:
                raise GameError("That game has already started.")
            return await self._join(ws, room)
        if t == "resume":
            key = token_key(str(msg.get("token", "")))
            code = self.by_token.get(key)
            if code is None:
                raise GameError("That seat no longer exists.")
            room = self.rooms[code]
            return await self._seat(ws, room, room.identity.get(key)["pid"], msg["token"])
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
        elif t == "leave":
            if g.started:
                g.leave_seat(room.identity.key_for(pid))
            room.conns.pop(pid, None)
            await room.push_all()
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
