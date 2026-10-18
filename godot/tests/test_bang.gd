extends BaseTest
## Bang! The Dice Game on the client: the ruleset's model, the table and end screens. Every test tries to break one thing: a role that
## is not public, a seat out of reach offered as a target, a dynamite die that can be let go, a frame out of order or from nobody,
## a table of 3 or 8 seats that overlaps, a press that lands on a rebuilt button.

const SIZES := [Vector2(360, 640), Vector2(412, 915), Vector2(1904, 1001)]
const HIT := {"face": "shoot1", "locked": false}

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("flash")


func teardown() -> void:
	super.teardown()
	Themes.use("placeholder")
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


# ---------------- frames ----------------

func _dice(faces: Array = ["arrow", "dynamite", "shoot1", "beer", "gatling"]) -> Array:
	return faces.map(func(f): return {"face": f, "locked": f == "dynamite"})


## A server `view` frame. `me` is my table position; seat 0 is the Sheriff; every other role is hidden (null) unless dead.
func _view(opts := {}) -> Dictionary:
	var n: int = opts.get("n", 5)
	var me: int = opts.get("me", 2)
	var phase: String = opts.get("phase", "roll")
	var turn: Variant = opts.get("turn", me)
	var players: Array = []
	for i in n:
		var dead: bool = i in opts.get("dead", [])
		players.append({"at": i, "name": "Player %d" % (i + 1), "life": 0 if dead else 8, "max": 10 if i == 0 else 8,
			"arrows": 0, "alive": not dead, "away": false, "role": "sheriff" if i == 0 else ("outlaw" if dead else null)})
	var can := {"roll": false, "reroll": false, "stop": false, "target": null}
	can.merge(opts.get("can", {}), true)
	var v := {"t": "view", "game": "bang", "phase": phase, "phase_id": "p-%s" % opts.get("pid", opts.get("seq", 1)),
		"seq": opts.get("seq", 1), "n": n, "you": {"at": me, "role": opts.get("role", "outlaw")}, "players": players,
		"turn": turn, "pile": 9, "rolls": opts.get("rolls", 1), "rolls_max": 3, "dice": opts.get("dice", _dice()),
		"pending": opts.get("pending"), "assigned": opts.get("assigned", []), "can": can, "log": opts.get("log", []),
		"winner": opts.get("winner"), "deadline": null}
	if opts.has("players"):
		v["players"] = opts.players
	return v


func _room(code := "BANG") -> void:
	go_online()
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "tok-bang", "room_code": code, "alias": "Player 3", "host": true, "game": "bang"})


func _send(opts := {}) -> void:
	fake.server_send(_view(opts))


func _acts() -> Array:
	return fake.sent.filter(func(m): return m.t == "act")


func _model() -> Dictionary:
	return Feed.models.get("view", {})


func _mount(screen: Control, size: Vector2) -> Control:
	var holder := Control.new()
	holder.theme = Themes.current.godot_theme
	holder.size = size
	add_child(holder)
	holder.add_child(screen)
	_mounted.append(holder)
	return holder


func _settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame


func _button(screen: Node, id: String) -> Button:
	var n := Ui.find(screen, id)
	return n if n is Button else null


# ---------------- declarations ----------------

func test_the_game_is_registered_and_declares_its_phases_verbs_and_a_screen_for_each_phase() -> void:
	check(RulesetRegistry.has("bang"), "registered")
	var r := BangRuleset.new()
	var routable: Array = load("res://main.gd").get_script_constant_map().SCREENS.keys()
	for p in r.phases():
		var screen: String = r.phases()[p].screen
		check(screen == "lobby" or screen in routable, "phase %s names screen %s that the router does not have" % [p, screen])
	var names := r.verbs().keys()
	names.sort()
	eq(names, ["reroll", "roll", "stop", "target"], "the server's four verbs")
	eq(VerbCheck.check(r.verbs(), "reroll", {"keep": 31}), "", "keep 31 is the largest mask")
	eq(VerbCheck.check(r.verbs(), "reroll", {"keep": 32}), "bad_args", "a sixth die does not exist")
	eq(VerbCheck.check(r.verbs(), "reroll", {"keep": -1}), "bad_args", "negative mask")
	eq(VerbCheck.check(r.verbs(), "reroll", {"keep": "3"}), "bad_args", "mask as text")
	eq(VerbCheck.check(r.verbs(), "reroll", {"keep": true}), "bad_args", "mask as bool")
	eq(VerbCheck.check(r.verbs(), "target", {"at": 8}), "bad_args", "a ninth seat")
	eq(VerbCheck.check(r.verbs(), "target", {"seat": 1}), "forbidden_arg", "a seat named like a seat")
	eq(VerbCheck.check(r.verbs(), "target", {}), "bad_args", "target needs a seat")
	eq(VerbCheck.check(r.verbs(), "roll", {"at": 1}), "bad_args", "roll takes nothing")


