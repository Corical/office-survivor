extends BaseTest
## The lobby's new parts: Copy, the honest bots note, the guest's waiting card, and the clipboard intent behind Copy.

var _mounted: Array = []
var _copied: Array = []
var _real_clipboard: Callable


func setup() -> void:
	super.setup()
	Themes.use("placeholder")
	_copied.clear()
	_real_clipboard = Intents.clipboard_set
	Intents.clipboard_set = func(t: String): _copied.append(t)


func teardown() -> void:
	super.teardown()
	Intents.clipboard_set = _real_clipboard
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _lobby(is_host: bool, taken := 2) -> Control:
	go_online()
	give_seat("t", "ABCD", is_host)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": taken, "seats_total": 4, "host": is_host})
	var s: Control = LobbyScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


func test_copy_text_puts_exactly_the_text_on_the_clipboard() -> void:
	eq(Intents.copy_text("KXQM"), "", "reports success")
	eq(_copied, ["KXQM"], "the clipboard got the code")


func test_copy_text_refuses_nothing_and_whitespace_and_never_copies_a_novel() -> void:
	eq(Intents.copy_text(""), "empty", "empty is refused")
	eq(Intents.copy_text("   \n\t"), "empty", "whitespace is refused")
	eq(_copied.size(), 0, "nothing reached the clipboard")
	eq(Intents.copy_text("  KXQM \n"), "", "padding is trimmed")
	eq(_copied[0], "KXQM", "trimmed")
	Intents.copy_text("x".repeat(5000))
	eq(String(_copied[1]).length(), Intents.COPY_MAX, "a hostile long text is cut")


func test_the_copy_button_copies_the_camp_code() -> void:
	var s := _lobby(true)
	(Ui.find(s, "copy_code") as Button).pressed.emit()
	eq(_copied, ["ABCD"], "the code, not the label")
	eq((Ui.find(s, "copy_code") as Button).text, "Copied", "the button says it worked")


func test_a_second_copy_press_is_not_undone_by_the_first_ones_timer() -> void:
	var s := _lobby(true)
	s.copied_seconds = 0.4
	var b := Ui.find(s, "copy_code") as Button
	b.pressed.emit()
	await get_tree().create_timer(0.2).timeout
	b.pressed.emit()
	await get_tree().create_timer(0.3).timeout          # the first timer (0.4 s) has now fired
	eq(b.text, "Copied", "still showing Copied for the second press")
	await get_tree().create_timer(0.3).timeout
	eq(b.text, "Copy", "back to Copy after the second press's time")


func test_the_host_is_told_bots_fill_empty_seats_only_when_there_are_empty_seats() -> void:
	var s := _lobby(true, 1)
	check(Ui.find(s, "bots_note") != null, "1 of 4: the note is there")
	check("bots" in text_of_node(Ui.find(s, "bots_note")).to_lower(), "and says bots")
	for taken in [2, 3]:
		fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": taken, "seats_total": 4, "host": true})
		check(Ui.find(s, "bots_note") != null, "%d of 4: still there" % taken)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 4, "seats_total": 4, "host": true})
	check(Ui.find(s, "bots_note") == null, "4 of 4: no empty seats, no note")


func test_a_guest_sees_the_waiting_card_and_neither_start_nor_the_bots_note() -> void:
	var s := _lobby(false, 1)
	check(Ui.find(s, "waiting_card") != null and Ui.find(s, "waiting") != null, "the waiting card")
	check(Ui.find(s, "start") == null, "no Start")
	check(Ui.find(s, "bots_note") == null, "no bots note for someone who cannot start")


func test_the_lobby_has_a_lantern_per_seat() -> void:
	Themes.use("flash")                                  # the placeholder theme has no lantern art
	var s := _lobby(true, 3)
	var row := Ui.find(s, "seat_lanterns")
	check(row != null, "lanterns shown")
	if row != null:
		eq(row.get_child_count(), 4, "one per seat")


func text_of_node(n: Node) -> String:
	return n.text if n != null else "<missing>"
