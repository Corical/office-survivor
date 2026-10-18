extends BaseTest
## The open-camps list against a fake server that misbehaves in every way a real one (or a hostile one) might: late, early,
## twice, never, with an error, with garbage, with a thousand entries. Nothing here is allowed to crash, to show a "bad
## frame" notice for a list, to keep a connection busy that nothing needs, or to send a field an old server never heard of.

const BIG := 10000


func _camp(code: Variant, taken: Variant = 1, total: Variant = 4, age: Variant = 30, camp_name: Variant = "") -> Dictionary:
	return {"code": code, "seats_taken": taken, "seats_total": total, "age_s": age, "name": camp_name}


## The title screen opens the list: the line comes up, the server says hello, the client asks for the list at once.
func _title_online() -> void:
	Intents.rooms_watch(true)
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})


func _reply(rooms: Variant) -> void:
	fake.server_send({"t": "rooms", "rooms": rooms})


func _model() -> Dictionary:
	return Feed.rooms_model()


func _codes() -> Array:
	return _model().rooms.map(func(r): return r.code)


# ---------------- asking, and when to stop ----------------

func test_opening_the_list_connects_and_asks_at_once() -> void:
	_title_online()
	eq(fake.count("list_rooms"), 1, "asked as soon as the line is up")
	check(not _model().supported, "not supported until the server has answered")
	check(_model().loading, "the list says it is waiting")


func test_a_reply_lights_the_list_up() -> void:
	_title_online()
	_reply([_camp("KXQM", 2, 4, 90, "Fig's camp"), _camp("ABCD")])
	check(_model().supported, "supported")
	eq(_codes(), ["KXQM", "ABCD"], "newest first, as sent")
	eq(_model().rooms[0].name, "Fig's camp", "the name")
	check(not _model().loading and not _model().stale, "settled")


func test_it_asks_again_every_three_seconds_while_showing() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	clock.advance(2900)
	Net.tick()
	eq(fake.count("list_rooms"), 1, "not yet")
	clock.advance(200)
	Net.tick()
	eq(fake.count("list_rooms"), 2, "three seconds on: asked again")
	_reply([_camp("KXQM")])
	clock.advance(3100)
	Net.tick()
	eq(fake.count("list_rooms"), 3, "and again")


func test_a_server_that_never_answers_hides_the_list_after_three_seconds_and_the_line_survives() -> void:
	_title_online()
	clock.advance(2900)
	Net.tick()
	check(_model().loading, "still waiting inside three seconds")
	clock.advance(300)
	Net.tick()
	check(not _model().supported and not _model().loading, "hidden after three seconds of silence")
	# the silence must not be taken for a dead socket: no watchdog drop, no reconnect, however long it goes on
	for i in 40:
		clock.advance(3000)
		Net.tick()
	eq(Net.state, "online", "the line is still up")
	eq(fake.closes, 0, "never dropped for want of a rooms answer")
	check(fake.count("list_rooms") >= 3 and fake.count("list_rooms") < 12, "and it asks only rarely once hidden: %d" % fake.count("list_rooms"))
	no_errors()


func test_a_late_first_answer_from_a_slow_server_lights_the_list_up_again() -> void:
	_title_online()
	clock.advance(3500)
	Net.tick()
	check(not _model().supported, "hidden")
	_reply([_camp("LATE")])
	check(_model().supported, "a real answer, however late, brings it back")
	eq(_codes(), ["LATE"], "with its camp")


func test_an_old_server_that_answers_with_an_error_hides_the_list_without_a_notice() -> void:
	_title_online()
	fake.server_send({"t": "error", "code": "unknown_type", "message": "unknown message type list_rooms"})
	check(not _model().supported and not _model().loading, "no list on this server")
	eq(notices.size(), 0, "and the player is told nothing: a list that is not there is not an error")
	eq(Net.state, "online", "the line is fine")


func test_rate_limited_keeps_the_list_you_have() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	clock.advance(3100)
	Net.tick()
	fake.server_send({"t": "error", "code": "rate_limited", "message": "slow down"})
	check(_model().supported, "still showing the list")
	eq(_codes(), ["KXQM"], "unchanged")
	eq(notices.size(), 0, "no notice")


func test_polling_stops_when_the_list_closes_and_the_idle_line_is_let_go() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.rooms_watch(false)
	for i in 5:
		clock.advance(3100)
		Net.tick()
	eq(fake.count("list_rooms"), 1, "nothing asked after the list closed")
	eq(Net.state, "offline", "and nothing else was using the line, so it was closed")


