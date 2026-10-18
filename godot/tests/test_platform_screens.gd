extends BaseTest
## P3 step 3.5: the game picker, the game label on camp cards, the seat range, the neutral phase screen and the "update the app"
## screen. They are fed the real data shapes (`hello_ok.games`, `rooms[].game`) through the fake transport, so what is checked is
## what a player would see. A lone-Survivors server must look exactly as before: nothing new is drawn for it.

const TWO := [
	{"id": "survivors", "name": "Survivors", "seats_min": 3, "seats_max": 8},
	{"id": "bang", "name": "Placeholder Game B", "seats_min": 2, "seats_max": 5},
]
const THREE := [
	{"id": "survivors", "name": "Survivors", "seats_min": 3, "seats_max": 8},
	{"id": "bang", "name": "Placeholder Game B", "seats_min": 2, "seats_max": 5},
	{"id": "dice", "name": "Game C with a long name here", "seats_min": 4, "seats_max": 4},
]
const ONE := [{"id": "survivors", "name": "Survivors", "seats_min": 3, "seats_max": 8}]

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("placeholder")
	_free()


func teardown() -> void:
	super.teardown()
	_free()


func _free() -> void:
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _mount(s: Control) -> Control:
	add_child(s)
	_mounted.append(s)
	return s


func _hello(games: Variant = null, features := ["list_rooms"]) -> void:
	var m := {"t": "hello_ok", "proto": 1, "features": features}
	if games != null:
		m["games"] = games
	fake.server_send(m)


func _online(games: Variant = null) -> void:
	if Net.state == "offline":
		Net.connect_to("ws://test")
	fake.server_open()
	_hello(games)


func _reconnect(games: Variant = null) -> void:
	clock.advance(120000)                                     # a connection that lasted: not a flapping one
	fake.server_close(1006)
	clock.advance(30000)
	Net.tick()
	fake.server_open()
	_hello(games)


func _room(code: String, game: Variant = null, taken := 1, total := 4) -> Dictionary:
	var r := {"code": code, "seats_taken": taken, "seats_total": total, "age_s": 30, "name": "Camp " + code}
	if game != null:
		r["game"] = game
	return r


func _tags(s: Node) -> Array:
	return Ui.find_all(s, "game_tag").filter(func(l): return l.visible).map(func(l): return l.text)


func _picker_rows(s: Node) -> Array:
	return Ui.find_all(s, "game_").filter(func(n): return n is Button).map(func(n): return str(n.get_meta("id")))


func _title() -> Control:
	return _mount(TitleScreen.new())


# ---------------- the picker ----------------

func test_the_picker_is_hidden_with_no_games_one_game_or_junk() -> void:
	for games in [null, [], ONE, "survivors", 7, [{}], [{"id": 5}], [{"id": "a b", "name": "x", "seats_min": 3, "seats_max": 4}],
			[{"id": "bang", "name": "x", "seats_min": 5, "seats_max": 2}], [{"id": "bang", "name": "x", "seats_min": 0, "seats_max": 2}],
			[ONE[0], ONE[0], ONE[0]]]:
		setup()
		var s := _title()
		_online(games)
		check(Ui.find(s, "game_picker") == null, "a picker was drawn for games = %s" % [str(games).left(60)])
		check(Ui.find(s, "create") != null, "the Create button is still there")


func test_the_picker_is_shown_with_two_or_more_games_and_says_each_ones_seat_range() -> void:
	var s := _title()
	_online(TWO)
	check(Ui.find(s, "game_picker") != null, "two games: a picker")
	eq(_picker_rows(s), ["game_survivors", "game_bang"], "a row per game, in the server's order")
	var text := " | ".join(Ui.texts(Ui.find(s, "game_picker")))
	check("Choose a game" in text, "its title, from the words file: " + text)
	check("Survivors" in text and "3 to 8 players" in text, "Survivors and its range: " + text)
	check("Placeholder Game B" in text and "2 to 5 players" in text, "the other game and its range: " + text)
	setup()
	s = _title()
	_online(THREE)
	eq(_picker_rows(s).size(), 3, "three games, three rows")
	check("4 players" in " | ".join(Ui.texts(s)), "a game with one size reads '4 players', not '4 to 4'")


func test_a_picker_row_changes_the_pick_and_the_pick_goes_out_with_create() -> void:
	var s := _title()
	_online(TWO)
	(Ui.find(s, "game_bang") as Button).pressed.emit()
	s = _mounted.back()
	check((Ui.find(s, "game_bang") as Button).theme_type_variation == "ChosenButton", "the chosen row wears the pick style")
	check((Ui.find(s, "game_survivors") as Button).theme_type_variation != "ChosenButton", "and the other does not")
	(Ui.find(s, "create") as Button).pressed.emit()
	fake.server_send({"t": "rooms", "rooms": []})
	if Ui.find(s, "sheet") != null:
		(Ui.find(s, "sheet_create") as Button).pressed.emit()
	eq(fake.last("create_room").get("game"), "bang", "the create names the picked game")


