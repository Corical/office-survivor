extends BaseTest
## Network: reconnect, resume, the watchdogs that notice a dead socket, bounded retries.


func test_reconnect_resumes_with_the_stored_token_and_the_fresh_view_wins() -> void:
	in_round(2)
	var creates_before := fake.count("create_room")        # the one the test helper sent to get a seat
	fake.server_close(1006, "abnormal")
	eq(Net.state, "reconnecting", "banner state")
	check(not Session.picker_open(), "picker closed while reconnecting")
	clock.advance(1000)
	Net.tick()
	eq(fake.open_urls.size(), 2, "reopened after the backoff")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.last("resume").get("token"), "tok-secret-1", "resume carries the token")
	eq(fake.count("create_room"), creates_before, "no other intent after the reconnect")
	fake.server_send({"t": "seat", "token": "tok-secret-1", "room_code": "ABCD", "alias": "Mango", "host": true})
	fake.server_send(round_view(2, true, 100, 3))
	eq(Session.view.locked_count, 3, "the fresh view replaced the old one")
	eq(Session.lock_state(), "locked", "lock kept")


func test_backoff_grows_and_is_capped() -> void:
	go_online()
	var waits: Array = []
	for i in 6:
		var before := fake.open_urls.size()
		fake.server_close(1006)
		var t0 := clock.t
		while fake.open_urls.size() == before and clock.t - t0 < 20000:
			clock.advance(100)
			Net.tick()
		waits.append(clock.t - t0)
	check(waits[0] >= 900 and waits[0] <= 1100, "first wait about 1 s, got %s" % waits[0])
	check(waits[1] >= 1900 and waits[1] <= 2100, "second about 2 s, got %s" % waits[1])
	check(waits[5] >= 7900 and waits[5] <= 8100, "capped at 8 s, got %s" % waits[5])


func test_hello_timeout_retries() -> void:
	Net.connect_to("ws://test")                       # the socket never opens
	clock.advance(5100)
	Net.tick()
	eq(Net.state, "reconnecting", "gave up on this attempt")
	check(fake.closes >= 1, "closed the half-open attempt")
	clock.advance(1100)
	Net.tick()
	eq(fake.open_urls.size(), 2, "tried again")


func test_silence_after_an_intent_means_a_dead_socket() -> void:
	in_round()
	Session.act("lock")
	clock.advance(7900)
	Net.tick()
	eq(Net.state, "online", "not yet")
	clock.advance(200)
	Net.tick()
	eq(Net.state, "reconnecting", "8 s with no view back: reconnecting")


func test_a_view_clears_the_ack_watchdog() -> void:
	in_round()
	Session.act("lock")
	fake.server_send(round_view(1, true))
	clock.advance(60000)
	Net.tick()
	eq(Net.state, "online", "answered in time, nothing to detect")


func test_no_intent_means_no_false_alarm() -> void:
	in_round()
	clock.advance(600000)
	Net.tick()
	eq(Net.state, "online", "a quiet server is not a dead one")


func test_unreachable_server_is_bounded_and_visible() -> void:
	Net.connect_to("ws://test")
	for i in 14:
		clock.advance(9000)
		Net.tick()
	eq(Net.state, "unreachable", "banner says so")
	check(Net.attempt >= 4, "attempts counted")
	var opens := fake.open_urls.size()
	clock.advance(8100)
	Net.tick()
	check(fake.open_urls.size() <= opens + 1, "still retrying slowly, not spinning")


func test_oversize_text_frame_is_dropped_and_bounded() -> void:
	in_round()
	fake.server_raw("{\"t\":\"lobby\",\"pad\":\"" + "x".repeat(70000) + "\"}")
	eq(Session.screen, "round", "the oversize frame changed nothing")
	eq(Net.state, "reconnecting", "first time: reconnect to fetch a fresh view")
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_raw("{\"t\":\"lobby\",\"pad\":\"" + "x".repeat(70000) + "\"}")
	eq(Net.state, "stopped", "second time: stop, visibly")
	eq(Session.terminal_reason, "too_big", "reason")


func test_flapping_connection_stops_with_a_reason_and_keeps_the_seat() -> void:
	in_round()
	for i in 8:
		if Net.state == "stopped":
			break
		fake.server_close(1000)                      # up, then dropped by the server at once (a seat fight)
		clock.advance(9000)
		Net.tick()
		if Net.state != "stopped":
			fake.server_open()
			fake.server_send({"t": "hello_ok", "proto": 1})
	eq(Net.state, "stopped", "gave up")
	eq(Session.terminal_reason, "flapping", "reason")
	eq(Session.token, "tok-secret-1", "seat kept")
	check(fake.open_urls.size() <= 5, "bounded: %d connections" % fake.open_urls.size())


func test_a_connection_that_stays_up_resets_the_backoff() -> void:
	in_round()
	fake.server_close(1006)
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	clock.advance(Net.STABLE_MS + 1000)              # healthy for a while
	fake.server_close(1006)
	clock.advance(1100)                              # back to the first backoff step, not the second
	Net.tick()
	eq(fake.open_urls.size(), 3, "reopened after 1 s again")


func test_a_quick_drop_does_not_reset_the_backoff() -> void:
	in_round()
	fake.server_close(1006)
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_close(1006)                          # dropped at once
	clock.advance(1100)
	Net.tick()
	eq(fake.open_urls.size(), 2, "not yet: the wait grew to 2 s")
	clock.advance(1000)
	Net.tick()
	eq(fake.open_urls.size(), 3, "after 2 s")


func test_connect_to_the_same_url_twice_is_a_no_op() -> void:
	Net.connect_to("ws://test")
	Net.connect_to("ws://test")
	eq(fake.open_urls.size(), 1, "one socket")


func test_send_before_the_handshake_says_why() -> void:
	Net.connect_to("ws://test")
	eq(Net.send("pick", {"kind": "scavenge"}), "not_connected", "reason returned")
	eq(fake.sent.size(), 0, "nothing sent")


func test_close_during_the_handshake_does_not_wedge_the_state() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_close(1006)
	eq(Net.state, "reconnecting", "retrying")
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(Net.state, "online", "online on the second go")
