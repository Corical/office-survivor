"""The Arena server over a real WebSocket on a local port: a whole game, then everything a client could do wrong.

Needs the `websockets` package (16+). The project venv does not have it yet; run with a Python that does:
    python -I -m unittest discover -s arena/tests -t .
Without it these tests report SKIPPED (never passed).
"""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

try:
    from websockets.asyncio.client import connect
    HAVE_WS = True
except ImportError:
    HAVE_WS = False

from arena.room import RoomSettings

FAST = RoomSettings(timer=4.0, reveal=1.0, grace=0.5, bot_lock_min=0.1, bot_lock_max=0.3)
WAIT = 8.0


class Client:
    def __init__(self, ws):
        self.ws, self.seen = ws, []

    @classmethod
    async def open(cls, port, hello=True):
        c = cls(await connect(f"ws://127.0.0.1:{port}", max_size=None))
        if hello:
            await c.send({"t": "hello", "proto": 1, "client_build": "test"})
            assert (await c.next())["t"] == "hello_ok"
        return c

    async def send(self, msg):
        await self.ws.send(json.dumps(msg))

    async def next(self):
        m = json.loads(await asyncio.wait_for(self.ws.recv(), WAIT))
        self.seen.append(m)
        return m

    async def until(self, t, pred=lambda m: True):
        while True:
            m = await self.next()
            if m["t"] == t and pred(m):
                return m

    async def close(self):
        await self.ws.close()


