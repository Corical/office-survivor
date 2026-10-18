extends Control
## Windowed screenshots of the platform screens (picker, game label, seat range, neutral phase, update the app) at the three sizes the
## designer drew (360x640, 412x915, desktop), on a lone-Survivors server and on a two-game server (a fake games list).
##   godot --path godot res://tests/snapshot/platform_shots.tscn -- --out=<dir> --mode=lone|two [--theme=flash|placeholder]
## `lone` is the "before and after" proof: those pictures must be pixel-identical to the ones taken before the picker existed.

const SIZES := [Vector2i(360, 640), Vector2i(412, 915), Vector2i(1280, 720)]
const GAMES_TWO := [
	{"id": "survivors", "name": "Survivors", "seats_min": 3, "seats_max": 8},
	{"id": "placeholder_b", "name": "Placeholder Game B", "seats_min": 3, "seats_max": 8},
	{"id": "game_c", "name": "Game C with a long name here", "seats_min": 2, "seats_max": 5},
]

var out_dir := ""
var mode := "lone"
var theme_id := "flash"
var fake: FakeTransport
var clock := FakeClock.new()
var router: Control
var _violations := 0


## A stand-in second game: one phase that no screen draws.
class Toy:
	extends Ruleset

	func view_types() -> Array:
		return ["view"]

	func phases() -> Dictionary:
		return {"deal": {"screen": "deal"}}

	func view_model(v: Dictionary) -> Dictionary:
		return {"phase": v.get("phase")}


func _toy(id: String) -> Ruleset:
	return Toy.new() if id == "placeholder_b" else RulesetRegistry.try_make(id)


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
		elif a.begins_with("--mode="):
			mode = a.substr(7)
		elif a.begins_with("--theme="):
			theme_id = a.substr(8)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Themes.use(theme_id)
	Themes.reduced_motion = true                       # motion would make two runs of the same code differ; the comparison needs stillness
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_fresh()
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	for s in SIZES:
		var tag := "%dx%d" % [s.x, s.y]
		get_window().size = s
		await _wait(0.6)
		_fresh()
		await _wait(0.4)
		await _shot("title_" + tag)
		_online()
		await _wait(0.6)
		await _shot("picker_" + tag)                         # the title once the server has said what it offers
		fake.server_send({"t": "rooms", "rooms": _rooms()})
		await _wait(0.6)
		_scroll_down()
		await _wait(0.3)
		await _shot("camps_" + tag)
		_fresh()
		_online()
		_seat("KXQM", "survivors" if mode == "lone" else "survivors")
		fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": 2, "seats_total": 4, "host": true})
		await _wait(0.8)
		await _shot("lobby_" + tag)
		if mode == "two":
			_fresh()
			Session.ruleset_factory = _toy
			_online()
			_seat("TOYB", "placeholder_b")
			fake.server_send({"t": "view", "game": "placeholder_b", "phase": "mystery_phase", "phase_id": "p1", "seq": 1})
			await _wait(0.8)
			await _shot("neutral_" + tag)
			_fresh()
			_online()
			_seat("WHAT", "mystery")
			await _wait(0.8)
			await _shot("update_game_" + tag)
		_fresh()
		_online()
		fake.server_send({"t": "upgrade_required", "min_proto": 2, "message": "x"})
		await _wait(0.8)
		await _shot("update_" + tag)
	print("CLEARANCE TOTAL: %d violations over these screens" % _violations)
	print("PLATFORM SHOTS DONE ", out_dir)
	get_tree().quit()


## The title scrolls; the open-rooms list is under the buttons, so bring it into view.
func _scroll_down() -> void:
	var stack: Array = [router.current]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is ScrollContainer:
			(n as ScrollContainer).scroll_vertical = 100000
		stack.append_array(n.get_children())


func _fresh() -> void:
	fake = FakeTransport.new()
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Feed.refresh()                                     # (Session.reset says nothing, so tell the router the screen is the title again)


func _online() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	var hello := {"t": "hello_ok", "proto": 1, "features": ["list_rooms"]}
	if mode == "two":
		hello["games"] = GAMES_TWO
	fake.server_send(hello)


func _seat(code: String, game: String) -> void:
	Session.act("create_room")
	var m := {"t": "seat", "token": "snap-" + code, "room_code": code, "alias": "Mango", "host": true}
	if mode == "two":
		m["game"] = game
	fake.server_send(m)


func _rooms() -> Array:
	var rows := [
		{"code": "C001", "seats_taken": 2, "seats_total": 4, "age_s": 60, "name": "Friday night"},
		{"code": "C002", "seats_taken": 1, "seats_total": 6, "age_s": 5, "name": "Fig's camp"},
		{"code": "C003", "seats_taken": 5, "seats_total": 8, "age_s": 420, "name": "Bartholomew's Extremely Long Camp Name"},
		{"code": "C004", "seats_taken": 1, "seats_total": 4, "age_s": 2400, "name": ""},
	]
	if mode == "two":
		rows[1]["game"] = "placeholder_b"
		rows[2]["game"] = "placeholder_b"
		rows[3]["game"] = "mystery"
		rows[0]["game"] = "survivors"
	return rows


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


## The screen as a list of lines (class, id, text, visibility, rectangle). The backdrop moves between runs of the same code, so
## two pictures of one screen never match to the pixel; this is what makes "nothing moved, nothing was added" checkable.
func _tree(n: Node, depth: int, out: PackedStringArray) -> void:
	if n is Control:
		var c := n as Control
		var text: String = c.text if (c is Label or c is Button) else ""
		out.append("%s%s id=%s text=%s vis=%s rect=%s" % ["  ".repeat(depth), c.get_class(), str(c.get_meta("id", "")), text.replace("\n", "/"),
			c.visible, str(Rect2(c.global_position.snapped(Vector2(0.01, 0.01)), c.size.snapped(Vector2(0.01, 0.01))))])
	for k in n.get_children():
		_tree(k, depth + 1, out)


func _shot(shot_name: String) -> void:
	var clear := Clearance.check(router.current)
	_violations += clear.size()
	for v in clear:
		print("CLEARANCE ", shot_name, ": ", v)
	var lines := PackedStringArray()
	_tree(router.current, 0, lines)
	var f := FileAccess.open(out_dir.path_join(shot_name + ".tree.txt"), FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	print("shot ", shot_name, " ", img.get_size(), " err=", img.save_png(out_dir.path_join(shot_name + ".png")))
