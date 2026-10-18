extends BaseTest
## The host removes a seat that dropped off (server note "the host can kick"). The host points at a seat with an opaque handle
## from the LATEST lobby message; the removed player gets `error kicked` and a close with 4004 (either alone must be enough:
## the engine can drop the last frame before a close). Everything a hostile or confused server could send is covered here.


func _lobby(seats: Variant, host := true, taken := 3) -> Dictionary:
	var m := {"t": "lobby", "room_code": "ABCD", "seats_taken": taken, "seats_total": 4, "host": host}
	if seats != null:
		m["seats"] = seats
	return m


func _host_lobby(seats: Variant = null) -> void:
	go_online()
	give_seat("tok", "ABCD", true)
	fake.server_send(_lobby(seats if seats != null else [{"id": "h-aaaa", "connected": true}, {"id": "h-bbbb", "connected": false}]))


func _model() -> Dictionary:
	return Feed.models.get("lobby", {})


func _ids() -> Array:
	return _model().seats.map(func(s): return s.id)


# ---------------- the seats the host sees ----------------

func test_the_host_sees_the_other_seats_with_who_is_connected() -> void:
	_host_lobby()
	eq(_ids(), ["h-aaaa", "h-bbbb"], "one entry per other seat, in the server's order")
	eq(_model().seats[0].connected, true, "here")
	eq(_model().seats[1].connected, false, "dropped off")
	check(_model().is_host, "host")


func test_a_guest_never_gets_a_seat_list_even_if_the_server_sends_one() -> void:
	go_online()
	give_seat("tok", "ABCD", false)
	fake.server_send(_lobby([{"id": "x-1", "connected": true}], false))
	eq(_model().seats, [], "guests have no kick handles to hold")


func test_a_lobby_without_seats_is_an_empty_list_not_a_crash() -> void:
	_host_lobby([])
	eq(_model().seats, [], "empty")
	fake.server_send(_lobby(null))
	eq(_model().seats, [], "absent field")


func test_hostile_seat_lists_never_crash_and_never_show_junk() -> void:
	var cases := [
		"not a list", 7, {"id": "x"}, null, [null, 1, "s", [], {}], [{"id": ""}], [{"id": 5, "connected": true}],
		[{"id": "ok", "connected": "yes"}], [{"id": "x".repeat(10000), "connected": true}], [{"connected": true}],
		[{"id": "dup", "connected": true}, {"id": "dup", "connected": false}],
	]
	for c in cases:
		setup()
		go_online()
		give_seat("tok", "ABCD", true)
		fake.server_send(_lobby(c))
		var ids := _ids()
		check(ids.size() <= 12, "bounded: %s" % [c])
		for id in ids:
			check(id is String and id != "" and id.length() <= 64, "only clean ids survive: %s" % [id])
		check(ids.size() == ids.duplicate().size() and _unique(ids), "no duplicate handle: %s" % [ids])
		check(Session.view.get("t") == "lobby", "the lobby itself still arrived: %s" % [c])


func _unique(a: Array) -> bool:
	var seen := {}
	for x in a:
		if seen.has(x):
			return false
		seen[x] = true
	return true


func test_a_thousand_seats_are_cut_to_a_camp_sized_list() -> void:
	var many: Array = []
	for i in 1000:
		many.append({"id": "s-%d" % i, "connected": true})
	_host_lobby(many)
	check(_model().seats.size() <= 12, "no camp has more seats than that")


func test_an_unclear_connected_flag_counts_as_here_never_as_dropped() -> void:
	_host_lobby([{"id": "a", "connected": "no"}, {"id": "b"}, {"id": "c", "connected": null}])
	for s in _model().seats:
		eq(s.connected, true, "%s: unclear means here (a wrong 'dropped' would invite a wrong kick)" % s.id)


# ---------------- sending a kick ----------------

