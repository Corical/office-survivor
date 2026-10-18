extends Node
## Real window, real main scene: press F11 and Alt+Enter through the input system and read the window mode back.
## Run (needs a display):  godot --path godot res://tests/perf/fullscreen.tscn
## Prints FULLSCREEN PASS or FULLSCREEN FAIL with the modes it saw. Not part of the headless suite (a headless window has no mode).


func _key(code: int, alt := false) -> void:
	var e := InputEventKey.new()
	e.keycode = code
	e.physical_keycode = code
	e.pressed = true
	e.alt_pressed = alt
	Input.parse_input_event(e)
	var r := InputEventKey.new()
	r.keycode = code
	r.pressed = false
	Input.parse_input_event(r)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _ready() -> void:
	var main: Node = load("res://main.tscn").instantiate()
	add_child(main)
	await _frames(20)
	var start := DisplayServer.window_get_mode()
	_key(KEY_F11)
	await _frames(30)
	var after_f11 := DisplayServer.window_get_mode()
	var size_full := DisplayServer.window_get_size()
	_key(KEY_ENTER, true)
	await _frames(30)
	var after_alt_enter := DisplayServer.window_get_mode()
	_key(KEY_ENTER)
	await _frames(15)
	var after_enter := DisplayServer.window_get_mode()
	_key(KEY_F11)
	await _frames(30)
	var after_second_f11 := DisplayServer.window_get_mode()
	print("FULLSCREEN modes: start=%d f11=%d (size %s) alt_enter=%d plain_enter=%d f11_again=%d" % [
		start, after_f11, size_full, after_alt_enter, after_enter, after_second_f11])
	var ok := start == DisplayServer.WINDOW_MODE_WINDOWED \
		and after_f11 == DisplayServer.WINDOW_MODE_FULLSCREEN \
		and after_alt_enter == DisplayServer.WINDOW_MODE_WINDOWED \
		and after_enter == DisplayServer.WINDOW_MODE_WINDOWED \
		and after_second_f11 == DisplayServer.WINDOW_MODE_FULLSCREEN
	print("FULLSCREEN PASS" if ok else "FULLSCREEN FAIL")
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	get_tree().quit(0 if ok else 1)
