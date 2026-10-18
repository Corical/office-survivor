extends BaseTest
## The title screen's open-camps list and the new-camp sheet, driven through a fake server: what shows, what does not, that a
## refresh changes words in place instead of rebuilding rows, and that the sheet sends only what the server understands.

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("placeholder")
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _title() -> Control:
	var s := TitleScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


func _online() -> void:
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})


func _camp(code: String, taken := 1, total := 4, age := 30, camp_name := "") -> Dictionary:
	return {"code": code, "seats_taken": taken, "seats_total": total, "age_s": age, "name": camp_name}


func _reply(rooms: Array) -> void:
	fake.server_send({"t": "rooms", "rooms": rooms})


func _btn(s: Node, id: String) -> Button:
	return Ui.find(s, id) as Button


func _texts_of(n: Node) -> String:
	return " | ".join(Ui.texts(n))


func _section(s: Node) -> Control:
	return Ui.find(s, "open_camps") as Control


# ---------------- showing ----------------

func test_the_title_asks_for_the_list_while_it_shows_and_stops_when_it_goes() -> void:
	var s := _title()
	check(Session.rooms.watching, "watching while the title is up")
	_online()
	eq(fake.count("list_rooms"), 1, "asked")
	s.free()
	_mounted.clear()
	check(not Session.rooms.watching, "and not once the title is gone")


func test_nothing_is_shown_for_a_server_that_cannot_list_camps() -> void:
	var s := _title()
	_online()
	clock.advance(3500)
	Net.tick()
	check(not _section(s).visible, "no section at all")
	check(_btn(s, "create") != null and _btn(s, "join") != null, "the rest of the title is untouched")


func test_a_quiet_header_shows_while_the_server_is_being_asked() -> void:
	var s := _title()
	_online()
	check(_section(s).visible, "the section is there, waiting")
	check(Ui.find(s, "no_open_camps") != null and not (Ui.find(s, "no_open_camps") as Control).visible, "but it does not say 'none' yet")


func test_an_empty_list_says_so() -> void:
	var s := _title()
	_online()
	_reply([])
	check((Ui.find(s, "no_open_camps") as Control).visible, "the empty state shows")
	eq((Ui.find(s, "no_open_camps") as Label).text, "No open camps. Create one.", "in plain words")
	eq(Ui.find_all(s, "camp_").filter(func(n): return n is Button).size(), 0, "no cards")


func test_each_camp_is_a_card_with_its_name_or_code_seats_and_age() -> void:
	var s := _title()
	_online()
	_reply([_camp("KXQM", 2, 4, 200, "Fig's camp"), _camp("ABCD", 1, 4, 5), _camp("WXYZ", 3, 4, 7300)])
	var a := _texts_of(_btn(s, "camp_KXQM"))
	check("Fig's camp" in a and "2 of 4" in a and "3 min ago" in a, "named camp: " + a)
	var b := _texts_of(_btn(s, "camp_ABCD"))
	check("Room ABCD" in b and "1 of 4" in b and "just now" in b, "unnamed camp shows its code: " + b)
	check("2 h ago" in _texts_of(_btn(s, "camp_WXYZ")), "hours")


func test_cards_come_in_the_servers_order() -> void:
	var s := _title()
	_online()
	_reply([_camp("CCCC"), _camp("AAAA"), _camp("BBBB")])
	var ids: Array = (Ui.find(s, "camp_list") as Node).get_children().map(func(c): return c.get_meta("id"))
	eq(ids, ["camp_CCCC", "camp_AAAA", "camp_BBBB"], "newest first, as sent")


func test_a_thousand_camps_make_at_most_twenty_cards() -> void:
	var s := _title()
	_online()
	var many := []
	for i in 1000:
		many.append(_camp("R%03d" % i))
	Session.apply({"t": "rooms", "rooms": many})
	eq(Ui.find_all(s, "camp_R").size(), RoomsWatch.MAX_ROOMS, "twenty")


func test_a_long_name_is_one_line_on_its_card() -> void:
	var s := _title()
	_online()
	_reply([_camp("LONG", 1, 4, 5, "Bartholomew the Magnificent's Camp")])
	for l in (_btn(s, "camp_LONG") as Node).find_children("*", "Label", true, false):
		check(l.autowrap_mode == TextServer.AUTOWRAP_OFF and l.text_overrun_behavior == TextServer.OVERRUN_TRIM_ELLIPSIS,
			"one line, trimmed: " + l.text)


# ---------------- refreshing without a jump ----------------

func test_a_refresh_with_the_same_camps_keeps_the_very_same_cards() -> void:
	var s := _title()
	_online()
	_reply([_camp("KXQM", 1), _camp("ABCD", 2)])
	var first := _btn(s, "camp_KXQM")
	var second := _btn(s, "camp_ABCD")
	for i in 3:
		clock.advance(3100)
		Net.tick()
		_reply([_camp("KXQM", 1), _camp("ABCD", 2)])
	check(_btn(s, "camp_KXQM") == first and _btn(s, "camp_ABCD") == second, "the same nodes: nothing under a finger was rebuilt")


func test_a_changed_camp_changes_its_words_in_place_and_a_gone_camp_goes_and_a_new_one_comes() -> void:
	var s := _title()
	_online()
	_reply([_camp("KXQM", 1, 4, 10), _camp("ABCD", 2, 4, 10)])
	var kept := _btn(s, "camp_KXQM")
	_reply([_camp("KXQM", 3, 4, 130), _camp("NEWW", 1, 4, 1)])
	check(_btn(s, "camp_KXQM") == kept, "the camp that is still there is the same card")
	check("3 of 4" in _texts_of(kept) and "2 min ago" in _texts_of(kept), "with its new seats and age: " + _texts_of(kept))
	check(_btn(s, "camp_ABCD") == null or _btn(s, "camp_ABCD").is_queued_for_deletion(), "the vanished camp is gone")
	check(_btn(s, "camp_NEWW") != null, "the new camp is there")


