extends BaseTest
## The platform server's additions to the wire (docs/ARENA.md): `hello_ok.games`, `rooms[].game` and the error
## `room_unavailable`. Each is optional: an older server sends none of them and the client must behave exactly as before.


func _camp(code: Variant, game: Variant = null) -> Dictionary:
	var d := {"code": code, "seats_taken": 1, "seats_total": 4, "age_s": 30, "name": ""}
	if game != null:
		d["game"] = game
	return d


func _hello(extra: Dictionary) -> void:
	var m := {"t": "hello_ok", "proto": 1}
	m.merge(extra, true)
	fake.server_send(m)


func _title_with(extra: Dictionary) -> void:
	Intents.rooms_watch(true)
	fake.server_open()
	_hello(extra)


func _good_games() -> Array:
	return [{"id": "survivors", "name": "Survivors", "seats_min": 4, "seats_max": 4},
		{"id": "bang", "name": "Bang!", "seats_min": 3, "seats_max": 8}]


# ---------------- hello_ok.games ----------------

func test_hello_ok_games_are_taken_in() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	_hello({"games": _good_games(), "features": ["list_rooms"]})
	eq(Net.state, "online", "the handshake completed")
	eq(Session.games.size(), 2, "both games kept")
	eq(Session.games[1], {"id": "bang", "name": "Bang!", "seats_min": 3, "seats_max": 8}, "with their seat range")
	eq(Net.server_features, ["list_rooms"], "the features beside them are untouched")


func test_a_hello_ok_without_games_is_an_old_server_not_an_error() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	_hello({})
	eq(Net.state, "online", "the handshake completed")
	eq(Session.games, [], "no games means no picker")
	no_errors()
	check(Log.since(mark, "WARN").is_empty(), "and not even a warning")


func test_games_from_one_connection_do_not_outlive_it() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	_hello({"games": _good_games()})
	eq(Session.games.size(), 2, "first connection offers two")
	Net.reconnect_now()
	fake.server_open()
	_hello({})
	eq(Session.games, [], "the next hello_ok with none clears them: the server we now talk to offers none")


func test_unknown_extra_fields_in_hello_ok_and_in_a_game_entry_do_no_harm() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	var g := _good_games()
	g[0]["future_field"] = {"nested": [1, 2, 3]}
	_hello({"games": g, "something_new": true})
	eq(Net.state, "online", "online")
	eq(Session.games.size(), 2, "the entry with an extra field is still a game")
	no_errors()


func test_hostile_games_never_throw_and_keep_only_what_is_sound() -> void:
	var hostile: Array = [
		null, 7, "bang", [], true,
		{"id": "ok", "name": "Fine", "seats_min": 2, "seats_max": 5},
		{"id": "ok", "name": "Duplicate id", "seats_min": 2, "seats_max": 5},
		{"id": 5, "name": "id is a number", "seats_min": 2, "seats_max": 5},
		{"id": "", "name": "empty id", "seats_min": 2, "seats_max": 5},
		{"id": "has space", "name": "bad chars", "seats_min": 2, "seats_max": 5},
		{"id": "x".repeat(500), "name": "long id", "seats_min": 2, "seats_max": 5},
		{"id": "a1", "name": "no max", "seats_min": 2},
		{"id": "a2", "name": "text seats", "seats_min": "2", "seats_max": "5"},
		{"id": "a3", "name": "bool seats", "seats_min": true, "seats_max": true},
		{"id": "a4", "name": "inverted", "seats_min": 6, "seats_max": 3},
		{"id": "a5", "name": "zero", "seats_min": 0, "seats_max": 4},
		{"id": "a6", "name": "absurd", "seats_min": 2, "seats_max": 99999999},
		{"id": "a7", "name": "fraction", "seats_min": 2.5, "seats_max": 4},
		{"id": "a8", "name": "nan-ish", "seats_min": INF, "seats_max": INF},
		{"id": "named", "name": {"x": 1}, "seats_min": 2, "seats_max": 4},
	]
	var clean := RoomsWatch.sanitize_games(hostile)
	var ids: Array = []
	for g in clean:
		ids.append(g.id)
	eq(ids, ["ok", "named"], "only the sound entries, the first of a repeated id")
	eq(clean[1].name, "named", "a name that is not text falls back to the id, never to a dictionary")
	for bad in [null, 5, "games", {"id": "x"}, true, 1.5]:
		eq(RoomsWatch.sanitize_games(bad), [], "a games value that is not a list is no games: %s" % str(bad))


