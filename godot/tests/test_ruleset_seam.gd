extends BaseTest
## P3 step 3.1 / 3.2, first slice: the ruleset seam. A ruleset declares its phases and verbs; Session keeps one ruleset per
## room, chosen by the game id the room's frames name; `view` frames carry a `seq` and an older one is ignored; Intents.act sends
## the generic `act` frame and refuses what the verb table does not allow before anything goes out. Every test here tries to
## break one of those: hostile ids, frames out of order, frames from the wrong game, a room that changes game, an old server.

## A game that is not Survivors, shaped like a game on the new wire: one `view` frame, three verbs.
class ToyRuleset:
	extends Ruleset

	func view_types() -> Array:
		return ["view"]

	func validate(msg: Dictionary) -> String:
		if msg.get("t") != "view":
			return ""
		return Schema.check(msg, {"dict": {"game": TYPE_STRING, "phase": TYPE_STRING, "phase_id": TYPE_STRING, "seq": Schema.ANY,
			"?mark": Schema.ANY}}, "view")

	func view_model(v: Dictionary) -> Dictionary:
		return {"phase": v.get("phase"), "phase_id": v.get("phase_id"), "mark": v.get("mark"), "pot": int(v.get("pot", 0))}

	func phases() -> Dictionary:
		return {"deal": {"screen": "deal"}, "play": {"screen": "play"}}

	func verbs() -> Dictionary:
		return {
			"bid": {"amount": {"type": "int", "min": 1, "max": 6}, "face": {"type": "int", "min": 1, "max": 6}},
			"note": {"text": {"type": "str", "optional": true, "nullable": true, "max_len": 10}},
			"flag": {"on": {"type": "bool"}, "mode": {"type": "str", "optional": true, "choices": ["a", "b"]}},
			"pass": {},
		}


func _toy_factory(id: String) -> Ruleset:
	return ToyRuleset.new() if id == "toy" else RulesetRegistry.try_make(id)


func _seat(code := "TOY1", game: Variant = "toy", tok := "tok-toy-1") -> void:
	Session.act("create_room")
	var m := {"t": "seat", "token": tok, "room_code": code, "alias": "Mango", "host": true}
	if game != null:
		m["game"] = game
	fake.server_send(m)


func _toy_room(code := "TOY1") -> void:
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat(code)


func _view(seq: Variant, mark := "", phase := "deal", game := "toy") -> Dictionary:
	var v := {"t": "view", "game": game, "phase": phase, "phase_id": "pid-" + str(mark if mark != "" else seq), "seq": seq}
	if mark != "":
		v["mark"] = mark
	return v


func _acts() -> Array:
	return fake.sent.filter(func(m): return m.t == "act")


# ---- the ruleset declares phases and verbs ----

func test_the_base_ruleset_declares_nothing_so_it_allows_nothing() -> void:
	var r := Ruleset.new()
	eq(r.phases(), {}, "no phases")
	eq(r.verbs(), {}, "no verbs")
	eq(VerbCheck.check(r.verbs(), "pick", {}), "unknown_verb", "an inert ruleset refuses every verb")


func test_survivors_declares_a_phase_for_every_view_it_draws_and_its_four_verbs() -> void:
	var r := SurvivorsRuleset.new()
	var phases := r.phases()
	for t in r.view_types():
		check(phases.has(t), "no phase declared for the '%s' view" % t)
		eq(phases.get(t, {}).get("screen"), t, "the '%s' phase draws the '%s' screen" % [t, t])
	eq(phases.size(), r.view_types().size(), "no phase without a view")
	var verbs := r.verbs()
	var names := verbs.keys()
	names.sort()
	eq(names, ["continue", "lock", "pick", "radio"], "the manifest's verbs, no more and no fewer")
	eq(VerbCheck.check(verbs, "pick", {"kind": "scavenge"}), "", "a plain pick is allowed")
	eq(VerbCheck.check(verbs, "pick", {"kind": "steal", "target": null, "amount": 2}), "", "a null target is allowed")
	eq(VerbCheck.check(verbs, "pick", {"kind": "steal", "amount": 100}), "bad_args", "an amount past the manifest's 99")
	eq(VerbCheck.check(verbs, "pick", {"kind": "steal", "amount": -1}), "bad_args", "a negative amount")
	eq(VerbCheck.check(verbs, "pick", {"target": "Fig"}), "bad_args", "a pick with no kind")
	eq(VerbCheck.check(verbs, "lock", {"kind": "x"}), "bad_args", "an argument the verb does not take")


