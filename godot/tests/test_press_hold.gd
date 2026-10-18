extends BaseTest
## A tap whose press and release straddle a rebuild is lost (the button the finger went down on is replaced by a new one).
## The server echoing a pick or a radio send rebuilds the round screen, so while a press is held the buttons must stay the same
## nodes, and the rebuild happens on release. The windowed driver failed "the lock was never confirmed" on exactly this.

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _view(pick: Variant = null) -> Dictionary:
	var v := round_view(1, false, 120)
	v.my_pick = pick
	return v


func _screen() -> RoundScreen:
	Themes.use("placeholder")
	go_online()
	give_seat()
	fake.server_send(_view({"kind": "scavenge", "target": null, "amount": 0}))
	var s := RoundScreen.new()
	add_child(s)
	s.set_anchors_preset(Control.PRESET_TOP_LEFT)
	s.size = Vector2(450, 800)
	_mounted.append(s)
	return s


func _mouse(s: RoundScreen, down: bool, button := MOUSE_BUTTON_LEFT) -> void:
	var ev := InputEventMouseButton.new()
	ev.button_index = button
	ev.pressed = down
	s._input(ev)


func _touch(s: RoundScreen, down: bool, index: int) -> void:
	var ev := InputEventScreenTouch.new()
	ev.index = index
	ev.pressed = down
	s._input(ev)


## A server push that changes what the screen draws (the echo of a different pick).
func _echo() -> void:
	fake.server_send(_view({"kind": "guard", "target": null, "amount": 0}))


func _lock(s: Node) -> Button:
	return Ui.find(s, "lock") as Button


func _locks_sent() -> int:
	return fake.sent.filter(func(m): return m.get("t") == "lock").size()


func test_an_echo_while_a_press_is_held_does_not_replace_the_button() -> void:
	var s := _screen()
	var btn := _lock(s)
	_mouse(s, true)
	_echo()
	check(is_instance_valid(btn) and not btn.is_queued_for_deletion(), "the button under the finger is still alive")
	check(_lock(s) == btn, "and it is still the screen's Lock button")
	check(btn.is_inside_tree(), "and still on screen")


func test_the_tap_completes_on_the_original_button_and_the_lock_is_sent() -> void:
	var s := _screen()
	var btn := _lock(s)
	check(not btn.disabled, "setup: Lock is live with a pick in")
	_mouse(s, true)
	_echo()
	check(btn.is_inside_tree() and not btn.is_queued_for_deletion(), "at the release the pressed button is still on screen")
	_mouse(s, false)
	btn.pressed.emit()                      # what the button does when the release reaches it (only a live button gets it)
	eq(_locks_sent(), 1, "the lock went out")


func test_the_deferred_rebuild_happens_after_the_release_and_shows_the_newest_view() -> void:
	var s := _screen()
	var before := _lock(s)
	_mouse(s, true)
	_echo()
	_mouse(s, false)
	await get_tree().process_frame
	await get_tree().process_frame
	check(_lock(s) != before, "rebuilt once the press was let go")
	check(s._sig == s._signature(s._m), "and it shows the newest view")
	check(str(s._m.my_pick.move_id) == "guard", "the model is the echoed one")


func test_without_a_press_an_echo_rebuilds_at_once() -> void:
	var s := _screen()
	var before := _lock(s)
	_echo()
	check(_lock(s) != before, "no press held: rebuilt straight away")


func test_many_echoes_while_held_collapse_into_one_rebuild_with_the_last_view() -> void:
	var s := _screen()
	var before := _lock(s)
	_mouse(s, true)
	for k in ["guard", "scavenge", "guard"]:
		fake.server_send(_view({"kind": k, "target": null, "amount": 0}))
	check(_lock(s) == before, "still the same button")
	_mouse(s, false)
	await get_tree().process_frame
	await get_tree().process_frame
	check(_lock(s) != before, "rebuilt")
	eq(str(s._m.my_pick.move_id), "guard", "from the last view")
	eq(s._sig, s._signature(s._m), "and it is the one drawn")


func test_a_release_that_never_comes_cannot_freeze_the_screen() -> void:
	var s := _screen()
	var before := _lock(s)
	_mouse(s, true)
	_echo()
	check(_lock(s) == before, "held: waiting")
	s._held_since_ms -= RoundScreen.HOLD_MAX_MS + 500       # the release was lost (the window lost focus mid-tap)
	s._process(0.016)
	check(_lock(s) != before, "after the cap the screen rebuilds anyway")
	check(s._held.is_empty(), "and forgets the phantom press")
	var again := _lock(s)
	_echo_other()
	check(_lock(s) != again, "the next push rebuilds normally, nothing stays stuck")


func _echo_other() -> void:
	fake.server_send(_view({"kind": "scavenge", "target": null, "amount": 0}))


func test_two_fingers_the_rebuild_waits_for_both() -> void:
	var s := _screen()
	var before := _lock(s)
	_touch(s, true, 0)
	_touch(s, true, 1)
	_echo()
	_touch(s, false, 0)
	await get_tree().process_frame
	check(_lock(s) == before, "one finger still down: no rebuild")
	_touch(s, false, 1)
	await get_tree().process_frame
	check(_lock(s) != before, "both up: rebuilt")


func test_a_release_with_no_press_and_other_mouse_buttons_are_harmless() -> void:
	var s := _screen()
	var before := _lock(s)
	_mouse(s, false)                                         # a release whose press we never saw
	_mouse(s, true, MOUSE_BUTTON_RIGHT)
	_mouse(s, false, MOUSE_BUTTON_LEFT)                      # the left release does not end the right press
	_echo()
	check(_lock(s) == before, "the right button is still held: waiting")
	_mouse(s, false, MOUSE_BUTTON_RIGHT)
	await get_tree().process_frame
	check(_lock(s) != before, "rebuilt after the right button is let go")
	_echo_other()
	check(s._held.is_empty(), "nothing left held")


func test_focus_lost_during_a_press_lets_the_rebuild_through() -> void:
	var s := _screen()
	var before := _lock(s)
	_mouse(s, true)
	_echo()
	s._notification(Node.NOTIFICATION_WM_WINDOW_FOCUS_OUT)
	await get_tree().process_frame
	check(_lock(s) != before, "focus loss ends the held press")


func test_a_round_change_while_held_still_resets_the_local_pick_state() -> void:
	var s := _screen()
	s._move = {"server_id": "steal"}
	_mouse(s, true)
	fake.server_send(round_view(2, false, 120))
	eq(s._move, {}, "the next round forgets a half-made pick even while the screen waits")
	_mouse(s, false)
	await get_tree().process_frame
	eq(int(s._m.round), 2, "and draws round 2 after the release")
