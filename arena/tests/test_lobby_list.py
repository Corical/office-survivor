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
    _play_round = S._play_round
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

    async def test_closing_the_app_without_leave_keeps_the_seat_in_case_they_come_back(self):
        """Documented (ARENA.md section 7): only the leave message frees a lobby seat; a dropped phone may resume."""
        c, seat = await self._camp()
        j = await self._join(seat["room_code"])
        joined = await j.until("seat")
        await j.close()
        for _ in range(20):                                    # let the server notice the drop
            await asyncio.sleep(0.05)
        self.assertEqual((await self._list())[0]["seats_taken"], 2)
        back = await Client.open(self.port)
        await back.send({"t": "resume", "token": joined["token"]})
        self.assertEqual((await back.until("seat"))["alias"], joined["alias"])

    # ---------------- leaving the lobby gives the seat back ----------------
    async def _lobby_count(self, client, n):
        return await client.until("lobby", lambda m: m["seats_taken"] == n)

    async def test_the_owners_exact_scenario_the_creator_sees_the_count_drop_when_the_joiner_leaves(self):
        creator, seat = await self._camp()
        joiner = await self._join(seat["room_code"])
        await joiner.until("seat")
        await self._lobby_count(creator, 2)
        await joiner.send({"t": "leave"})
        lobby = await self._lobby_count(creator, 1)             # the creator is told: 1 of 4, not a stuck 2
        self.assertTrue(lobby["host"])
        self.assertEqual((await self._list())[0]["seats_taken"], 1)

    async def test_the_leaver_hears_nothing_more_and_their_token_is_dead(self):
        creator, seat = await self._camp()
        joiner = await self._join(seat["room_code"])
        joined = await joiner.until("seat")
        await self._lobby_count(creator, 2)
        mark = len(joiner.seen)
        await joiner.send({"t": "leave"})
        await self._lobby_count(creator, 1)
        await asyncio.sleep(0.2)
        self.assertEqual([m["t"] for m in joiner.seen[mark:]], [], "a player who left gets no more lobby pushes")
        again = await Client.open(self.port)
        await again.send({"t": "resume", "token": joined["token"]})
        self.assertEqual((await again.until("error"))["code"], "seat_gone")

    async def test_the_freed_seat_is_taken_by_the_next_person_and_the_whole_game_plays_to_the_end(self):
        """Three humans, the middle one leaves, a fourth takes the place, then 10 rounds: pids have been reused."""
        host, seat = await self._camp()
        code = seat["room_code"]
        b = await self._join(code)
        await b.until("seat")
        c = await self._join(code)
        await c.until("seat")
        await self._lobby_count(host, 3)
        await b.send({"t": "leave"})
        await self._lobby_count(host, 2)
        d = await self._join(code)
        await d.until("seat")
        await self._lobby_count(host, 3)
        await host.send({"t": "start"})
        humans = [host, c, d]

        async def play(cl):
            for n in range(1, 11):
                await self._play_round(cl)
                await cl.send({"t": "continue"})
            return await cl.until("end")

        ends = await asyncio.gather(*(play(cl) for cl in humans))
        self.assertTrue(all(len(e["results"]) == 4 for e in ends))
        self.assertEqual(len({r["alias"] for r in ends[0]["results"]}), 4)

    async def test_a_full_room_reopens_when_someone_leaves_and_shows_up_in_the_list_again(self):
        creator, seat = await self._camp()
        code = seat["room_code"]
        others = []
        for _ in range(3):
            o = await self._join(code)
            await o.until("seat")
            others.append(o)
        self.assertEqual(await self._list(), [])
        await others[0].send({"t": "leave"})
        await self._until_listed(code, True)
        self.assertEqual((await self._list())[0]["seats_taken"], 3)
        late = await self._join(code)
        await late.until("seat")
        self.assertEqual(await self._list(), [])

    async def test_the_host_leaving_passes_the_camp_to_the_next_person(self):
        creator, seat = await self._camp()
        other = await self._join(seat["room_code"])
        await other.until("seat")
        await creator.send({"t": "leave"})
        lobby = await self._lobby_count(other, 1)
        self.assertTrue(lobby["host"], "the one left behind runs the lobby now")
        await other.send({"t": "start"})                        # and can start it
        await other.until("round")

    async def test_the_last_person_out_deletes_the_camp_and_frees_its_room_slot(self):
        self.server.max_rooms = 1
        c, seat = await self._camp()
        code = seat["room_code"]
        folder = os.path.join(self.data, "rooms", code)
        self.assertTrue(os.path.isdir(folder))
        await c.send({"t": "leave"})
        for _ in range(40):
            if not os.path.isdir(folder):
                break
            await asyncio.sleep(0.05)
        self.assertFalse(os.path.isdir(folder), "an emptied lobby is deleted from disk")
        self.assertEqual(await self._list(), [])
        late = await self._join(code)
        self.assertEqual((await late.until("error"))["code"], "room_gone")
        again, _ = await self._camp()                           # the one slot is free again: no "server is full"
        await again.close()

    async def test_leave_then_join_again_on_the_same_connection_is_a_fresh_seat(self):
        creator, seat = await self._camp()
        j = await self._join(seat["room_code"])
        first = await j.until("seat")
        await j.send({"t": "leave"})
        await self._lobby_count(creator, 1)
        await j.send({"t": "join_room", "code": seat["room_code"]})
        second = await j.until("seat", lambda m: m["token"] != first["token"])
        self.assertNotEqual(second["token"], first["token"])
        await self._lobby_count(creator, 2)

    async def test_leaving_twice_or_without_a_seat_is_a_calm_error_not_a_crash(self):
        creator, seat = await self._camp()
        j = await self._join(seat["room_code"])
        await j.until("seat")
        await j.send({"t": "leave"})
        await j.send({"t": "leave"})
        self.assertIn("Join or create", (await j.until("error"))["message"])
        stranger = await Client.open(self.port)
        await stranger.send({"t": "leave"})
        self.assertIn("Join or create", (await stranger.until("error"))["message"])
        await creator.send({"t": "start"})                      # the room is unharmed
        await creator.until("round")

    async def test_a_second_device_holding_the_leavers_token_is_dead_too(self):
        creator, seat = await self._camp()
        j = await self._join(seat["room_code"])
        joined = await j.until("seat")
        phone2 = await Client.open(self.port)
        await phone2.send({"t": "resume", "token": joined["token"]})        # takes the seat over: j is told and closed
        await phone2.until("seat")
        await phone2.send({"t": "leave"})
        await self._lobby_count(creator, 1)
        again = await Client.open(self.port)
        await again.send({"t": "resume", "token": joined["token"]})
        self.assertEqual((await again.until("error"))["code"], "seat_gone")

    async def test_a_restart_after_a_leave_keeps_the_free_seat_and_the_dead_token_dead(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        seat_b = await b.until("seat")
        c = await self._join(seat_a["room_code"])
        seat_c = await c.until("seat")
        await self._lobby_count(a, 3)
        await b.send({"t": "leave"})
        await self._lobby_count(a, 2)
        for cl in (a, b, c):
            await cl.close()
        await self._stop()
        await self._start()
        ra = await Client.open(self.port)
        await ra.send({"t": "resume", "token": seat_a["token"]})
        await ra.until("seat")
        rc = await Client.open(self.port)
        await rc.send({"t": "resume", "token": seat_c["token"]})
        self.assertEqual((await rc.until("seat"))["alias"], seat_c["alias"])
        dead = await Client.open(self.port)
        await dead.send({"t": "resume", "token": seat_b["token"]})
        self.assertEqual((await dead.until("error"))["code"], "seat_gone")
        d = await self._join(seat_a["room_code"])               # the free place is still there after the restart
        await d.until("seat")
        await self._lobby_count(ra, 3)
        await ra.send({"t": "start"})
        await ra.until("round")

    async def test_identity_left_behind_by_a_crash_does_not_revive_the_leaver_after_a_restart(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        seat_b = await b.until("seat")
        await self._lobby_count(a, 2)
        ident_path = os.path.join(self.data, "rooms", seat_a["room_code"], "identity.json")
        with open(ident_path, encoding="utf-8") as f:
            before_leave = f.read()
        await b.send({"t": "leave"})
        await self._lobby_count(a, 1)
        await a.close()
        await b.close()
        await self._stop()
        with open(ident_path, "w", encoding="utf-8") as f:       # the identity write that never happened
            f.write(before_leave)
        await self._start()
        dead = await Client.open(self.port)
        await dead.send({"t": "resume", "token": seat_b["token"]})
        self.assertEqual((await dead.until("error"))["code"], "seat_gone")
        live = await Client.open(self.port)
        await live.send({"t": "resume", "token": seat_a["token"]})
        await live.until("seat")

    # ---------------- the host kicks ----------------
    async def _host_sees(self, host, n, connected=None):
        """The host's next lobby with n other seats (and, if given, with exactly this connected flag on every one)."""
        return await host.until("lobby", lambda m: "seats" in m and len(m["seats"]) == n
                                and (connected is None or all(s["connected"] == connected for s in m["seats"])))

    async def test_only_the_host_is_told_about_the_other_seats_and_nobody_is_named(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        seat_b = await b.until("seat")
        lobby = await self._host_sees(a, 1, connected=True)
        self.assertRegex(lobby["seats"][0]["id"], r"^[0-9a-f]{8}$")
        guest = await b.until("lobby", lambda m: m["seats_taken"] == 2)
        self.assertNotIn("seats", guest)
        self.assertNotIn(seat_b["alias"], json.dumps(a.seen), "the host never learns a guest's alias")

    async def test_the_host_kicks_a_dropped_player_without_waiting_for_anything(self):
        """The owner's case: a connection that is gone, a seat that should be open now."""
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        seat_b = await b.until("seat")
        await self._host_sees(a, 1, connected=True)
        await b.close()
        dropped = await self._host_sees(a, 1, connected=False)         # the host can see which seat is dead
        await a.send({"t": "kick", "seat": dropped["seats"][0]["id"]})
        lobby = await self._lobby_count(a, 1)
        self.assertEqual(lobby["seats"], [])
        self.assertEqual((await self._list())[0]["seats_taken"], 1)
        back = await Client.open(self.port)
        await back.send({"t": "resume", "token": seat_b["token"]})
        self.assertEqual((await back.until("error"))["code"], "seat_gone")

    async def test_a_connected_player_is_told_kicked_and_closed_with_4004(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        seat_b = await b.until("seat")
        lobby = await self._host_sees(a, 1)
        await a.send({"t": "kick", "seat": lobby["seats"][0]["id"]})
        self.assertEqual((await b.until("error"))["code"], "kicked")
        after = []
        from websockets.exceptions import ConnectionClosed
        try:
            while True:                                     # everything the kicked socket hears until it is closed
                after.append(json.loads(await asyncio.wait_for(b.ws.recv(), 5)))
        except ConnectionClosed:
            pass
        self.assertEqual(after, [], "a kicked player is not pushed lobbies for a seat they no longer hold")
        self.assertEqual(b.ws.close_code, 4004)
        await self._lobby_count(a, 1)
        again = await Client.open(self.port)
        await again.send({"t": "resume", "token": seat_b["token"]})
        self.assertEqual((await again.until("error"))["code"], "seat_gone")

    async def test_a_guest_can_not_kick_and_nothing_changes(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        await b.until("seat")
        host_view = await self._host_sees(a, 1)
        for handle in (host_view["seats"][0]["id"], "deadbeef", None):
            await b.send({"t": "kick", "seat": handle})
            err = await b.until("error")
            self.assertEqual((err["code"], err["message"]), ("refused", "Only the host can kick."))
        await asyncio.sleep(0.2)
        self.assertEqual((await self._list())[0]["seats_taken"], 2)

    async def test_self_unknown_malformed_stale_and_after_the_start_are_all_refused_calmly(self):
        from arena import views
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        await b.until("seat")
        room = self.server.rooms[seat_a["room_code"]]
        mine = views.seat_handle(room.game, room.host_pid())
        handle_b = (await self._host_sees(a, 1))["seats"][0]["id"]
        cases = [(mine, "yourself"), ("00000000", "not in the room"), ("", "not in the room"), (None, "not in the room"),
                 (123, "not in the room"), (["x"], "not in the room"), ({"a": 1}, "not in the room")]
        for handle, words in cases:
            await a.send({"t": "kick", "seat": handle})
            err = await a.until("error")
            self.assertEqual(err["code"], "refused", f"seat={handle!r}")
            self.assertIn(words, err["message"], f"seat={handle!r}")
        await a.send({"t": "kick"})                                      # no field at all
        self.assertEqual((await a.until("error"))["code"], "refused")
        self.assertEqual((await self._list())[0]["seats_taken"], 2, "nothing was removed by any of those")
        await a.send({"t": "kick", "seat": handle_b})
        await self._lobby_count(a, 1)
        await a.send({"t": "kick", "seat": handle_b})                    # the same handle again: stale
        self.assertIn("not in the room", (await a.until("error"))["message"])
        await a.send({"t": "start"})
        await a.until("round")
        await a.send({"t": "kick", "seat": handle_b})
        self.assertIn("only possible in the lobby", (await a.until("error"))["message"])

    async def test_a_stale_handle_never_hits_the_next_person_who_takes_the_seat(self):
        a, seat_a = await self._camp()
        code = seat_a["room_code"]
        b = await self._join(code)
        await b.until("seat")
        old = (await self._host_sees(a, 1))["seats"][0]["id"]
        await a.send({"t": "kick", "seat": old})
        await self._lobby_count(a, 1)
        c = await self._join(code)                                       # takes the freed pid
        await c.until("seat")
        fresh = (await self._host_sees(a, 1))["seats"][0]["id"]
        self.assertNotEqual(fresh, old, "a new occupant gets a new handle")
        await a.send({"t": "kick", "seat": old})
        self.assertIn("not in the room", (await a.until("error"))["message"])
        await asyncio.sleep(0.2)
        self.assertEqual((await self._list())[0]["seats_taken"], 2, "the newcomer is still there")

    async def test_a_kicked_player_can_join_again_by_code_and_the_host_sees_a_new_handle(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        await b.until("seat")
        first = (await self._host_sees(a, 1))["seats"][0]["id"]
        await a.send({"t": "kick", "seat": first})
        await self._lobby_count(a, 1)
        again = await self._join(seat_a["room_code"])
        await again.until("seat")
        self.assertNotEqual((await self._host_sees(a, 1))["seats"][0]["id"], first)

    async def test_when_the_host_drops_off_the_next_seat_becomes_host_and_can_kick_the_old_one(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        await b.until("seat")
        await self._host_sees(a, 1, connected=True)
        await a.close()
        lobby = await b.until("lobby", lambda m: m["host"] and "seats" in m and m["seats"] and not m["seats"][0]["connected"])
        await b.send({"t": "kick", "seat": lobby["seats"][0]["id"]})
        await self._lobby_count(b, 1)
        gone = await Client.open(self.port)
        await gone.send({"t": "resume", "token": seat_a["token"]})
        self.assertEqual((await gone.until("error"))["code"], "seat_gone")

    async def test_a_kick_reopens_a_full_camp_and_the_host_is_never_left_with_an_empty_room(self):
        a, seat_a = await self._camp()
        code = seat_a["room_code"]
        guests = []
        for _ in range(3):
            g = await self._join(code)
            await g.until("seat")
            guests.append(g)
        self.assertEqual(await self._list(), [])
        lobby = await self._host_sees(a, 3)
        await a.send({"t": "kick", "seat": lobby["seats"][0]["id"]})
        await self._until_listed(code, True)
        lobby = await self._host_sees(a, 2)
        for s in lobby["seats"]:
            await a.send({"t": "kick", "seat": s["id"]})
        await self._lobby_count(a, 1)
        await a.send({"t": "start"})                                     # the room is alive and the host can still start
        await a.until("round")

    async def test_a_kick_survives_a_restart_and_the_log_says_kicked(self):
        a, seat_a = await self._camp()
        b = await self._join(seat_a["room_code"])
        seat_b = await b.until("seat")
        c = await self._join(seat_a["room_code"])
        seat_c = await c.until("seat")
        from arena import views
        from arena.server import token_key
        await self._host_sees(a, 2)
        room = self.server.rooms[seat_a["room_code"]]
        kicked_pid = room.identity.get(token_key(seat_b["token"]))["pid"]
        await a.send({"t": "kick", "seat": views.seat_handle(room.game, kicked_pid)})
        await self._lobby_count(a, 2)
        for cl in (a, b, c):
            await cl.close()
        await self._stop()
        log = os.path.join(self.data, "rooms", seat_a["room_code"], "log.jsonl")
        with open(log, encoding="utf-8") as f:
            recs = [json.loads(line) for line in f if line.strip()]
        self.assertEqual([r.get("kicked") for r in recs if r["type"] == "left_lobby"], [True])
        await self._start()
        for seat in (seat_a, seat_c):
            cl = await Client.open(self.port)
            await cl.send({"t": "resume", "token": seat["token"]})
            self.assertEqual((await cl.until("seat"))["alias"], seat["alias"])
        dead = await Client.open(self.port)
        await dead.send({"t": "resume", "token": seat_b["token"]})
        self.assertEqual((await dead.until("error"))["code"], "seat_gone")
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
