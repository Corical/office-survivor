extends BaseTest
## The screens, mounted for real and driven the way a player would: the server's data goes in through the fake
## transport, buttons are pressed by id, and what reaches the wire is checked. Headless: scene-tree state, no pixels.

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


func mount(script: GDScript) -> Control:
	var s: Control = script.new()
	add_child(s)
	_mounted.append(s)
	return s


func press(screen: Node, id: String) -> void:
	var b := Ui.find(screen, id)
	check(b != null, "no control with id '%s' (have: %s)" % [id, Ui.texts(screen)])
	if b != null:
		b.pressed.emit()


func text_of(screen: Node, id: String) -> String:
	var n := Ui.find(screen, id)
	return n.text if n != null else "<missing %s>" % id


## Every word on a card (a container carrying an id), joined with spaces.
func card_text(screen: Node, id: String) -> String:
	var n := Ui.find(screen, id)
	check(n != null, "no card with id '%s'" % id)
	return " ".join(Ui.texts(n)) if n != null else ""


func btn(screen: Node, id: String) -> Button:
	return Ui.find(screen, id) as Button


# ---------------- title ----------------

func test_title_offers_create_join_and_settings() -> void:
	var s := mount(TitleScreen)
	check(btn(s, "create") != null and btn(s, "join") != null and btn(s, "settings_toggle") != null, "the three controls")
	eq(text_of(s, "app_name"), "Arena", "the theme's app name")
	check(btn(s, "resume") == null, "no resume without a stored seat")


func test_title_offers_resume_when_a_seat_is_stored() -> void:
	Session.token = "tok"
	Session.room_code = "ABCD"
	var s := mount(TitleScreen)
	check(btn(s, "resume") != null, "resume offered")


func test_create_with_a_bad_server_address_says_so_in_the_themes_words() -> void:
	Session.server_url = ""
	var s := mount(TitleScreen)
	press(s, "create")
	eq(text_of(s, "notice"), "Enter the server address first.", "refusal worded by the theme")
	eq(fake.open_urls.size(), 0, "no socket opened")


func test_create_goes_out_once_the_connection_is_up() -> void:
	var s := mount(TitleScreen)
	press(s, "create")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.count("create_room"), 1, "create sent")


func test_join_sends_the_typed_code_in_capitals() -> void:
	var s := mount(TitleScreen)
	var edit := Ui.find(s, "code") as LineEdit
	edit.text = "wxyz"
	edit.text_changed.emit("wxyz")
	press(s, "join")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.last("join_room").get("code"), "WXYZ", "code normalised")


func test_settings_shows_the_server_address_and_editing_it_changes_it() -> void:
	var s := mount(TitleScreen)
	check(Ui.find(s, "server_url") == null, "hidden at first")
	press(s, "settings_toggle")
	var url := Ui.find(s, "server_url") as LineEdit
	check(url != null, "shown after the toggle")
	eq(url.text, "ws://test", "current address")
	url.text_changed.emit("wss://other.example:8470")
	eq(Session.server_url, "wss://other.example:8470", "applied")


func test_a_typo_in_the_address_never_costs_the_stored_seat() -> void:
	Session.token = "keep"
	Session.room_code = "ABCD"
	var s := mount(TitleScreen)
	press(s, "settings_toggle")
	(Ui.find(s, "server_url") as LineEdit).text_changed.emit("not an address")
	press(s, "create")
	eq(Session.token, "keep", "seat kept")


# ---------------- lobby ----------------

func _to_lobby(is_host: bool) -> void:
	go_online()
	give_seat("t", "ABCD", is_host)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 2, "seats_total": 4, "host": is_host})


func test_lobby_shows_the_room_code_and_seats_and_lets_the_host_start() -> void:
	_to_lobby(true)
	var s := mount(LobbyScreen)
	eq(text_of(s, "room_code"), "Room ABCD", "code")
	eq(text_of(s, "seats"), "2 of 4 seats taken", "seats")
	press(s, "start")
	eq(fake.count("start"), 1, "start sent")
	check(Ui.find(s, "waiting") == null, "the host is not told to wait")