# ---- the game of a room ----

func test_a_seat_that_names_no_game_is_survivors_and_plays_as_before() -> void:
	in_round(1)
	check(Session.ruleset is SurvivorsRuleset, "the default game")
	eq(Session.unsupported_game, "", "nothing unsupported")
	eq(Session.screen, "round", "a Survivors round view still draws the round screen")
	no_errors()


func test_a_seat_naming_survivors_is_survivors() -> void:
	go_online()
	_seat("SURV", "survivors")
	check(Session.ruleset is SurvivorsRuleset, "survivors by name")
	fake.server_send(round_view(1))
	eq(Session.screen, "round", "and it plays")


func test_an_unknown_game_is_never_played_as_survivors() -> void:
	go_online()
	_seat("WHAT", "mystery")
	eq(Session.unsupported_game, "mystery", "the client knows it cannot play this room")
	check(not (Session.ruleset is SurvivorsRuleset), "the room did not fall back to Survivors")
	fake.server_send(round_view(1))                 # a Survivors-shaped frame in a room of some other game
	eq(Session.view, {}, "the frame was not taken as a Survivors view")
	eq(Session.screen, "title", "and no round screen was drawn")
	check(notices.any(func(n): return n.kind == "unknown"), "it was reported as a frame nobody here understands")
	no_errors()


func test_hostile_game_ids_are_unsupported_and_never_reach_the_log_raw() -> void:
	var hostile: Array = ["../../etc/passwd", "Survivors", "SURVIVORS", "x\nERROR injected line", 5, true, {}, [], "a".repeat(500), "",
		" survivors", "survivors ", "sur vivors", "1abc", "survivors\u0000"]
	for g in hostile:
		setup()
		go_online()
		_seat("HOST", g)
		check(not (Session.ruleset is SurvivorsRuleset), "a game id %s was played as Survivors" % [str(g).left(30)])
		check(Session.unsupported_game != "", "a game id %s is marked unsupported" % [str(g).left(30)])
		var logged := "\n".join(Log.since(mark))
		check(not ("injected" in logged) and not ("passwd" in logged), "the raw id %s reached the log" % [str(g).left(30)])
		no_errors()


func test_a_known_game_id_is_matched_exactly() -> void:
	go_online()
	Session.ruleset_factory = _toy_factory
	_seat("CASE", "Toy")
	check(not (Session.ruleset is ToyRuleset), "'Toy' is not 'toy'")
	check(Session.unsupported_game != "", "an id in the wrong case is not a known game")


func test_a_room_that_changes_game_gets_that_games_ruleset_and_its_frames_are_judged_by_it() -> void:
	_toy_room("CHG1")
	check(Session.ruleset is ToyRuleset, "a toy room")
	fake.server_send(_view(1))
	eq(Session.screen, "deal", "a toy view is taken and asks for the screen its phase names")
	# the same room now says it is a game this client does not have
	fake.server_send(_view(2, "", "deal", "mystery"))
	check(not (Session.ruleset is ToyRuleset), "the toy ruleset no longer judges this room")
	eq(Session.unsupported_game, "mystery", "marked unsupported")
	# and back: the seq of the old game must not shut the room out
	fake.server_send(_view(1, "again", "deal", "toy"))
	check(Session.ruleset is ToyRuleset, "back to the toy game")
	eq(Session.view.get("mark"), "again", "a seq of 1 after a change of game is taken, not called stale")


