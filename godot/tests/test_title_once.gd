extends BaseTest
## After a takeover (or any reason the title explains) the sentence is on screen exactly once: not as the title's own line AND
## as the overlay's toast. Driven through the real router, which owns the title and the overlay together.

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("flash")


func teardown() -> void:
	super.teardown()
	Themes.use("placeholder")
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


## How many visible labels, anywhere under the router (title and overlay), say this sentence.
func _times_said(n: Node, sentence: String) -> int:
	var count := 0
	if n is Label and (n as Label).is_visible_in_tree() and (n as Label).text.contains(sentence):
		count += 1
	for c in n.get_children():
		count += _times_said(c, sentence)
	return count


func _router_in_lobby() -> Control:
	var r: Control = preload("res://main.gd").new()
	add_child(r)
	_mounted.append(r)
	go_online()
	give_seat("tok", "ABCD", true)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 2, "seats_total": 4, "host": true})
	return r


func test_a_takeover_says_its_sentence_once() -> void:
	var r := _router_in_lobby()
	eq(r.current_name, "lobby", "in the lobby")
	fake.server_send({"t": "error", "code": "taken_over", "message": "opened elsewhere"})
	eq(r.current_name, "title", "on the title")
	var sentence := Words.render("notice.taken_over")
	await get_tree().process_frame
	await get_tree().process_frame
	eq(_times_said(r, sentence), 1, "the takeover sentence appears exactly once on screen")


func test_the_other_reasons_the_title_explains_are_also_said_once() -> void:
	for code in [["flapping", "notice.flapping"], ["too_big", "notice.too_big"]]:
		setup()
		var r := _router_in_lobby()
		Net._stop(code[0])                                       # the connection ends for this terminal reason
		eq(r.current_name, "title", "on the title after " + code[0])
		await get_tree().process_frame
		eq(_times_said(r, Words.render(code[1])), 1, "%s said once" % code[0])
		r.free()
		_mounted.erase(r)


func test_being_sent_away_says_its_sentence_once() -> void:
	var r := _router_in_lobby()
	fake.server_send({"t": "error", "code": "kicked", "message": "removed"})
	eq(r.current_name, "title", "on the title")
	await get_tree().process_frame
	eq(_times_said(r, Words.render("notice.kicked")), 1, "the kicked sentence appears exactly once")
