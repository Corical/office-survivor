extends Control
## Live test: the real client (Net, Session, Intents, Feed, the bang ruleset and the router with its screens) plays a whole Bang! game
## against a real arena server, with bots in the other seats. Not headless: it also takes pictures.
##   godot --path godot res://tests/live/live_bang.tscn -- --server=wss://host:8470 --out=<dir>
## Plays: connect, create a PRIVATE bang camp through the same call the picker makes, start (bots fill), then every turn of mine:
## roll, keep everything but arrows and reroll, stop on the second look, give each die that needs one the first offered target.
## Prints "LIVE BANG PASS" and exits 0 when phase "over" was reached with no unexpected notice or error, else "LIVE BANG FAIL" and 1.

const RUN_TIMEOUT_S := 420.0           # chosen: bots play fast, but a whole table of 5 takes many turns
const SETTLE_S := 0.8                  # chosen: the router's cross-fade is 0.4 s

var url := "wss://raspberrypi.tail87b476.ts.net:8470"
var out_dir := ""
var router: Control
var problems: Array[String] = []
var screens_seen := {}
var phases_seen := {}
var acted_for := ""                    # the phase_id the last act went out for: one act per view
var my_turns := {}                     # "turn-number" -> true; a turn of mine is counted once
var turn_changes := 0
var last_turn := -2
var acts := {"roll": 0, "reroll": 0, "stop": 0, "target": 0}
var shot_roll := false
var shot_resolve := false
var shot_over := false
var finish_called := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
		elif a.begins_with("--out="):
			out_dir = a.substr(6)
	if out_dir != "":
		DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Session.reset(MemorySessionStore.new())
	Session.server_url = url
	Feed.reset()
	Themes.use("flash")
	Session.notice.connect(func(k, c, t): problems.append("notice %s %s %s" % [k, c, t]))
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	get_window().size = Vector2i(412, 915)
	var log_mark := Log.mark()
	Net.connect_to(url)
	var t0 := Time.get_ticks_msec()
	while not Net.handshake_done and Time.get_ticks_msec() - t0 < 15000:
		await get_tree().process_frame
	if not Net.handshake_done:
		return _finish(log_mark, "never connected to %s (state=%s)" % [url, Net.state])
	var listed := Session.games.any(func(g): return g.id == "bang")
	print("LIVE BANG games listed: ", Session.games.map(func(g): return g.id))
	if not listed:
		return _finish(log_mark, "the server does not list bang")
	var why := Session.create_camp("private", "", "bang")
	if why != "":
		return _finish(log_mark, "create refused: " + why)
	t0 = Time.get_ticks_msec()
	while Session.screen != "lobby" and Time.get_ticks_msec() - t0 < 10000:
		await get_tree().process_frame
	if Session.screen != "lobby":
		return _finish(log_mark, "never reached the lobby (screen=%s)" % Session.screen)
	print("LIVE BANG room ", Session.room_code, " ruleset ", Session.ruleset.get_class(), " game entry ", Session.room_game_entry())
	screens_seen[router.current_name] = true
	await _wait(SETTLE_S)
	await _shot("lobby")
	why = Intents.start()
	if why != "":
		return _finish(log_mark, "start refused: " + why)
	t0 = Time.get_ticks_msec()
	while not finish_called and (Time.get_ticks_msec() - t0) / 1000.0 < RUN_TIMEOUT_S:
		await get_tree().process_frame
		screens_seen[router.current_name] = true
		var m: Dictionary = Feed.models.get("view", {})
		if m.is_empty():
			continue
		phases_seen[m.phase] = true
		if m.turn != last_turn:
			last_turn = m.turn
			turn_changes += 1
		if m.phase == "over":
			await _wait(SETTLE_S)
			if not shot_over:
				shot_over = true
				await _shot("over")
			break
		await _play(m)
	_finish(log_mark, "")


## One move for the view I hold, once per phase_id. Everything goes through Intents.act, and the keep mask and the targets come from
## the same ruleset helpers the screen uses.
func _play(m: Dictionary) -> void:
	if not m.my_turn or acted_for == m.phase_id:
		return
	my_turns["%d" % turn_changes] = true
	if m.phase == "roll":
		if m.can.roll:
			await _send(m, "roll", {})
		elif m.can.reroll:
			if not shot_roll:
				shot_roll = true
				await _wait(SETTLE_S)
				await _shot("roll")
			var kept := {}
			for d in m.dice:
				kept[d.index] = d.face != "arrow"
			if m.rolls >= 2 or not BangRuleset.can_send_reroll(m, kept):
				await _send(m, "stop", {})
			else:
				await _send(m, "reroll", {"keep": BangRuleset.keep_mask(m.dice, kept)})
		elif m.can.stop:
			await _send(m, "stop", {})
	elif m.phase == "resolve" and not m.targets.is_empty():
		if not shot_resolve:
			shot_resolve = true
			await _wait(SETTLE_S)
			await _shot("resolve")
		await _send(m, "target", {"at": m.targets[0]})


func _send(m: Dictionary, verb: String, args: Dictionary) -> void:
	acted_for = m.phase_id
	var why := Intents.act(verb, args)
	if why != "":
		problems.append("act %s %s refused locally: %s" % [verb, args, why])
		acted_for = ""
		await _wait(0.5)
		return
	acts[verb] += 1


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _shot(shot_name: String) -> void:
	if out_dir == "":
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := out_dir.path_join("live_%s_412x915.png" % shot_name)
	print("LIVE BANG shot ", path, " screen=", router.current_name, " err=", img.save_png(path))


func _finish(log_mark: int, early: String) -> void:
	finish_called = true
	if early != "":
		problems.append(early)
	var m: Dictionary = Feed.models.get("view", {})
	if m.get("phase", "") != "over":
		problems.append("did not reach phase over (phase=%s screen=%s net=%s)" % [m.get("phase", "-"), Session.screen, Net.state])
	if router != null and router.current_name != "bang_end":
		problems.append("the end screen was not showing (screen=%s)" % router.current_name)
	for l in Log.since(log_mark, "ERROR"):
		problems.append("log: " + l)
	var warns := Log.since(log_mark, "WARN")
	print("LIVE BANG: turn changes=%d my steps=%d acts=%s phases=%s screens=%s warnings=%d" % [turn_changes, my_turns.size(), acts,
		phases_seen.keys(), screens_seen.keys(), warns.size()])
	if not m.is_empty():
		print("LIVE BANG winner: ", m.winner, " seats: ", m.seats.map(func(s): return "%d:%s:%s" % [s.at, "alive" if s.alive else "out", s.role]))
	for w in warns:
		print("  warn: " + w)
	if problems.is_empty():
		print("LIVE BANG PASS")
	else:
		print("LIVE BANG FAIL")
		for p in problems:
			print("  " + p)
	get_tree().quit(0 if problems.is_empty() else 1)