func test_two_rooms_in_a_row_keep_their_own_games() -> void:
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("AAAA", null, "tok-a")                    # a Survivors room
	check(Session.ruleset is SurvivorsRuleset, "room A: survivors")
	fake.server_send(round_view(1))
	eq(Session.screen, "round", "room A plays")
	Intents.leave()
	go_online()
	_seat("BBBB", "toy", "tok-b")
	check(Session.ruleset is ToyRuleset, "room B: toy")
	fake.server_send(round_view(1))
	eq(Session.view.get("t"), null, "a Survivors round frame in the toy room is not taken")
	fake.server_send(_view(1))
	eq(Session.view.get("t"), "view", "a toy view is")
	Intents.leave()
	go_online()
	_seat("AAAA", null, "tok-a2")                   # the code of room A again, no game named
	check(Session.ruleset is SurvivorsRuleset, "room A again is survivors, it did not inherit room B's game")
	fake.server_send(round_view(1))
	eq(Session.screen, "round", "and plays")


func test_a_reused_room_code_does_not_inherit_the_old_games() -> void:
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("SAME", "toy", "tok-1")
	check(Session.ruleset is ToyRuleset, "toy")
	Intents.leave()
	go_online()
	_seat("SAME", null, "tok-2")
	check(Session.ruleset is SurvivorsRuleset, "the same code with no game named is the default game")


func test_a_missing_games_list_is_an_old_server_and_changes_nothing() -> void:
	go_online()                                      # hello_ok without `games`
	eq(Session.games, [], "no games offered")
	_seat("OLD1", null)
	check(Session.ruleset is SurvivorsRuleset, "survivors")
	fake.server_send(round_view(1))
	eq(Session.screen, "round", "and plays")
	for junk in [null, "survivors", 7, {"id": "x"}, [{"id": 5}], ["a", "b"]]:
		setup()
		Net.connect_to("ws://test")
		fake.server_open()
		fake.server_send({"t": "hello_ok", "proto": 1, "games": junk})
		_seat("OLD2", null)
		check(Session.ruleset is SurvivorsRuleset, "a games list of %s does not change the room's game" % [str(junk)])
		no_errors()


func test_a_lobby_frame_naming_another_game_switches_the_room_too() -> void:
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("LOBY", null)
	check(Session.ruleset is SurvivorsRuleset, "starts as the default")
	fake.server_send({"t": "lobby", "room_code": "LOBY", "seats_taken": 1, "seats_total": 4, "host": true, "game": "toy"})
	check(Session.ruleset is ToyRuleset, "a lobby that names the toy game")


# ---- the seq rule for view frames ----

func test_a_view_older_than_the_last_is_ignored() -> void:
	_toy_room()
	fake.server_send(_view(1, "one"))
	fake.server_send(_view(3, "three"))
	fake.server_send(_view(2, "two"))               # late
	eq(Session.view.get("mark"), "three", "the late view did not replace the newer one")
	fake.server_send(_view(4, "four"))
	eq(Session.view.get("mark"), "four", "and the next newer one still does")


func test_a_repeated_view_is_ignored() -> void:
	_toy_room()
	fake.server_send(_view(5, "first"))
	var seen := 0
	var cb := func(_v): seen += 1
	Session.view_changed.connect(cb)
	fake.server_send(_view(5, "echo"))
	fake.server_send(_view(5, "echo2"))
	Session.view_changed.disconnect(cb)
	eq(Session.view.get("mark"), "first", "a repeat of seq 5 changes nothing")
	eq(seen, 0, "and announces nothing")


func test_a_burst_in_scrambled_order_ends_on_the_newest() -> void:
	_toy_room()
	for s in [4, 1, 9, 2, 8, 3, 7, 9, 5, 6]:
		fake.server_send(_view(s, "m%d" % s))
	eq(Session.view.get("mark"), "m9", "the highest seq wins whatever the order")


func test_a_view_with_no_usable_seq_is_refused_and_does_not_move_the_counter() -> void:
	_toy_room()
	fake.server_send(_view(3, "three"))
	for bad in [null, "4", 4.5, true, false, 0, -1, [], {}]:
		var v := _view(bad, "bad")
		fake.server_send(v)
		eq(Session.view.get("mark"), "three", "a view with seq %s was taken" % [str(bad)])
	fake.server_send(_view(4, "four"))
	eq(Session.view.get("mark"), "four", "the counter was not poisoned: seq 4 still arrives")
	check(notices.any(func(n): return n.kind == "invalid"), "the refusals were reported")


