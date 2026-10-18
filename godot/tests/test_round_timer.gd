extends BaseTest
## The round clock must create urgency: colour stages by seconds left, a bigger beating number at the end, a call to act for
## an unpicked player, and a ring that drains every frame rather than once a second. (Round screen items of the stranger
## pass: #1 and #21.)

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _screen(secs: float, locked := false, pick := false) -> RoundScreen:
	Themes.use("placeholder")
	go_online()
	give_seat()
	var v := round_view(1, locked, secs)
	if pick:
		v.my_pick = {"kind": "scavenge", "target": null, "amount": 0}
	fake.server_send(v)
	var s := RoundScreen.new()
	add_child(s)
	_mounted.append(s)
	s._tick()
	return s


func _label(s: Node, id: String) -> Label:
	return Ui.find(s, id) as Label


func test_a_calm_clock_is_calm() -> void:
	var s := _screen(100.0)
	eq(s._ring.state, 0, "ring calm")
	eq(str(_label(s, "timer_label").theme_type_variation), "HeaderLabel", "number calm")
	eq(str(_label(s, "pick_prompt").theme_type_variation), "MutedLabel", "no nagging yet")


func test_under_thirty_seconds_the_clock_turns_amber() -> void:
	var s := _screen(25.0)
	eq(s._ring.state, 1, "ring: running short")
	eq(str(_label(s, "timer_label").theme_type_variation), "TimerWarn", "number: running short")


func test_under_ten_seconds_the_clock_is_urgent() -> void:
	var s := _screen(8.0)
	eq(s._ring.state, 2, "ring: urgent")
	eq(str(_label(s, "timer_label").theme_type_variation), "TimerUrgent", "number: urgent")


func test_the_stage_edges_are_exactly_thirty_and_ten() -> void:
	eq(_screen(31.0)._ring.state, 0, "31 s is calm")
	eq(_screen(29.0)._ring.state, 1, "29 s is short")
	eq(_screen(11.0)._ring.state, 1, "11 s is short")
	eq(_screen(9.0)._ring.state, 2, "9 s is urgent")


func test_an_unpicked_player_under_twenty_seconds_is_told_to_pick() -> void:
	var s := _screen(15.0)
	var p := _label(s, "pick_prompt")
	eq(p.text, "Pick a move!", "the call to act")
	eq(str(p.theme_type_variation), "PromptLabel", "in its loud style")
	var calm := _screen(40.0)
	eq(_label(calm, "pick_prompt").text, "Pick a move", "not before twenty seconds")


func test_a_player_who_has_picked_or_locked_is_not_nagged() -> void:
	eq(_label(_screen(15.0, false, true), "pick_prompt").text, "Pick a move", "picked: quiet")
	eq(_label(_screen(15.0, true, true), "pick_prompt").text, "Pick a move", "locked: quiet")


func test_the_prompt_never_changes_the_height_of_its_row() -> void:
	var s := _screen(15.0)
	check(_label(s, "pick_prompt").custom_minimum_size.y >= 30.0, "the row reserves room for the loud version, so nothing jumps")


func test_the_ring_drains_between_the_servers_whole_seconds() -> void:
	var s := _screen(100.0)
	s._tick()
	var v1: float = s._ring.value
	await get_tree().create_timer(0.15).timeout
	s._tick()
	var v2: float = s._ring.value
	check(v2 < v1, "the ring moved without the clock ticking a second: %f -> %f" % [v1, v2])
	check(v1 - v2 < 1.0, "and by a fraction of a second only")
	await get_tree().create_timer(0.15).timeout
	s._tick()
	check(s._ring.value < v2, "and again a frame later")


func test_the_number_keeps_clear_of_the_ring() -> void:
	var s := _screen(169.0)
	var l := _label(s, "timer_label")
	check(l is FitLabel, "the number is a fitted label: it shrinks rather than touch the ring")
	check(l.offset_left >= 20.0 and l.offset_right <= -20.0, "with room each side inside the ring: %f / %f" % [l.offset_left, l.offset_right])
