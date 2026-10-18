extends Control
## The autopilot: plays a whole game through the REAL screens of the REAL app against a REAL server, in a real window,
## by sending genuine mouse events at the centre of each button (so an overlay that blocks a tap, or a button pushed
## off screen, is caught). Takes screenshots as it goes and fails on any engine error or unexpected state.
##   godot --path godot res://tests/drive/drive.tscn -- --server=ws://127.0.0.1:8765 --out=<dir> --log=<file>

const TIMEOUT_S := 420.0          # chosen: the whole game, bots included
const SHOT_ROUNDS := [1, 2, 5, 10]

var url := "ws://127.0.0.1:8765"
var out_dir := ""
var router: Control
var problems: Array[String] = []
var taps := 0
var rounds_played := 0
var reveals_seen := 0
var moves_used := {}
var radios := 0
var _t0 := 0
var _mark := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
		elif a.begins_with("--out="):
			out_dir = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await _frames(2)
	Session.reset(MemorySessionStore.new())
	Feed.reset()
	Themes.use("flash")                                   # the default look, as the owner sees it
	_mark = Log.mark()
	_t0 = Time.get_ticks_msec()
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	get_window().size = Vector2i(540, 960)
	await _frames(6)
	await _play()
	_finish()


# ---------------- the game ----------------

func _play() -> void:
	await _shot("01_title")
	if not await _tap("settings_toggle"):
		return
	var le := Ui.find(router.current, "server_url") as LineEdit
	var tries := 0
	while le == null and tries < 3:                  # the open-camps list arriving moves the button under the first tap
		tries += 1
		if not await _tap("settings_toggle"):
			return
		le = Ui.find(router.current, "server_url") as LineEdit
	if le == null:
		return _fail("no server address field after opening settings")
	le.text = url
	le.text_changed.emit(url)                              # typing the address
	await _shot("02_settings")
	await _tap("settings_toggle")
	if not await _tap("create"):
		return
	if await _until(func(): return Ui.find(router.current, "sheet_create") != null, 1.0):
		if not await _tap("sheet_create"):                 # the new-camp sheet opens first on a server that lists camps
			return
	if not await _until(func(): return router.current_name == "lobby", 12.0):
		return _fail("never reached the lobby after Create room (screen=%s net=%s)" % [router.current_name, Net.state])
	await _frames(3)
	await _shot("03_lobby")
	if not await _tap("start"):
		return
	var last_round := 0
	while router.current_name != "end":
		if _over():
			return _fail("ran out of time on screen '%s' (net=%s)" % [router.current_name, Net.state])
		match router.current_name:
			"round":
				var r: int = Feed.models.get("round", {}).get("round", 0)
				if r != 0 and r != last_round:
					last_round = r
					if not await _play_round(r):
						return
			"reveal":
				if not await _handle_reveal():
					return
			_:
				await _frames(2)
		await _frames(2)
	await _frames(4)
	await _shot("20_end")
	var end_texts := Ui.texts(router.current)
	if end_texts.size() < 8:
		_fail("the end screen looks empty: %s" % [end_texts])
	if not await _tap("back"):
		return
	if not await _until(func(): return router.current_name == "title", 6.0):
		return _fail("did not return to the title after the end screen")
	await _shot("21_title_again")
	if Session.token != "":
		_fail("the finished game's seat was not forgotten")


func _play_round(r: int) -> bool:
	if not await _until(func(): return Feed.models.round.lock.picker_open, 12.0):
		_fail("round %d: the picker never opened (net=%s)" % [r, Net.state])
		return false
	await _frames(2)
	var m: Dictionary = Feed.models.round
	var usable: Array = m.pickers.filter(func(p): return (not p.takes_target) or not p.targets.is_empty())
	var p: Dictionary = usable[(r - 1) % usable.size()]
	moves_used[p.move_id] = moves_used.get(p.move_id, 0) + 1
	if not await _tap("move_" + p.server_id):
		return false
	if p.takes_target:
		if not await _tap("target_" + p.targets[0]):
			return false
		if not p.amounts.is_empty():
			if not await _tap("amount_%s" % p.amounts[0]):
				return false
	if not await _until(func(): return Feed.models.round.my_pick != null, 6.0):
		_fail("round %d: the server never echoed my pick" % r)
		return false
	await _frames(3)
	if r in SHOT_ROUNDS:
		await _shot("round_%02d_picked" % r)
	if r % 2 == 0 and Feed.models.round.radio.available:
		if await _tap("radio_toggle"):
			var ph: Dictionary = Feed.models.round.radio.phrases[0]
			if await _tap("phrase_" + ph.server_id):
				if ph.needs_player:
					var others: Array = Feed.models.round.roster.filter(func(e): return not e.is_me)
					await _tap("about_" + others[0].alias)
				radios += 1
	if not await _tap("lock"):
		return false
	if not await _until(func(): return Feed.models.round.lock.state == "locked" or router.current_name != "round", 10.0):
		_fail("round %d: the lock was never confirmed" % r)
		return false
	await _frames(2)
	if r in SHOT_ROUNDS and router.current_name == "round":
		await _shot("round_%02d_locked" % r)
	rounds_played += 1
	return true