func test_a_view_with_no_seq_at_all_is_refused() -> void:
	_toy_room()
	var v := _view(1, "noseq")
	v.erase("seq")
	fake.server_send(v)
	eq(Session.view, {}, "no seq, no view")


func test_a_frame_the_schema_refuses_never_advances_the_counter() -> void:
	_toy_room()
	var broken := _view(50, "broken")
	broken.erase("phase")                            # the toy schema requires it
	fake.server_send(broken)
	eq(Session.view, {}, "refused")
	fake.server_send(_view(2, "two"))
	eq(Session.view.get("mark"), "two", "seq 50 on a refused frame did not make seq 2 stale")


func test_the_counter_starts_again_on_a_new_seat() -> void:
	_toy_room("SEQ1")
	fake.server_send(_view(7, "seven"))
	Intents.leave()
	go_online()
	_seat("SEQ2", "toy", "tok-seq2")
	fake.server_send(_view(1, "fresh"))
	eq(Session.view.get("mark"), "fresh", "seq 1 of a new seat is not stale because the last seat reached 7")


func test_a_server_restart_with_a_client_still_connected_is_not_stale() -> void:
	_toy_room("RST1")
	fake.server_send(_view(7, "before"))
	fake.server_close(1006)                          # the server restarted: its counters are gone
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	# on resume the server may answer with the view FIRST and the seat after it
	fake.server_send(_view(1, "after"))
	eq(Session.view.get("mark"), "after", "seq 1 on the new connection is a fresh view, not an old one")
	fake.server_send({"t": "seat", "token": "tok-toy-1", "room_code": "RST1", "alias": "Mango", "host": true, "game": "toy"})
	fake.server_send(_view(2, "next"))
	eq(Session.view.get("mark"), "next", "and the numbering goes on from there")
	fake.server_send(_view(1, "late"))
	eq(Session.view.get("mark"), "next", "a straggler from the new connection is still stale")


func test_the_legacy_stale_round_rule_still_holds() -> void:
	in_round(3)
	fake.server_send(round_view(2))
	eq(Session.view.get("round"), 3, "round 2 after round 3 is ignored, as before")


# ---- Intents.act ----

func test_act_sends_the_generic_frame_with_the_current_phase_and_a_fresh_id() -> void:
	_toy_room()
	fake.server_send(_view(1, "one"))
	eq(Intents.act("bid", {"amount": 2, "face": 3}), "", "sent")
	var a: Dictionary = fake.last("act")
	eq(a.get("verb"), "bid", "verb")
	eq(a.get("args"), {"amount": 2, "face": 3}, "args")
	eq(a.get("phase_id"), "pid-one", "the phase of the view I hold, supplied by the client")
	check(a.get("act_id") is String and a.act_id != "" and a.act_id.length() <= 64, "an act id of 1 to 64 characters")
	eq(a.keys().size(), 5, "t, verb, args, phase_id, act_id and nothing else: %s" % [a.keys()])
	fake.server_send(_view(2, "two"))
	eq(Intents.act("pass"), "", "a second act")
	var b: Dictionary = fake.last("act")
	check(b.act_id != a.act_id, "two acts never share an id")
	eq(b.phase_id, "pid-two", "and it names the newer phase")
	eq(b.args, {}, "no args is an empty object, not null")


func test_act_ids_differ_even_for_identical_calls() -> void:
	_toy_room()
	fake.server_send(_view(1))
	var ids := {}
	for i in 6:
		fake.server_send(_view(2 + i))               # each view ends the wait on the last act
		eq(Intents.act("pass"), "", "act %d sent" % i)
		ids[fake.last("act").act_id] = true
	eq(ids.size(), 6, "six acts, six ids")