func test_lobby_makes_a_guest_wait_without_a_start_button() -> void:
	_to_lobby(false)
	var s := mount(LobbyScreen)
	check(btn(s, "start") == null, "no start for a guest")
	check(Ui.find(s, "waiting") != null, "told to wait")


func test_lobby_updates_when_the_host_changes() -> void:
	_to_lobby(false)
	var s := mount(LobbyScreen)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 3, "seats_total": 4, "host": true})
	check(btn(s, "start") != null, "now the host: Start appears")
	eq(text_of(s, "seats"), "3 of 4 seats taken", "seats updated")


# ---------------- round ----------------

func _round_screen(n := 1) -> Control:
	in_round(n)
	return mount(RoundScreen)


func test_round_shows_who_i_am_the_round_the_goal_and_everyone() -> void:
	var s := _round_screen(3)
	eq(text_of(s, "round_of"), "Round 3 of 10", "round")
	eq(text_of(s, "you_are"), "You are Mango", "alias")
	eq(text_of(s, "resource"), "Rations: 7", "my exact food")
	eq(text_of(s, "goal"), "give away 3 rations over the game", "goal worded from the server's text")
	check(Ui.find(s, "home_Mango") != null and Ui.find(s, "home_Fig") != null and Ui.find(s, "home_Kiwi") != null, "everyone has a home")
	check("(you)" in card_text(s, "home_Mango"), "I am marked")


func test_round_offers_exactly_the_moves_the_server_listed() -> void:
	var s := _round_screen()
	var ids: Array = Ui.find_all(s, "move_").map(func(b): return b.get_meta("id"))
	ids.sort()
	eq(ids, ["move_gift", "move_guard", "move_scavenge", "move_steal"], "no move the server did not offer")


func test_a_move_without_a_target_goes_out_at_once() -> void:
	var s := _round_screen()
	press(s, "move_scavenge")
	eq(fake.last("pick").kind, "scavenge", "pick sent")
	eq(fake.last("pick").target, null, "no target")


func test_a_move_with_a_target_waits_for_the_target() -> void:
	var s := _round_screen()
	press(s, "move_steal")
	eq(fake.count("pick"), 0, "nothing sent yet")
	check(btn(s, "target_Fig") != null and btn(s, "target_Kiwi") != null, "the server's targets are offered")
	check(btn(s, "target_Mango") == null, "never myself")
	press(s, "target_Fig")
	eq([fake.last("pick").kind, fake.last("pick").target], ["steal", "Fig"], "pick sent with its target")


func test_a_gift_asks_for_target_then_amount() -> void:
	var s := _round_screen()
	press(s, "move_gift")
	press(s, "target_Kiwi")
	eq(fake.count("pick"), 0, "still waiting for the amount")
	check(btn(s, "amount_1") != null and btn(s, "amount_2") != null and btn(s, "amount_3") == null, "only the server's amounts")
	press(s, "amount_2")
	eq([fake.last("pick").kind, fake.last("pick").target, fake.last("pick").amount], ["gift", "Kiwi", 2], "gift sent")


func test_lock_is_disabled_until_there_is_a_pick() -> void:
	var s := _round_screen()
	check(btn(s, "lock").disabled, "no pick yet: lock disabled")
	press(s, "move_scavenge")
	fake.server_send(_view_with_pick())
	check(not btn(s, "lock").disabled, "picked: lock enabled")


func _view_with_pick(n := 1, locked := false) -> Dictionary:
	var v := round_view(n, locked)
	v.my_pick = {"kind": "scavenge", "target": null, "amount": 0}
	return v


func test_lock_sends_once_and_the_screen_shows_it() -> void:
	var s := _round_screen()
	fake.server_send(_view_with_pick())
	press(s, "lock")
	eq(fake.count("lock"), 1, "lock sent")
	eq(text_of(s, "lock"), "Locking in...", "while waiting for the server")
	check(btn(s, "lock").disabled, "cannot be pressed again")
	for m in Ui.find_all(s, "move_"):
		check(m.disabled, "the picker is shut once the lock is out")
	fake.server_send(_view_with_pick(1, true))
	eq(text_of(s, "lock"), "Locked in", "confirmed")


