extends Node
## Live test, second human: the real client joins a room a Python host created (tools/live_host.py), then plays
## through Feed and Intents (the same door the screens will use) with a different move every round, a radio message,
## and one dropped connection mid-game that must resume. Checks that every real night's beats add up to the real total.
##   godot --headless --path godot res://tests/live/live_varied.tscn -- --server=ws://... --join=ABCD --drop-at=4 --log=<f>
## Exits 0 when the end screen is reached with no problems.

const RUN_TIMEOUT_S := 240.0

var url := "ws://127.0.0.1:8791"
var code := ""
var drop_at := 4
var problems: Array[String] = []
var moves_used := {}
var radios := 0
var reveals_checked := 0
var residual_nights := 0
var dropped := false
var finished := false
var _pick_sent := {}
var _lock_sent := {}
var _radio_sent := {}
var _continue_sent := {}
var _ends := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
		elif a.begins_with("--join="):
			code = a.substr(7)
		elif a.begins_with("--drop-at="):
			drop_at = int(a.substr(10))
	await get_tree().process_frame
	Session.reset(MemorySessionStore.new())
	Session.server_url = url
	Feed.reset()
	Feed.model_changed.connect(_on_model)
	Feed.notice_raised.connect(func(n): problems.append("notice %s" % [n]))
	var mark := Log.mark()
	var why := Intents.join_room(code)
	if why != "":
		problems.append("join refused: " + why)
	var t0 := Time.get_ticks_msec()
	while not finished and Session.screen != "end" and (Time.get_ticks_msec() - t0) / 1000.0 < RUN_TIMEOUT_S:
		await get_tree().process_frame
	_finish(mark)


func _on_model(kind: String, m: Dictionary) -> void:
	match kind:
		"round":
			_play_round(m)
		"reveal":
			_check_reveal(m)
		"end":
			_ends += 1


func _play_round(m: Dictionary) -> void:
	var r: int = m.round
	if r == drop_at and not dropped and m.lock.state == "open":
		dropped = true
		Log.event("live", "dropping_connection", {"round": r})
		Net.transport.close()                       # the phone loses the network; Net must reconnect and resume
		return
	if not m.lock.picker_open:
		return
	if not _pick_sent.has(r):
		var p := _choose(m)
		if p.is_empty():
			return
		_pick_sent[r] = true
		moves_used[p.move_id] = moves_used.get(p.move_id, 0) + 1
		var target: Variant = p.targets[0] if p.takes_target and not p.targets.is_empty() else null
		var amount: int = p.amounts[0] if not p.amounts.is_empty() else 0
		var why := Intents.pick(p.server_id, target, amount)
		if why != "":
			problems.append("pick refused in round %d: %s" % [r, why])
		return
	if m.radio.available and not _radio_sent.has(r):
		_radio_sent[r] = true
		var ph: Dictionary = m.radio.phrases[r % m.radio.phrases.size()]
		var about: Variant = null
		if ph.needs_player:
			var others: Array = m.roster.filter(func(e): return not e.is_me)
			about = others[0].alias if not others.is_empty() else null
		if Intents.radio(ph.server_id, about) == "":
			radios += 1
		return
	if m.my_pick != null and not _lock_sent.has(r):
		_lock_sent[r] = true
		var why2 := Intents.lock()
		if why2 != "":
			problems.append("lock refused in round %d: %s" % [r, why2])


## A different legal move each round, cycling through everything the server offers (skipping ones with no target).
func _choose(m: Dictionary) -> Dictionary:
	var usable: Array = m.pickers.filter(func(p): return (not p.takes_target) or not p.targets.is_empty())
	if usable.is_empty():
		return {}
	return usable[(m.round - 1) % usable.size()]


func _check_reveal(m: Dictionary) -> void:
	if m.totals.before != null and m.totals.after != null:
		var net := 0
		for b in m.beats:
			if b.kind == "move_resource":
				if b.to == "@me":
					net += b.amount_in
				if b.from == "@me":
					net -= b.amount_out
		if net != int(m.totals.after) - int(m.totals.before):
			problems.append("beats do not add up: net %d, real change %d" % [net, int(m.totals.after) - int(m.totals.before)])
		if m.totals.residual != 0:
			residual_nights += 1
	if not _continue_sent.has(m.round):
		_continue_sent[m.round] = true
		reveals_checked += 1
		var why := Intents.proceed()
		if why != "":
			problems.append("continue refused in round %d: %s" % [m.round, why])


func _finish(mark: int) -> void:
	finished = true
	if Session.screen != "end":
		problems.append("did not reach the end screen (screen=%s net=%s)" % [Session.screen, Net.state])
	if reveals_checked != 10:
		problems.append("checked %d reveals, wanted 10" % reveals_checked)
	if not dropped:
		problems.append("the connection was never dropped (drop-at %d)" % drop_at)
	if moves_used.size() < 4:
		problems.append("not enough variety of moves: %s" % [moves_used])
	for l in Log.since(mark, "ERROR"):
		problems.append("log: " + l)
	print("LIVE2: moves=%s radios=%d reveals=%d residual_nights=%d dropped=%s screen=%s" % [JSON.stringify(moves_used),
		radios, reveals_checked, residual_nights, dropped, Session.screen])
	for w in Log.since(mark, "WARN"):
		print("  warn: " + w)
	if problems.is_empty():
		print("LIVE2 PASS")
	else:
		print("LIVE2 FAIL")
		for p in problems:
			print("  " + p)
	get_tree().quit(0 if problems.is_empty() else 1)