func test_the_same_act_twice_in_a_row_is_one_tap() -> void:
	_toy_room()
	fake.server_send(_view(1))
	eq(Intents.act("bid", {"amount": 1, "face": 1}), "", "first")
	eq(Intents.act("bid", {"amount": 1, "face": 1}), "in_flight", "the double tap is held back")
	eq(_acts().size(), 1, "one frame went out")
	eq(Intents.act("bid", {"amount": 2, "face": 1}), "", "a different bid is a different act")
	eq(_acts().size(), 2, "two frames")
	fake.server_send(_view(2))
	eq(Intents.act("bid", {"amount": 1, "face": 1}), "", "after the next view the same bid may go again")


func test_act_forbidden_argument_names_are_refused_before_anything_is_sent() -> void:
	_toy_room()
	fake.server_send(_view(1))
	for name in ["seat", "pid", "player", "player_id", "seat_id", "user", "user_id", "token", "seed", "sim", "Seat", "TOKEN", "Player_Id"]:
		eq(Intents.act("note", {name: "x"}), "forbidden_arg", "the argument '%s'" % name)
		eq(Intents.act("bid", {"amount": 1, "face": 1, name: 1}), "forbidden_arg", "'%s' next to good arguments" % name)
	eq(_acts().size(), 0, "not one act left the client")


func test_act_arguments_that_are_not_the_verbs_are_refused() -> void:
	_toy_room()
	fake.server_send(_view(1))
	var cases := {
		"bool for int": ["bid", {"amount": true, "face": 1}],
		"float for int": ["bid", {"amount": 2.0, "face": 1}],
		"numeric string for int": ["bid", {"amount": "2", "face": 1}],
		"below min": ["bid", {"amount": 0, "face": 1}],
		"above max": ["bid", {"amount": 7, "face": 1}],
		"huge int": ["bid", {"amount": 9223372036854775807, "face": 1}],
		"missing required": ["bid", {"amount": 2}],
		"extra argument": ["bid", {"amount": 2, "face": 1, "cheat": 1}],
		"null for a non-nullable": ["bid", {"amount": null, "face": 1}],
		"string too long": ["note", {"text": "x".repeat(11)}],
		"int for string": ["note", {"text": 5}],
		"nested object for a scalar": ["bid", {"amount": {"seat": 1}, "face": 1}],
		"array for a scalar": ["bid", {"amount": [1], "face": 1}],
		"int for bool": ["flag", {"on": 1}],
		"not one of the choices": ["flag", {"on": true, "mode": "c"}],
		"args an array": ["pass", []],
		"args null": ["pass", null],
		"args a string": ["pass", "{}"],
		"an argument to a verb that takes none": ["pass", {"x": 1}],
	}
	for label in cases:
		var why: String = Intents.act(cases[label][0], cases[label][1])
		eq(why, "bad_args", label)
	eq(_acts().size(), 0, "none of them was sent")


func test_act_arguments_that_are_the_verbs_are_accepted_at_their_edges() -> void:
	_toy_room()
	fake.server_send(_view(1))
	var n := 0
	for call in [["bid", {"amount": 1, "face": 6}], ["bid", {"amount": 6, "face": 1}], ["note", {}], ["note", {"text": null}],
			["note", {"text": "x".repeat(10)}], ["flag", {"on": false}], ["flag", {"on": true, "mode": "b"}]]:
		fake.server_send(_view(2 + n))
		eq(Intents.act(call[0], call[1]), "", "edge %s" % [str(call)])
		n += 1
	eq(_acts().size(), n, "all of them went out")


func test_act_unknown_verbs_are_refused() -> void:
	_toy_room()
	fake.server_send(_view(1))
	for v in ["", "BID", "bid ", "__proto__", "pick", "start", null, 5, true, ["bid"], {"verb": "bid"}]:
		eq(Intents.act(v, {}), "unknown_verb", "verb %s" % [str(v)])
	eq(_acts().size(), 0, "none went out")


func test_act_with_no_phase_to_name_is_refused() -> void:
	_toy_room()
	eq(Intents.act("pass"), "no_phase", "before any view")
	var bare := _view(1)
	bare["phase_id"] = ""
	fake.server_send(bare)
	eq(Intents.act("pass"), "no_phase", "a view whose phase id is empty")
	eq(_acts().size(), 0, "nothing sent")


