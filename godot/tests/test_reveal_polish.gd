extends BaseTest
## Stranger-pass items on the reveal and the screen change: a band label that waits for its explanation, the "waiting for the
## others" caption, a screen that stops reacting once it is fading out, and an event (the tide) that is always in the log.

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _stage_with(beats: Array, finished := false, index := 0) -> Stage:
	var s := Stage.new()
	add_child(s)
	_mounted.append(s)
	s._beats = beats
	s._timeline = Timeline.new(1, beats)
	s._timeline.finished = finished
	s._timeline.index = beats.size() if finished else index
	return s


func _rich_stage() -> Stage:
	Themes.use("flash")
	var s := Stage.new()
	add_child(s)
	_mounted.append(s)
	s._load_art()
	s._pos = {"@me": Vector2(100, 200), "Fig": Vector2(200, 100), "Plum": Vector2(50, 100)}
	return s


func _beat_of(kind: String, from_: String, to: String, style: String) -> Dictionary:
	return {"kind": kind, "from": from_, "to": to, "amount_out": 0, "amount_in": 0, "style": style, "detail": ""}


func test_a_caught_thief_and_an_exposed_thief_are_flagged_on_their_own_huts() -> void:
	var s := _rich_stage()
	check(s._rich, "the flash theme draws huts")
	s._on_beat(_beat_of("blocked", "@me", "Fig", "guard"))
	check(float(s._hurt.get("@me", 0.0)) > 0.9, "I walked into a guard: my own hut flashes")
	check(not s._hurt.has("Fig"), "the guard's hut is not flagged as the thief")
	s._on_beat(_beat_of("blocked", "Plum", "@me", "guard"))
	check(float(s._hurt.get("Plum", 0.0)) > 0.9, "Plum was caught by me: Plum's hut flashes")
	s._on_beat(_beat_of("marked", "@me", "Fig", "exposed"))
	check(float(s._exposed.get("Fig", 0.0)) > 0.9, "Fig was exposed: Fig's hut is tinted")


func test_nothing_is_flagged_when_nobody_nameable_was_caught() -> void:
	var s := _rich_stage()
	s._on_beat(_beat_of("blocked", "@offstage", "@me", "guard"))   # an unnamed thief: no hut to point at
	s._on_beat(_beat_of("blocked", "@offstage", "@me", "idol"))    # an idol saved me: nobody was caught
	s._on_beat(_beat_of("blocked", "Fig", "@me", "idol"))          # an idol, not a guard: no thief to flag
	s._on_beat(_beat_of("marked", "@me", "@offstage", "exposed"))  # an exposure with no named thief
	eq(s._hurt.size(), 0, "no hut flashed: %s" % [s._hurt])
	eq(s._exposed.size(), 0, "no hut tinted: %s" % [s._exposed])


func test_the_flags_fade_out_and_calm_mode_has_none() -> void:
	var s := _rich_stage()
	s._on_beat(_beat_of("blocked", "@me", "Fig", "guard"))
	s._on_beat(_beat_of("marked", "@me", "Fig", "exposed"))
	s._roster = [{"alias": "Fig", "is_me": false, "band": "", "band_before": ""}]
	s._timeline = Timeline.new(1, [_beat_of("quiet", "@offstage", "@offstage", "")])
	s._beats = s._timeline.beats
	for i in 200:
		s._animate(0.05, 0.05)
	check(float(s._hurt.get("@me", 1.0)) == 0.0, "the red flash ends")
	check(float(s._exposed.get("Fig", 1.0)) == 0.0, "the violet tint ends (slower, but ends)")
	Themes.reduced_motion = true
	var calm := _rich_stage()
	calm._on_beat(_beat_of("blocked", "@me", "Fig", "guard"))
	eq(calm._hurt.size(), 0, "calm mode: no flashing")
	Themes.reduced_motion = false


func _beat(from_: String, to: String) -> Dictionary:
	return {"kind": "move_resource", "from": from_, "to": to, "amount_out": 1, "amount_in": 1, "style": "", "detail": ""}


func _fig(before: String, now: String) -> Dictionary:
	return {"alias": "Fig", "is_me": false, "band": now, "band_before": before}


func test_a_changed_band_keeps_the_old_word_until_something_happens_to_that_home() -> void:
	var beats := [_beat("@offstage", "Plum"), _beat("@me", "Kiwi"), _beat("Mango", "Fig"), _beat("@offstage", "Plum")]
	var e := _fig("band.well_fed", "band.starving")
	for i in 3:                                         # beats 0..2 not yet finished: the one touching Fig is index 2
		eq(_stage_with(beats, false, i)._band_of(e), "band.well_fed", "still last morning's word at beat index %d" % i)
	eq(_stage_with(beats, false, 3)._band_of(e), "band.starving", "the beat on Fig has finished: the new word")
	eq(_stage_with(beats, true)._band_of(e), "band.starving", "everything played: the new word")


