extends BaseTest
## The last night of a Survivors game through the REAL router and the real screens: round 10, its reveal with lines on it, then the
## end. The driver once reported "reveal 10 shows no lines at all" and a drop to the title after the router learned to send an
## undrawn phase to the neutral screen; this pins the router's choice for exactly those frames.

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _router() -> Control:
	var r: Control = preload("res://main.gd").new()
	add_child(r)
	_mounted.append(r)
	return r


func _reveal(rnd: int) -> Dictionary:
	return {"t": "reveal", "round": rnd, "news": [{"code": "news_bandit", "args": {"player": "Fig"}}],
		"private": [{"code": "scavenged", "args": {"found": 1}}, {"code": "now_have", "args": {"rations": 8}}],
		"radio": [{"phrase": "trust", "about": "Kiwi"}], "board": null, "seconds_left": 20}


func _end() -> Dictionary:
	var rows := []
	for a in [["Fig", 5, 9, true], ["Mango", 3, 4, false], ["Kiwi", 1, 1, false]]:
		rows.append({"alias": a[0], "score": a[1], "rations": a[2], "seat": a[3], "goal_done": a[3], "stole": 2, "times_robbed": 0, "gave_away": 1})
	return {"t": "end", "extracted": ["Fig"], "winners": ["Fig"], "results": rows}


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func test_the_last_reveal_and_the_end_reach_their_screens_with_their_lines() -> void:
	Themes.use("placeholder")
	var r := _router()
	go_online()
	give_seat("tok-final", "FINL", true)
	fake.server_send({"t": "lobby", "room_code": "FINL", "seats_taken": 2, "seats_total": 4, "host": true})
	eq(r.current_name, "lobby", "lobby")
	for n in range(1, 11):
		fake.server_send(round_view(n))
		eq(r.current_name, "round", "round %d" % n)
		fake.server_send(_reveal(n))
		eq(r.current_name, "reveal", "reveal %d is the reveal screen, not the neutral one or the title" % n)
		if n == 10:
			await _frames(4)
			check(Ui.find_all(r.current, "line_").size() > 0, "reveal 10 shows its lines")
			check(Ui.find(r.current, "continue") != null, "and a Continue button")
			eq(Session.screen, "reveal", "Session agrees")
	fake.server_send(_end())
	eq(r.current_name, "end", "the end screen follows the last reveal")
	eq(Session.screen, "end", "Session agrees")
	no_errors()


func test_the_end_may_arrive_without_the_last_reveal_being_tapped_and_still_routes() -> void:
	Themes.use("placeholder")
	var r := _router()
	go_online()
	give_seat("tok-final2", "FIN2", true)
	fake.server_send(round_view(10))
	fake.server_send(_reveal(10))
	fake.server_send(_end())
	eq(r.current_name, "end", "end straight after reveal 10")
	fake.server_send(_reveal(10))                     # a late straggler of the last reveal after the end
	check(r.current_name in ["end", "reveal"], "a late reveal never drops to the title: %s" % r.current_name)
	check(r.current_name != "title" and r.current_name != "neutral", "not title or neutral")