func test_act_in_a_survivors_room_is_refused_without_a_phase() -> void:
	in_round(1)
	eq(Intents.act("lock"), "no_phase", "a legacy Survivors view names no phase_id; the legacy lock is the way")
	eq(_acts().size(), 0, "nothing sent")
	eq(Intents.act("start"), "unknown_verb", "start is not a verb of the game")


func test_act_is_held_back_while_the_view_is_stale() -> void:
	_toy_room()
	fake.server_send(_view(1))
	fake.server_close(1006)
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(Intents.act("pass"), "awaiting_view", "after a reconnect the first word is resume, not an act on the old phase")
	eq(_acts().size(), 0, "nothing sent")


func test_a_refused_act_costs_the_connection_nothing() -> void:
	_toy_room()
	fake.server_send(_view(1))
	Intents.act("bid", {"amount": 99, "face": 1})
	Intents.act("nope")
	Intents.act("pass", {"seat": 1})
	clock.advance(Net.ACK_TIMEOUT_MS + 1000)
	Net.tick()
	eq(Net.state, "online", "no answer was ever awaited for a frame that was never sent")
	no_errors()


func test_the_stale_phase_answer_releases_the_act_so_the_next_one_can_go() -> void:
	_toy_room()
	fake.server_send(_view(1))
	eq(Intents.act("pass"), "", "sent")
	fake.server_send({"t": "error", "code": "stale_phase", "message": "That action is for an earlier phase."})
	eq(Intents.act("pass"), "", "an error answered the act: it is not stuck in flight")
	eq(_acts().size(), 2, "both went out")


func test_the_log_never_carries_the_arguments_of_an_act() -> void:
	_toy_room()
	fake.server_send(_view(1))
	Intents.act("note", {"text": "SECRETWORD-123"})
	Intents.act("note", {"text": "SECRETWORD-123", "token": "SECRETWORD-456"})
	Intents.act("bid", {"amount": 99, "face": "SECRETWORD-789"})
	var logged := "\n".join(Log.since(mark))
	check(not ("SECRETWORD" in logged), "act arguments reached the log")


# ---- Feed and the router follow the room's ruleset (C2) ----

var _mounted: Array = []


func teardown() -> void:
	for s in _mounted:
		s.free()
	_mounted.clear()
	super.teardown()


## The real router with plain stand-ins for screens, so only its choice is under test.
func _router() -> Control:
	var r: Control = preload("res://main.gd").new()
	r.screen_factory = func(_name): return Control.new()
	add_child(r)
	_mounted.append(r)
	return r


func _model_log() -> Array:
	var seen: Array = []
	Feed.model_changed.connect(func(kind, m): seen.append([kind, m]))
	return seen


func test_a_toy_game_runs_hello_view_act_view_end_to_end() -> void:
	var r := _router()
	Session.ruleset_factory = _toy_factory
	var seen := _model_log()
	go_online()
	_seat("TOY9")
	fake.server_send(_view(1, "dealt"))
	eq(Feed.models.get("view", {}).get("phase"), "deal", "Feed asked the toy ruleset for the model of the view")
	eq(Feed.models.get("view", {}).get("mark"), "dealt", "its own tiny model")
	check(not Feed.models.has("round") and not Feed.models.has("lobby"), "no Survivors model was built for a toy view")
	eq(Intents.act("bid", {"amount": 3, "face": 2}), "", "the toy verb goes out")
	var a: Dictionary = fake.last("act")
	eq(a.get("phase_id"), "pid-dealt", "naming the phase of the view the model came from")
	var reply := _view(2, "played", "play")
	reply["pot"] = 3
	fake.server_send(reply)
	eq(Feed.models.view.phase, "play", "the second phase")
	eq(Feed.models.view.pot, 3, "carrying the toy's own field")
	eq(Session.screen, "play", "Session asks for the screen the phase names")
	eq(seen.filter(func(e): return e[0] == "view").size(), 2, "one model per view, announced")
	eq(r.current_name, "neutral", "no screen is drawn for a toy phase: the neutral screen stands in, never a Survivors one")
	no_errors()


