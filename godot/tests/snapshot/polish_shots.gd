extends Control
## Before/after pictures for the title, lobby and end screens at the three sizes the owner checks, with the clearance
## audit on every one. Not headless.
##   godot --path godot res://tests/snapshot/polish_shots.tscn -- --out=<dir> [--theme=flash]
## Output files are named <screen>_<state>_<width>x<height>.png.

const SIZES := [Vector2i(450, 800), Vector2i(540, 960), Vector2i(1904, 1001)]
const NAMES := ["SoggyBiscuit", "LuckyLantern", "IronSpatula", "QuietOtter"]

var out_dir := ""
var theme_id := "flash"
var only := ""
var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control
var violations := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
		elif a.begins_with("--theme="):
			theme_id = a.substr(8)
		elif a.begins_with("--only="):
			only = a.substr(7)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Themes.use(theme_id)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	await _size(SIZES[1])
	await _wait(0.9)
	if only == "" or only == "title":
		await _title()
	if only == "" or only == "lobby":
		await _lobby()
	if only == "" or only == "end":
		await _end()
	print("POLISH CLEARANCE TOTAL: ", violations, " violations")
	print("POLISH DONE ", out_dir)
	get_tree().quit(0)


func _title() -> void:
	for s in SIZES:
		await _size(s)
		await _wait(0.5)
		await _shot("title_idle", s)
	var settings := Ui.find(router.current, "settings_toggle") as Button
	if settings != null:
		settings.pressed.emit()
		for s in SIZES:
			await _size(s)
			await _wait(0.4)
			await _shot("title_settings", s)
		var adv := Ui.find(router.current, "advanced_toggle") as Button
		if adv != null:
			adv.pressed.emit()
			for s in SIZES:
				await _size(s)
				await _wait(0.4)
				await _shot("title_settings_advanced", s)
			(Ui.find(router.current, "advanced_toggle") as Button).pressed.emit()
		(Ui.find(router.current, "settings_toggle") as Button).pressed.emit()
	await _size(SIZES[1])
	var create := Ui.find(router.current, "create") as Button
	if create != null:
		create.pressed.emit()
		await _wait(0.4)
		for s in SIZES:
			await _size(s)
			await _wait(0.4)
			await _shot("title_sheet", s)
		var cancel := Ui.find(router.current, "sheet_cancel") as Button
		if cancel != null:
			cancel.pressed.emit()
			await _wait(0.3)


func _seat(host: bool) -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "polish-token", "room_code": "KXQM", "alias": NAMES[0], "host": host})


func _lobby() -> void:
	_seat(true)
	var here := {"id": "h-a", "connected": true}
	var gone := {"id": "h-b", "connected": false}
	var states := [["host_1of4", true, 1, []], ["host_4of4", true, 4, [here, here, here]], ["guest_2of4", false, 2, []],
		["host_dropped_seat", true, 3, [here, gone]], ["host_all_here", true, 3, [here, {"id": "h-c", "connected": true}]]]
	for st in states:
		fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": st[2], "seats_total": 4, "host": st[1], "seats": st[3]})
		await _wait(0.8)
		for s in SIZES:
			await _size(s)
			await _wait(0.4)
			await _shot("lobby_" + st[0], s)


## Scores per player, in the order the server sends them; goal_done and seat follow the first two.
func _end_msg(scores: Array, winners: Array) -> Dictionary:
	var rows := []
	for i in scores.size():
		rows.append({"alias": NAMES[i], "score": scores[i], "rations": 6 - i, "seat": i == 0, "goal_done": i % 2 == 0,
			"stole": i, "times_robbed": i + 1, "gave_away": 3 - i})
	var win_names := []
	for w in winners:
		win_names.append(NAMES[w])
	return {"t": "end", "extracted": [NAMES[0]], "winners": win_names, "results": rows}


func _end() -> void:
	if only == "end":
		_seat(true)
	var shapes := {
		"three_tied_second": [[5, 3, 3, 3], [0]],
		"four_tied": [[4, 4, 4, 4], [0, 1, 2, 3]],
		"distinct": [[7, 5, 3, 1], [0]],
	}
	for key in shapes:
		fake.server_send(_end_msg(shapes[key][0], shapes[key][1]))
		await _wait(1.6)
		for s in SIZES:
			await _size(s)
			await _wait(0.5)
			await _shot("end_" + key, s)
			_audit("end %s %s" % [key, s])


func _audit(tag: String) -> void:
	var found := Clearance.check(router)
	violations += found.size()
	for v in found:
		print("CLEARANCE ", tag, ": ", v)


func _size(s: Vector2i) -> void:
	get_window().size = s
	await _wait(0.5)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _shot(shot_name: String, s: Vector2i) -> void:
	_audit("%s %s" % [shot_name, s])
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := out_dir.path_join("%s_%dx%d.png" % [shot_name, s.x, s.y])
	print("shot ", path, " ", img.get_size(), " err=", img.save_png(path))