func test_a_locked_round_keeps_the_picker_shut_whatever_arrives() -> void:
	var s := _round_screen()
	fake.server_send(_view_with_pick(1, true))
	for m in Ui.find_all(s, "move_"):
		check(m.disabled, "move disabled")
	fake.server_send(_view_with_pick(1, false))                      # a racing, stale view
	check(btn(s, "lock").disabled, "still no second lock")


func test_the_picker_is_shut_while_the_connection_is_down_or_stale() -> void:
	var s := _round_screen()
	fake.server_close(1006)
	for m in Ui.find_all(s, "move_"):
		check(m.disabled, "move disabled while reconnecting")
	check(btn(s, "lock").disabled, "lock disabled while reconnecting")


func test_the_locked_count_is_a_count_only() -> void:
	var s := _round_screen()
	fake.server_send(round_view(1, false, 150, 2))
	eq(text_of(s, "locked_count"), "2 of 4 locked in", "count")
	for t in Ui.texts(s):
		check(not ("locked by" in t.to_lower()), "no list of who locked")


func test_other_players_show_only_a_band_never_a_number() -> void:
	in_round()
	var v := round_view(1)
	v.board = [{"alias": "Fig", "band": "well_fed"}, {"alias": "Kiwi", "band": "starving"},
		{"alias": "Plum", "band": "bandit"}, {"alias": "Mango", "band": "getting_by"}]
	fake.server_send(v)
	var s := mount(RoundScreen)
	eq(card_text(s, "home_Fig"), "Fig Well fed", "name and band word")
	eq(card_text(s, "home_Plum"), "Plum Bandit", "the outcast is public")
	for id in ["home_Fig", "home_Kiwi", "home_Plum"]:
		for ch in card_text(s, id):
			check(not ch.is_valid_int(), "a digit in another player's card: " + card_text(s, id))


func test_a_push_that_only_moves_the_locked_count_keeps_the_same_buttons() -> void:
	# found by driving: bots lock all the time, and a rebuild between a press and its release lost the tap
	var s := _round_screen()
	var steal := btn(s, "move_steal")
	fake.server_send(round_view(1, false, 150, 2))
	check(btn(s, "move_steal") == steal, "the very same button node survives a locked-count push")
	eq(text_of(s, "locked_count"), "2 of 4 locked in", "the count still updates")
	fake.server_send(round_view(1, false, 140, 3))
	check(btn(s, "move_steal") == steal, "and a second push")
	eq(text_of(s, "locked_count"), "3 of 4 locked in", "count updated again")


func test_a_push_that_changes_what_is_shown_does_rebuild() -> void:
	var s := _round_screen()
	var before := btn(s, "move_steal")
	fake.server_send(_view_with_pick())
	check(btn(s, "move_steal") != before, "a pick echo rebuilds the screen")
	check(Ui.find(s, "my_pick") != null, "and shows it")


func test_the_same_reveal_pushed_again_keeps_the_continue_button() -> void:
	in_round(1)
	fake.server_send(_reveal_view())
	var s := mount(RevealScreen)
	var cont := btn(s, "continue")
	for i in 5:
		fake.server_send(_reveal_view())
	check(btn(s, "continue") == cont, "five identical pushes, the same Continue button")
	fake.server_send(_reveal_view(1).merged({"private": []}, true))
	check(btn(s, "continue") != cont, "a changed reveal does rebuild")


func test_the_goal_status_line_does_not_say_decided_at_the_end_twice() -> void:
	in_round()
	var v := round_view(1)
	v.me.goal_progress = {"state": "end", "text": "x", "line": {"code": "progress_beat",
		"args": {"rations": 8, "target": "Fig"}}}
	fake.server_send(v)
	var s := mount(RoundScreen)
	var text: String = (Ui.find(s, "goal_status") as Label).text
	eq(text.to_lower().count("decided at the end"), 1, "once, not twice: " + text)


func test_the_timer_shows_the_clock_and_says_unknown_when_stale() -> void:
	var s := _round_screen()
	s._tick()
	eq(text_of(s, "timer_label"), "180 s", "seconds left")
	clock.advance(30000)
	s._tick()
	eq(text_of(s, "timer_label"), "150 s", "the clock, not the phone")
	fake.server_close(1006)
	s._tick()
	eq(text_of(s, "timer_label"), "Waiting for the server", "stale: unknown")