func test_the_band_word_is_never_held_back_when_there_is_nothing_to_hold() -> void:
	var beats := [_beat("@offstage", "Plum")]
	var s := _stage_with(beats, false, 0)
	eq(s._band_of(_fig("", "band.starving")), "band.starving", "no earlier band known")
	eq(s._band_of(_fig("band.starving", "band.starving")), "band.starving", "unchanged")
	eq(s._band_of(_fig("band.well_fed", "")), "", "ranges off: nothing to show, nothing invented")
	var snapped := Stage.new()
	add_child(snapped)
	_mounted.append(snapped)
	eq(snapped._band_of(_fig("band.well_fed", "band.starving")), "band.starving", "no timeline at all: the new word")


func test_the_band_word_of_a_home_hit_by_a_later_beat_does_not_change_early() -> void:
	# a beat that names the home only as the SENDER counts as touching it too
	var beats := [_beat("Fig", "@offstage"), _beat("@offstage", "Plum")]
	var e := _fig("band.well_fed", "band.getting_by")
	eq(_stage_with(beats, false, 0)._band_of(e), "band.well_fed", "its own beat is playing, not finished")
	eq(_stage_with(beats, false, 1)._band_of(e), "band.getting_by", "its beat has finished")


func test_the_waiting_words_say_how_long_and_leave_no_gap() -> void:
	eq(Words.render("ui.reveal_waiting", {"n": 14}).find("14") >= 0, true, "the countdown is in the sentence")
	check(Words.render("ui.reveal_waiting", {"n": 0}).find("{") < 0, "no raw slot left over at zero")
	in_round(2)
	fake.server_send({"t": "reveal", "round": 2, "news": [], "private": [{"code": "now_have", "args": {"rations": 5}}],
		"radio": [], "board": null, "seconds_left": 20})
	var s := Stage.new()
	add_child(s)
	_mounted.append(s)
	check(s._waiting_text() != "", "a countdown is running, so the caption has something to say")


func test_a_screen_that_is_fading_out_stops_reacting_but_its_neighbour_does_not() -> void:
	var gone := TitleScreen.new()
	var stays := TitleScreen.new()
	add_child(gone)
	add_child(stays)
	_mounted.append(gone)
	_mounted.append(stays)
	var before := _connections_to(stays)
	check(_connections_to(gone) > 0, "the title listens to the feed (lambdas included)")
	var cut := Ui.freeze(gone, [Feed, Themes, Intents])
	check(cut > 0, "something was cut")
	eq(_connections_to(gone), 0, "nothing of the frozen screen is still connected")
	eq(_connections_to(stays), before, "the other screen keeps all of its connections")
	eq(Ui.freeze(gone, [Feed, Themes, Intents]), 0, "freezing twice is harmless")


func test_an_inert_screen_has_no_control_left_that_takes_a_tap() -> void:
	var s := TitleScreen.new()
	add_child(s)
	_mounted.append(s)
	var buttons := 0
	for c in s.find_children("*", "Button", true, false):
		buttons += 1
	check(buttons > 0, "the title has buttons to be stolen")
	Ui.inert(s)
	for c in s.find_children("*", "Control", true, false):
		eq((c as Control).mouse_filter, Control.MOUSE_FILTER_IGNORE, "%s ignores the mouse" % c.name)
		eq((c as Control).focus_mode, Control.FOCUS_NONE, "%s takes no focus" % c.name)


func _connections_to(n: Node) -> int:
	var count := 0
	for src in [Feed, Themes, Intents]:
		for sig in src.get_signal_list():
			for c in src.get_signal_connection_list(sig.name):
				var o: Object = (c.callable as Callable).get_object()
				if o is Node and (o == n or n.is_ancestor_of(o)):
					count += 1
	return count


func test_a_wilderness_event_such_as_the_tide_is_in_the_written_log() -> void:
	in_round(3)
	var tide := "🌊 The tide came in further than Fig expected. -1 ration."
	fake.server_send({"t": "reveal", "round": 3, "seconds_left": 20, "radio": [], "board": null,
		"news": [{"code": "event", "args": {"event": "rain", "line": tide, "scope": "one", "who": "Fig"}}],
		"private": [{"code": "now_have", "args": {"rations": 4}}]})
	var screen := RevealScreen.new()
	add_child(screen)
	_mounted.append(screen)
	var found := false
	for l in Ui.find_all(screen, "line_"):
		if (l as Label).text.contains("tide came in"):
			found = true
	check(found, "the tide sentence is one of the log lines: %s" % [Ui.texts(screen)])