func test_every_key_the_game_emits_is_in_its_words_file_and_nothing_else_is() -> void:
	var t: Translation = load(BangRuleset.new().words_path())
	check(t != null, "words.po loads")
	var have := {}
	for k in t.get_message_list():
		if str(k) != "":
			have[str(k)] = true
	var want := {}
	for k in BangRuleset.KEYS:
		want[k] = true
		check(have.has(k), "words.po lacks %s" % k)
	for k in have:
		check(want.has(k), "words.po has %s that nothing emits" % k)
	for k in BangRuleset.KEYS:
		check(Words.has(k), "Words cannot find %s through the theme" % k)
		check(not Words.render(k).begins_with("["), "%s renders as a hole" % k)


func test_the_theme_files_are_untouched_by_the_game() -> void:
	for p in ["res://themes/flash/words.po", "res://themes/placeholder/words.po"]:
		check(not ("bang." in FileAccess.get_file_as_string(p)), "%s carries a bang key" % p)


# ---------------- the model ----------------

func test_a_role_that_is_not_public_never_reaches_the_model() -> void:
	var r := BangRuleset.new()
	# a hostile or buggy frame that carries an Outlaw's role on a living seat and a Deputy's role on another
	var v := _view({"n": 5, "me": 2})
	v.players[1].role = "outlaw"
	v.players[3].role = "deputy"
	v.players[4].role = "renegade"
	var m := r.view_model(v)
	for s in m.seats:
		match s.at:
			0: eq(s.role, "sheriff", "the Sheriff is public")
			2: eq(s.role, "outlaw", "my own role, from `you`")
			_: eq(s.role, "", "seat %d is a living non-Sheriff: its role stays hidden" % s.at)
	# the same frame as a 3-seat game shows all, and as a finished game shows all, and a dead seat shows its role
	v.n = 3
	for s in r.view_model(v).seats:
		check(s.role != "" or s.at == 2, "3 seats: roles are face up (seat %d)" % s.at)
	v.n = 5
	v.phase = "over"
	for s in r.view_model(v).seats:
		check(s.role != "", "game over: every role shows (seat %d)" % s.at)
	v.phase = "roll"
	v.players[1].alive = false
	eq(r.view_model(v).seats[1].role, "outlaw", "an eliminated seat shows its role")


func test_my_own_role_comes_from_you_even_when_my_seat_row_says_something_else() -> void:
	var v := _view({"me": 2, "role": "renegade"})
	v.players[2].role = "sheriff"          # a frame that contradicts itself must not make me the Sheriff
	var m := BangRuleset.new().view_model(v)
	eq(m.me.role, "renegade", "role from you")
	eq(m.seats[2].role, "renegade", "my row follows `you`")


func test_seats_come_out_in_table_order_whatever_order_the_frame_lists_them() -> void:
	var v := _view({"n": 6})
	v.players.reverse()
	v.players.append(v.players[0].duplicate())                          # a repeated position
	var dup: Dictionary = v.players[1].duplicate()
	dup.name = "Impostor"
	v.players.append(dup)
	v.players.append({"at": 99, "name": "Far", "life": 1, "max": 8, "arrows": 0, "alive": true, "away": false, "role": null})
	v.players.append({"at": -1, "name": "Neg", "life": 1, "max": 8, "arrows": 0, "alive": true, "away": false, "role": null})
	var m := BangRuleset.new().view_model(v)
	eq(m.seats.map(func(s): return s.at), [0, 1, 2, 3, 4, 5], "sorted, de-duplicated, out-of-table positions dropped")
	for s in m.seats:
		check(s.name != "Impostor", "the first of a repeated position wins")


