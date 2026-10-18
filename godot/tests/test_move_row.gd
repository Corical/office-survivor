extends BaseTest
## The move row keeps its shape from night to night (a move that is not on offer stays, greyed out, with a reason), captions
## are one line, the "Your pick" panel always takes its room, and a greyed-out Lock has no light moving across it.

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _mount(n: int, legal_without := "", locked := false, secs := 120.0, pick := false) -> RoundScreen:
	Themes.use("placeholder")
	var v := round_view(n, locked, secs)
	if legal_without != "":
		v.legal.erase(legal_without)
		v.me.guarded = true
	if pick:
		v.my_pick = {"kind": "steal", "target": "Fig", "amount": 1}
	fake.server_send(v)
	var s := RoundScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


func _moves(s: Node) -> Array:
	return Ui.find_all(s, "move_").filter(func(b): return b is Button)


func test_a_night_without_a_move_keeps_the_row_the_same_length() -> void:
	go_online()
	give_seat()
	var n1 := _moves(_mount(1)).size()
	var s2 := _mount(2, "guard")
	eq(_moves(s2).size(), n1, "same number of medallions on the next night")
	var gone := Ui.find(s2, "move_guard") as Button
	check(gone != null and gone.disabled, "the missing move is there, greyed out")
	var why := Ui.find(s2, "why_unavailable") as Label
	check(why.text.length() > 0, "and the reason is written under the row: " + why.text)


func test_the_reason_line_is_there_even_when_empty() -> void:
	go_online()
	give_seat()
	var s := _mount(1)
	var why := Ui.find(s, "why_unavailable") as Label
	check(why != null and why.custom_minimum_size.y >= 24.0, "reserved height, so nothing jumps when it fills")
	eq(why.text, "", "and nothing written when every move is on offer")


func test_a_new_game_forgets_the_old_rows() -> void:
	go_online()
	give_seat()
	_mount(3, "guard")
	var s := _mount(1)
	eq(_moves(s).size(), 4, "round 1 starts from what is offered")


func test_the_pick_shows_in_the_prompt_row_without_changing_its_height() -> void:
	go_online()
	give_seat()
	var s1 := _mount(1)
	s1.size = Vector2(540, 960)
	await get_tree().process_frame
	await get_tree().process_frame
	var none := Ui.find(s1, "pick_prompt") as Label
	check(none != null, "no pick: the quiet prompt")
	var h_none: float = none.size.y
	var s2 := _mount(1, "", false, 120.0, true)
	s2.size = Vector2(540, 960)
	await get_tree().process_frame
	await get_tree().process_frame
	var some := Ui.find(s2, "my_pick") as Label
	check(some != null and some.text.begins_with("Your pick"), "a pick: the same row says what it is")
	eq(h_none, some.size.y, "same height both ways: nothing moves when a move is chosen")


func test_a_greyed_out_lock_has_no_light_moving_across_it() -> void:
	go_online()
	give_seat()
	var s := _mount(1, "", false, 60.0, false)       # nothing picked: Lock is disabled
	s._tick()
	check(s._lock_btn.disabled, "the Lock is disabled with no pick")
	eq(s._charge.fraction, 0.0, "no charge light on it")
	var locked := _mount(1, "", true, 60.0, true)
	locked._tick()
	eq(locked._charge.fraction, 0.0, "none once locked either")


func test_the_charge_light_runs_when_the_lock_is_live() -> void:
	go_online()
	give_seat()
	var s := _mount(1, "", false, 30.0, true)
	check(not s._lock_btn.disabled, "Lock is live with a pick")
	await get_tree().create_timer(0.4).timeout
	s._tick()
	check(s._charge.fraction > 0.0, "and its light is on once time has run: %f" % s._charge.fraction)


func test_captions_are_one_fitted_line() -> void:
	go_online()
	give_seat()
	var s := _mount(1)
	Themes.use("flash")
	s._build()
	for b in _moves(s):
		var cap: Node = b.get_child(b.get_child_count() - 1)
		check(cap is FitLabel, "%s has a fitted caption" % b.name)
	for b in _moves(s):
		check(b.text == "", "the caption is not the button's own wrapping text")
