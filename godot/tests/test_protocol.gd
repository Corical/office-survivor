extends BaseTest
## Protocol robustness: whatever the wire carries, the client logs it, does not crash and does not change screen
## unless the message is a valid view.


func test_unknown_type_is_ignored_and_reported() -> void:
	in_round()
	fake.server_send({"t": "zzz_future", "x": 1})
	eq(Session.screen, "round", "screen unchanged")
	eq(notices.size(), 1, "one notice")
	eq(notices[0].kind, "unknown", "notice kind")
	check(not Log.since(mark, "WARN").is_empty(), "warning logged")
	no_errors()


func test_garbage_frames_are_dropped() -> void:
	in_round()
	fake.server_raw("this is not json")
	fake.server_raw("[1,2,3]")
	fake.server_raw("{\"t\": 5}")
	fake.server_raw("{\"no_t\": true}")
	fake.server_raw("")
	fake.server_raw("null")
	eq(Session.screen, "round", "screen unchanged")
	eq(Session.view.get("round"), 1, "view unchanged")
	no_errors()


func test_binary_frame_is_logged_not_fatal() -> void:
	in_round()
	fake.binary_received.emit(300)
	eq(Session.screen, "round", "screen unchanged")
	check(not Log.since(mark, "WARN").is_empty(), "binary drop logged")


func test_malformed_round_keeps_previous_view() -> void:
	in_round(2)
	var bad := round_view(3)
	bad.erase("me")
	fake.server_send(bad)
	eq(Session.view.round, 2, "kept round 2")
	var nullsecs := round_view(3)
	nullsecs.seconds_left = null
	fake.server_send(nullsecs)
	eq(Session.view.round, 2, "null seconds_left rejected")
	var noration := round_view(3)
	noration.me.erase("rations")
	fake.server_send(noration)
	eq(Session.view.round, 2, "me without rations rejected")
	var wrongtype := round_view(3)
	wrongtype.legal = "scavenge"
	fake.server_send(wrongtype)
	eq(Session.view.round, 2, "legal of the wrong type rejected")
	eq(notices.filter(func(n): return n.kind == "invalid").size(), 4, "four invalid notices")


func test_malformed_other_views() -> void:
	go_online()
	give_seat()
	fake.server_send({"t": "lobby", "room_code": "ABCD"})
	eq(Session.screen, "title", "lobby without seats rejected")
	fake.server_send({"t": "reveal", "round": 1})
	eq(Session.screen, "title", "reveal without news rejected")
	fake.server_send({"t": "end"})
	eq(Session.screen, "title", "end without results rejected")
	fake.server_send({"t": "seat", "token": 5})
	eq(Session.token, "tok-secret-1", "bad seat did not replace the token")


func test_intent_naming_a_seat_is_refused() -> void:
	in_round()
	var before := fake.sent.size()
	eq(Net.send("pick", {"kind": "steal", "seat": 2}), "forbidden_key", "seat")
	eq(Net.send("pick", {"kind": "steal", "pid": 2}), "forbidden_key", "pid")
	eq(Net.send("pick", {"kind": "steal", "Seat": 2}), "forbidden_key", "case")
	eq(Net.send("pick", {"kind": "steal", "player_id": 2}), "forbidden_key", "player_id")
	eq(fake.sent.size(), before, "nothing reached the wire")


func test_upgrade_required_message_is_terminal() -> void:
	go_online()
	fake.server_send({"t": "upgrade_required", "min_proto": 2, "message": "update"})
	eq(Session.screen, "upgrade", "upgrade screen")
	eq(Net.state, "stopped", "net stopped")
	fake.server_send(round_view(1))
	eq(Session.screen, "upgrade", "later frames ignored")
	Session.apply(round_view(1))
	eq(Session.screen, "upgrade", "even if applied directly")
	clock.advance(60000)
	Net.tick()
	eq(fake.open_urls.size(), 1, "never reconnects")