func test_kick_sends_exactly_the_handle_from_the_latest_lobby() -> void:
	_host_lobby()
	eq(Intents.kick("h-bbbb"), "", "goes out")
	var sent := fake.last("kick")
	eq(sent.get("seat"), "h-bbbb", "the handle, as given")
	eq(sent.keys().size(), 2, "only t and seat: %s" % [sent.keys()])


func test_a_stale_or_made_up_handle_is_refused_locally_and_sends_nothing() -> void:
	_host_lobby()
	for bad in ["h-gone", "", "H-AAAA", "h-aaaa ", "x".repeat(500)]:
		eq(Intents.kick(bad), "unknown_seat", "not in the latest lobby: '%s'" % bad.left(20))
	eq(fake.count("kick"), 0, "nothing went to the server")


func test_a_handle_from_an_earlier_lobby_is_not_reused_after_the_list_changed() -> void:
	_host_lobby()
	fake.server_send(_lobby([{"id": "h-cccc", "connected": false}], true, 2))
	eq(Intents.kick("h-bbbb"), "unknown_seat", "the old handle is dead the moment a newer lobby arrives")
	eq(Intents.kick("h-cccc"), "", "the new one works")


func test_only_the_host_in_the_lobby_can_kick() -> void:
	go_online()
	give_seat("tok", "ABCD", false)
	fake.server_send(_lobby([{"id": "g-1", "connected": false}], false))
	eq(Intents.kick("g-1"), "not_host", "a guest")
	setup()
	in_round(1)
	eq(Intents.kick("h-aaaa"), "not_in_lobby", "during the game")
	eq(fake.count("kick"), 0, "nothing sent in either case")


func test_a_double_tap_sends_one_kick() -> void:
	_host_lobby()
	eq(Intents.kick("h-bbbb"), "", "first")
	eq(Intents.kick("h-bbbb"), "in_flight", "second tap while the first is unanswered")
	eq(fake.count("kick"), 1, "one on the wire")


func test_the_next_lobby_frees_the_guard_so_a_second_kick_can_go() -> void:
	_host_lobby([{"id": "a", "connected": false}, {"id": "b", "connected": false}])
	Intents.kick("a")
	fake.server_send(_lobby([{"id": "b2", "connected": false}], true, 2))
	eq(Intents.kick("b2"), "", "free again after the lobby that answers the kick")
	eq(fake.count("kick"), 2, "two kicks in total, one each")


func test_a_kick_the_server_never_answers_does_not_cost_the_connection() -> void:
	_host_lobby()
	Intents.kick("h-bbbb")
	clock.advance(Net.ACK_TIMEOUT_MS + 3000)
	Net.tick()
	eq(Net.state, "online", "no reply is expected, so no ack timeout may drop the line")


func test_the_seat_field_is_allowed_for_kick_and_nowhere_else() -> void:
	go_online()
	eq(Net.send("pick", {"kind": "guard", "seat": "x"}), "forbidden_key", "a pick must never carry a seat")
	eq(Net.send("kick", {"seat": "x", "pid": "y"}), "forbidden_key", "kick may carry its handle but not a pid")
	eq(Net.send("kick", {"seat": "x", "player": "y"}), "forbidden_key", "nor a player")
	eq(Net.send("kick", {"seat": "x", "seat_id": "y"}), "forbidden_key", "nor a seat_id")
	eq(Net.send("kick", {"Seat": "x"}), "forbidden_key", "only the exact lowercase 'seat' the server names is allowed")
	eq(Net.send("kick", {"seat": "x"}), "", "the handle alone is fine")


# ---------------- refusals ----------------

func test_a_seat_that_left_first_is_silent_and_waits_for_the_next_lobby() -> void:
	_host_lobby()
	Intents.kick("h-bbbb")
	var before := notices.size()
	fake.server_send({"t": "error", "code": "refused", "message": "That seat is not in the room any more."})
	eq(notices.size(), before, "nothing to tell the host: the list changed under them")
	eq(Session.token, "tok", "and the host keeps their seat")
	fake.server_send(_lobby([{"id": "h-aaaa", "connected": true}], true, 2))
	eq(Intents.kick("h-aaaa"), "", "the guard was released")