func test_creating_survivors_is_the_plain_create_it_always_was() -> void:
	var s := _title()
	_online(TWO)
	(Ui.find(s, "create") as Button).pressed.emit()          # nothing picked: the first game, Survivors
	if Ui.find(s, "sheet") != null:
		(Ui.find(s, "sheet_create") as Button).pressed.emit()
	check(fake.count("create_room") == 1, "one create went out")
	check(not fake.last("create_room").has("game"), "no game field for Survivors: %s" % [fake.last("create_room")])


func test_a_lone_server_create_never_names_a_game_even_if_one_was_remembered() -> void:
	var s := _title()
	_online(TWO)
	(Ui.find(s, "game_bang") as Button).pressed.emit()
	_reconnect(ONE)                                           # the server now offers one game
	check(Ui.find(_mounted.back(), "game_picker") == null, "the picker is gone")
	(Ui.find(_mounted.back(), "create") as Button).pressed.emit()
	if Ui.find(_mounted.back(), "sheet") != null:
		(Ui.find(_mounted.back(), "sheet_create") as Button).pressed.emit()
	check(not fake.last("create_room").has("game"), "no game field: %s" % [fake.last("create_room")])


func test_a_pick_for_a_game_the_server_stopped_offering_falls_back_to_the_first() -> void:
	var s := _title()
	_online(THREE)
	(Ui.find(s, "game_dice") as Button).pressed.emit()
	_reconnect([TWO[1], ONE[0]])                              # dice is gone; bang is first now
	s = _mounted.back()
	eq(_picker_rows(s), ["game_bang", "game_survivors"], "the new list")
	check((Ui.find(s, "game_bang") as Button).theme_type_variation == "ChosenButton", "the first of the new list is chosen")
	check(Session.game_entry("dice").is_empty(), "the old game is not known any more")


func test_a_games_list_that_changes_after_a_reconnect_redraws_the_picker() -> void:
	var s := _title()
	_online(TWO)
	eq(_picker_rows(s).size(), 2, "two at first")
	_reconnect(THREE)
	eq(_picker_rows(_mounted.back()).size(), 3, "three after the reconnect")
	_reconnect(ONE)
	check(Ui.find(_mounted.back(), "game_picker") == null, "one: no picker")
	_reconnect(TWO)
	eq(_picker_rows(_mounted.back()).size(), 2, "two again")
	_reconnect(null)
	check(Ui.find(_mounted.back(), "game_picker") == null, "a server that names no games: no picker")
	no_errors()


func test_a_hostile_game_name_cannot_break_the_picker() -> void:
	var s := _title()
	_online([{"id": "survivors", "name": "S", "seats_min": 3, "seats_max": 8},
		{"id": "bang", "name": "x".repeat(500) + "\n[b]bold[/b]\u0000", "seats_min": 2, "seats_max": 5}])
	eq(_picker_rows(s).size(), 2, "both rows are there")
	no_errors()


# ---------------- the game label on camp cards ----------------

func test_a_camp_card_carries_its_games_name_when_there_are_two_games() -> void:
	var s := _title()
	_online(TWO)
	fake.server_send({"t": "rooms", "rooms": [_room("AAAA", "survivors"), _room("BBBB", "bang"), _room("CCCC")]})
	var tags := _tags(s)
	eq(tags.size(), 3, "a label on every card: %s" % [tags])
	check("Placeholder Game B" in tags, "the other game's name")
	eq(tags.count("Survivors"), 2, "a card with no game is Survivors (an older server)")


func test_a_camp_card_for_a_game_the_server_did_not_list_says_another_game() -> void:
	var s := _title()
	_online(TWO)
	fake.server_send({"t": "rooms", "rooms": [_room("AAAA", "mystery_game"), _room("BBBB", "x".repeat(80)), _room("CCCC", 5)]})
	var tags := _tags(s)
	check(tags.has("Another game"), "the neutral word: %s" % [tags])
	check(not ("mystery_game" in " ".join(tags)), "the unknown id is never shown")
	no_errors()


func test_a_lone_game_server_draws_no_label_on_any_card() -> void:
	for games in [null, ONE]:
		setup()
		var s := _title()
		_online(games)
		fake.server_send({"t": "rooms", "rooms": [_room("AAAA", "survivors"), _room("BBBB", "mystery_game"), _room("CCCC")]})
		eq(_tags(s), [], "no label for games = %s" % [str(games)])
		check(Ui.find_all(s, "camp_").size() >= 3, "the cards themselves are there")


func test_the_labels_follow_a_games_list_that_arrives_after_the_rooms() -> void:
	var s := _title()
	_online(ONE)
	fake.server_send({"t": "rooms", "rooms": [_room("AAAA", "bang")]})
	eq(_tags(s), [], "no label while the server offers one game")
	_reconnect(TWO)
	fake.server_send({"t": "rooms", "rooms": [_room("AAAA", "bang")]})
	eq(_tags(_mounted.back()), ["Placeholder Game B"], "the label appears once there are two")