@unittest.skipUnless(HAVE_WS, "websockets is not installed in this Python: server tests SKIPPED, not passed")
class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.data = tempfile.mkdtemp(prefix="arena-test-")
        await self._start()

    async def _start(self):
        from arena.server import serve
        got = asyncio.get_running_loop().create_future()
        self.task = asyncio.create_task(serve(self.data, "127.0.0.1", 0, FAST,
                                              ready=lambda s, p: got.set_result((s, p))))
        self.server, self.port = await asyncio.wait_for(got, WAIT)

    async def _stop(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass

    async def asyncTearDown(self):
        await self._stop()
        shutil.rmtree(self.data, ignore_errors=True)

    async def _new_room(self):
        c = await Client.open(self.port)
        await c.send({"t": "create_room"})
        seat = await c.until("seat")
        await c.until("lobby")
        return c, seat

    async def _play_round(self, c):
        """Pick the first legal move, lock, and wait for this round's reveal."""
        r = await c.until("round", lambda m: not m["my_locked"])
        kind = "scavenge" if "scavenge" in r["legal"] else sorted(r["legal"])[0]
        tgt = r["legal"][kind][0] if r["legal"][kind] else None
        await c.send({"t": "pick", "kind": kind, "target": tgt, "amount": r["gift_amounts"][0] if kind == "gift" else 0})
        await c.send({"t": "lock"})
        return await c.until("reveal", lambda m: m["round"] == r["round"])

    # ---------------- the happy path ----------------
    async def test_a_whole_game_with_one_human_and_three_bots_over_the_socket(self):
        c, seat = await self._new_room()
        self.assertTrue(seat["host"])
        await c.send({"t": "start"})
        for n in range(1, 11):
            rv = await self._play_round(c)
            self.assertEqual(rv["round"], n)
            self.assertTrue(rv["private"], "a human always gets private lines")
            await c.send({"t": "continue"})
        end = await c.until("end")
        self.assertEqual(len(end["results"]), 4)
        self.assertIn(seat["alias"], [r["alias"] for r in end["results"]])
        await c.close()

    # ---------------- protocol abuse ----------------
    async def test_no_hello_first_is_refused(self):
        c = await Client.open(self.port, hello=False)
        await c.send({"t": "create_room"})
        self.assertEqual((await c.next())["code"], "hello_first")

    async def test_an_old_client_is_told_to_upgrade(self):
        c = await Client.open(self.port, hello=False)
        await c.send({"t": "hello", "proto": 0})
        self.assertEqual((await c.next())["t"], "upgrade_required")

    async def test_garbage_and_unknown_messages_get_errors_and_the_connection_survives(self):
        c, _ = await self._new_room()
        await c.ws.send("{not json")
        self.assertEqual((await c.until("error"))["code"], "bad_message")
        await c.ws.send("[1, 2]")
        self.assertEqual((await c.until("error"))["code"], "bad_message")
        await c.send({"t": "fly_to_the_moon"})
        self.assertIn("Unknown", (await c.until("error"))["message"])
        await c.send({"t": "start"})                      # still works afterwards
        await c.until("round")

    async def test_an_oversized_frame_drops_that_client_and_the_server_keeps_serving(self):
        c, _ = await self._new_room()
        await c.ws.send(json.dumps({"t": "pick", "kind": "x" * 10000}))
        with self.assertRaises(Exception):
            for _ in range(5):
                await c.next()
        d, _ = await self._new_room()                    # a new client is served
        await d.close()

    async def test_a_seat_or_pid_in_the_payload_is_ignored(self):
        c, _ = await self._new_room()
        await c.send({"t": "start"})
        await c.until("round")
        await c.send({"t": "pick", "kind": "guard", "pid": 2, "seat": 3})
        room = next(iter(self.server.rooms.values()))
        await c.until("round", lambda m: m["my_pick"] is not None)
        self.assertEqual(set(room.game.moves), {0}, "only my own seat got a move")

    async def test_bad_joins_and_a_non_host_start_are_refused(self):
        c, seat = await self._new_room()
        d = await Client.open(self.port)
        await d.send({"t": "join_room", "code": "ZZZZ"})
        self.assertIn("no room", (await d.until("error"))["message"])
        await d.send({"t": "join_room", "code": seat["room_code"].lower()})   # codes are not case sensitive
        dseat = await d.until("seat")
        self.assertFalse(dseat["host"])
        self.assertNotEqual(dseat["alias"], seat["alias"])
        await d.send({"t": "start"})
        self.assertIn("host", (await d.until("error"))["message"])
        await c.send({"t": "start"})
        await c.until("round")
        e = await Client.open(self.port)
        await e.send({"t": "join_room", "code": seat["room_code"]})
        self.assertIn("already started", (await e.until("error"))["message"])

    async def test_each_seat_sees_its_own_alias_only(self):
        c, seat = await self._new_room()
        d = await Client.open(self.port)
        await d.send({"t": "join_room", "code": seat["room_code"]})
        dseat = await d.until("seat")
        await c.send({"t": "start"})
        rc, rd = await c.until("round"), await d.until("round")
        self.assertEqual(rc["me"]["alias"], seat["alias"])
        self.assertEqual(rd["me"]["alias"], dseat["alias"])
        self.assertNotIn(seat["alias"], rc["aliases"])

    # ---------------- reconnects ----------------
    async def test_resume_after_a_drop_gives_the_current_view_and_keeps_the_lock(self):
        c, seat = await self._new_room()
        d = await Client.open(self.port)                 # a second human so my lock does not end the round
        await d.send({"t": "join_room", "code": seat["room_code"]})
        await d.until("seat")
        await c.send({"t": "start"})
        await c.until("round")
        await c.send({"t": "pick", "kind": "scavenge"})
        await c.send({"t": "lock"})
        await c.until("round", lambda m: m["my_locked"])
        await c.close()
        c2 = await Client.open(self.port)
        await c2.send({"t": "resume", "token": seat["token"]})
        again = await c2.until("seat")
        self.assertEqual(again["alias"], seat["alias"])
        view = await c2.until("round")
        self.assertTrue(view["my_locked"])
        self.assertEqual(view["my_pick"]["kind"], "scavenge")

    async def test_a_second_device_takes_the_seat_and_the_first_is_told(self):
        c, seat = await self._new_room()
        c2 = await Client.open(self.port)
        await c2.send({"t": "resume", "token": seat["token"]})
        await c2.until("seat")
        self.assertEqual((await c.until("error"))["code"], "taken_over")

    async def test_a_wrong_token_is_refused(self):
        c = await Client.open(self.port)
        await c.send({"t": "resume", "token": "not-a-token"})
        self.assertIn("no longer exists", (await c.until("error"))["message"])

    async def test_a_server_restart_mid_game_and_the_game_carries_on(self):
        c, seat = await self._new_room()
        await c.send({"t": "start"})
        for _ in range(3):
            await self._play_round(c)
            await c.send({"t": "continue"})
        await c.until("round", lambda m: m["round"] == 4)
        await c.close()
        await self._stop()
        await self._start()                               # same data directory
        c2 = await Client.open(self.port)
        await c2.send({"t": "resume", "token": seat["token"]})
        await c2.until("seat")
        for n in range(4, 11):
            rv = await self._play_round(c2)
            self.assertEqual(rv["round"], n)
            await c2.send({"t": "continue"})
        await c2.until("end")

    async def test_nothing_secret_is_written_where_a_client_could_read_it(self):
        c, seat = await self._new_room()
        room_dir = os.path.join(self.data, "rooms", seat["room_code"])
        ident = open(os.path.join(room_dir, "identity.json"), encoding="utf-8").read()
        self.assertNotIn(seat["token"], ident, "tokens are stored hashed")
        salt = json.load(open(os.path.join(room_dir, "room.json")))["salt"]
        self.assertNotIn(salt, json.dumps(c.seen))
        self.assertNotIn(salt, seat["room_code"])


if __name__ == "__main__":
    unittest.main()