func test_net_itself_drops_frames_after_a_terminal_stop() -> void:
	# Net must not even emit a message after stopping, independent of Session's own locked_out guard
	go_online()
	fake.server_send({"t": "upgrade_required", "min_proto": 2, "message": "update"})
	var seen := []
	var cb := func(m): seen.append(m.t)
	Net.message_received.connect(cb)
	fake.server_send(round_view(1))
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 1, "seats_total": 4, "host": true})
	Net.message_received.disconnect(cb)
	eq(seen, [], "nothing emitted after the stop")


func test_upgrade_required_by_close_code_alone() -> void:
	go_online()
	fake.server_close(4002, "upgrade_required")      # the message may have been lost to the engine
	eq(Session.screen, "upgrade", "upgrade screen from the close code")
	eq(Net.state, "stopped", "net stopped")
	clock.advance(60000)
	Net.tick()
	eq(fake.open_urls.size(), 1, "never reconnects")


func test_seat_gone_by_close_code_alone() -> void:
	in_round()
	fake.server_close(4001, "seat_gone")
	eq(Session.token, "", "token forgotten")
	eq(store.data.get("token"), "", "forgotten in the store too")
	eq(Session.screen, "title", "back to title")
	eq(notices.back().code, "seat_gone", "notice")


func test_resume_refused_forgets_the_seat() -> void:
	Session.token = "old-token"
	Session.room_code = "ZZZZ"
	check(Session.resume_if_stored(), "resume started")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.types(), ["hello", "resume"], "hello then resume")
	fake.server_send({"t": "error", "code": "refused", "message": "That seat no longer exists."})
	eq(Session.token, "", "token forgotten")
	eq(Session.screen, "title", "title")


func test_ordinary_error_keeps_the_seat_and_shows_a_notice() -> void:
	in_round()
	fake.server_send({"t": "error", "code": "refused", "message": "Pick a move before you lock in."})
	eq(Session.token, "tok-secret-1", "seat kept")
	eq(Session.screen, "round", "same screen")
	eq(notices.back().kind, "error", "notice")
	eq(notices.back().text, "Pick a move before you lock in.", "server text kept as fallback")


func test_taken_over_stops_without_reconnecting() -> void:
	in_round()
	fake.server_send({"t": "error", "code": "taken_over", "message": "This seat was opened on another device."})
	fake.server_close(1000)
	eq(Net.state, "stopped", "stopped")
	eq(Session.token, "tok-secret-1", "seat kept, Title offers resume")
	clock.advance(120000)
	Net.tick()
	eq(fake.open_urls.size(), 1, "did not take the seat back")


func test_oversize_frame_is_bounded() -> void:
	in_round()
	fake.server_close(1009, "Message too big")
	eq(Net.state, "reconnecting", "first time: retry")
	clock.advance(1000)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_close(1009, "Message too big")            # the server re-sends the same oversized view
	eq(Net.state, "stopped", "second time: give up, visibly")
	eq(Session.terminal_reason, "too_big", "reason")
	clock.advance(120000)
	Net.tick()
	eq(fake.open_urls.size(), 2, "no endless loop")


func test_token_never_appears_in_the_log() -> void:
	Net.log_payloads = true
	in_round()
	var joined := "\n".join(Log.since(mark))
	check(not ("tok-secret-1" in joined), "token leaked into the log")
	check("<redacted>" in joined, "payload logging shows the redaction")


func test_numbers_arrive_as_ints() -> void:
	in_round()
	check(typeof(Session.view.round) == TYPE_INT, "round is an int")
	check(typeof(Session.view.gift_amounts[0]) == TYPE_INT, "amounts are ints")
	fake.server_raw("{\"t\":\"round\",\"round\":2,\"rounds\":10,\"seconds_left\":12.5,\"me\":{\"alias\":\"A\"," +
		"\"rations\":3,\"bandit\":false},\"legal\":{},\"gift_amounts\":[],\"my_locked\":false," +
		"\"locked_count\":0,\"seats_total\":4,\"radio_available\":true,\"radio_phrases\":[],\"aliases\":[]}")
	eq(Session.view.seconds_left, 12.5, "fractions survive")