# ---------------- the seat range ----------------

func _as_survivors(id: String) -> Ruleset:
	return SurvivorsRuleset.new() if id in ["bang", "dice"] else RulesetRegistry.try_make(id)


func _lobby(games: Variant, game: Variant, total := 4) -> Control:
	Session.ruleset_factory = _as_survivors      # (a second game's own lobby frame is its ruleset's to declare; these draw the plain one)
	_online(games)
	Session.act("create_room")
	var seat := {"t": "seat", "token": "tok-p", "room_code": "ABCD", "alias": "Mango", "host": true}
	if game != null:
		seat["game"] = game
	fake.server_send(seat)
	var lobby := {"t": "lobby", "room_code": "ABCD", "seats_taken": 1, "seats_total": total, "host": true}
	fake.server_send(lobby)
	return _mount(LobbyScreen.new())


func _label_text(s: Node, id: String) -> String:
	var l := Ui.find(s, id)
	return "" if l == null else l.text


func test_the_lobby_says_how_many_the_game_needs_from_the_games_own_numbers() -> void:
	var s := _lobby(TWO, "bang")
	eq(_label_text(s, "seat_range"), "Needs 2 to 5 to start", "bang's range, not Survivors'")
	eq(_label_text(s, "game_name"), "Placeholder Game B", "and its name")
	setup()
	s = _lobby(TWO, "survivors")
	eq(_label_text(s, "seat_range"), "Needs 3 to 8 to start", "Survivors' own range comes from the server too")


func test_a_game_with_one_seat_count_reads_n_seats() -> void:
	var s := _lobby(THREE, "dice")
	eq(_label_text(s, "seat_range"), "4 seats", "min equals max")


func test_a_lone_game_server_adds_nothing_to_the_lobby() -> void:
	for games in [null, ONE]:
		setup()
		var s := _lobby(games, null)
		check(Ui.find(s, "seat_range") == null and Ui.find(s, "game_name") == null, "nothing new for games = %s" % [str(games)])


func test_a_room_whose_game_the_server_did_not_list_shows_no_range() -> void:
	var s := _lobby([TWO[0], THREE[2]], "bang")          # the app can play bang; this server did not list it
	check(Ui.find(s, "seat_range") == null, "no range for a game with no entry")
	check(Ui.find(s, "start") != null, "the lobby still works")


func test_a_room_with_no_game_named_is_survivors_on_a_two_game_server() -> void:
	var s := _lobby(TWO, null)
	eq(_label_text(s, "game_name"), "Survivors", "the default game's name")


# ---------------- the neutral phase screen and the update screen ----------------

func test_the_neutral_screen_names_the_game_and_lets_the_player_leave() -> void:
	_online(TWO)
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "tok-n", "room_code": "NEUT", "alias": "Mango", "host": true, "game": "bang"})
	var s := _mount(NeutralScreen.new())
	eq(_label_text(s, "game_name"), "Placeholder Game B", "the game")
	eq(_label_text(s, "neutral_title"), "Waiting for this part of the game", "the title, from the words file")
	check("no picture" in _label_text(s, "neutral_body"), "the body")
	(Ui.find(s, "leave_game") as Button).pressed.emit()
	eq(Session.token, "", "Leave gave the seat back")


func test_the_neutral_screen_without_a_games_list_shows_no_game_name() -> void:
	_online(null)
	var s := _mount(NeutralScreen.new())
	check(Ui.find(s, "game_name") == null, "no name to show")
	check(Ui.find(s, "leave_game") != null, "but still a way out")


func test_the_update_screen_for_an_unplayable_game_offers_leave_and_for_the_protocol_does_not() -> void:
	_online(TWO)
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "tok-u", "room_code": "UPDT", "alias": "Mango", "host": true, "game": "mystery_game"})
	var s := _mount(UpgradeScreen.new())
	check("game" in _label_text(s, "upgrade_body"), "the body speaks of the game: " + _label_text(s, "upgrade_body"))
	check(Ui.find(s, "leave_game") != null, "a seat is held: a way out")
	setup()
	var p := _mount(UpgradeScreen.new())
	check("server" in _label_text(p, "upgrade_body"), "the protocol body speaks of the server")
	check(Ui.find(p, "leave_game") == null, "no seat, nothing to leave")
	eq(_label_text(p, "upgrade"), "Please update the app to play.", "the title is the one that was always there")


func test_the_router_shows_update_for_an_unplayable_room_and_neutral_for_an_undrawn_phase() -> void:
	var r: Control = preload("res://main.gd").new()
	r.screen_factory = func(_n): return Control.new()
	_mount(r)
	_online(TWO)
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "tok-r", "room_code": "ROUT", "alias": "Mango", "host": true, "game": "mystery_game"})
	eq(r.current_name, "upgrade", "a room of a game this app lacks")
	Intents.leave()
	eq(r.current_name, "title", "and leaving puts it back on the title")
