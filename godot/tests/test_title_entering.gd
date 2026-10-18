extends BaseTest
## Tapping Create or Join must not re-lay the title out before the screen changes (a "Rejoin camp" button flashed in the
## moment the seat arrived), and the new-camp sheet must fade in rather than cut in.

var _mounted: Array = []
var _calm := false


func setup() -> void:
	super.setup()
	Themes.use("flash")
	_calm = Themes.reduced_motion
	Themes.settings_store = null
	Themes.reduced_motion = false


func teardown() -> void:
	super.teardown()
	Themes.reduced_motion = _calm
	Themes.use("placeholder")
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _title() -> Control:
	var s: Control = TitleScreen.new()
	s.theme = Themes.current.godot_theme
	add_child(s)
	_mounted.append(s)
	return s


func _press(s: Node, id: String) -> void:
	var b := Ui.find(s, id) as Button
	check(b != null, "no control '%s'" % id)
	if b != null:
		b.pressed.emit()


func test_the_seat_arriving_does_not_rebuild_the_title_or_show_rejoin() -> void:
	var s := _title()
	var create := Ui.find(s, "create") as Button
	_press(s, "create")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	check(Feed.status().entering, "entering from the tap")
	fake.server_send({"t": "seat", "token": "t1", "room_code": "ABCD", "alias": "Mango", "host": true})
	check(Feed.status().entering, "still entering with the seat in hand and no view yet")
	check(Feed.status().has_seat, "the seat is held")
	check(Ui.find(s, "resume") == null, "no Rejoin camp button between the seat and the first view")
	check(is_instance_valid(create) and create.is_inside_tree(), "the title was not rebuilt (the very same Create button is still there)")
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 1, "seats_total": 4, "host": true})
	check(not Feed.status().entering, "no longer entering once the first view is in")


func test_a_stored_seat_does_not_bring_rejoin_back_while_creating() -> void:
	Session.token = "old"
	Session.room_code = "WXYZ"
	var s := _title()
	check(Ui.find(s, "resume") != null, "before: the stored seat offers Rejoin")
	_press(s, "create")
	check(Ui.find(s, "resume") == null, "after the tap: no Rejoin while the new camp is being made")


func test_resume_is_not_entering() -> void:
	Session.token = "tok"
	Session.room_code = "ABCD"
	var s := _title()
	check(Ui.find(s, "resume") != null, "resume offered")
	check(not Feed.status().entering, "a stored seat is not 'entering'")


func test_a_refused_join_ends_entering_and_the_title_comes_back_to_life() -> void:
	var s := _title()
	var edit := Ui.find(s, "code") as LineEdit
	edit.text = "ZZZZ"
	edit.text_changed.emit("ZZZZ")
	_press(s, "join")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	check(Feed.status().entering, "joining")
	fake.server_send({"t": "error", "code": "room_gone", "message": "There's no room with that code."})
	check(not Feed.status().entering, "the refusal ends it")
	check(Ui.find(s, "notice") != null, "and the reason is shown")


func test_leaving_or_a_terminal_reason_never_leaves_entering_stuck_on() -> void:
	var s := _title()
	_press(s, "create")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "seat", "token": "t1", "room_code": "ABCD", "alias": "Mango", "host": true})
	check(Feed.status().entering, "entering")
	Intents.leave()
	check(not Feed.status().entering, "leave clears it")
	Session.seat_pending_view = true
	Session.back_to_title()
	check(not Feed.status().entering, "back to title clears it")


func _open_sheet(s: Control) -> void:
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "rooms", "rooms": []})
	_press(s, "create")


func test_the_new_camp_sheet_fades_in_and_is_not_replayed_by_a_rebuild() -> void:
	var s := _title()
	_open_sheet(s)
	var sheet := Ui.find(s, "sheet") as Control
	check(sheet != null, "the sheet is open")
	if sheet == null:
		return
	check(sheet.modulate.a < 0.05, "it starts invisible (a fade, not a cut): %.2f" % sheet.modulate.a)
	var samples := []
	for i in 11:
		await get_tree().create_timer(0.05).timeout
		samples.append((Ui.find(s, "sheet") as Control).modulate.a)
	var partway := 0
	for i in samples.size():
		if samples[i] > 0.05 and samples[i] < 0.95:
			partway += 1
		if i > 0:
			check(samples[i] >= samples[i - 1] - 0.001, "it never gets less visible on the way in: %s" % [samples])
	check(partway >= 2, "it is seen part-way for at least two samples (a fade, not a jump): %s" % [samples])
	eq((Ui.find(s, "sheet") as Control).modulate.a, 1.0, "fully in after the transition time")
	s._build()                                              # e.g. a status change rebuilds the title under the open sheet
	eq((Ui.find(s, "sheet") as Control).modulate.a, 1.0, "a rebuild does not replay the fade")


func test_reduced_motion_keeps_the_fade_and_drops_the_settling() -> void:
	Themes.reduced_motion = true
	var s := _title()
	_open_sheet(s)
	var sheet := Ui.find(s, "sheet") as Control
	check(sheet != null and sheet.modulate.a < 0.05, "still fades from nothing")
	var card := sheet.get_child(0).get_child(0) as Control
	eq(card.scale, Vector2.ONE, "but the card does not scale in")
	await get_tree().create_timer(0.55).timeout
	eq((Ui.find(s, "sheet") as Control).modulate.a, 1.0, "and arrives")