func test_names_are_cut_and_single_line_and_never_empty() -> void:
	var v := _view({})
	v.players[0].name = "x".repeat(300)
	v.players[1].name = "a\nb"
	v.players[3].name = "   "
	var m := BangRuleset.new().view_model(v)
	eq(m.seats[0].name.length(), 24, "cut")
	check(not ("\n" in m.seats[1].name), "no line break")
	eq(m.seats[3].name, "#4", "a blank name falls back to the table position")


func test_targets_are_only_what_the_server_offered_to_me_in_the_resolve_step_and_only_living_seats() -> void:
	var r := BangRuleset.new()
	var base := {"phase": "resolve", "pending": {"die": 2, "face": "shoot1", "targets": [1, 3]}, "dead": [3],
		"can": {"target": [1, 3, 3, 9, -1]}}
	var m := r.view_model(_view(base))
	eq(m.targets, [1], "a dead seat, a repeat, a seat that does not exist and a negative one are not targets")
	# not my turn: the server says can.target is null, but a hostile frame may send a list anyway
	m = r.view_model(_view(base.merged({"turn": 4})))
	eq(m.targets, [], "not my turn: no targets whatever `can` says")
	eq(m.can.roll, false, "nor any verb")
	# the roll step has no targets even when `can.target` is filled
	m = r.view_model(_view({"phase": "roll", "can": {"target": [1], "roll": true}}))
	eq(m.targets, [], "roll step: no targets")
	# eliminated: my seat is dead, nothing is mine to do even on my 'turn'
	m = r.view_model(_view({"phase": "resolve", "dead": [2], "can": {"target": [1], "roll": true, "stop": true},
		"pending": {"die": 0, "face": "beer", "targets": [1]}}))
	eq(m.my_turn, false, "a dead seat has no turn")
	eq(m.targets, [], "and no targets")
	eq(m.can.stop, false, "and no verbs")
	check(not BangRuleset.may_target(m, 1), "may_target says no")


func test_may_target_refuses_a_seat_out_of_range_a_stale_model_and_the_wrong_step() -> void:
	var r := BangRuleset.new()
	var m := r.view_model(_view({"phase": "resolve", "pending": {"die": 2, "face": "shoot2", "targets": [4]}, "can": {"target": [4]}}))
	check(BangRuleset.may_target(m, 4), "the offered seat")
	for at in [0, 1, 2, 3, 5, 7, -1, 100]:
		check(not BangRuleset.may_target(m, at), "seat %d is not offered" % at)
	m.pending = {}
	check(not BangRuleset.may_target(m, 4), "nothing pending: nothing to target")


func test_keep_mask_always_keeps_dynamite_and_nothing_the_player_did_not_tap() -> void:
	var m := BangRuleset.new().view_model(_view({"dice": _dice(["dynamite", "arrow", "dynamite", "beer", "shoot1"])}))
	eq(BangRuleset.keep_mask(m.dice, {}), 0b00101, "only the two dynamite")
	eq(BangRuleset.keep_mask(m.dice, {1: true}), 0b00111, "tapped die 1 as well")
	eq(BangRuleset.keep_mask(m.dice, {0: false, 2: false}), 0b00101, "un-tapping a dynamite die changes nothing")
	eq(BangRuleset.keep_mask(m.dice, {1: true, 3: true, 4: true}), 31, "everything kept")
	m.can.reroll = true
	check(not BangRuleset.can_send_reroll(m, {1: true, 3: true, 4: true}), "all five kept: nothing to roll, Stop instead")
	check(BangRuleset.can_send_reroll(m, {}), "some free dice: a reroll is possible")
	m.can.reroll = false
	check(not BangRuleset.can_send_reroll(m, {}), "the server did not offer one")


