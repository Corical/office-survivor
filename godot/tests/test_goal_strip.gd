extends BaseTest
## At phone width the player's goal sits directly under the header (not below the fold) and a tap opens or closes the detail.

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _screen(w: float) -> RoundScreen:
	Themes.use("placeholder")
	go_online()
	give_seat()
	var v := round_view(1, false, 120.0)
	v.me.goal = {"code": "robbed2_extract", "text": "get robbed at least 1x and still get a seat on the helicopter", "target": null}
	fake.server_send(v)
	var s := RoundScreen.new()
	add_child(s)
	s.set_anchors_preset(Control.PRESET_TOP_LEFT)
	s.size = Vector2(w, 800)
	_mounted.append(s)
	return s


func _y(s: Node, id: String) -> float:
	return (Ui.find(s, id) as Control).get_global_rect().position.y


func test_the_goal_comes_before_the_moves_at_phone_width() -> void:
	var s := _screen(450)
	await get_tree().process_frame
	await get_tree().process_frame
	check(Ui.find(s, "goal") != null, "the goal is on the screen")
	check(_y(s, "goal") < _y(s, Ui.find_all(s, "move_")[0].get_meta("id")), "above the moves, so it is in the first screenful")
	check(_y(s, "goal") < 330.0, "and near the top: y=%f" % _y(s, "goal"))


func test_collapsed_by_default_and_a_tap_opens_the_detail() -> void:
	var s := _screen(450)
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	check(Ui.find(s, "goal_status") == null, "collapsed: " + str(Ui.texts(s)))
	check(Ui.find(s, "goal_note") == null, "collapsed: no seat note yet")
	var card: Control = Ui.find(s, "goal").get_parent().get_parent()
	var up := InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	card.gui_input.emit(up)
	check(s._goal_open, "a tap opens the goal")
	check(Ui.find(s, "goal_status") != null, "after a tap: how it is going")
	check(Ui.find(s, "goal_note") != null, "and what a seat is")
	s.size = Vector2(450, 800)                             # (a test window may grow the screen when it lays out)
	s._build()
	var card2: Control = Ui.find(s, "goal").get_parent().get_parent()
	card2.gui_input.emit(up)
	check(not s._goal_open, "a second tap closes it again")


func test_a_wide_window_shows_everything_without_a_tap() -> void:
	var s := _screen(1200)
	await get_tree().process_frame
	await get_tree().process_frame
	check(Ui.find(s, "goal_status") != null and Ui.find(s, "goal_note") != null, "wide: the whole goal card is open")
	check(Ui.find(s, "goal_toggle_hint") == null, "and there is nothing to tap")
