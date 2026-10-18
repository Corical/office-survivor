extends Control
## The states the stranger pass (docs/stranger-pass-2026-10-18/REPORT.md) complained about, each captured at 450x800, 540x960
## and 1904x1001 with the clearance audit, so a fix has a before and an after at the sizes the reviewer used. Windowed:
##   godot --path godot res://tests/snapshot/stranger.tscn -- --out=<dir> --log=<file>
## Names are the ones the game itself generates (11 and 12 letters).

const SIZES := [Vector2i(360, 640), Vector2i(450, 800), Vector2i(540, 960), Vector2i(1904, 1001)]
const ME := "QuietBadger"
const OTHERS := ["IronSpatula", "LuckyLantern", "SoggyBiscuit"]
const LONG_GOAL := "get robbed at least 1x and still get a seat on the helicopter"

var out_dir := ""
var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control
var audits := 0
var violations := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Net.log_payloads = false
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Themes.use("flash")
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	await _wait(0.8)
	await _each_size("title")

	# the lobby, alone in it
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "tok", "room_code": "ELWJ", "alias": ME, "host": true})
	fake.server_send({"t": "lobby", "room_code": "ELWJ", "seats_taken": 1, "seats_total": 4, "host": true})
	await _wait(0.8)
	await _each_size("lobby_1of4")

	# night 1: a long secret goal, 12-letter names, plenty of time
	fake.server_send(_round(1, 150.0))
	await _wait(0.9)
	await _each_size("round_open")
	# the last seconds, nothing picked
	for secs in [28.0, 18.0, 9.0, 3.0]:
		fake.server_send(_round(1, secs))
		await _wait(0.5)
		await _each_size("round_%ds_nopick" % int(secs))
	# a move picked (the 'Your pick' panel appears)
	var picked := _round(1, 120.0)
	picked["my_pick"] = {"kind": "scavenge", "target": null, "amount": 0}
	fake.server_send(picked)
	await _wait(0.6)
	await _each_size("round_picked")
	# Give: the move chosen (amount and target both on offer), then a target chosen (amount still missing)
	fake.server_send(_round(1, 120.0))
	await _wait(0.6)
	var rs: Node = router.current
	for p in rs._m.pickers:
		if p.server_id == "gift":
			rs._choose(p)
	await _wait(0.4)
	await _each_size("round_give_move")
	rs._choose_target(OTHERS[0])
	await _wait(0.4)
	await _each_size("round_give_target")
	# the next night after keeping watch: guard is not offered and the header says so
	var guarded := _round(2, 150.0)
	guarded.me.guarded = true
	guarded.legal.erase("guard")
	fake.server_send(guarded)
	await _wait(0.9)
	await _each_size("round_guarded_night2")

	# the reveal after a timeout (the synthetic night of the snapshot tool: one of every beat)
	fake.server_send(_round(3, 150.0))
	await _wait(0.4)
	fake.server_send(_night(3))
	await _wait(1.2)
	await _each_size("reveal_start")
	var tl: Timeline = Feed.player.timeline
	if tl != null:
		tl.snap_to_end()
	await _wait(0.8)
	await _each_size("reveal_finished")

	# the end, in every shape of tie
	var shapes := {"tie3at2": [5, 3, 3, 3], "tie4": [4, 4, 4, 4], "tie2at2": [5, 3, 3, 1], "tie1and2": [5, 5, 3, 1],
		"nottied": [6, 5, 3, 1], "tie2at1": [4, 4, 2, 1]}
	for k in shapes:
		fake.server_send(_end(shapes[k]))
		await _wait(0.9)
		await _each_size("end_" + k)
	print("CLEARANCE TOTAL: %d violations in %d audits" % [violations, audits])
	print("STRANGER DONE ", out_dir)
	get_tree().quit(0)


# ---------------- scenes ----------------

func _round(n: int, secs: float) -> Dictionary:
	var bands := ["well_fed", "starving", "getting_by"]
	var board: Array = [{"alias": ME, "band": "getting_by"}]
	for i in OTHERS.size():
		board.append({"alias": OTHERS[i], "band": bands[i % bands.size()]})
	return {"t": "round", "round": n, "rounds": 10, "seconds_left": secs,
		"me": {"alias": ME, "rations": 7, "bandit": false, "guards_left": 3, "guarded": false,
			"goal": {"code": "robbed2_extract", "target": null, "text": LONG_GOAL,
				"line": {"code": "goal_robbed2_extract", "args": {"n": 1}}},
			"goal_progress": {"state": "open", "text": "robbed 0/1 so far, and you'll need a seat at the end"}},
		"legal": {"scavenge": [], "guard": [], "steal": OTHERS.duplicate(), "gift": OTHERS.duplicate(),
			"investigate": OTHERS.duplicate()},
		"gift_amounts": [1, 2], "my_pick": null, "my_locked": false, "locked_count": 1, "seats_total": 4,
		"radio_available": true, "radio_phrases": [{"key": "trust", "needs_player": true}, {"key": "me", "needs_player": false}],
		"aliases": OTHERS.duplicate(), "board": board}


func _night(n: int) -> Dictionary:
	var x: String = OTHERS[0]
	var y: String = OTHERS[1]
	var z: String = OTHERS[2]
	return {"t": "reveal", "round": n, "seconds_left": 16.0, "board": _round(n, 0)["board"],
		"news": [{"code": "news_bandit", "args": {"player": x}}, {"code": "news_hit_1", "args": {"victim": z, "total": 2}}],
		"private": [{"code": "scavenged_auto", "args": {"found": 1}}, {"code": "stole", "args": {"target": y, "amount": 2}},
			{"code": "steal_caught", "args": {"target": z, "paid": 2}}, {"code": "gave", "args": {"receiver": x, "amount": 1}},
			{"code": "event", "args": {"event": "storm", "line": "A storm rolls over the camp", "scope": "camp"}},
			{"code": "now_have", "args": {"rations": 9}}],
		"radio": [{"phrase": "trust", "about": x}]}


func _end(scores: Array) -> Dictionary:
	var names := [ME] + OTHERS
	var rows: Array = []
	var best := 0
	for s in scores:
		best = maxi(best, int(s))
	var winners: Array = []
	for i in names.size():
		rows.append({"alias": names[i], "score": scores[i], "rations": 4 + i, "seat": i < 2, "goal_done": i % 2 == 0,
			"stole": i, "times_robbed": 3 - i if i < 3 else 0, "gave_away": 4})
		if int(scores[i]) == best:
			winners.append(names[i])
	return {"t": "end", "extracted": [names[0]], "winners": winners, "results": rows}


# ---------------- helpers ----------------

func _each_size(shot_name: String) -> void:
	for s in SIZES:
		get_window().size = s
		await _wait(0.45)
		await _shot("%s_%dx%d" % [shot_name, s.x, s.y])
		audits += 1
		var found := Clearance.check(router)
		for v in found:
			violations += 1
			print("CLEARANCE ", shot_name, " @", s, ": ", v)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _shot(shot_name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(out_dir.path_join(shot_name + ".png"))
	print("shot ", shot_name, " ", img.get_size())