func test_log_lines_with_bad_shapes_are_dropped_and_names_are_resolved() -> void:
	var log := [
		{"n": 1, "k": "rolled", "by": 2, "roll": 1, "dice": ["arrow", "arrow", "beer", "shoot1", "dynamite"]},
		{"n": 2, "k": "rolled", "by": 2, "roll": 2, "dice": ["arrow"]},
		{"n": 3, "k": "mystery", "by": 1},
		"just text",
		{"n": 5, "k": "shot", "by": 2, "at": 3},
		{"n": 6, "k": "out", "at": 3, "role": "renegade"},
		{"n": 7, "k": "shot", "by": "x", "at": 77},
		{"n": 8, "k": "indians", "hits": [{"at": 1, "dmg": 2}, "bad"]},
	]
	var m := BangRuleset.new().view_model(_view({"log": log}))
	eq(m.log.map(func(l): return l.key), ["bang.log.indians", "bang.log.shot", "bang.log.out", "bang.log.shot", "bang.log.rolled"],
		"newest first; the short dice list, the unknown kind and the string are gone")
	eq(m.log[3].slots.by, "Player 3", "a name from the table")
	eq(m.log[1].slots.by, "#0", "a non-number position never crashes")
	eq(m.log[1].slots.at, "#78", "an unknown position never crashes")
	for l in m.log:
		check(not Words.render(l.key, l.slots).begins_with("["), "%s renders" % l.key)


# ---------------- the wire ----------------

func test_a_bang_room_routes_the_table_for_roll_and_resolve_and_the_end_for_over() -> void:
	_room()
	check(Session.ruleset is BangRuleset, "the room plays Bang")
	_send({"seq": 1})
	eq(Session.screen, "bang_table", "roll")
	_send({"seq": 2, "phase": "resolve", "pending": {"die": 2, "face": "shoot1", "targets": [1]}})
	eq(Session.screen, "bang_table", "resolve")
	_send({"seq": 3, "phase": "over", "turn": null, "winner": {"team": "outlaws", "ats": [2]}})
	eq(Session.screen, "bang_end", "over")
	check("bang_table" in Feed.game_screens() and "bang_end" in Feed.game_screens(), "the router may show them")
	no_errors()


func test_a_stale_view_never_replaces_a_newer_one() -> void:
	_room()
	_send({"seq": 5, "rolls": 2})
	_send({"seq": 3, "rolls": 1})
	eq(_model().seq, 5, "the older frame was ignored")
	eq(_model().rolls, 2, "and its content with it")
	_send({"seq": 5, "rolls": 0})
	eq(_model().rolls, 2, "a repeated seq is ignored too")
	_send({"seq": 6, "rolls": 3})
	eq(_model().rolls, 3, "a newer one is taken")


func test_frames_that_are_not_a_bang_view_are_refused_not_drawn() -> void:
	_room()
	var bad := _view({"seq": 1})
	bad.erase("you")
	fake.server_send(bad)
	eq(_model(), {}, "no `you`: nothing drawn")
	bad = _view({"seq": 2})
	bad.dice = "five"
	fake.server_send(bad)
	eq(_model(), {}, "dice that are not a list: nothing drawn")
	bad = _view({"seq": 3})
	bad.game = "survivors"
	fake.server_send(bad)
	eq(_model(), {}, "a frame naming another game in a Bang room")
	bad = _view({"seq": 4})
	bad.players[0].role = 5
	fake.server_send(bad)
	eq(_model(), {}, "a role that is not text")
	check(notices.any(func(n): return n.kind == "invalid"), "reported")


func test_the_lobby_of_a_bang_room_is_the_shared_lobby() -> void:
	_room()
	fake.server_send({"t": "lobby", "game": "bang", "room_code": "BANG", "seats_taken": 1, "seats_total": 5, "host": true,
		"seats": [{"id": "h1", "connected": true}, {"id": 5, "connected": true}, "x"]})
	eq(Session.screen, "lobby", "lobby")
	eq(Feed.models.lobby.seats.size(), 1, "only the clean seat entry")


# ---------------- the table screen ----------------