func test_radio_offers_the_phrases_and_asks_whom_when_needed() -> void:
	in_round()
	var v := round_view(1)
	v.radio_phrases = [{"key": "trust", "needs_player": true}, {"key": "me", "needs_player": false}]
	fake.server_send(v)
	var s := mount(RoundScreen)
	press(s, "radio_toggle")
	check(btn(s, "phrase_trust") != null and btn(s, "phrase_me") != null, "phrases offered")
	press(s, "phrase_trust")
	check(btn(s, "about_Fig") != null and btn(s, "about_Mango") == null, "choose someone else")
	press(s, "about_Fig")
	eq([fake.last("radio").phrase, fake.last("radio").about], ["trust", "Fig"], "radio sent")


func test_a_phrase_that_names_nobody_goes_out_at_once() -> void:
	in_round()
	var v := round_view(1)
	v.radio_phrases = [{"key": "me", "needs_player": false}]
	fake.server_send(v)
	var s := mount(RoundScreen)
	press(s, "radio_toggle")
	press(s, "phrase_me")
	eq(fake.last("radio").phrase, "me", "sent")


func test_a_new_round_forgets_the_half_made_choice() -> void:
	var s := _round_screen(1)
	press(s, "move_steal")
	check(btn(s, "target_Fig") != null, "targets shown")
	fake.server_send(round_view(2))
	check(btn(s, "target_Fig") == null, "a fresh round starts fresh")


func test_a_round_with_nobody_to_target_shows_the_move_but_cannot_be_completed() -> void:
	in_round()
	var v := round_view(1)
	v.legal = {"scavenge": [], "steal": []}
	v.aliases = []
	fake.server_send(v)
	var s := mount(RoundScreen)
	press(s, "move_steal")
	check(Ui.find_all(s, "target_").is_empty(), "no targets to offer")
	eq(fake.count("pick"), 0, "and nothing sent")


# ---------------- reveal, end, upgrade ----------------

func _reveal_view(rnd := 1) -> Dictionary:
	return {"t": "reveal", "round": rnd, "news": [{"code": "news_bandit", "args": {"player": "Fig"}}],
		"private": [{"code": "scavenged", "args": {"found": 1}}, {"code": "now_have", "args": {"rations": 8}}],
		"radio": [{"phrase": "trust", "about": "Kiwi"}], "board": null, "seconds_left": 20}


func test_reveal_writes_every_line_and_the_radio() -> void:
	in_round(1)
	fake.server_send(_reveal_view())
	var s := mount(RevealScreen)
	var all := Ui.texts(s)
	check("You scavenged and found 1." in all, "my private line: %s" % [all])
	check("You now have 8 rations." in all, "my total")
	check("Fig ran out of food. Fig is back... as a bandit." in all, "the public line")
	check("Don't trust Kiwi." in all, "the radio")


func test_continue_sends_once() -> void:
	in_round(1)
	fake.server_send(_reveal_view())
	var s := mount(RevealScreen)
	press(s, "continue")
	press(s, "continue")
	eq(fake.count("continue"), 1, "one continue")


func _end_view() -> Dictionary:
	var rows := []
	for a in [["Fig", 5, 9, true, 3], ["Mango", 3, 4, false, 7], ["Kiwi", 1, 1, false, 0]]:
		rows.append({"alias": a[0], "score": a[1], "rations": a[2], "seat": a[3], "goal_done": a[3], "stole": 2,
			"times_robbed": a[4], "gave_away": 1})
	return {"t": "end", "extracted": ["Fig"], "winners": ["Fig"], "results": rows}


func test_end_shows_the_winner_and_the_results_in_the_servers_order() -> void:
	in_round(10)
	fake.server_send(_end_view())
	var s := mount(EndScreen)
	eq(text_of(s, "winners"), "Fig", "winner")
	var order: Array = Ui.find_all(s, "row_").map(func(l): return l.get_meta("id"))
	eq(order, ["row_Fig", "row_Mango", "row_Kiwi"], "the server's order")
	check("(you)" in text_of(s, "row_Mango"), "I am marked")
	check("winner" in text_of(s, "marks_Fig") and "seat" in text_of(s, "marks_Fig"), "winner with a seat")
	check("goal missed" in text_of(s, "marks_Mango"), "goal missed shown")


