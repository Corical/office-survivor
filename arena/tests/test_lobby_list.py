"""The open-camps list (`list_rooms`) over a real WebSocket: what is listed, what must never be, and every way a client
or a race can make it wrong. Same needs as test_server.py (the `websockets` package; otherwise SKIPPED, never passed).
"""
import asyncio
import json
import os
import unittest

from . import test_server as base               # the module, not its test class: importing ServerTests would re-run it here
from .test_server import HAVE_WS, Client


@unittest.skipUnless(HAVE_WS, "websockets is not installed in this Python: server tests SKIPPED, not passed")
class OpenCamps(unittest.IsolatedAsyncioTestCase):
    # the server fixtures of ServerTests, borrowed rather than copied so a change there reaches here
    S = base.ServerTests
    asyncSetUp, _start, _stop, asyncTearDown = S.asyncSetUp, S._start, S._stop, S.asyncTearDown
    del S

    # ---------------- helpers ----------------
    async def _camp(self, **fields):
        """Create a room; returns (client, seat). Extra fields ride on create_room."""
        c = await Client.open(self.port)
        await c.send({"t": "create_room", **fields})
        seat = await c.until("seat")
        await c.until("lobby")
        return c, seat

    async def _list(self):
        """The list as a stranger sees it: a fresh connection each time (one list per second per connection)."""
        c = await Client.open(self.port)
        await c.send({"t": "list_rooms"})
        got = await c.until("rooms")
        await c.close()
        return got["rooms"]

    async def _codes(self):
        return [r["code"] for r in await self._list()]

    async def _until_listed(self, code, listed):
        for _ in range(40):
            if (code in await self._codes()) == listed:
                return
            await asyncio.sleep(0.1)
        self.fail(f"room {code} never became {'listed' if listed else 'unlisted'}")

    async def _join(self, code):
        c = await Client.open(self.port)
        await c.send({"t": "join_room", "code": code})
        return c

    # ---------------- what is listed ----------------
    async def test_hello_ok_advertises_the_feature(self):
        c = await Client.open(self.port, hello=False)
        await c.send({"t": "hello", "proto": 1})
        m = await c.next()
        self.assertEqual((m["t"], m["features"]), ("hello_ok", ["list_rooms"]))

    async def test_a_fresh_public_camp_is_listed_with_exactly_the_agreed_fields_and_nothing_else(self):
        c, seat = await self._camp()
        rooms = await self._list()
        self.assertEqual(len(rooms), 1)
        self.assertEqual(sorted(rooms[0]), ["age_s", "code", "name", "seats_taken", "seats_total"])
        self.assertEqual((rooms[0]["code"], rooms[0]["seats_taken"], rooms[0]["seats_total"], rooms[0]["name"]),
                         (seat["room_code"], 1, 4, ""))
        self.assertIsInstance(rooms[0]["age_s"], int)
        self.assertGreaterEqual(rooms[0]["age_s"], 0)
        blob = json.dumps(rooms)
        self.assertNotIn(seat["alias"], blob)
        self.assertNotIn(seat["token"], blob)

    async def test_nobody_listed_when_there_are_no_camps(self):
        self.assertEqual(await self._list(), [])

    async def test_private_camps_are_never_listed_but_still_joinable_by_code(self):
        c, seat = await self._camp(visibility="private", name="secret")
        self.assertEqual(await self._list(), [])
        j = await self._join(seat["room_code"])
        self.assertEqual((await j.until("seat"))["room_code"], seat["room_code"])

    async def test_the_default_when_visibility_is_absent_is_public_so_an_old_client_is_listed(self):
        c, seat = await self._camp()
        self.assertEqual(await self._codes(), [seat["room_code"]])

    async def test_newest_first(self):
        made = []
        for _ in range(3):
            c, seat = await self._camp()
            made.append(seat["room_code"])
            await asyncio.sleep(0.05)
        self.assertEqual(await self._codes(), list(reversed(made)))

    async def test_seats_taken_counts_humans_and_the_full_room_drops_out(self):
        c, seat = await self._camp()
        code = seat["room_code"]
        joiners = []
        for taken in (2, 3):
            joiners.append(await self._join(code))
            await joiners[-1].until("seat")
            self.assertEqual((await self._list())[0]["seats_taken"], taken)
        joiners.append(await self._join(code))                 # the 4th seat
        await joiners[-1].until("seat")
        self.assertEqual(await self._list(), [], "a full room cannot be joined, so it is not offered")

    async def test_a_started_game_never_appears(self):
        c, seat = await self._camp()
        await c.send({"t": "start"})
        await c.until("round")
        self.assertEqual(await self._list(), [])

    async def test_a_camp_nobody_is_in_drops_out_and_comes_back_when_someone_resumes(self):
        c, seat = await self._camp()
        code = seat["room_code"]
        await c.close()
        await self._until_listed(code, False)
        back = await Client.open(self.port)
        await back.send({"t": "resume", "token": seat["token"]})
        await back.until("seat")
        await self._until_listed(code, True)

    async def test_a_seat_that_left_the_lobby_still_counts_as_taken(self):
        """Known and documented (ARENA.md): leaving the lobby does not free the seat. The list tells the truth about it."""
        c, seat = await self._camp()
        j = await self._join(seat["room_code"])
        await j.until("seat")
        await j.close()
        for _ in range(20):                                    # let the server notice the drop
            await asyncio.sleep(0.05)
        self.assertEqual((await self._list())[0]["seats_taken"], 2)

    # ---------------- the races the list creates ----------------
    async def test_room_fills_between_the_list_and_the_tap(self):
        c, seat = await self._camp()
        code = seat["room_code"]
        listed = await self._codes()
        self.assertEqual(listed, [code])
        joiners = [await self._join(code) for _ in range(3)]
        for j in joiners:
            await j.until("seat")
        late = await self._join(code)                          # tapped the stale card
        err = await late.until("error")
        self.assertEqual(err["code"], "room_full")
        self.assertTrue(err["message"])
        await late.send({"t": "list_rooms"})                   # and the connection is still good: refresh works
        self.assertEqual((await late.until("rooms"))["rooms"], [])

    async def test_room_starts_between_the_list_and_the_tap(self):
        c, seat = await self._camp()
        await self._codes()
        await c.send({"t": "start"})
        await c.until("round")
        late = await self._join(seat["room_code"])
        self.assertEqual((await late.until("error"))["code"], "room_started")

    async def test_a_code_that_vanished_still_answers_room_gone(self):
        late = await self._join("ZZZZ")
        self.assertEqual((await late.until("error"))["code"], "room_gone")

    # ---------------- hostile create_room fields ----------------
    async def test_a_bad_visibility_is_refused_and_creates_nothing(self):
        before = set(os.listdir(os.path.join(self.data, "rooms"))) if os.path.exists(os.path.join(self.data, "rooms")) else set()
        c = await Client.open(self.port)
        for bad in ("Private", "PUBLIC", "", " public", "pubic", None, 0, 1, True, False, ["private"], {"v": 1}):
            await c.send({"t": "create_room", "visibility": bad})
            err = await c.until("error")
            self.assertEqual(err["code"], "refused", f"visibility={bad!r}")
        self.assertEqual(len(self.server.rooms), 0, "a refused create must not leave a room behind")
        after = set(os.listdir(os.path.join(self.data, "rooms")))
        self.assertEqual(after, before)
        await c.send({"t": "create_room", "visibility": "private"})        # the same connection can still create
        await c.until("seat")

    async def test_a_name_is_cleaned_cut_and_never_breaks_the_list(self):
        pairs = [
            ("  Friday‮ night\x00\n  ", "Friday night"),    # bidi override and NUL gone, newline and spaces collapse
            ("a\tb​c", "a bc"),                              # a tab is a space; the zero-width space is dropped
            ("\ud800camp", "camp"),                               # a lone surrogate cannot be sent: dropped
            ("x" * 3000, "x" * 24),                               # cut
            ("\U0001F525 " + "y" * 40, "\U0001F525 " + "y" * 22), # an emoji is kept and counts as one character
            ("   \n\t  ", ""),                                    # only whitespace: no label
            (123, ""), (["a"], ""), (None, ""), (True, ""), ({"a": 1}, ""),   # not text: no label
        ]
        keep = []
        for raw, want in pairs:
            keep.append(await self._camp(name=raw))                 # each also proves the room is still created
            got = (await self._list())[0]                           # newest first: ours is on top
            self.assertEqual(got["name"], want, f"name={raw!r}")
            self.assertIsInstance(got["name"], str)
            self.assertLessEqual(len(got["name"]), 24)
            await asyncio.sleep(0.02)
        self.assertEqual(len(await self._list()), len(pairs))

    async def test_a_private_name_is_not_leaked_anywhere(self):
        c, seat = await self._camp(visibility="private", name="top secret")
        j = await Client.open(self.port)
        await j.send({"t": "list_rooms"})
        await j.until("rooms")
        self.assertNotIn("top secret", json.dumps(j.seen))

    # ---------------- rate limit and protocol order ----------------
    async def test_list_rooms_before_hello_is_refused_like_everything_else(self):
        c = await Client.open(self.port, hello=False)
        await c.send({"t": "list_rooms"})
        self.assertEqual((await c.next())["code"], "hello_first")

    async def test_a_second_list_within_the_second_is_rate_limited_and_the_refusal_does_not_reset_the_clock(self):
        c = await Client.open(self.port)
        await c.send({"t": "list_rooms"})
        await c.until("rooms")
        await c.send({"t": "list_rooms"})
        err = await c.until("error")
        self.assertEqual(err["code"], "rate_limited")
        self.assertNotIn("rooms", [m["t"] for m in c.seen[-1:]], "a refused list sends no list")
        await asyncio.sleep(0.6)
        await c.send({"t": "list_rooms"})                       # still inside the interval since the first
        self.assertEqual((await c.until("error"))["code"], "rate_limited")
        await asyncio.sleep(0.5)                                # 1.1 s after the first answered list: allowed again
        await c.send({"t": "list_rooms"})
        await c.until("rooms")                                  # had the refusal reset the clock, this would be refused

    async def test_the_limit_is_per_connection_not_global(self):
        a, b = await Client.open(self.port), await Client.open(self.port)
        for c in (a, b):
            await c.send({"t": "list_rooms"})
        for c in (a, b):
            await c.until("rooms")

    async def test_a_seated_player_can_list_and_the_game_carries_on(self):
        c, seat = await self._camp()
        other, _ = await self._camp()
        await c.send({"t": "list_rooms", "code": "ignored", "junk": [1] * 50})
        rooms = (await c.until("rooms"))["rooms"]
        self.assertEqual(len(rooms), 2)
        await c.send({"t": "start"})                            # nothing was disturbed
        await c.until("round")

    async def test_a_player_can_not_create_or_join_a_second_room_after_listing(self):
        c, seat = await self._camp()
        await c.send({"t": "list_rooms"})
        await c.until("rooms")
        await c.send({"t": "create_room"})
        self.assertIn("already", (await c.until("error"))["message"])

    # ---------------- persistence ----------------
    async def test_visibility_and_name_survive_a_server_restart(self):
        pub, pub_seat = await self._camp(name="Night owls")
        priv, priv_seat = await self._camp(visibility="private", name="hidden")
        await pub.close()
        await priv.close()
        await self._stop()
        await self._start()
        back = []
        for seat in (pub_seat, priv_seat):
            c = await Client.open(self.port)
            await c.send({"t": "resume", "token": seat["token"]})
            await c.until("seat")
            back.append(c)
        rooms = await self._list()
        self.assertEqual([(r["code"], r["name"]) for r in rooms], [(pub_seat["room_code"], "Night owls")])

    async def test_an_old_room_json_without_the_new_fields_loads_as_public_and_unnamed(self):
        c, seat = await self._camp()
        await c.close()
        path = os.path.join(self.data, "rooms", seat["room_code"], "room.json")
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        for k in ("visibility", "name", "created"):
            meta.pop(k, None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        await self._stop()
        await self._start()
        back = await Client.open(self.port)
        await back.send({"t": "resume", "token": seat["token"]})
        await back.until("seat")
        rooms = await self._list()
        self.assertEqual([(r["code"], r["name"]) for r in rooms], [(seat["room_code"], "")])
        self.assertGreaterEqual(rooms[0]["age_s"], 0)

    async def test_a_hand_edited_junk_visibility_on_disk_is_not_listed(self):
        """Fail closed: only the exact word `public` publishes a camp."""
        c, seat = await self._camp()
        await c.close()
        path = os.path.join(self.data, "rooms", seat["room_code"], "room.json")
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        meta["visibility"] = "Public "
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        await self._stop()
        await self._start()
        back = await Client.open(self.port)
        await back.send({"t": "resume", "token": seat["token"]})
        await back.until("seat")
        self.assertEqual(await self._list(), [])


if __name__ == "__main__":
    unittest.main()
