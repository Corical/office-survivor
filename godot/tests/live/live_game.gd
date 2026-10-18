extends Node
## Live test: the real Net + WsTransport + Session play a whole game against a real arena server.
##   python -m arena.server --data <dir> --port 8791        (ARENA_TIMER=20 keeps rounds short)
##   godot --headless --path godot res://tests/live/live_game.tscn -- --server=ws://127.0.0.1:8791 --log=<file>
## Plays: create room -> start (bots fill) -> every round pick scavenge + lock -> continue on every reveal -> end.
## Exits 0 when the end screen is reached after the right number of rounds with no engine errors, else 1.

const RUN_TIMEOUT_S := 150.0           # chosen

var url := "ws://127.0.0.1:8791"
var rounds_seen := {}
var reveals_seen := {}
var views := 0
var finished := false
var problems: Array[String] = []


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
	await get_tree().process_frame
	Session.reset(MemorySessionStore.new())
	Session.server_url = url
	Session.view_changed.connect(_on_view)
	Session.notice.connect(func(k, c, t): problems.append("notice %s %s %s" % [k, c, t]))
	var log_mark := Log.mark()
	Log.event("live", "begin", {"url": url})
	Session.begin("create_room")
	var t0 := Time.get_ticks_msec()
	while Session.screen != "lobby" and Time.get_ticks_msec() - t0 < 10000:
		await get_tree().process_frame
	if Session.screen != "lobby":
		_finish(log_mark, "never reached the lobby (state=%s)" % Net.state)
		return
	var why := Session.act("start")
	if why != "":
		_finish(log_mark, "start refused: " + why)
		return
	t0 = Time.get_ticks_msec()
	while not finished and Session.screen != "end" and (Time.get_ticks_msec() - t0) / 1000.0 < RUN_TIMEOUT_S:
		await get_tree().process_frame
	_finish(log_mark, "")


func _on_view(v: Dictionary) -> void:
	views += 1
	match v.t:
		"round":
			rounds_seen[int(v.round)] = true
			if v.my_pick == null:
				if v.legal.has("scavenge"):
					Session.pick("scavenge", null)
			elif not v.my_locked and Session.lock_state() == "open":
				Session.act("lock")
		"reveal":
			reveals_seen[int(v.round)] = true
			Session.act("continue")


func _finish(log_mark: int, early: String) -> void:
	finished = true
	if early != "":
		problems.append(early)
	if Session.screen != "end":
		problems.append("did not reach the end screen (screen=%s net=%s)" % [Session.screen, Net.state])
	if rounds_seen.size() != 10:
		problems.append("saw %d round views for rounds %s, wanted 10" % [rounds_seen.size(), rounds_seen.keys()])
	if reveals_seen.size() != 10:
		problems.append("saw %d reveals, wanted 10" % reveals_seen.size())
	for l in Log.since(log_mark, "ERROR"):
		problems.append("log: " + l)
	var warns := Log.since(log_mark, "WARN")
	print("LIVE: views=%d rounds=%d reveals=%d warnings=%d screen=%s" % [views, rounds_seen.size(),
		reveals_seen.size(), warns.size(), Session.screen])
	for w in warns:
		print("  warn: " + w)
	if problems.is_empty():
		print("LIVE PASS")
	else:
		print("LIVE FAIL")
		for p in problems:
			print("  " + p)
	get_tree().quit(0 if problems.is_empty() else 1)
