extends BaseTest
## A goal that depends on holding a seat explains what a seat is, right under the goal; other goals stay clean.

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func test_adapter_flags_only_the_seat_goals() -> void:
	var a := SurvivorsAdapter
	for code in ["robbed2_extract"]:
		eq(a.goal_card({"text": "x"}, code, {}, "open").note_key, "ui.goal_seat_note", code + " explains the seat")
	var deny := a.goal_card({"text": "x", "line": {"code": "goal_grudge_deny", "args": {}}}, "grudge", {}, "open")
	eq(deny.note_key, "ui.goal_seat_note", "the 'deny a seat' grudge explains it too")
	for code in ["give", "detective", "grudge"]:
		eq(a.goal_card({"text": "x"}, code, {}, "open").note_key, "", code + " has no note")


func test_the_note_is_shown_under_the_goal_in_the_theme_words() -> void:
	Themes.use("placeholder")
	go_online()
	give_seat()
	var v := round_view(1, false, 60.0)
	v.me.goal = {"code": "robbed2_extract", "text": "get robbed at least 1x and still extract", "target": null}
	fake.server_send(v)
	var s := RoundScreen.new()
	add_child(s)
	_mounted.append(s)
	s._goal_open = true                                   # the note is part of the opened goal
	s._build()
	var note := Ui.find(s, "goal_note") as Label
	check(note != null, "the note is on the goal card")
	if note == null:
		return
	check(note.text.contains("seat"), "it says what a seat is: " + note.text)