func test_dynamite_cannot_be_tapped_or_let_go_and_always_goes_out_in_the_keep_mask() -> void:
	_room()
	_send({"can": {"reroll": true, "stop": true}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	var dyn := _button(screen, "die_1")
	check(dyn != null and dyn.disabled, "the dynamite die is a disabled button")
	dyn.pressed.emit()                                           # even a forced press does nothing
	await _settle()
	eq(screen._kept.get(1, false), false, "dynamite was not toggled")
	_button(screen, "die_0").pressed.emit()                      # keep the arrow
	await _settle()
	_button(screen, "reroll").pressed.emit()
	var acts := _acts()
	eq(acts.size(), 1, "one act sent")
	eq(acts[0].verb, "reroll", "verb")
	eq(acts[0].args.keep, 0b00011, "arrow (bit 0) and dynamite (bit 1) kept, the rest rolled")


func test_nothing_tapped_still_keeps_the_dynamite() -> void:
	_room()
	_send({"can": {"reroll": true, "stop": true}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	_button(screen, "reroll").pressed.emit()
	eq(_acts()[0].args.keep, 0b00010, "only the dynamite")


func test_keeping_every_die_turns_roll_again_off_and_leaves_stop() -> void:
	_room()
	_send({"can": {"reroll": true, "stop": true}, "dice": _dice(["arrow", "beer", "shoot1", "shoot2", "gatling"])})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	for i in 5:
		_button(screen, "die_%d" % i).pressed.emit()
		await _settle()
	var again := _button(screen, "reroll")
	check(again.disabled, "Roll again is off when everything is kept")
	again.pressed.emit()
	eq(_acts().size(), 0, "a forced press sends nothing: the server would say nothing_to_reroll")
	check(not _button(screen, "stop").disabled, "Stop is available")
	_button(screen, "stop").pressed.emit()
	eq(_acts()[0].verb, "stop", "stop")


func test_the_keep_marks_are_cleared_by_a_new_roll_and_a_new_turn() -> void:
	_room()
	_send({"seq": 1, "can": {"reroll": true, "stop": true}, "rolls": 1, "dice": _dice(["arrow", "beer", "shoot1", "shoot2", "gatling"])})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	_button(screen, "die_0").pressed.emit()
	await _settle()
	eq(screen._kept.size(), 1, "one die kept")
	_send({"seq": 2, "can": {"reroll": true, "stop": true}, "rolls": 2, "dice": _dice(["beer", "beer", "shoot1", "shoot2", "gatling"])})
	await _settle()
	eq(screen._kept.size(), 0, "a new roll starts with nothing kept")


func test_only_the_offered_seats_are_buttons_while_choosing_a_target() -> void:
	_room()
	_send({"n": 8, "me": 2, "phase": "resolve", "pending": {"die": 2, "face": "shoot2", "targets": [4]}, "can": {"target": [4]},
		"dice": _dice(["shoot2", "arrow", "shoot1", "beer", "gatling"])})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	for at in 8:
		var is_button := _button(screen, "seat_%d" % at) != null
		eq(is_button, at == 4, "seat %d %s a button" % [at, "is" if is_button else "is not"])
		check(Ui.find(screen, "seat_%d" % at) != null, "seat %d is drawn either way" % at)
	screen._target(5)
	screen._target(2)
	screen._target(0)
	eq(_acts().size(), 0, "a tap that gets through on a seat out of range sends nothing")
	_button(screen, "seat_4").pressed.emit()
	eq(_acts().size(), 1, "the offered seat")
	eq(_acts()[0].args, {"at": 4}, "by table position")
	eq(_acts()[0].verb, "target", "verb")


func test_a_seat_that_became_a_target_for_someone_else_is_not_mine_to_tap() -> void:
	_room()
	_send({"n": 5, "me": 2, "turn": 3, "phase": "resolve", "pending": {"die": 2, "face": "shoot1", "targets": [2, 4]},
		"can": {"target": [2, 4]}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	for at in 5:
		check(_button(screen, "seat_%d" % at) == null, "seat %d is not a button on someone else's turn" % at)
	screen._target(4)
	eq(_acts().size(), 0, "nothing sent")
	check(Ui.find(screen, "roll") == null and Ui.find(screen, "reroll") == null and Ui.find(screen, "stop") == null, "no action buttons")


func test_roll_button_only_when_the_server_offers_the_first_roll() -> void:
	_room()
	_send({"rolls": 0, "dice": [], "can": {"roll": true}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	var roll := _button(screen, "roll")
	check(roll != null, "Roll the dice")
	roll.pressed.emit()
	eq(_acts()[0].verb, "roll", "verb")
	eq(_acts()[0].args, {}, "no args")
	check(Ui.find(screen, "die_0") == null, "no dice yet")


func test_a_player_who_is_out_sees_the_table_and_has_no_buttons_at_all() -> void:
	_room()
	_send({"dead": [2], "turn": 4, "can": {"roll": true, "reroll": true, "stop": true, "target": [1]}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	for id in ["roll", "reroll", "stop", "die_0", "die_2", "seat_1"]:
		var b := _button(screen, id)
		check(b == null or b.disabled, "%s is not live for a seat that is out" % id)
	check(Ui.texts(screen).any(func(t): return t == Words.render("bang.turn_out")), "it says so")


func test_an_older_model_does_not_redraw_the_table() -> void:
	_room()
	_send({"seq": 7, "rolls": 2, "can": {"reroll": true, "stop": true}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	var old := BangRuleset.new().view_model(_view({"seq": 4, "rolls": 1}))
	screen._on_model("view", old)
	eq(screen._m.seq, 7, "the screen kept the newer model")
	eq(screen._m.rolls, 2, "and its content")


func test_no_role_but_mine_and_the_sheriffs_is_written_on_the_table() -> void:
	_room()
	var v := _view({"n": 5, "me": 2, "role": "deputy"})
	v.players[1].role = "outlaw"                  # hostile
	v.players[4].role = "renegade"
	fake.server_send(v)
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	var seats_text := []
	for at in 5:
		seats_text.append(" ".join(Ui.texts(Ui.find(screen, "seat_%d" % at))))
	check(Words.render("bang.role.sheriff") in seats_text[0], "seat 0 shows Sheriff")
	check(Words.render("bang.role.deputy") in seats_text[2], "my seat shows my role")
	for at in [1, 3, 4]:
		for r in ["sheriff", "deputy", "outlaw", "renegade"]:
			check(not (Words.render("bang.role." + r) in seats_text[at]), "seat %d shows %s" % [at, r])


func test_the_table_fits_3_and_8_seats_in_every_window_without_overlap_or_clipping() -> void:
	for n in [3, 8]:
		for resolving in [false, true]:
			setup()
			_room("T%d" % n)
			if resolving:
				_send({"n": n, "me": 1, "phase": "resolve", "pending": {"die": 2, "face": "beer", "targets": range(n)},
					"can": {"target": range(n)}, "log": [{"n": 1, "k": "shot", "by": 1, "at": 0}]})
			else:
				_send({"n": n, "me": 1, "can": {"reroll": true, "stop": true},
					"log": [{"n": 1, "k": "rolled", "by": 1, "roll": 1, "dice": ["arrow", "arrow", "beer", "shoot1", "dynamite"]}]})
			for s in SIZES:
				var screen := BangTableScreen.new()
				var holder := _mount(screen, s)
				await _settle()
				var tag := "%d seats %s %s" % [n, "resolving" if resolving else "rolling", s]
				var rects: Array = []
				for at in n:
					var seat := Ui.find(screen, "seat_%d" % at) as Control
					check(seat != null, "%s: seat %d is drawn" % [tag, at])
					if seat != null:
						var r := seat.get_global_rect()
						rects.append(r)
						check(r.size.x > 8.0 and r.size.y > 8.0, "%s: seat %d has a size" % [tag, at])
						check(r.position.x >= -0.5 and r.end.x <= s.x + 0.5, "%s: seat %d is inside the window width" % [tag, at])
				for i in rects.size():
					for j in range(i + 1, rects.size()):
						check(not rects[i].intersects(rects[j].grow(-1.0)), "%s: seats %d and %d overlap" % [tag, i, j])
				for d in Ui.find_all(screen, "die_"):
					var dr := (d as Control).get_global_rect()
					check(dr.position.x >= -0.5 and dr.end.x <= s.x + 0.5, "%s: %s is inside the window width" % [tag, d.get_meta("id")])
				for v in Clearance.check(holder):
					check(false, "%s: %s" % [tag, v])
				for v in NineFit.check(holder):
					check(false, "%s: %s" % [tag, v])
				holder.queue_free()
				_mounted.erase(holder)


func test_a_press_that_is_held_keeps_the_same_buttons_until_it_is_released() -> void:
	_room()
	_send({"seq": 1, "can": {"reroll": true, "stop": true}})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	var before := _button(screen, "die_0")
	screen._note_press("mouse1", true)
	_send({"seq": 2, "pid": 2, "rolls": 2, "can": {"reroll": true, "stop": true}, "dice": _dice(["beer", "beer", "shoot1", "shoot2", "gatling"])})
	await _settle()
	check(_button(screen, "die_0") == before, "the button under the finger is still the same node")
	screen._note_press("mouse1", false)
	await _settle()
	check(_button(screen, "die_0") != before, "after the release the new view is drawn")


func test_every_text_on_the_screens_is_a_real_sentence_not_a_hole() -> void:
	_room()
	_send({"n": 5, "can": {"reroll": true, "stop": true}, "log": [{"n": 1, "k": "indians", "hits": [{"at": 1, "dmg": 1}]},
		{"n": 2, "k": "out", "at": 3, "role": "outlaw"}, {"n": 3, "k": "turn", "at": 2}]})
	var screen := BangTableScreen.new()
	_mount(screen, SIZES[1])
	await _settle()
	var texts := Ui.texts(screen)
	check(texts.size() > 10, "there is text to look at (%d)" % texts.size())
	for t in texts:
		check(not (str(t).begins_with("[") and "." in str(t)) and not ("{" in str(t)), "hole in: %s" % t)


# ---------------- the end screen ----------------

func test_the_end_screen_shows_the_winners_and_every_role_to_a_player_who_was_out() -> void:
	_room()
	_send({"phase": "over", "turn": null, "dead": [1, 2], "winner": {"team": "outlaws", "ats": [1, 2, 3]}, "role": "outlaw",
		"players": _over_players()})
	var screen := BangEndScreen.new()
	_mount(screen, SIZES[0])
	await _settle()
	var all := " ".join(Ui.texts(screen))
	check(Words.render("bang.team.outlaws") in all, "the winning side")
	check(Words.render("bang.end.win") in all, "I am on the winning side, though I am out")
	for at in [1, 2, 3]:
		check(Ui.find(screen, "winner_%d" % at) != null, "winner %d listed" % at)
	check(Ui.find(screen, "winner_0") == null and Ui.find(screen, "winner_4") == null, "and only the winners")
	for at in 5:
		check(Ui.find(screen, "role_%d" % at) != null, "role of seat %d listed" % at)
	check(Words.render("bang.role.renegade") in all and Words.render("bang.role.deputy") in all, "all roles are public at the end")
	check(_button(screen, "back") != null, "a way back")


func _over_players() -> Array:
	var roles := ["sheriff", "outlaw", "outlaw", "renegade", "deputy"]
	var out: Array = []
	for i in 5:
		out.append({"at": i, "name": "Player %d" % (i + 1), "life": 0 if i in [0, 4] else 3, "max": 8, "arrows": 0,
			"alive": not (i in [0, 4]), "away": false, "role": roles[i]})
	return out


func test_the_end_screen_for_a_side_that_lost_and_for_a_table_everyone_left() -> void:
	_room()
	_send({"phase": "over", "turn": null, "winner": {"team": "sheriff", "ats": [0, 4]}, "players": _over_players(), "role": "outlaw"})
	var screen := BangEndScreen.new()
	_mount(screen, SIZES[1])
	await _settle()
	check(Words.render("bang.end.lose") in " ".join(Ui.texts(screen)), "my side lost")
	_send({"seq": 2, "phase": "over", "turn": null, "winner": {"team": "abandoned", "ats": []}, "players": _over_players()})
	await _settle()
	var all := " ".join(Ui.texts(screen))
	check(Words.render("bang.team.abandoned") in all, "everyone left")
	check(not (Words.render("bang.end.win") in all) and not (Words.render("bang.end.lose") in all), "no win or loss is claimed")
	_send({"seq": 3, "phase": "over", "turn": null, "winner": {"team": "friendly-ghosts", "ats": [1]}, "players": _over_players()})
	await _settle()
	check(Words.render("bang.team.unknown") in " ".join(Ui.texts(screen)), "an unknown side never renders as a hole")


func test_the_end_screen_fits_3_and_8_seats() -> void:
	for n in [3, 8]:
		setup()
		_room("E%d" % n)
		var players: Array = []
		for i in n:
			players.append({"at": i, "name": "Player %d" % (i + 1), "life": 0, "max": 8, "arrows": 0, "alive": i == 0, "away": false,
				"role": "outlaw"})
		_send({"n": n, "me": 1, "phase": "over", "turn": null, "winner": {"team": "outlaws", "ats": range(1, n)}, "players": players})
		for s in SIZES:
			var screen := BangEndScreen.new()
			var holder := _mount(screen, s)
			await _settle()
			for v in Clearance.check(holder) + NineFit.check(holder):
				check(false, "%d seats %s: %s" % [n, s, v])
			holder.queue_free()
			_mounted.erase(holder)
