extends Node
## Live fault test: the real Net + WsTransport against tools/fault_server.py in one mode.
##   godot --headless --path godot res://tests/live/live_fault.tscn -- --server=ws://127.0.0.1:8792 --mode=<mode> --log=<f>
## Prints "FAULT <mode> PASS|FAIL ..." and exits 0/1. Wall-clock; each mode finishes within WINDOW_S seconds.

const WINDOW_S := 14.0        # chosen: covers the 8 s ack timeout plus one backoff

var url := "ws://127.0.0.1:8792"
var mode := ""


func _opens(mark: int) -> int:
	return Log.since(mark).filter(func(l): return "[net] open " in l).size()


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
		elif a.begins_with("--mode="):
			mode = a.substr(7)
	await get_tree().process_frame
	var store := MemorySessionStore.new()
	Session.reset(store)
	Session.server_url = url
	var mark := Log.mark()
	var problems: Array[String] = []
	var notes: Array[String] = []
	match mode:
		"burst_seat_gone":
			Session.token = "stale-token"
			Session.room_code = "OLDR"
			Session.resume_if_stored()
			await _wait(func(): return Session.token == "" and Session.screen == "title" and Net.state == "stopped", 6.0)
			if Session.token != "":
				problems.append("seat was not forgotten (token=%s state=%s)" % [Session.token, Net.state])
			if Net.state != "stopped":
				problems.append("net state %s, wanted stopped" % Net.state)
		"burst_upgrade":
			Session.begin("create_room")
			await _wait(func(): return Session.screen == "upgrade", 6.0)
			if Session.screen != "upgrade":
				problems.append("screen %s, wanted upgrade" % Session.screen)
			await get_tree().create_timer(3.0).timeout
			if _opens(mark) != 1:
				problems.append("reconnected after upgrade_required: %d opens" % _opens(mark))
		"taken_over_1000":
			Session.token = "tok"
			Session.room_code = "ABCD"
			Session.resume_if_stored()
			await _wait(func(): return Net.state == "stopped", WINDOW_S)
			notes.append("opens=%d state=%s reason=%s seat_kept=%s" % [_opens(mark), Net.state,
				Session.terminal_reason, Session.token != ""])
			# the engine drops the `taken_over` message that precedes the close, so the client sees four short-lived
			# connections in a row and must stop with a visible reason, keeping the seat, not ping-pong forever
			if Net.state != "stopped" or Session.terminal_reason not in ["flapping", "taken_over"]:
				problems.append("did not stop: state=%s reason=%s opens=%d" % [Net.state, Session.terminal_reason,
					_opens(mark)])
			if _opens(mark) > 4:
				problems.append("ping-pong: %d connections" % _opens(mark))
			if Session.token == "":
				problems.append("the seat was forgotten, but it still belongs to us")
		"oversize":
			Session.token = "tok"                    # a seated client resumes on every connection, so it meets the
			Session.room_code = "ABCD"               # oversize view again each time, as it would for real
			Session.resume_if_stored()
			await _wait(func(): return Net.state == "stopped", WINDOW_S)
			if Net.state != "stopped" or Session.terminal_reason != "too_big":
				problems.append("state=%s reason=%s, wanted stopped/too_big" % [Net.state, Session.terminal_reason])
			if _opens(mark) > 2:
				problems.append("%d connections, wanted 2" % _opens(mark))
		"halfopen":
			Session.begin("create_room")
			await _wait(func(): return _opens(mark) >= 2, WINDOW_S)
			if _opens(mark) < 2:
				problems.append("never noticed the dead socket (opens=%d state=%s)" % [_opens(mark), Net.state])
		"slow_hello":
			Session.begin("create_room")
			await _wait(func(): return _opens(mark) >= 2, WINDOW_S)
			if _opens(mark) < 2:
				problems.append("never gave up waiting for hello_ok (opens=%d)" % _opens(mark))
		_:
			problems.append("unknown mode " + mode)
	for l in Log.since(mark, "ERROR"):
		problems.append("log: " + l)
	print("FAULT %s %s %s" % [mode, "FAIL" if problems else "PASS", " | ".join(notes)])
	for p in problems:
		print("  " + p)
	get_tree().quit(1 if problems else 0)


func _wait(cond: Callable, seconds: float) -> void:
	var t0 := Time.get_ticks_msec()
	while not cond.call() and (Time.get_ticks_msec() - t0) / 1000.0 < seconds:
		await get_tree().process_frame