func test_end_highlights_the_top_of_points_but_never_being_robbed() -> void:
	in_round(10)
	fake.server_send(_end_view())
	var s := mount(EndScreen)
	eq(text_of(s, "cell_Fig_score"), "[5]", "top score marked")
	eq(text_of(s, "cell_Mango_score"), "3", "others plain")
	eq(text_of(s, "cell_Mango_times_robbed"), "7", "the most-robbed player's count is plain text")
	for r in ["Fig", "Mango", "Kiwi"]:
		check(not ("[" in text_of(s, "cell_%s_times_robbed" % r)), "robbed is never highlighted")


func test_back_to_title_leaves_the_game() -> void:
	in_round(10)
	fake.server_send(_end_view())
	var s := mount(EndScreen)
	press(s, "back")
	eq(Session.screen, "title", "back on the title")
	eq(Session.token, "", "seat forgotten")


func test_upgrade_screen_says_to_update() -> void:
	var s := mount(UpgradeScreen)
	eq(text_of(s, "upgrade"), "Please update the app to play.", "message")


# ---------------- router and overlay ----------------

func test_the_router_follows_the_connection_through_a_whole_game() -> void:
	var r := mount(preload("res://main.gd"))
	eq(r.current_name, "title", "starts on the title")
	go_online()
	give_seat("t", "ABCD", true)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 2, "seats_total": 4, "host": true})
	eq(r.current_name, "lobby", "lobby")
	fake.server_send(round_view(1))
	eq(r.current_name, "round", "round")
	fake.server_send(_reveal_view(1))
	eq(r.current_name, "reveal", "reveal")
	fake.server_send(_end_view())
	eq(r.current_name, "end", "end")


func test_the_router_shows_the_upgrade_screen_and_stays_there() -> void:
	var r := mount(preload("res://main.gd"))
	go_online()
	fake.server_send({"t": "upgrade_required", "min_proto": 2, "message": "x"})
	eq(r.current_name, "upgrade", "upgrade")
	fake.server_send(round_view(1))
	eq(r.current_name, "upgrade", "nothing moves it")


func test_the_overlay_is_quiet_when_all_is_well_and_speaks_when_not() -> void:
	var r := mount(preload("res://main.gd"))
	go_online()
	var banner := Ui.find(r, "net_banner") as Label
	check(not banner.visible, "quiet while online")
	fake.server_close(1006)
	check(banner.visible, "shown while reconnecting")
	eq(banner.text, "Reconnecting...", "in the theme's words")


func _overlay_of(r: Node) -> Overlay:
	for c in r.get_children():
		if c is Overlay:
			return c
	return null


func test_the_banner_is_calm_while_connecting_and_alarming_only_when_it_has_given_up() -> void:
	for net in ["connecting", "reconnecting"]:
		eq(Overlay.variation_for({"net": net, "terminal": ""}), "Banner", "%s is calm" % net)
	for net in ["unreachable", "offline", "stopped"]:
		eq(Overlay.variation_for({"net": net, "terminal": ""}), "BannerAlert", "%s is an alert" % net)
	eq(Overlay.variation_for({"net": "online", "terminal": "taken_over"}), "BannerAlert", "a terminal reason is an alert")


func test_the_live_overlay_wears_the_calm_look_while_reconnecting() -> void:
	var r := mount(preload("res://main.gd"))
	go_online()
	fake.server_close(1006)                           # the line dropped: the app is trying again
	var o := _overlay_of(r)
	eq(o.banner_variation(), "Banner", "reconnecting is not red")
	o._on_status({"net": "unreachable", "net_key": "ui.net.unreachable", "terminal": ""})
	eq(o.banner_variation(), "BannerAlert", "unreachable is")
	o._on_status({"net": "connecting", "net_key": "ui.net.connecting", "terminal": ""})
	eq(o.banner_variation(), "Banner", "and back to calm when it tries again")