func test_two_screens_asking_one_leaving_does_not_stop_the_list() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.rooms_watch(true)                          # the rebuilt screen asks before the old one has gone
	Intents.rooms_watch(false)                         # the old one leaves
	check(Session.rooms.watching, "still watching")
	clock.advance(3100)
	Net.tick()
	eq(fake.count("list_rooms"), 2, "and still asking")
	Intents.rooms_watch(false)
	check(not Session.rooms.watching, "the last one leaving stops it")


func test_starting_a_game_stops_the_list() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.create_room()
	fake.server_send({"t": "seat", "token": "t1", "room_code": "ZZZZ", "alias": "Mango", "host": true})
	fake.server_send({"t": "lobby", "room_code": "ZZZZ", "seats_taken": 1, "seats_total": 4, "host": true})
	eq(Session.screen, "lobby", "in the lobby")
	check(not Session.rooms.watching, "the list is over")
	var before := fake.count("list_rooms")
	for i in 5:
		clock.advance(3100)
		Net.tick()
	eq(fake.count("list_rooms"), before, "nothing asked from the lobby")


func test_a_reply_after_leaving_the_screen_is_ignored() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.rooms_watch(false)
	var before := _codes()
	_reply([_camp("LATE1"), _camp("LATE2")])
	eq(_codes(), before, "a list that arrives after the screen closed changes nothing")


func test_nothing_is_asked_while_an_intent_waits_for_its_answer() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.join_room("KXQM", true)
	var before := fake.count("list_rooms")
	for i in 3:
		clock.advance(3100)
		Net.tick()
	eq(fake.count("list_rooms"), before, "an error that answers the join must never be taken for the list's")


# ---------------- reconnects ----------------

func test_a_dropped_line_marks_the_list_stale_and_the_reconnect_asks_again() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	fake.server_close(1006)
	check(_model().stale, "the list we hold is the last one we had")
	check(_model().rooms.size() == 1, "and it is still there to look at")
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("list_rooms"), 2, "asked again as soon as the line was back")
	check(not _model().supported, "the new connection has not proved itself yet")
	_reply([_camp("NEWW")])
	check(_model().supported and not _model().stale, "and it has now")
	eq(_codes(), ["NEWW"], "the fresh list replaced the old")


func test_a_stored_seat_is_not_resumed_behind_the_players_back_but_resume_still_works() -> void:
	Session.token = "stored-token"
	Session.room_code = "OLDR"
	Intents.rooms_watch(true)
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("resume"), 0, "the list opened the line; it does not rejoin a game by itself")
	eq(fake.count("list_rooms"), 1, "but it asks for the list")
	check(Intents.resume(), "the Resume button works on the open line")
	eq(fake.count("resume"), 1, "and resumes on it")
	eq(fake.last("resume").token, "stored-token", "with the stored token")


func test_editing_the_server_address_reconnects_after_the_typing_settles() -> void:
	_title_online()
	Intents.set_server_url("ws://other")
	eq(Net.state, "offline", "the old line is dropped")
	clock.advance(500)
	Net.tick()
	eq(fake.open_urls.back(), "ws://test", "not yet: still typing")
	clock.advance(600)
	Net.tick()
	eq(fake.open_urls.back(), "ws://other", "a second after the last edit, the new address is tried")


# ---------------- create and join ----------------

func test_create_sends_no_new_fields_to_a_server_that_has_not_answered_a_list() -> void:
	Intents.rooms_watch(true)
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})                # connected, but the server has said nothing about rooms
	Intents.create_room("private", "Fig's camp")
	var sent := fake.last("create_room")
	check(not sent.is_empty(), "create_room went out")
	check(not sent.has("visibility") and not sent.has("name"), "with neither field: an old server might reject them: %s" % [sent])


func test_create_sends_visibility_and_name_after_a_valid_reply() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.create_room("private", "  Fig's   camp  ")
	var sent := fake.last("create_room")
	eq(sent.get("visibility"), "private", "visibility")
	eq(sent.get("name"), "Fig's camp", "name, trimmed and tidied")


func test_create_never_sends_a_bad_visibility_or_a_bad_name() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.create_room("secret", "\n\t" + char(0x200e) + "" + char(0x202e) + "")
	var sent := fake.last("create_room")
	check(not sent.has("visibility"), "an unknown visibility is not sent")
	check(not sent.has("name"), "a name that is nothing but control characters is not sent")


func test_create_cuts_a_huge_name_to_24_characters() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.create_room("public", "x".repeat(BIG))
	eq(str(fake.last("create_room").get("name")).length(), 24, "24 characters at most")


func test_plain_create_on_an_old_server_is_exactly_what_it_always_was() -> void:
	go_online()
	Intents.create_room()
	eq(fake.last("create_room"), {"t": "create_room"}, "no extra field at all")


func test_tapping_a_listed_camp_joins_that_code_through_the_normal_path() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.join_room("kxqm", true)
	eq(fake.last("join_room"), {"t": "join_room", "code": "KXQM"}, "the join the player would have typed")


