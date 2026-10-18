extends BaseTest
## The pick flow, move by move: while a pick is incomplete the Lock is grey and a line under it says what is missing; the pick
## goes out the moment it is complete; the Lock is live exactly when the server's view holds a pick. And the amount picker is
## always on screen with the move and target pickers, above the dock, at every phone size. (Stranger pass 2, N1 / N5.)

const SIZES := [Vector2(360, 640), Vector2(450, 800), Vector2(540, 960)]
const KINDS_NO_TARGET := ["scavenge", "guard"]
const KINDS_TARGET := ["steal", "investigate"]

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _view(pick: Variant = null, secs := 120.0, locked := false) -> Dictionary:
	var v := round_view(1, locked, secs)
	v.legal = {"scavenge": [], "guard": [], "steal": ["Fig", "Kiwi"], "investigate": ["Fig", "Kiwi"], "gift": ["Fig", "Kiwi"]}
	v.my_pick = pick
	return v


func _screen(w := 450.0, h := 800.0) -> RoundScreen:
	Themes.use("placeholder")
	go_online()
	give_seat()
	fake.server_send(_view())
	var s := RoundScreen.new()
	add_child(s)
	s.set_anchors_preset(Control.PRESET_TOP_LEFT)
	s.size = Vector2(w, h)
	_mounted.append(s)
	return s


func _picker(s: RoundScreen, kind: String) -> Dictionary:
	for p in s._m.pickers:
		if p.server_id == kind:
			return p
	return {}


func _hint(s: Node) -> String:
	return (Ui.find(s, "lock_hint") as Label).text


func _lock_disabled(s: Node) -> bool:
	return (Ui.find(s, "lock") as Button).disabled


func _picks_sent() -> Array:
	return fake.sent.filter(func(m): return m.get("t") == "pick")


func test_nothing_chosen_the_lock_is_grey_and_says_pick_a_move() -> void:
	var s := _screen()
	check(_lock_disabled(s), "grey")
	eq(_hint(s), "Pick a move first", "and why")


func test_moves_without_a_target_go_out_at_once_and_unlock_the_lock_when_the_server_echoes() -> void:
	for kind in KINDS_NO_TARGET:
		var s := _screen()
		var before := _picks_sent().size()
		s._choose(_picker(s, kind))
		eq(_picks_sent().size(), before + 1, kind + ": the pick went out with the tap")
		check(_lock_disabled(s), kind + ": still grey until the server holds the pick")
		fake.server_send(_view({"kind": kind, "target": null, "amount": 0}))
		check(not _lock_disabled(s), kind + ": live once the server has it")
		eq(_hint(s), "", kind + ": nothing to explain")


func test_moves_with_a_target_are_grey_with_the_right_reason_until_the_target_is_in() -> void:
	for kind in KINDS_TARGET:
		var s := _screen()
		s._choose(_picker(s, kind))
		check(_lock_disabled(s), kind + ": grey after the move")
		eq(_hint(s), "Pick a target first", kind + ": the reason")
		var before := _picks_sent().size()
		s._choose_target("Fig")
		eq(_picks_sent().size(), before + 1, kind + ": the pick went out with the target")
		fake.server_send(_view({"kind": kind, "target": "Fig", "amount": 0}))
		check(not _lock_disabled(s), kind + ": live")
		eq(_hint(s), "", kind + ": no reason")


func test_gift_needs_a_target_and_an_amount_in_either_order() -> void:
	for amount in [1, 2]:
		fake.sent.clear()
		# target first
		var a := _screen()
		a._choose(_picker(a, "gift"))
		eq(_hint(a), "Pick a target first", "gift: both missing, target is asked first")
		a._choose_target("Kiwi")
		check(_lock_disabled(a), "gift %d: grey with only a target" % amount)
		eq(_hint(a), "Pick an amount first", "gift %d: the amount is what is missing" % amount)
		eq(_picks_sent().size(), 0, "nothing sent yet")
		a._choose_amount(amount)
		var sent := _picks_sent()
		eq(sent.size(), 1, "gift %d: sent once complete" % amount)
		eq([sent[0].get("target"), sent[0].get("amount")], ["Kiwi", amount], "with both values")
		fake.server_send(_view({"kind": "gift", "target": "Kiwi", "amount": amount}))
		check(not _lock_disabled(a), "gift %d: live" % amount)
		eq(_hint(a), "", "gift %d: no reason" % amount)
		# amount first
		fake.sent.clear()
		var b := _screen()
		b._choose(_picker(b, "gift"))
		b._choose_amount(amount)
		check(_lock_disabled(b), "gift %d, amount first: grey" % amount)
		eq(_hint(b), "Pick a target first", "gift %d, amount first: the target is missing" % amount)
		eq(_picks_sent().size(), 0, "not sent on the amount alone")
		b._choose_target("Fig")
		eq(_picks_sent().size(), 1, "gift %d, amount first: sent when the target arrives" % amount)


func test_changing_a_move_after_a_complete_pick_keeps_the_lock_live_for_the_pick_the_server_holds() -> void:
	var s := _screen()
	fake.server_send(_view({"kind": "scavenge", "target": null, "amount": 0}))
	check(not _lock_disabled(s), "live with a pick in")
	s._choose(_picker(s, "gift"))
	check(not _lock_disabled(s), "starting another move does not take the Lock away: the server still holds a valid pick")
	eq(_hint(s), "", "and says nothing")


func test_a_valid_pick_is_never_left_with_a_grey_lock_after_a_reconnect_or_a_new_view() -> void:
	var s := _screen()
	for pick in [{"kind": "scavenge", "target": null, "amount": 0}, {"kind": "steal", "target": "Fig", "amount": 0},
			{"kind": "gift", "target": "Kiwi", "amount": 2}, {"kind": "guard", "target": null, "amount": 0}]:
		fake.server_send(_view(pick))
		check(not _lock_disabled(s), "a view that carries %s unlocks" % pick.kind)
	fake.server_close(1006)
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send(_view({"kind": "steal", "target": "Kiwi", "amount": 0}))
	check(not _lock_disabled(s), "after a reconnect the view's pick unlocks it")


func test_a_locked_or_closed_night_does_not_claim_a_pick_is_missing() -> void:
	var s := _screen()
	fake.server_send(_view({"kind": "scavenge", "target": null, "amount": 0}, 120.0, true))
	check(_lock_disabled(s), "locked: grey")
	eq(_hint(s), "", "locked: no reason line (the button already says so)")


func test_the_amount_picker_is_on_screen_above_the_dock_at_every_phone_size() -> void:
	for sz in SIZES:
		var s := _screen(sz.x, sz.y)
		s._choose(_picker(s, "gift"))
		await get_tree().process_frame
		await get_tree().process_frame
		var amount := Ui.find(s, "amount_1") as Control
		var dock := Ui.find(s, "lock") as Control
		check(amount != null, "%s: the amount picker is there as soon as the move is chosen" % sz)
		var rect := amount.get_global_rect()
		var top := dock.get_global_rect().position.y - 70.0              # the dock's own top: the Lock button sits under its lantern row
		check(rect.end.y <= dock.get_global_rect().position.y, "%s: amount rect ends at %f, the Lock starts at %f" % [sz, rect.end.y, dock.get_global_rect().position.y])
		check(top > 0.0 and rect.position.y >= 0.0, "%s: and it starts on screen (%f)" % [sz, rect.position.y])
		var targets := Ui.find_all(s, "target_")
		for t in targets:
			check((t as Control).get_global_rect().end.y <= dock.get_global_rect().position.y, "%s: every target card is above the dock too" % sz)