func test_a_notice_reaches_the_overlay_in_the_themes_words() -> void:
	var r := mount(preload("res://main.gd"))
	in_round()
	fake.server_send({"t": "error", "code": "refused", "message": "Pick a move before you lock in."})
	eq((Ui.find(r, "notice_toast") as Label).text, "Pick a move before you lock in.", "generic notice uses the server's text")


func test_the_overlay_never_blocks_a_tap() -> void:
	var r := mount(preload("res://main.gd"))
	var o: Control = null
	for c in r.get_children():
		if c is Overlay:
			o = c
	eq(o.mouse_filter, Control.MOUSE_FILTER_IGNORE, "overlay container ignores the mouse")
	eq((Ui.find(r, "net_banner") as Label).mouse_filter, Control.MOUSE_FILTER_IGNORE, "banner ignores the mouse")


# ---------------- why the connection ended is still there when the title appears (stranger pass #7) ----------------

func _title_text(s: Control) -> String:
	return " | ".join(Ui.texts(s))


## The notice is emitted when the connection ends, a moment BEFORE the title exists; the reason must be read from state.
func test_a_title_that_appears_after_being_kicked_still_says_why() -> void:
	go_online()
	give_seat("tok", "ABCD", true)
	fake.server_send({"t": "error", "code": "taken_over", "message": "This seat was opened on another device."})
	eq(Session.terminal_reason, "taken_over", "the connection ended for that reason")
	var s := mount(TitleScreen)                            # built AFTER the notice went out
	check("another device" in _title_text(s), "the title tells the player why: %s" % _title_text(s))
	var n := Ui.find(s, "notice")
	check(n != null, "there is a notice label")
	if n != null:
		check((n as Label).text.count("another device") == 1, "once, not twice")


func test_every_terminal_reason_that_keeps_the_seat_is_explained_on_the_title() -> void:
	for pair in [["too_big", 0], ["flapping", 0]]:
		setup()
		go_online()
		give_seat("tok", "ABCD", true)
		Session._on_terminal(pair[0])                      # how Net reports a connection that cannot be fixed by retrying
		eq(Session.terminal_reason, pair[0], "%s: the reason is held as state" % pair[0])
		var s := mount(TitleScreen)
		var n := Ui.find(s, "notice")
		check(n != null, "%s: something is said" % pair[0])
		if n != null:
			check((n as Label).text != "" and not ("notice." in (n as Label).text), "%s: in words, not a key: %s" % [pair[0], (n as Label).text])


func test_the_reason_goes_away_when_the_player_acts_again() -> void:
	go_online()
	give_seat("tok", "ABCD", true)
	fake.server_send({"t": "error", "code": "taken_over", "message": "x"})
	var s := mount(TitleScreen)
	check(Ui.find(s, "notice") != null, "shown after the kick")
	Session.begin("create_room")                           # the player taps Create: a fresh start
	eq(Session.terminal_reason, "", "the reason is cleared")
	var t2 := mount(TitleScreen)
	check(Ui.find(t2, "notice") == null, "and a title built after that does not repeat it")


func test_the_upgrade_reason_is_not_dumped_on_the_title() -> void:
	go_online()
	Session.terminal_reason = "upgrade_required"
	var s := mount(TitleScreen)
	check(Ui.find(s, "notice") == null, "the upgrade screen owns that message")


func test_the_resume_button_names_the_camp_and_survives_a_hostile_code() -> void:
	go_online()
	give_seat("tok", "KXQM", true)
	Session.back_to_title()
	var s := mount(TitleScreen)
	var b := Ui.find(s, "resume") as Button
	check(b != null and "KXQM" in b.text, "names the camp: %s" % (b.text if b else "no button"))
	Session.room_code = "X".repeat(10000)
	var t2 := mount(TitleScreen)
	var b2 := Ui.find(t2, "resume") as Button
	check(b2 != null and b2.text.length() < 80, "a huge code cannot blow up the button: %d chars" % (b2.text.length() if b2 else -1))
	Session.room_code = ""
	var t3 := mount(TitleScreen)
	var b3 := Ui.find(t3, "resume") as Button
	check(b3 != null and b3.text != "" and not ("{" in b3.text), "no code: the plain label, no stray slot: %s" % (b3.text if b3 else ""))
