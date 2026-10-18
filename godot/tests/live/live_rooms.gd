extends Node
## Live test, the open-camps list, against a real arena server. A server that cannot list camps (today's) must make this test
## SKIP, not fail: the client's promise is that such a server works exactly as before. A server that can list them must
## give a clean list, accept a create with a name and visibility, and then show that camp.
##   godot --headless --path godot res://tests/live/live_rooms.tscn -- --server=ws://... --log=<f>
## Prints "LIVE3 SKIP ..." (exit 0) when the server never answers a list, "LIVE3 PASS" (exit 0) or "LIVE3 FAIL" (exit 1).

const WAIT_FOR_LIST_S := 6.0
const WAIT_FOR_LOBBY_S := 10.0

var url := "ws://127.0.0.1:8765"
var problems: Array[String] = []


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--server="):
			url = a.substr(9)
	await get_tree().process_frame
	Session.reset(MemorySessionStore.new())
	Session.server_url = url
	Feed.reset()
	Feed.notice_raised.connect(func(n): problems.append("notice %s" % [n]))
	Intents.rooms_watch(true)
	var t0 := Time.get_ticks_msec()
	while not Feed.rooms_model().supported and (Time.get_ticks_msec() - t0) / 1000.0 < WAIT_FOR_LIST_S:
		await get_tree().process_frame
	if not Feed.rooms_model().supported:
		# the old-server contract: no list, the line still fine, and a plain create still works
		if Net.state != "online":
			problems.append("the line is not up (state %s) although the server is only silent about lists" % Net.state)
		print("LIVE3 SKIP: this server does not list camps (no rooms reply in %.0f s); checking the old path still works" % WAIT_FOR_LIST_S)
		await _plain_create_still_works()
		_finish()
		return
	_check_list(Feed.rooms_model())
	var why := Intents.create_room("public", "Live test camp")
	if why != "":
		problems.append("create refused: " + why)
	var t1 := Time.get_ticks_msec()
	while Session.screen != "lobby" and (Time.get_ticks_msec() - t1) / 1000.0 < WAIT_FOR_LOBBY_S:
		await get_tree().process_frame
	if Session.screen != "lobby":
		problems.append("never reached the lobby after creating a named public camp (screen %s)" % Session.screen)
	if Session.rooms.watching:
		problems.append("the list is still running in the lobby")
	_finish()


func _check_list(m: Dictionary) -> void:
	if m.rooms.size() > RoomsWatch.MAX_ROOMS:
		problems.append("more than %d camps" % RoomsWatch.MAX_ROOMS)
	var seen := {}
	for r in m.rooms:
		if seen.has(r.code):
			problems.append("code listed twice: " + str(r.code))
		seen[r.code] = true
		if int(r.seats_taken) >= int(r.seats_total):
			problems.append("a full camp is listed: %s" % [r])
		if str(r.name).length() > RoomsWatch.MAX_NAME:
			problems.append("a name longer than 24: %s" % [r])


func _plain_create_still_works() -> void:
	Intents.rooms_watch(false)
	var why := Intents.create_room()
	if why != "":
		problems.append("plain create refused on the old server: " + why)
	var t := Time.get_ticks_msec()
	while Session.screen != "lobby" and (Time.get_ticks_msec() - t) / 1000.0 < WAIT_FOR_LOBBY_S:
		await get_tree().process_frame
	if Session.screen != "lobby":
		problems.append("a plain create on this server never reached the lobby (screen %s)" % Session.screen)


func _finish() -> void:
	if problems.is_empty():
		print("LIVE3 PASS")
	else:
		print("LIVE3 FAIL")
		for p in problems:
			print("  ", p)
	get_tree().quit(0 if problems.is_empty() else 1)