func _handle_reveal() -> bool:
	var r: int = Feed.models.get("reveal", {}).get("round", 0)
	if not await _until(func(): return Ui.find(router.current, "continue") != null, 6.0):
		_fail("reveal %d: no Continue button" % r)
		return false
	await _frames(3)
	if (Ui.find_all(router.current, "line_").size() == 0):
		_fail("reveal %d shows no lines at all" % r)
	if r in SHOT_ROUNDS:
		await _shot("reveal_%02d" % r)
	reveals_seen += 1
	return await _tap("continue")


# ---------------- driving ----------------

## Tap a button by id with real mouse events at the centre of its rect. False (and a recorded problem) if it cannot be
## tapped: missing, disabled, hidden, or outside the visible window.
func _tap(id: String) -> bool:
	if not await _until(func(): return Ui.find(router.current, id) != null, 6.0):
		_fail("no control '%s' on screen '%s' (have: %s)" % [id, router.current_name, Ui.texts(router.current)])
		return false
	var b := Ui.find(router.current, id) as Button
	if b == null or b.disabled or not b.is_visible_in_tree():
		_fail("'%s' cannot be tapped (disabled=%s)" % [id, b.disabled if b else "missing"])
		return false
	# a person scrolls to what they want to tap: do the same (and the app should already have scrolled radio into view)
	var node: Node = b.get_parent()
	while node != null and not (node is ScrollContainer):
		node = node.get_parent()
	if node != null:
		(node as ScrollContainer).ensure_control_visible(b)
		await _frames(2)
		b = Ui.find(router.current, id) as Button          # the screen may have rebuilt meanwhile: aim at what is there now
		if b == null or b.disabled:
			_fail("'%s' vanished or was disabled while scrolling to it" % id)
			return false
	var canvas := b.get_global_rect().get_center()
	var win := get_window().size
	var pos: Vector2 = get_viewport().get_screen_transform() * canvas
	if pos.x < 0 or pos.y < 0 or pos.x > win.x or pos.y > win.y:
		_fail("'%s' is off screen at %s (window %s)" % [id, pos, win])
		return false
	var down := InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.position = pos
	down.global_position = pos
	down.pressed = true
	down.button_mask = MOUSE_BUTTON_MASK_LEFT
	Input.parse_input_event(down)
	await _frames(1)
	var up := InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.position = pos
	up.global_position = pos
	up.pressed = false
	Input.parse_input_event(up)
	await _frames(2)
	taps += 1
	return true


func _until(cond: Callable, secs: float) -> bool:
	var t := Time.get_ticks_msec()
	while not cond.call():
		if (Time.get_ticks_msec() - t) / 1000.0 > secs or _over():
			return false
		await get_tree().process_frame
	return true


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _over() -> bool:
	return (Time.get_ticks_msec() - _t0) / 1000.0 > TIMEOUT_S


func _shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(out_dir.path_join(name + ".png"))
	print("shot ", name)


func _fail(why: String) -> void:
	problems.append(why)
	printerr("DRIVE problem: ", why)


func _finish() -> void:
	for l in Log.since(_mark, "ERROR"):
		problems.append("log: " + l)
	var warns := Log.since(_mark, "WARN")
	print("DRIVE: taps=%d rounds=%d reveals=%d radios=%d moves=%s warnings=%d screen=%s" % [taps, rounds_played,
		reveals_seen, radios, JSON.stringify(moves_used), warns.size(), router.current_name])
	for w in warns:
		print("  warn: ", w)
	if rounds_played != 10:
		problems.append("played %d rounds, wanted 10" % rounds_played)
	if problems.is_empty():
		print("DRIVE PASS")
	else:
		print("DRIVE FAIL")
		for p in problems:
			print("  ", p)
	get_tree().quit(0 if problems.is_empty() else 1)