func test_the_router_shows_only_the_screens_the_rooms_game_names() -> void:
	var r := _router()
	go_online()
	_seat("SURV", null)
	for s in ["lobby", "round", "reveal", "end", "title", "upgrade"]:
		check(r._routable(s), "'%s' is routable in a Survivors room" % s)
	check(not r._routable("deal"), "a screen no script draws is not routable")
	Intents.leave()
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("TOY2", "toy", "tok-t2")
	for s in ["lobby", "round", "reveal", "end"]:
		check(not r._routable(s), "'%s' is not routable in a toy room" % s)
	check(r._routable("title") and r._routable("upgrade"), "the shared screens still are")
	Intents.leave()
	go_online()
	_seat("WHAT", "mystery", "tok-w")
	for s in ["lobby", "round", "reveal", "end"]:
		check(not r._routable(s), "'%s' is not routable in a room of a game this client lacks" % s)


func test_a_view_for_an_unknown_game_never_reaches_feed() -> void:
	var r := _router()
	go_online()
	_seat("WHAT", "mystery")
	var seen := _model_log()
	fake.server_send(_view(1, "x", "deal", "mystery"))
	fake.server_send(round_view(1))
	eq(seen.filter(func(e): return e[0] != "rooms").size(), 0, "no model was built")
	eq(Feed.models.keys().filter(func(k): return k != "rooms").size(), 0, "none is held")
	eq(r.current_name, "upgrade", "and the router says the app cannot play it")
	no_errors()


func test_a_survivors_frame_in_a_toy_room_never_reaches_feed() -> void:
	var r := _router()
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("TOY3")
	fake.server_send(_view(1, "dealt"))
	var seen := _model_log()
	fake.server_send({"t": "lobby", "room_code": "TOY3", "seats_taken": 1, "seats_total": 4, "host": true})
	fake.server_send(round_view(5))
	fake.server_send({"t": "reveal", "round": 5, "news": [], "private": [], "radio": [], "board": null, "seconds_left": 9})
	fake.server_send({"t": "end", "extracted": [], "winners": [], "results": []})
	eq(seen.size(), 0, "not one model was built from a Survivors frame")
	eq(Feed.models.get("view", {}).get("mark"), "dealt", "the toy's model is untouched")
	eq(Session.view.get("mark"), "dealt", "and so is the view")
	check(notices.any(func(n): return n.kind == "unknown"), "the frames were reported, not swallowed")
	eq(r.current_name, "neutral", "the router did not show a Survivors screen")
	no_errors()


func test_a_room_whose_game_changes_between_frames_is_judged_by_each_frame_game() -> void:
	var r := _router()
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("FLIP")
	fake.server_send(_view(1, "toy1"))
	eq(Feed.models.view.mark, "toy1", "toy model")
	var seen := _model_log()
	fake.server_send(_view(2, "ghost", "deal", "mystery"))        # the same room, now a game nobody here has
	eq(seen.size(), 0, "nothing built for it")
	eq(Feed.models.view.mark, "toy1", "the last toy model is not overwritten by a ghost")
	fake.server_send(round_view(1))                                 # and it is not Survivors either
	eq(seen.size(), 0, "a Survivors frame is not taken for it")
	fake.server_send(_view(1, "toy2"))                              # back to the toy game; its numbering starts again
	eq(Feed.models.view.mark, "toy2", "the toy game is heard again")
	eq(r.current_name, "neutral", "the router stays on the neutral screen, never a Survivors one")
	no_errors()


func test_survivors_still_builds_its_models_through_feed_after_a_toy_room() -> void:
	_router()
	Session.ruleset_factory = _toy_factory
	go_online()
	_seat("TOY4")
	fake.server_send(_view(1, "dealt"))
	Intents.leave()
	go_online()
	_seat("SURV", null, "tok-s")
	fake.server_send(round_view(1))
	check(Feed.models.has("round"), "the Survivors round model is built again")
	eq(Session.screen, "round", "on the round screen")