func test_the_camp_filling_between_the_list_and_the_tap_gives_the_neutral_notice_and_a_refresh() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.join_room("KXQM", true)
	fake.server_send({"t": "error", "code": "room_full", "message": "That room is full."})
	eq(notices.size(), 1, "one notice")
	eq(notices[0].code, "camp_unavailable", "the neutral one, not the server's wording")
	var before := fake.count("list_rooms")
	clock.advance(50)
	Net.tick()
	eq(fake.count("list_rooms"), before + 1, "and the list is asked for again at once")
	eq(Session.screen, "title", "still on the title")


func test_a_vanished_camp_and_an_unknown_error_are_both_neutral() -> void:
	for code in ["room_gone", "no_such_room", "something_new_nobody_planned"]:
		setup()
		_title_online()
		_reply([_camp("KXQM")])
		Intents.join_room("KXQM", true)
		fake.server_send({"t": "error", "code": code, "message": "x"})
		eq(notices.size(), 1, "one notice for " + code)
		eq(notices[0].code, "camp_unavailable", "neutral for " + code)
		eq(Session.token, "", "no seat remembered for " + code)


func test_a_refused_typed_code_keeps_the_servers_own_error_path() -> void:
	_title_online()
	_reply([_camp("KXQM")])
	Intents.join_room("WXYZ")
	fake.server_send({"t": "error", "code": "refused", "message": "No such room."})
	eq(notices[0].code, "refused", "typed codes are not the list's business")


# ---------------- hostile input ----------------

func test_a_thousand_entry_list_is_cut_to_twenty() -> void:
	var many := []
	for i in 1000:
		many.append(_camp("R%03d" % i))
	_title_online()
	Session.apply({"t": "rooms", "rooms": many})
	eq(_model().rooms.size(), RoomsWatch.MAX_ROOMS, "twenty at most")
	eq(_codes()[0], "R000", "the first (newest) ones kept, in order")


func test_a_big_list_that_fits_in_a_frame_comes_through_the_wire_cut_to_twenty() -> void:
	var many := []
	for i in 500:
		many.append(_camp("Q%03d" % i, 1, 4, i, "camp number %d" % i))
	_title_online()
	_reply(many)
	eq(_model().rooms.size(), RoomsWatch.MAX_ROOMS, "twenty")
	no_errors()


func test_entries_of_the_wrong_type_or_shape_are_dropped_and_the_rest_kept() -> void:
	_title_online()
	_reply([_camp("GOOD1"), 7, "text", null, [], {"code": 5}, {"code": "NOSEATS"},
		{"code": "BADSEATS", "seats_taken": "1", "seats_total": 4, "age_s": 3},
		{"code": "FLOATY", "seats_taken": 1.5, "seats_total": 4, "age_s": 3},
		{"code": "BOOLY", "seats_taken": true, "seats_total": 4, "age_s": 3},
		{"code": "NOAGE", "seats_taken": 1, "seats_total": 4},
		{"code": "AGESTR", "seats_taken": 1, "seats_total": 4, "age_s": "soon"},
		_camp("GOOD2")])
	eq(_codes(), ["GOOD1", "GOOD2"], "only the two sound entries survive")


func test_negative_full_and_absurd_seat_counts_are_dropped() -> void:
	_title_online()
	_reply([_camp("NEG", -1, 4), _camp("ZEROTOT", 0, 0), _camp("FULL", 4, 4), _camp("OVER", 5, 4),
		_camp("HUGE", 1, 9999999), _camp("NEGTOT", 1, -4), _camp("OK", 3, 4)])
	eq(_codes(), ["OK"], "only the joinable camp is listed")


func test_a_repeated_code_is_listed_once_the_first_wins() -> void:
	_title_online()
	_reply([_camp("DUPE", 1, 4, 10, "first"), _camp("DUPE", 2, 4, 20, "second"), _camp("dupe", 3, 4, 30, "third"), _camp("OTHR")])
	eq(_codes(), ["DUPE", "OTHR"], "once")
	eq(_model().rooms[0].name, "first", "the newest one")


func test_codes_that_are_not_codes_are_dropped() -> void:
	_title_online()
	_reply([_camp(""), _camp("  "), _camp("AB CD"), _camp("AB\nCD"), _camp("<b>X</b>"), _camp("A".repeat(50)), _camp("ok-1"),
		_camp(" ab12 ")])
	eq(_codes(), ["AB12"], "letters and digits only, trimmed and upper-cased")


