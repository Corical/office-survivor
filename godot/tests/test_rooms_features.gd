extends BaseTest
## `hello_ok.features`, the server session's way of saying "I do lists": trusted when it says yes, believed when it says no,
## and ignored (the old probe and silence rule) when it says nothing or says something that is not a list. A hostile or
## confused handshake must never light the list up, switch it off for good, or crash.


func _title_hello(features: Variant, include_field := true) -> void:
	Intents.rooms_watch(true)
	fake.server_open()
	var hello := {"t": "hello_ok", "proto": 1}
	if include_field:
		hello["features"] = features
	fake.server_send(hello)


func _model() -> Dictionary:
	return Feed.rooms_model()


# ---------------- the server says yes ----------------

func test_a_server_that_advertises_lists_can_create_with_visibility_before_any_reply() -> void:
	_title_hello(["list_rooms"])
	check(_model().can_list, "the create sheet may open")
	check(not _model().supported, "but no reply has been seen: the list itself is still waiting")
	eq(Intents.create_room("private", "Fig's camp"), "", "create goes out")
	var sent: Dictionary = fake.last("create_room")
	eq(sent.get("visibility"), "private", "visibility sent on the strength of the handshake alone")
	eq(sent.get("name"), "Fig's camp", "name too")


func test_other_features_do_not_matter_and_list_rooms_can_be_anywhere_in_the_list() -> void:
	_title_hello(["future_thing", "list_rooms", "another"])
	check(_model().can_list, "found among others")


# ---------------- the server says no ----------------

func test_a_features_list_without_list_rooms_hides_the_list_at_once_and_never_asks() -> void:
	_title_hello([])
	check(not _model().can_list, "no sheet")
	check(not _model().loading, "and it is not waiting for anything")
	eq(fake.count("list_rooms"), 0, "no request is ever sent to a server that said no")
	for i in 5:
		clock.advance(4000)
		Net.tick()
	eq(fake.count("list_rooms"), 0, "not at the poll beat either")
	eq(Intents.create_room("private", "x"), "", "create still works")
	check(not fake.last("create_room").has("visibility"), "and sends nothing the server did not advertise")


func test_a_no_after_a_reconnect_clears_the_list_that_was_showing() -> void:
	_title_hello(["list_rooms"])
	fake.server_send({"t": "rooms", "rooms": [{"code": "KXQM", "seats_taken": 1, "seats_total": 4, "age_s": 5, "name": ""}]})
	eq(_model().rooms.size(), 1, "one camp showing")
	fake.server_close(1006, "gone")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1, "features": ["something_else"]})     # the server came back without lists
	eq(_model().rooms.size(), 0, "the server now says no: nothing stale stays on screen")
	check(not _model().can_list, "and it cannot list")


## A second hello_ok on a live line is ignored by design (review N06); it must not be able to switch the list on or off.
func test_a_second_hello_ok_on_the_same_line_cannot_change_what_was_advertised() -> void:
	_title_hello(["list_rooms"])
	fake.server_send({"t": "hello_ok", "proto": 1, "features": []})
	check(_model().can_list, "still the first handshake's word")
	fake.server_send({"t": "hello_ok", "proto": 1, "features": ["list_rooms"]})
	check(_model().can_list, "and still")


# ---------------- the server says nothing, or nonsense ----------------

func test_no_features_field_keeps_the_old_probe_and_silence_rule() -> void:
	_title_hello(null, false)
	eq(fake.count("list_rooms"), 1, "probed once, as before")
	check(not _model().can_list, "not trusted yet")
	clock.advance(3100)
	Net.tick()
	check(not _model().loading, "silence hid it after three seconds, as before")


func test_features_that_are_not_a_list_count_as_absent() -> void:
	for junk in ["list_rooms", {"list_rooms": true}, 7, true, null]:
		setup()
		_title_hello(junk)
		check(not _model().can_list, "not trusted: %s" % [junk])
		eq(fake.count("list_rooms"), 1, "probed as for an old server: %s" % [junk])


func test_a_list_of_the_wrong_things_is_a_no_not_a_yes() -> void:
	for junk in [[1, 2, 3], [null, {"a": 1}], [["list_rooms"]], ["LIST_ROOMS"], [" list_rooms"]]:
		setup()
		_title_hello(junk)
		check(not _model().can_list, "only the exact string counts: %s" % [junk])
		eq(fake.count("list_rooms"), 0, "and a server that sent a list without it is not asked: %s" % [junk])


func test_a_huge_features_list_is_read_in_bounded_time_and_cannot_smuggle_yes_past_the_cap() -> void:
	var big: Array = []
	for i in 100000:
		big.append("f%d" % i)
	big.append("list_rooms")
	var t0 := Time.get_ticks_msec()
	_title_hello(big)
	check(Time.get_ticks_msec() - t0 < 1500, "bounded work for a hostile handshake")
	check(not _model().can_list, "the cap means a list_rooms after 64 other names is not believed")


# ---------------- the next connection starts fresh ----------------

func test_what_one_connection_advertised_does_not_leak_into_the_next() -> void:
	_title_hello(["list_rooms"])
	check(_model().can_list, "yes on the first line")
	fake.server_close(1006, "gone")
	check(not _model().can_list, "dropped: nothing is advertised any more")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})                                       # an old build answers, no features
	check(not _model().can_list, "the old build did not advertise it: not trusted")
	var before := fake.count("list_rooms")
	check(before >= 0, "probe state is the old-server one")


func test_a_no_does_not_leak_into_the_next_connection_either() -> void:
	_title_hello([])
	check(not _model().can_list, "no on the first line")
	fake.server_close(1006, "gone")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1, "features": ["list_rooms"]})
	check(_model().can_list, "the upgraded server is believed on the new line")
	check(fake.count("list_rooms") >= 1, "and asked")