func test_other_refusals_are_shown_in_the_servers_words() -> void:
	for text in ["Only the host can kick.", "You can't kick yourself; use leave.", "Kicking is only possible in the lobby."]:
		setup()
		_host_lobby()
		Intents.kick("h-bbbb")
		var before := notices.size()
		fake.server_send({"t": "error", "code": "refused", "message": text})
		check(notices.size() > before, "told: %s" % text)
		eq(Session.token, "tok", "a refusal never costs the host the seat: %s" % text)


# ---------------- the player who was removed ----------------

func _kicked_player() -> void:
	go_online()
	give_seat("mine", "ABCD", false)
	fake.server_send(_lobby(null, false, 2))


func test_error_kicked_forgets_the_seat_and_goes_to_the_title() -> void:
	_kicked_player()
	fake.server_send({"t": "error", "code": "kicked", "message": "x"})
	eq(Session.token, "", "the seat is forgotten")
	eq(store.data.get("token", ""), "", "and the stored copy")
	eq(Feed.status().screen, "title", "back on the title screen")
	eq(Session.terminal_reason, "kicked", "the reason is state, so the title can say it")
	check(not Feed.status().has_seat, "no Resume offered")


func test_close_4004_alone_is_enough_when_the_message_was_lost() -> void:
	_kicked_player()
	fake.server_close(4004, "kicked")
	eq(Session.token, "", "forgotten on the close code alone")
	eq(Session.terminal_reason, "kicked", "same reason")
	eq(Feed.status().screen, "title", "same screen")


func test_both_the_message_and_the_close_end_it_once() -> void:
	_kicked_player()
	var before := notices.size()
	fake.server_send({"t": "error", "code": "kicked", "message": "x"})
	fake.server_close(4004, "kicked")
	var terminal_notices := 0
	for n in notices.slice(before):
		if n.kind == "terminal":
			terminal_notices += 1
	eq(terminal_notices, 1, "told once, not twice")


func test_a_removed_player_is_never_reconnected_in_the_background() -> void:
	_kicked_player()
	fake.server_send({"t": "error", "code": "kicked", "message": "x"})
	fake.server_close(4004, "kicked")
	var opened := fake.open_urls.size()
	clock.advance(60000)
	Net.tick()
	eq(fake.open_urls.size(), opened, "the client does not knock again by itself")
	eq(Net.state, "stopped", "the line stays down")


func test_a_removed_player_can_join_again_by_code() -> void:
	_kicked_player()
	fake.server_send({"t": "error", "code": "kicked", "message": "x"})
	eq(Session.begin("join_room", {"code": "ABCD"}), "", "nothing blocks a fresh join (the server has no ban)")
	eq(Session.terminal_reason, "", "the old reason is cleared by the new attempt")


func test_a_kick_while_in_the_game_is_not_a_thing_the_client_invents() -> void:
	in_round(2)
	fake.server_send({"t": "error", "code": "kicked", "message": "x"})
	eq(Session.token, "", "if the server says kicked, believe it: the seat is gone")
	eq(Feed.status().screen, "title", "and leave the game screen")


func test_the_title_says_why_in_words() -> void:
	_kicked_player()
	fake.server_send({"t": "error", "code": "kicked", "message": "x"})
	var s := TitleScreen.new()
	add_child(s)
	var n := Ui.find(s, "notice")
	check(n != null, "there is a notice on the title")
	if n != null:
		check((n as Label).text != "" and not ("notice." in (n as Label).text), "words, not a key: %s" % (n as Label).text)
		check("host" in (n as Label).text.to_lower(), "it says the host did it: %s" % (n as Label).text)
	s.free()