func test_a_huge_games_list_is_bounded() -> void:
	var many: Array = []
	for i in 5000:
		many.append({"id": "g%d" % i, "name": "G", "seats_min": 2, "seats_max": 4})
	check(RoomsWatch.sanitize_games(many).size() <= RoomsWatch.MAX_GAMES, "at most MAX_GAMES kept")


func test_a_games_name_cannot_smuggle_control_or_direction_characters() -> void:
	var dirty := "Ba" + char(0x202E) + "ng" + char(1) + "!"       # a right-to-left override and a control character
	var clean := RoomsWatch.sanitize_games([{"id": "a", "name": dirty, "seats_min": 2, "seats_max": 4}])
	eq(clean[0].name, "Bang!", "cleaned like a camp name")


# ---------------- rooms[].game ----------------

func test_a_listed_camp_keeps_its_game() -> void:
	_title_with({"features": ["list_rooms"]})
	fake.server_send({"t": "rooms", "rooms": [_camp("KXQM", "bang"), _camp("ABCD")]})
	var rooms: Array = Feed.rooms_model().rooms
	eq(rooms.size(), 2, "both camps listed")
	eq(rooms[0].get("game"), "bang", "the game is kept")
	check(not rooms[1].has("game"), "an older server's entry has no game: none is invented")


func test_a_bad_game_on_a_camp_does_not_cost_the_camp() -> void:
	_title_with({"features": ["list_rooms"]})
	fake.server_send({"t": "rooms", "rooms": [_camp("AAAA", 7), _camp("BBBB", {"x": 1}), _camp("CCCC", "has space"),
		_camp("DDDD", "x".repeat(300)), _camp("EEEE", true)]})
	var rooms: Array = Feed.rooms_model().rooms
	eq(rooms.size(), 5, "every camp is still listed")
	for r in rooms:
		check(not r.has("game"), "%s: an unusable game is dropped, not shown" % r.code)


func test_unknown_extra_fields_on_a_camp_do_not_make_it_unlistable() -> void:
	_title_with({"features": ["list_rooms"]})
	var c := _camp("KXQM", "bang")
	c["mode"] = "future"
	c["players"] = [1, 2]
	fake.server_send({"t": "rooms", "rooms": [c]})
	eq(Feed.rooms_model().rooms.size(), 1, "still listed")


# ---------------- room_unavailable ----------------

func _held_seat() -> void:
	store.data = {"token": "old-seat", "room_code": "ABCD", "alias": "Mango", "server_url": Session.server_url}
	Session.load_store()


func test_a_refused_resume_with_room_unavailable_keeps_the_seat_and_is_not_the_seat_gone_screen() -> void:
	setup()
	_held_seat()
	go_online()
	Session.resume_if_stored()
	var opened := fake.open_urls.size()
	fake.server_send({"t": "error", "code": "room_unavailable", "message": "That room is not available right now."})
	eq(Session.token, "old-seat", "the token is kept")
	eq(Session.room_code, "ABCD", "and the room it belongs to")
	eq(store.data.get("token"), "old-seat", "and so is the stored copy: the seat may come back")
	check(not notices.is_empty(), "the player is told")
	eq(notices.back().code, "room_unavailable", "with its own code")
	eq(notices.back().text, "That room is not available right now.", "and the server's plain words")
	check(notices.back().kind != "terminal", "not a terminal notice")
	check(Session.terminal_reason != "seat_gone", "not the seat-gone reason")
	eq(Session.awaiting_view, false, "the title is not left waiting for a view that will not come")
	eq(fake.open_urls.size(), opened, "the line is not dropped: the server keeps it open")
	eq(Net.state, "online", "still online")