func test_the_list_is_dimmed_while_the_connection_is_down_and_bright_again_after() -> void:
	var s := _title()
	_online()
	_reply([_camp("KXQM")])
	eq((Ui.find(s, "camp_list") as Control).modulate.a, 1.0, "live")
	fake.server_close(1006)
	check((Ui.find(s, "camp_list") as Control).modulate.a < 1.0, "dimmed: the last list we had")
	clock.advance(1100)
	Net.tick()
	_online()
	_reply([_camp("KXQM")])
	eq((Ui.find(s, "camp_list") as Control).modulate.a, 1.0, "live again")


# ---------------- tapping ----------------

func test_a_tap_joins_that_camp() -> void:
	var s := _title()
	_online()
	_reply([_camp("KXQM")])
	_btn(s, "camp_KXQM").pressed.emit()
	eq(fake.last("join_room"), {"t": "join_room", "code": "KXQM"}, "joined by code")


func test_a_camp_that_filled_first_gives_a_neutral_message_on_the_title() -> void:
	var s := _title()
	_online()
	_reply([_camp("KXQM")])
	_btn(s, "camp_KXQM").pressed.emit()
	fake.server_send({"t": "error", "code": "room_full", "message": "That room is full."})
	eq((Ui.find(s, "notice") as Label).text, "That camp filled up or closed first. Here is the fresh list.", "neutral words")
	clock.advance(50)
	Net.tick()
	eq(fake.count("list_rooms"), 2, "and the list is asked for at once")
	eq(Session.screen, "title", "still here")


# ---------------- the new-camp sheet ----------------

func test_create_goes_straight_out_on_a_server_that_cannot_list_camps() -> void:
	var s := _title()
	_online()
	_btn(s, "create").pressed.emit()
	check(Ui.find(s, "sheet") == null, "no sheet: there is nothing to choose")
	eq(fake.last("create_room"), {"t": "create_room"}, "the plain create")


func test_create_opens_the_sheet_when_the_server_can_list_camps() -> void:
	var s := _title()
	_online()
	_reply([])
	_btn(s, "create").pressed.emit()
	check(Ui.find(s, "sheet") != null, "the sheet is open")
	eq(fake.count("create_room"), 0, "nothing sent yet")
	check((_btn(s, "vis_public") as Button).theme_type_variation == "ChosenButton", "public is the default")
	check((_btn(s, "vis_private") as Button).theme_type_variation == "", "private is not")
	eq((Ui.find(s, "vis_help") as Label).text, "Anyone who opens the app can see this camp and join it.", "its one-line explanation")
	eq((Ui.find(s, "camp_name") as LineEdit).max_length, 24, "names stop at 24")


func test_the_sheet_sends_the_choice_and_the_name() -> void:
	var s := _title()
	_online()
	_reply([])
	_btn(s, "create").pressed.emit()
	(Ui.find(s, "camp_name") as LineEdit).text_changed.emit("Fig's camp")
	_btn(s, "vis_private").pressed.emit()
	eq((Ui.find(s, "vis_help") as Label).text, "Not listed. Only people you give the code to can join.", "the private explanation shows")
	check((_btn(s, "vis_private") as Button).theme_type_variation == "ChosenButton", "private is picked")
	_btn(s, "sheet_create").pressed.emit()
	var sent := fake.last("create_room")
	eq(sent.get("visibility"), "private", "visibility")
	eq(sent.get("name"), "Fig's camp", "name")
	check(Ui.find(s, "sheet") == null, "the sheet closed")


func test_cancel_closes_the_sheet_and_sends_nothing() -> void:
	var s := _title()
	_online()
	_reply([])
	_btn(s, "create").pressed.emit()
	_btn(s, "sheet_cancel").pressed.emit()
	check(Ui.find(s, "sheet") == null, "closed")
	eq(fake.count("create_room"), 0, "nothing sent")


func test_a_sheet_left_open_keeps_its_text_across_a_rebuild() -> void:
	var s := _title()
	_online()
	_reply([])
	_btn(s, "create").pressed.emit()
	(Ui.find(s, "camp_name") as LineEdit).text_changed.emit("Keep me")
	Feed.status_changed.emit(Feed.status())                    # something rebuilt the menu (a connection change, say)
	eq((Ui.find(s, "camp_name") as LineEdit).text, "Keep me", "the name is still there")
	check(Ui.find(s, "sheet") != null, "and so is the sheet")


func test_the_sheet_still_creates_when_the_list_went_away_meanwhile_but_without_the_new_fields() -> void:
	var s := _title()
	_online()
	_reply([])
	_btn(s, "create").pressed.emit()
	clock.advance(3500)                                         # the next poll goes out and the server says nothing...
	Net.tick()
	clock.advance(3500)                                         # ...so three seconds later the list is hidden
	Net.tick()
	check(not Feed.rooms_model().supported, "hidden")
	_btn(s, "vis_private").pressed.emit()
	_btn(s, "sheet_create").pressed.emit()
	var sent := fake.last("create_room")
	check(not sent.is_empty() and not sent.has("visibility"), "an unproven server gets the plain create: %s" % [sent])
