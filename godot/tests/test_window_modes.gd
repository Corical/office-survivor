extends BaseTest
## Full screen: the decision (which mode next) and the key that asks for it. Applying a mode to a real window is a one-line
## call checked by hand; everything that can be wrong without a window is here.


func _key(code: int, pressed := true, echo := false, alt := false) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = code
	e.pressed = pressed
	e.echo = echo
	e.alt_pressed = alt
	return e


func test_every_mode_goes_somewhere_sane() -> void:
	eq(WindowModes.next(DisplayServer.WINDOW_MODE_WINDOWED), WindowModes.FULLSCREEN, "windowed -> full screen")
	eq(WindowModes.next(DisplayServer.WINDOW_MODE_MAXIMIZED), WindowModes.FULLSCREEN, "maximised -> full screen")
	eq(WindowModes.next(DisplayServer.WINDOW_MODE_MINIMIZED), WindowModes.FULLSCREEN, "minimised -> full screen")
	eq(WindowModes.next(DisplayServer.WINDOW_MODE_FULLSCREEN), WindowModes.WINDOWED, "full screen -> windowed")
	eq(WindowModes.next(DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN), WindowModes.WINDOWED, "exclusive full screen -> windowed")
	for odd in [-1, 99, 2147483647]:
		var n := WindowModes.next(odd)
		check(n == WindowModes.WINDOWED or n == WindowModes.FULLSCREEN, "an unexpected mode %d cannot produce an unexpected one" % odd)


func test_toggling_twice_comes_back() -> void:
	var m := DisplayServer.WINDOW_MODE_WINDOWED
	eq(WindowModes.next(WindowModes.next(m)), m, "there and back")


func test_only_the_real_shortcuts_toggle() -> void:
	check(WindowModes.is_toggle(_key(KEY_F11)), "F11")
	check(WindowModes.is_toggle(_key(KEY_ENTER, true, false, true)), "Alt+Enter")
	check(WindowModes.is_toggle(_key(KEY_KP_ENTER, true, false, true)), "Alt+keypad Enter")
	check(not WindowModes.is_toggle(_key(KEY_ENTER)), "Enter alone must never toggle (it submits a text box)")
	check(not WindowModes.is_toggle(_key(KEY_ALT, true, false, true)), "Alt alone")
	check(not WindowModes.is_toggle(_key(KEY_F10)), "another function key")
	check(not WindowModes.is_toggle(_key(KEY_F11, false)), "a key release")
	check(not WindowModes.is_toggle(_key(KEY_F11, true, true)), "a held key (echo) must not flicker the window")
	check(not WindowModes.is_toggle(_key(KEY_ENTER, false, false, true)), "Alt+Enter release")
	check(not WindowModes.is_toggle(InputEventMouseButton.new()), "a mouse event")
	check(not WindowModes.is_toggle(InputEventScreenTouch.new()), "a touch")


func test_toggle_does_nothing_where_there_is_no_window_to_toggle() -> void:
	if not WindowModes.available():
		WindowModes.toggle()                           # must not throw on a phone
		check(true, "no-op without a desktop window")
	else:
		check(WindowModes.available(), "desktop: available")