func test_room_unavailable_after_resume_leaves_no_wait_that_kills_the_line_later() -> void:
	setup()
	_held_seat()
	go_online()
	Session.resume_if_stored()
	fake.server_send({"t": "error", "code": "room_unavailable", "message": "x"})
	var opened := fake.open_urls.size()
	clock.advance(Net.ACK_TIMEOUT_MS + 3000)
	Net.tick()
	eq(Net.state, "online", "still on the line well past the ack deadline")
	eq(fake.open_urls.size(), opened, "no reconnect")
	eq(Session.token, "old-seat", "seat still held")


func test_the_seat_can_resume_once_the_room_comes_back() -> void:
	setup()
	_held_seat()
	go_online()
	Session.resume_if_stored()
	fake.server_send({"t": "error", "code": "room_unavailable", "message": "x"})
	var before := fake.count("resume")
	eq(Session.resume_if_stored(), true, "a second resume attempt is allowed")
	eq(fake.count("resume"), before + 1, "and it goes out")
	fake.server_send({"t": "seat", "token": "old-seat", "room_code": "ABCD", "alias": "Mango", "host": false})
	eq(Session.token, "old-seat", "the room is back: same seat")


func test_a_typed_join_refused_with_room_unavailable_is_that_joins_refusal() -> void:
	setup()
	go_online()
	eq(Session.begin("join_room", {"code": "WXYZ"}), "", "the join goes out")
	fake.server_send({"t": "error", "code": "room_unavailable", "message": "That room is not available right now."})
	eq(notices.back().code, "room_unavailable", "told, with its code")
	eq(notices.back().text, "That room is not available right now.", "in the server's words")
	check(notices.back().kind != "terminal", "not terminal")
	eq(Feed.status().screen, "title", "still on the title")
	eq(Session.expecting_seat(), false, "nothing waits for a seat")
	clock.advance(Net.ACK_TIMEOUT_MS + 3000)
	Net.tick()
	eq(Net.state, "online", "no stray wait tears the line down")
	eq(Session.begin("join_room", {"code": "ABCD"}), "", "and the next join goes out")


func test_tapping_a_listed_camp_that_is_unavailable_gets_the_neutral_notice_and_keeps_a_held_seat() -> void:
	setup()
	_held_seat()
	_title_with({"features": ["list_rooms"]})
	fake.server_send({"t": "rooms", "rooms": [_camp("KXQM", "bang")]})
	Intents.join_room("KXQM", true)
	fake.server_send({"t": "error", "code": "room_unavailable", "message": "x"})
	eq(notices.size(), 1, "one notice")
	check(notices[0].kind != "terminal", "not terminal")
	eq(Session.screen, "title", "still on the title")


func test_room_unavailable_in_the_middle_of_a_game_does_not_end_the_seat() -> void:
	# A stray one (a server answering an old request late): nothing about a held, playing seat changes.
	in_round(1)
	var tok: String = Session.token
	var screen: String = Session.screen
	fake.server_send({"t": "error", "code": "room_unavailable", "message": "x"})
	eq(Session.token, tok, "seat kept")
	eq(Session.screen, screen, "screen unchanged")
	check(Session.terminal_reason != "seat_gone", "never the seat-gone reason")


func test_real_seat_gone_codes_still_end_the_seat() -> void:
	# The guard against over-reaching: room_unavailable keeps the seat, these do not.
	for code in ["seat_gone", "bad_token", "room_gone"]:
		setup()
		_held_seat()
		go_online()
		Session.resume_if_stored()
		fake.server_send({"t": "error", "code": code, "message": "x"})
		eq(Session.token, "", "%s still ends the seat" % code)
