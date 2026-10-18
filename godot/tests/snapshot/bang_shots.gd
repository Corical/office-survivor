extends Control
## Pictures of the Bang! screens through the real router at the phone sizes and a desktop size, with the clearance audit on each.
## Not headless.
##   godot --path godot res://tests/snapshot/bang_shots.tscn -- --out=<dir>
## Output files are named bang_<state>_<width>x<height>.png.

const SIZES := [Vector2i(360, 640), Vector2i(412, 915), Vector2i(1904, 1001)]

var out_dir := ""
var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control
var violations := 0
var _seq := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Themes.use("flash")
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	await _size(SIZES[1])
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "tok", "room_code": "BANG", "alias": "Player 3", "host": true, "game": "bang"})
	fake.server_send(_view(5, "roll", {"rolls": 1, "can": {"reroll": true, "stop": true},
		"dice": [["arrow", false], ["dynamite", true], ["shoot1", false], ["beer", false], ["gatling", false]]}))
	await _each("roll_mine")
	fake.server_send(_view(8, "resolve", {"rolls": 3, "pending": {"die": 2, "face": "shoot1", "targets": [1, 3]},
		"can": {"target": [1, 3]}, "assigned": [{"die": 4, "face": "beer", "at": 2}],
		"dice": [["arrow", false], ["dynamite", true], ["shoot1", false], ["beer", false], ["beer", false]],
		"log": [{"n": 1, "k": "rolled", "by": 2, "roll": 3, "dice": ["arrow", "dynamite", "shoot1", "beer", "beer"]},
			{"n": 2, "k": "arrow", "by": 2}]}))
	await _each("resolve_8_seats")
	fake.server_send(_view(3, "roll", {"turn": 0, "rolls": 2, "dice": [["shoot1", false], ["shoot1", false], ["beer", false],
		["arrow", false], ["shoot2", false]]}))
	await _each("roll_waiting_3_seats")
	fake.server_send(_view(5, "over", {"turn": null, "winner": {"team": "outlaws", "ats": [1, 2, 3]}, "dead": [0, 4],
		"dice": [["arrow", false], ["arrow", false], ["beer", false], ["arrow", false], ["shoot2", false]]}))
	await _each("over")
	print("BANG CLEARANCE TOTAL: ", violations, " violations")
	print("BANG DONE ", out_dir)
	get_tree().quit(0)


func _view(n: int, phase: String, o: Dictionary) -> Dictionary:
	_seq += 1
	var dead: Array = o.get("dead", [])
	var over := phase == "over"
	var roles := ["sheriff", "outlaw", "outlaw", "renegade", "deputy", "outlaw", "outlaw", "renegade"]
	var players: Array = []
	for i in n:
		var d: bool = i in dead
		players.append({"at": i, "name": "Player %d" % (i + 1) if i != 4 else "Bot 1", "life": 0 if d else (10 if i == 0 else 6),
			"max": 10 if i == 0 else 8, "arrows": 1 if i == 1 else 0, "alive": not d, "away": false,
			"role": roles[i] if (i == 0 or d or over) else null})
	var me := 2 if n > 2 else 1
	var can := {"roll": false, "reroll": false, "stop": false, "target": null}
	can.merge(o.get("can", {}), true)
	var dice: Array = []
	for d in o.get("dice", []):
		dice.append({"face": d[0], "locked": d[1]})
	return {"t": "view", "game": "bang", "phase": phase, "phase_id": "p%d" % _seq, "seq": _seq, "n": n,
		"you": {"at": me, "role": "outlaw"}, "players": players, "turn": o.get("turn", me), "pile": 8, "rolls": o.get("rolls", 0),
		"rolls_max": 3, "dice": dice, "pending": o.get("pending"), "assigned": o.get("assigned", []), "can": can,
		"log": o.get("log", []), "winner": o.get("winner"), "deadline": null}


func _each(state: String) -> void:
	for s in SIZES:
		await _size(s)
		await _wait(0.6)
		await _shot("bang_" + state, s)


func _size(s: Vector2i) -> void:
	get_window().size = s
	await _wait(0.5)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _shot(shot_name: String, s: Vector2i) -> void:
	var found: Array[String] = Clearance.check(router) + NineFit.check(router)
	for f in found:
		print("CLEARANCE ", shot_name, " ", s, " ", f)
	violations += found.size()
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := out_dir.path_join("%s_%dx%d.png" % [shot_name, s.x, s.y])
	print("shot ", path, " ", img.get_size(), " err=", img.save_png(path))
