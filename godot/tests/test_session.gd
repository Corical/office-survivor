extends BaseTest
## Session: intents, double taps, the lock, the seat token, stale intents. Written to break the code: worst-case
## order, repeats, state left over from a previous room.


func test_create_with_a_stored_seat_sends_create_not_resume() -> void:
	Session.token = "old"
	Session.room_code = "OLDR"
	Session.begin("create_room")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.types(), ["hello", "create_room"], "the tap was not swallowed by a resume")
	eq(Session.token, "", "old seat forgotten")


func test_create_while_online_in_a_room_starts_over() -> void:
	in_round()
	var creates_before := fake.count("create_room")        # the one the test helper sent to get the first seat
	Session.begin("create_room")
	eq(Net.state, "connecting", "old connection closed, new one opening")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("create_room"), creates_before + 1, "exactly one new create sent")
	eq(fake.count("resume"), 0, "no resume with the old seat")


func test_double_tap_create_before_the_handshake_opens_one_socket() -> void:
	Session.begin("create_room")
	Session.begin("create_room")
	eq(fake.open_urls.size(), 1, "one socket")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("create_room"), 1, "one room")


func test_double_tap_create_after_the_handshake_sends_once() -> void:
	go_online()
	eq(Session.begin("create_room"), "", "first goes")
	eq(Session.begin("create_room"), "in_flight", "second refused")
	eq(fake.count("create_room"), 1, "one room")


func test_every_intent_sends_once_until_the_server_answers() -> void:
	in_round()
	for t in ["start", "radio"]:
		eq(Session.act(t, {"phrase": "me"} if t == "radio" else {}), "", t + " first")
		eq(Session.act(t, {"phrase": "me"} if t == "radio" else {}), "in_flight", t + " second")
	eq(Session.pick("steal", "Fig"), "", "pick first")
	eq(Session.pick("steal", "Fig"), "in_flight", "same pick twice")
	eq(Session.pick("steal", "Kiwi"), "", "a different pick is a change of mind")
	fake.server_send(round_view(1))          # the server answered: the guards clear
	eq(Session.act("start"), "", "start allowed again after a view")


func test_pending_intent_is_cleared_by_leave_and_close() -> void:
	Session.begin("join_room", {"code": "ABCD"})
	check(Session.pending_intent != {}, "pending while connecting")
	Session.leave()
	eq(Session.pending_intent, {}, "cleared by leave")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("join_room"), 0, "abandoned intent never replayed")


func test_pending_intent_expires() -> void:
	Session.begin("join_room", {"code": "ABCD"})
	clock.advance(11000)
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("join_room"), 0, "a tap from 11 s ago is not replayed")


func test_lock_double_tap_and_stale_view() -> void:
	in_round(3)
	eq(Session.lock_state(), "open", "open")
	check(Session.picker_open(), "picker open")
	eq(Session.act("lock"), "", "first lock")
	eq(Session.act("lock"), "in_flight", "second lock")
	eq(fake.count("lock"), 1, "one lock on the wire")
	eq(Session.lock_state(), "sent", "sent")
	check(not Session.picker_open(), "picker closed once we sent")
	fake.server_send(round_view(3, false, 170))        # a racing view that has not seen the lock yet
	eq(Session.lock_state(), "sent", "stale view does not re-open it")
	check(not Session.picker_open(), "picker still closed")
	fake.server_send(round_view(3, true, 165))
	eq(Session.lock_state(), "locked", "locked")
	fake.server_send(round_view(3, false, 160))        # a buggy server un-locks: we still never re-open locally
	eq(Session.lock_state(), "sent", "our own guard keeps the picker closed for this round")
	check(not Session.picker_open(), "picker stays closed")
	eq(Session.act("lock"), "in_flight", "and no second lock goes out")


func test_new_round_reopens_the_picker() -> void:
	in_round(3)
	Session.act("lock")
	fake.server_send(round_view(3, true))
	fake.server_send(round_view(4))
	eq(Session.lock_state(), "open", "round 4 is open")
	eq(Session.act("lock"), "", "lock works in round 4")


func test_rejected_lock_reopens_the_picker() -> void:
	in_round()
	Session.act("lock")
	fake.server_send({"t": "error", "code": "refused", "message": "Pick a move before you lock in."})
	eq(Session.lock_state(), "open", "open again")
	eq(Session.act("lock"), "", "can try again")


func test_lock_works_in_a_new_room_after_the_seat_was_lost() -> void:
	in_round(3)
	Session.act("lock")
	fake.server_close(4001, "seat_gone")
	Session.begin("create_room")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	give_seat("tok-2", "WXYZ")
	fake.server_send(round_view(3))
	eq(Session.act("lock"), "", "round 3 of the NEW room can be locked")
	eq(fake.count("lock"), 2, "two locks on the wire, one per room")


func test_reply_to_a_lock_with_a_pick_view_does_not_clear_the_lock_guard() -> void:
	in_round()
	Session.act("lock")
	fake.server_send(round_view(1))          # an unrelated push (someone else locked)
	eq(Session.act("lock"), "in_flight", "still guarded")


func test_continue_sends_once_per_round() -> void:
	in_round(2)
	fake.server_send({"t": "reveal", "round": 2, "news": [], "private": [], "radio": [], "board": null,
		"seconds_left": 20})
	eq(Session.screen, "reveal", "reveal")
	eq(Session.act("continue"), "", "first")
	eq(Session.act("continue"), "in_flight", "second")
	eq(fake.count("continue"), 1, "one continue")


func test_seat_is_stored_and_redacted() -> void:
	go_online()
	give_seat("tok-xyz", "QRST")
	eq(store.data.get("token"), "tok-xyz", "stored")
	eq(store.data.get("room_code"), "QRST", "room stored")
	eq(Session.alias, "Mango", "alias")
	check(store.saves >= 1, "saved")


func test_lobby_carries_host_and_code() -> void:
	go_online()
	give_seat("t", "ABCD", false)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 2, "seats_total": 4, "host": true})
	eq(Session.screen, "lobby", "lobby")
	eq(Session.host, true, "host updated by the lobby message")


func test_leave_forgets_everything() -> void:
	in_round()
	Session.leave()
	eq(Session.token, "", "token")
	eq(Session.screen, "title", "screen")
	eq(Session.view, {}, "view")
	eq(fake.last("leave").t, "leave", "leave sent")
	eq(Net.state, "offline", "closed")


func test_timer_follows_the_clock_not_the_phone() -> void:
	in_round(1)
	eq(Session.seconds_left_now(), 180, "at the start")
	clock.advance(30000)
	eq(Session.seconds_left_now(), 150, "30 s later")
	clock.advance(500000)
	eq(Session.seconds_left_now(), 0, "never negative")
	check(not Session.picker_open(), "picker closes when the time is up")


func test_before_state_is_kept_for_the_reveal() -> void:
	in_round(5)
	fake.server_send(round_view(5, true, 3))
	eq(Session.before_state_for(5).get("round"), 5, "round 5 view available")
	eq(Session.before_state_for(4), {}, "nothing invented for another round")
