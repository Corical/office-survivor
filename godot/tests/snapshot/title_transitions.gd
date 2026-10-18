extends Control
## How hard does the title cut when you tap Create? Records the window at 30 frames a second (like the stranger pass did)
## through two taps and prints the largest frame-to-frame difference (mean absolute brightness change over the picture,
## 0 to 255; a hard cut of a dark veil or a new screen is 30 or more, a fade is a few):
##   A. Create on a server that lists camps: the new-camp sheet opens.
##   B. Create on a server that does not: the camp is made straight away, the seat arrives, the lobby follows.
## Also reports whether a "Rejoin camp" button was on screen in any frame of B (it must never be).
##   godot --path godot res://tests/snapshot/title_transitions.tscn -- --out=<dir> [--name=after]

const SIZE := Vector2i(450, 800)
const FPS := 30.0
const STEP := 3                       # sample every third pixel each way: enough for a mean, 9x faster

var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control
var _out := ""
var _name := "run"


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			_out = a.substr(6)
		elif a.begins_with("--name="):
			_name = a.substr(7)
	DirAccess.make_dir_recursive_absolute(_out)
	await get_tree().process_frame
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Themes.use("flash")
	Themes.reduced_motion = false
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	get_window().size = SIZE
	await _wait(1.2)
	await _run_a()
	await _wait(0.5)
	await _run_b()
	get_tree().quit(0)


func _wait(s: float) -> void:
	await get_tree().create_timer(s).timeout


func _luma(img: Image) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	for y in range(0, img.get_height(), STEP):
		for x in range(0, img.get_width(), STEP):
			var p := img.get_pixel(x, y)
			out.append((p.r * 0.3 + p.g * 0.59 + p.b * 0.11) * 255.0)
	return out


## Grab frames at 30 fps for `seconds`, calling `at` (a Callable taking the frame index) before each grab.
func _record(seconds: float, tag: String, at: Callable) -> Dictionary:
	var prev := PackedFloat32Array()
	var worst := 0.0
	var worst_i := -1
	var n := int(seconds * FPS)
	var rejoin_frames := 0
	var first_png := true
	for i in n:
		at.call(i)
		await _wait(1.0 / FPS)
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		if router.current != null and Ui.find(router.current, "resume") != null:
			rejoin_frames += 1
		var cur := _luma(img)
		if prev.size() == cur.size():
			var sum := 0.0
			for k in cur.size():
				sum += absf(cur[k] - prev[k])
			var d := sum / float(cur.size())
			if d > worst:
				worst = d
				worst_i = i
		prev = cur
		if i % 3 == 0:
			img.save_png(_out.path_join("%s_%s_%02d.png" % [_name, tag, i]))
	print("TRANSITION %s %s: %d frames at %d fps, largest frame-to-frame difference %.1f (at frame %d), frames with a Rejoin button %d" % [
		_name, tag, n, int(FPS), worst, worst_i, rejoin_frames])
	return {"worst": worst, "rejoin": rejoin_frames}


func _run_a() -> void:
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	await _wait(0.3)
	fake.server_send({"t": "rooms", "rooms": []})
	await _wait(0.4)
	var tapped := [false]
	await _record(1.5, "A_sheet", func(i):
		if i == 6 and not tapped[0]:
			tapped[0] = true
			(Ui.find(router.current, "create") as Button).pressed.emit())
	var cancel := Ui.find(router.current, "sheet_cancel") as Button
	if cancel != null:
		cancel.pressed.emit()
	await _wait(0.6)


func _run_b() -> void:
	# a server that does not list camps: Create makes the camp straight away
	fake.server_close(1000)
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	await _wait(0.3)
	var state := {"tapped": false, "seat_at": -1, "lobby_at": -1}
	await _record(2.0, "B_create", func(i):
		if i == 6 and not state.tapped:
			state.tapped = true
			(Ui.find(router.current, "create") as Button).pressed.emit()
			fake.server_open()
			fake.server_send({"t": "hello_ok", "proto": 1})
		if i == 12 and state.seat_at < 0:
			state.seat_at = i
			fake.server_send({"t": "seat", "token": "tt", "room_code": "KXQM", "alias": "Mango", "host": true})
		if i == 15 and state.lobby_at < 0:
			state.lobby_at = i
			fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": 1, "seats_total": 4, "host": true}))
