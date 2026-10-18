extends BaseTest
## The host's seat list in the lobby: one row per OTHER seat of the latest lobby model, named by position, a one-tap Send away
## for a seat that dropped off, a confirm step for a seat that is here, nothing for a guest. Fake server, real screen.

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("placeholder")


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _seats(spec: String) -> Array:
	# "hd" = a seat that is here, then one that dropped; handles are opaque
	var out := []
	for i in spec.length():
		out.append({"id": "h-%d" % i, "connected": spec[i] == "h"})
	return out


func _send(seats: Array, host := true) -> void:
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 1 + seats.size(), "seats_total": 12, "host": host,
		"seats": seats})


func _host(spec: String) -> Control:
	go_online()
	give_seat("tok", "ABCD", true)
	_send(_seats(spec))
	var s: Control = LobbyScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


func _press(s: Node, id: String) -> void:
	var b := Ui.find(s, id) as Button
	check(b != null, "no button '%s'" % id)
	if b != null:
		b.pressed.emit()


func _rows(s: Node) -> int:
	return Ui.find_all(s, "seat_row_").size()


func test_a_host_with_nobody_else_sees_no_list_and_no_help() -> void:
	var s := _host("")
	eq(_rows(s), 0, "no rows")
	check(Ui.find(s, "seat_list") == null and Ui.find(s, "kick_help") == null, "no list, no caption")


func test_one_dropped_seat_has_a_row_a_dim_lantern_and_an_enabled_button() -> void:
	var s := _host("d")
	eq(_rows(s), 1, "one row")
	eq((Ui.find(s, "seat_name_1") as Label).text, "Seat 1", "named by position")
	eq((Ui.find(s, "seat_state_1") as Label).text, Words.render("ui.seat_dropped"), "says it dropped off")
	check(not (Ui.find(s, "kick_1") as Button).disabled, "a dropped seat can be sent away with a tap")
	check(Ui.find(s, "kick_help") != null, "the help caption shows when a seat has dropped")


func test_everyone_here_shows_no_caption_and_a_tap_only_asks() -> void:
	var s := _host("hh")
	eq(_rows(s), 2, "two rows")
	check(Ui.find(s, "kick_help") == null, "no caption when nobody has dropped")
	_press(s, "kick_1")
	eq(fake.count("kick"), 0, "one tap on a seat that is here sends nothing")
	check(Ui.find(s, "seat_confirm_1") != null, "it asks first")
	_press(s, "kick_no_1")
	eq(fake.count("kick"), 0, "cancel sends nothing")
	check(Ui.find(s, "seat_confirm_1") == null, "and the question is gone")
	_press(s, "kick_1")
	_press(s, "kick_yes_1")
	eq(fake.count("kick"), 1, "the confirmed kick goes out exactly once")
	eq(fake.last("kick").get("seat"), "h-0", "with the right handle")


func test_a_dropped_seat_is_sent_with_one_tap_and_the_handle_of_that_row() -> void:
	var s := _host("hdh")
	_press(s, "kick_2")
	eq(fake.count("kick"), 1, "exactly one kick")
	eq(fake.last("kick").get("seat"), "h-1", "the dropped seat's own handle, not its position")
	check((Ui.find(s, "kick_2") as Button).disabled, "that row's button is off while the kick is out")
	_press(s, "kick_2")
	eq(fake.count("kick"), 1, "a second tap sends nothing more")


func test_the_row_vanishes_when_the_server_sends_the_new_lobby() -> void:
	var s := _host("dd")
	_press(s, "kick_1")
	_send([{"id": "h-1", "connected": false}])                    # the server answers: h-0 is gone
	eq(_rows(s), 1, "one row left")
	eq(fake.last("kick").get("seat"), "h-0", "(the first kick went to h-0)")
	_press(s, "kick_1")                                          # now position 1 is h-1: the row was rebuilt from the latest model
	eq(fake.count("kick"), 2, "a second kick goes out")
	eq(fake.last("kick").get("seat"), "h-1", "to the handle the LATEST model gives that position")


func test_a_model_that_changes_between_taps_never_sends_a_stale_handle() -> void:
	var s := _host("hh")
	_press(s, "kick_1")                                           # asks about h-0
	check(Ui.find(s, "seat_confirm_1") != null, "asking about the first seat")
	_send([{"id": "h-9", "connected": true}])                     # h-0 left on its own: the question must not follow position 1
	check(Ui.find(s, "seat_confirm_1") == null, "the question about a seat that is gone is dropped")
	_press(s, "kick_1")
	eq(fake.count("kick"), 0, "and a tap on the new first seat only asks again")


func test_a_refused_kick_brings_the_button_back() -> void:
	var s := _host("d")
	_press(s, "kick_1")
	check((Ui.find(s, "kick_1") as Button).disabled, "off while out")
	_send(_seats("d"))                                            # the same lobby again: the seat is still there
	check(not (Ui.find(s, "kick_1") as Button).disabled, "back when the server shows the seat is still taken")


func test_a_guest_sees_no_list_even_if_the_server_sends_seats() -> void:
	go_online()
	give_seat("tok", "ABCD", false)
	_send(_seats("dh"), false)
	var s: Control = LobbyScreen.new()
	add_child(s)
	_mounted.append(s)
	eq(_rows(s), 0, "no rows for a guest")
	check(Ui.find(s, "seat_list") == null, "no list")
	eq(fake.count("kick"), 0, "nothing sent")


func test_twelve_seats_all_get_a_row_with_the_right_handle() -> void:
	var s := _host("dhdhdhdhdhdh")
	eq(_rows(s), 12, "twelve rows")
	for n in [1, 5, 12]:
		check(Ui.find(s, "seat_name_%d" % n) != null, "Seat %d is there" % n)
	_press(s, "kick_12")                                          # index 11 is 'h' (here): asks
	_press(s, "kick_yes_12")
	eq(fake.last("kick").get("seat"), "h-11", "the last row sends the last handle")
	var more := []
	for i in 40:
		more.append({"id": "x-%d" % i, "connected": false})
	_send(more)
	eq(_rows(s), 12, "a hostile 40-seat list is capped at twelve rows")


func test_every_button_in_the_list_is_tall_enough_for_the_wood_art() -> void:
	Themes.use("flash")
	var s := _host("hdh")
	var holder := Control.new()
	holder.theme = Themes.current.godot_theme
	holder.size = Vector2(450, 1400)
	add_child(holder)
	_mounted.append(holder)
	remove_child(s)
	holder.add_child(s)
	await get_tree().process_frame
	await get_tree().process_frame
	for v in NineFit.check(holder):
		check(false, v)
	var buttons := Ui.find_all(s, "kick_").filter(func(n): return n is Button)
	check(buttons.size() == 3, "three Send away buttons")
	for b in buttons:
		check((b as Control).size.y >= Ui.MIN_ART_BUTTON_HEIGHT, "kick button at least %d px: %s" % [Ui.MIN_ART_BUTTON_HEIGHT, b.size])