func test_an_absurd_age_is_shown_as_a_week_and_a_negative_or_nan_one_is_dropped() -> void:
	_title_online()
	_reply([_camp("OLD", 1, 4, 10 * 1000 * 1000 * 1000), _camp("NEGAGE", 1, 4, -5), _camp("FRESH", 1, 4, 0.0)])
	eq(_codes(), ["OLD", "FRESH"], "the negative age entry is gone")
	eq(_model().rooms[0].age_s, RoomsWatch.MAX_AGE_S, "a week at most")
	eq(_model().rooms[1].age_s, 0, "just now")


func test_names_are_made_safe_control_characters_removed_and_cut_at_24() -> void:
	_title_online()
	_reply([_camp("CTRL", 1, 4, 5, "Fi\u0000g\u0007's\ncamp\r\t!"), _camp("BIDI", 1, 4, 5, "evil" + char(0x202e) + "EVIL" + char(0x2066) + "x"),
		_camp("LONG", 1, 4, 5, "y".repeat(BIG)), _camp("SPACY", 1, 4, 5, "   a     b   "), _camp("NUM", 1, 4, 5, 12345),
		_camp("NUL", 1, 4, 5, null), _camp("WORDS", 1, 4, 5, "Corne's very long camp name here")])
	var by := {}
	for r in _model().rooms:
		by[r.code] = r.name
	eq(by.CTRL, "Fig's camp !", "control characters gone")
	eq(by.BIDI, "evilEVILx", "direction overrides gone")
	eq(by.LONG, "y".repeat(24), "ten thousand characters cut to 24")
	eq(by.SPACY, "a b", "spaces tidied")
	eq(by.NUM, "", "a name that is not text is empty")
	eq(by.NUL, "", "null is empty")
	check(str(by.WORDS).length() <= 24, "never longer than 24")
	for n in by.values():
		for i in str(n).length():
			check(str(n).unicode_at(i) >= 32, "no control character survives in '%s'" % n)


func test_a_rooms_frame_that_is_not_a_list_never_crashes_and_never_raises_a_bad_frame_notice() -> void:
	_title_online()
	for bad in ["a string", 42, null, {"code": "X"}, true, 3.5]:
		fake.server_send({"t": "rooms", "rooms": bad})
	fake.server_send({"t": "rooms"})
	fake.server_send({"t": "rooms", "rooms": [], "extra": {"deep": [1, 2, 3]}})
	eq(notices.size(), 0, "no notice for any of it")
	check(_model().supported, "the one valid (empty) list is taken")
	eq(_model().rooms.size(), 0, "empty")
	eq(Net.state, "online", "still up")
	no_errors()


func test_a_non_list_reply_counts_as_no_answer_so_silence_still_hides_the_list() -> void:
	_title_online()
	fake.server_send({"t": "rooms", "rooms": "garbage"})
	check(not _model().supported, "garbage lights nothing up")
	clock.advance(3500)
	Net.tick()
	check(not _model().loading, "and the wait ends")


func test_out_of_order_and_duplicate_lists_the_last_one_wins_and_nothing_breaks() -> void:
	_title_online()
	_reply([_camp("AAAA"), _camp("BBBB")])
	_reply([_camp("CCCC")])
	_reply([_camp("CCCC")])
	_reply([_camp("BBBB"), _camp("AAAA")])
	eq(_codes(), ["BBBB", "AAAA"], "the last frame is what is shown")
	eq(Session.rooms.replies, 4, "each valid one was taken in")


func test_an_unsolicited_rooms_frame_while_not_watching_changes_nothing() -> void:
	go_online()
	Session.apply({"t": "rooms", "rooms": [_camp("KXQM")]})
	eq(_model().rooms.size(), 0, "nobody asked")


# ---------------- the pure parts ----------------

func test_sanitize_is_pure_and_bounded() -> void:
	eq(RoomsWatch.sanitize("nope"), null, "not a list is null, not a crash")
	eq((RoomsWatch.sanitize([]) as Array).size(), 0, "an empty list is an empty list")
	var many := []
	for i in 100000:
		many.append(7)                                # a million-ish junk entries: only MAX_RAW are even looked at
	var t0 := Time.get_ticks_msec()
	RoomsWatch.sanitize(many)
	check(Time.get_ticks_msec() - t0 < 200, "a hostile list is dealt with quickly")


func test_clean_name_and_visibility() -> void:
	eq(RoomsWatch.clean_name("Hello"), "Hello", "plain text unchanged")
	eq(RoomsWatch.clean_name("x".repeat(30)), "x".repeat(24), "24 characters")
	eq(RoomsWatch.clean_name(5), "", "not text")
	eq(RoomsWatch.clean_visibility("public"), "public", "public")
	eq(RoomsWatch.clean_visibility("private"), "private", "private")
	eq(RoomsWatch.clean_visibility("Public"), "", "exact words only")
	eq(RoomsWatch.clean_visibility(null), "", "null")
