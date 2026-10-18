extends BaseTest
## The second review's findings, one test each, written to break the code: frames that arrive late, twice, out of order
## or in the wrong shape; refusals that must not release the wrong thing; a socket that dies while nobody speaks.

const A = preload("res://rulesets/survivors/adapter.gd")


func _with_pick(n := 1) -> Dictionary:
	var v := round_view(n)
	v.my_pick = {"kind": "scavenge", "target": null, "amount": 0}
	return v


# ---- N05: frames that outlive a deliberate close ----

func test_n05_a_late_view_after_leave_changes_nothing() -> void:
	in_round(3)
	Session.leave()
	fake.server_send(round_view(5))
	eq(Session.screen, "title", "still on the title")
	eq(Session.view, {}, "no view")


func test_n05_a_late_seat_after_leave_does_not_write_a_ghost_token() -> void:
	in_round(3)
	Session.leave()
	fake.server_send({"t": "seat", "token": "ghost", "room_code": "GHOS", "alias": "Mango", "host": false})
	eq(Session.token, "", "no ghost token in memory")
	eq(store.data.get("token"), "", "none on disk either")


# ---- N06: control frames in any order ----

func test_n06_a_second_hello_ok_does_not_reopen_the_lock_or_resume_again() -> void:
	in_round(3)
	Session.act("lock")
	var resumes := fake.count("resume")
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(Session.lock_state(), "sent", "still sent")
	eq(fake.count("resume"), resumes, "no second resume")


func test_n06_a_seat_nobody_asked_for_is_ignored() -> void:
	in_round()
	fake.server_send({"t": "seat", "token": "other-token", "room_code": "ZZZZ", "alias": "Intruder", "host": false})
	eq(Session.token, "tok-secret-1", "token unchanged")
	eq(Session.alias, "Mango", "alias unchanged")
	eq(Session.room_code, "ABCD", "room unchanged")


func test_n06_an_older_round_never_replaces_a_newer_view() -> void:
	in_round(4)
	Session.act("lock")
	fake.server_send(round_view(3))
	eq(Session.view.round, 4, "round 4 kept")
	eq(Session.lock_state(), "sent", "round 4's lock guard kept")
	check(not Session.picker_open(), "picker stays shut")


func test_n06_view_order_is_round_then_its_reveal_then_the_next_round() -> void:
	in_round(4)
	var rv := {"t": "reveal", "round": 4, "news": [], "private": [], "radio": [], "board": null, "seconds_left": 20}
	fake.server_send(rv)
	eq(Session.view.t, "reveal", "reveal 4 follows round 4")
	fake.server_send(round_view(4))
	eq(Session.view.t, "reveal", "a late round-4 view does not replace its reveal")
	fake.server_send(round_view(5))
	eq(Session.view.round, 5, "round 5 follows")
	fake.server_send(rv)
	eq(Session.view.t, "round", "an old reveal does not replace round 5")


# ---- N07: refusals and the lock ----

func test_n07_a_refused_radio_does_not_reopen_a_lock_in_flight() -> void:
	in_round()
	eq(Session.act("lock"), "", "lock out")
	eq(Session.act("radio", {"phrase": "me"}), "", "radio out")
	fake.server_send({"t": "error", "code": "refused", "message": "One radio message a day."})
	eq(Session.lock_state(), "sent", "the lock is still waiting for its own answer")
	check(not Session.picker_open(), "picker still shut")


func test_n07_pick_is_refused_locally_once_locked_or_sent() -> void:
	in_round()
	Session.act("lock")
	var before := fake.sent.size()
	eq(Session.pick("steal", "Fig"), "locked_round", "refused while the lock is in flight")
	fake.server_send(round_view(1, true))
	eq(Session.pick("steal", "Fig"), "locked_round", "and after the server says locked")
	eq(fake.sent.size(), before, "nothing reached the wire")


func test_n07_radio_is_refused_locally_when_the_view_says_unavailable() -> void:
	in_round()
	var v := round_view(1)
	v.radio_available = false
	fake.server_send(v)
	eq(Session.act("radio", {"phrase": "me"}), "radio_unavailable", "no radio today")


func test_n07_act_is_refused_after_upgrade_required() -> void:
	in_round()
	fake.server_send({"t": "upgrade_required", "min_proto": 2, "message": "update"})
	var before := fake.sent.size()
	eq(Session.act("lock"), "locked", "refused")
	eq(Session.pick("steal", "Fig"), "locked", "refused")
	eq(fake.sent.size(), before, "nothing sent")


# ---- N08: one wait per intent ----

func test_n08_the_picks_echo_does_not_disarm_the_locks_watchdog() -> void:
	in_round()
	Session.pick("scavenge", null)
	fake.server_send(_with_pick())                    # the echo of the pick
	Session.act("lock")
	clock.advance(8100)
	Net.tick()
	eq(Net.state, "reconnecting", "an unanswered lock is noticed even though the pick was answered")


func test_n08_a_view_that_answers_the_radio_does_not_disarm_the_lock() -> void:
	# two different intents in flight; the first reply must release only its own wait
	in_round()
	Session.act("radio", {"phrase": "me"})
	Session.act("lock")
	fake.server_send(round_view(1, false, 170))        # answers the radio, says nothing about the lock yet
	clock.advance(8100)
	Net.tick()
	eq(Net.state, "reconnecting", "the lock still had its own deadline")


func test_n08_a_locked_view_disarms_only_the_lock() -> void:
	in_round()
	Session.act("lock")
	Session.act("start")                              # a second intent in flight (the host starting)
	fake.server_send(round_view(1, true))
	clock.advance(8100)
	Net.tick()
	eq(Net.state, "online", "the view answered both")


# ---- N09: an idle dead socket ----

func test_n09_after_30_seconds_of_silence_the_client_probes_with_resume() -> void:
	in_round()
	var resumes := fake.count("resume")
	clock.advance(29000)
	Net.tick()
	eq(fake.count("resume"), resumes, "not yet")
	clock.advance(1100)
	Net.tick()
	eq(fake.count("resume"), resumes + 1, "probe sent")
	fake.server_send({"t": "seat", "token": "tok-secret-1", "room_code": "ABCD", "alias": "Mango", "host": true})
	fake.server_send(round_view(1, false, 150))
	clock.advance(20000)
	Net.tick()
	eq(Net.state, "online", "a live server answered the probe")


func test_n09_an_unanswered_probe_means_a_dead_socket() -> void:
	in_round()
	clock.advance(30100)
	Net.tick()
	clock.advance(8100)
	Net.tick()
	eq(Net.state, "reconnecting", "no answer in 8 s: reconnect")


func test_n09_no_probe_without_a_seat_or_on_the_title_screen() -> void:
	go_online()
	clock.advance(120000)
	Net.tick()
	eq(fake.count("resume"), 0, "nothing to probe with")


# ---- N16: the server address ----

func test_n16_a_bad_server_address_is_refused_before_anything_happens() -> void:
	Session.token = "keep-me"
	for bad in ["", "http://x.example", "ws://", "ws://a b", "localhost:8765"]:
		Session.server_url = bad
		eq(Session.begin("create_room"), "no_server_url", "refused: '%s'" % bad)
		eq(Session.resume_if_stored(), false, "resume refused: '%s'" % bad)
	eq(fake.open_urls.size(), 0, "never opened a socket")
	eq(Session.token, "keep-me", "a typo in the address does not cost you your seat")
	check(Session.valid_url("ws://127.0.0.1:8765"), "plain ws is fine")
	check(Session.valid_url("wss://pi.example.ts.net:8470"), "wss is fine")


## The server now answers a join of a camp that is full, started or gone with room_full / room_started / room_gone. For a
## typed code those are refusals of THAT join. room_gone used to hit the seat-gone path (written for a refused resume), so a
## mistyped code showed the terminal "your seat no longer exists" screen: the wrong message. (Starting a join forgets the old
## seat by design, review B1-2, so no seat is lost HERE; the point is the wording and the screen.)
func test_a_refused_typed_join_is_worded_as_that_join_not_as_a_lost_seat() -> void:
	for code in ["room_gone", "room_full", "room_started"]:
		setup()
		go_online()
		eq(Session.begin("join_room", {"code": "WXYZ"}), "", "the join goes out")
		fake.server_send({"t": "error", "code": code, "message": "x"})
		check(not notices.is_empty(), "%s: the player is told, in words" % code)
		eq(notices.back().code, code, "%s: with its own code so the theme can word it" % code)
		check(notices.back().kind != "terminal", "%s: not the seat-gone terminal screen" % code)
		eq(Feed.status().screen, "title", "%s: still on the title screen, free to try another code" % code)
		eq(Session.expecting_seat(), false, "%s: nothing is waiting for a seat any more" % code)


func _logged_since(m: int) -> String:
	var n: int = Log.total - m
	return "\n".join(Log.lines.slice(maxi(0, Log.lines.size() - n)))


## Stranger pass: the idle probe's resume is answered by the view and then the seat. The seat for the seat we hold is an
## echo, not a warning; a seat for any OTHER token or room is still ignored and still warned about.
func test_the_seat_that_answers_an_idle_probe_is_not_a_warning_but_a_stranger_seat_is() -> void:
	in_round(1)
	var mine: String = Session.token                      # whatever the helper's seat is: that is the seat we hold
	var room: String = Session.room_code
	check(mine != "" and room != "", "a seat is held")
	var m := Log.mark()
	fake.server_send({"t": "seat", "token": mine, "room_code": room, "alias": "Mango", "host": true})
	check(not ("unexpected_seat" in _logged_since(m)), "our own seat echoed back: no warning")
	eq(Session.token, mine, "and nothing changed")
	var m2 := Log.mark()
	fake.server_send({"t": "seat", "token": "someone-else", "room_code": room, "alias": "Fig", "host": false})
	check("unexpected_seat" in _logged_since(m2), "a seat with another token is still warned about")
	eq(Session.token, mine, "and still changes nothing")
	fake.server_send({"t": "seat", "token": mine, "room_code": "WXYZ", "alias": "Mango", "host": true})
	eq(Session.room_code, room, "the right token for another room does not move us")
	Session.token = ""
	var m3 := Log.mark()
	fake.server_send({"t": "seat", "token": "", "room_code": "", "alias": "x", "host": false})
	check("unexpected_seat" in _logged_since(m3), "with no seat held, an empty-token seat is not an echo of anything")


## Stranger pass #11: 8 s after a refused code the log said `ack_timeout ... lost code=-1`: a refused join must not leave a
## wait running that later tears the connection down. Every refusal shape, then well past the ack deadline.
func test_a_refused_join_leaves_no_wait_that_kills_the_line_later() -> void:
	for pair in [["room_gone", "x"], ["room_full", "x"], ["room_started", "x"], ["refused", "There's no room with that code."],
			["refused", "anything else"], ["bad_request", "x"]]:
		setup()
		go_online()
		eq(Session.begin("join_room", {"code": "ZZZZ"}), "", "the join goes out: %s" % [pair])
		fake.server_send({"t": "error", "code": pair[0], "message": pair[1]})
		var opened_before := fake.open_urls.size()
		clock.advance(Net.ACK_TIMEOUT_MS + 3000)
		Net.tick()
		eq(Net.state, "online", "still on the line 11 s after a refusal: %s" % [pair])
		eq(fake.open_urls.size(), opened_before, "no reconnect was triggered: %s" % [pair])
		eq(Session.begin("join_room", {"code": "ABCD"}), "", "and the next try goes out: %s" % [pair])


## A refused RESUME with room_gone is still the end of that seat (the camp is gone, the seat with it), and it must not be
## mistaken for a join refusal just because both use the same code.
func test_a_resume_that_hears_room_gone_still_ends_the_seat() -> void:
	setup()
	store.data = {"token": "old-seat", "room_code": "ABCD", "alias": "Mango", "server_url": Session.server_url}
	Session.load_store()
	go_online()
	Session.resume_if_stored()
	fake.server_send({"t": "error", "code": "room_gone", "message": "x"})
	eq(Session.token, "", "the seat is forgotten when RESUME hears room_gone")
	eq(notices.back().kind, "terminal", "and the player is told it is over")


## A mistyped join code, then a good one: the second attempt must not be swallowed by the first one's leftovers.
func test_after_a_refused_typed_join_the_next_join_goes_out() -> void:
	setup()
	go_online()
	Session.begin("join_room", {"code": "WXYZ"})
	fake.server_send({"t": "error", "code": "room_gone", "message": "x"})
	eq(Session.begin("join_room", {"code": "ABCD"}), "", "second join accepted")
	eq(fake.count("join_room"), 2, "both joins went out, each once")


## The owner's PC kept showing the retired localhost default because earlier builds SAVED it to disk and a saved address
## beats the default. A saved copy of the retired default is not a choice and must give way; a typed address must not.
func test_a_saved_retired_default_gives_way_but_a_typed_address_survives() -> void:
	var fresh_default: String = Session.server_url
	for kept in ["wss://my-own-box.example.net:9000", "ws://127.0.0.1:9999", "ws://localhost:8765", "ws://127.0.0.1:8765/x"]:
		store.data = {"token": "t", "room_code": "ABCD", "alias": "Mango", "server_url": kept}
		Session.server_url = fresh_default
		Session.load_store()
		eq(Session.server_url, kept, "an address the player chose is kept: %s" % kept)
	for retired in ["ws://127.0.0.1:8765", "  ws://127.0.0.1:8765  "]:
		store.data = {"token": "t", "room_code": "ABCD", "alias": "Mango", "server_url": retired}
		Session.server_url = fresh_default
		Session.load_store()
		eq(Session.server_url, fresh_default, "the retired default is replaced: '%s'" % retired)
		eq(Session.token, "t", "and the seat is untouched")
	store.data = {"server_url": ""}
	Session.server_url = fresh_default
	Session.load_store()
	eq(Session.server_url, fresh_default, "an empty saved address keeps the default")


## A fresh install must point at the real arena server on every platform: the old default was localhost (nothing there on a
## player's PC, so the first tap on Create showed "can't reach the server") and empty on Android.
func test_the_default_address_is_the_real_server_and_valid() -> void:
	var fresh: Node = load("res://autoload/session.gd").new()
	check(Session.valid_url(fresh.server_url), "valid: '%s'" % fresh.server_url)
	check(fresh.server_url.begins_with("wss://"), "TLS, not plain ws: '%s'" % fresh.server_url)
	check(not ("127.0.0.1" in fresh.server_url or "localhost" in fresh.server_url), "not a loopback address")
	fresh.free()


# ---- N17: the stale view after a reconnect ----

func test_n17_the_picker_stays_shut_until_the_fresh_view_arrives() -> void:
	in_round(2)
	fake.server_close(1006)
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(Net.state, "online", "connected again")
	check(Session.awaiting_view, "waiting for the fresh view")
	check(not Session.picker_open(), "the stale picker is not live")
	check(not Session.timer_known(), "the timer is unknown")
	fake.server_send({"t": "seat", "token": "tok-secret-1", "room_code": "ABCD", "alias": "Mango", "host": true})
	fake.server_send(round_view(2, false, 100))
	check(not Session.awaiting_view, "fresh view arrived")
	check(Session.picker_open(), "picker live again")


# ---- N28 (found by the live two-human game): the first word on a new connection is `resume` ----

func test_n28_nothing_but_resume_goes_out_first_after_a_reconnect() -> void:
	in_round(2)
	# a screen that reacts to every model by picking, the way the live test does
	var cb := func(kind, m):
		if kind == "round" and m.lock.picker_open:
			Intents.pick("scavenge")
	Feed.model_changed.connect(cb)
	fake.server_close(1006)
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	var n := fake.sent.size()
	fake.server_send({"t": "hello_ok", "proto": 1})
	var after: Array = fake.types().slice(n)
	Feed.model_changed.disconnect(cb)
	eq(after[0], "resume", "resume is the first intent on the new connection")
	check(not ("pick" in after), "no move went out ahead of it: %s" % [after])


func test_n28_intents_are_refused_while_the_held_view_is_stale() -> void:
	in_round(2)
	fake.server_close(1006)
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	var before := fake.sent.size()
	eq(Session.act("lock"), "awaiting_view", "lock refused")
	eq(Session.pick("steal", "Fig"), "awaiting_view", "pick refused")
	eq(Session.act("continue"), "awaiting_view", "continue refused")
	eq(fake.sent.size(), before, "nothing reached the wire")
	fake.server_send({"t": "seat", "token": "tok-secret-1", "room_code": "ABCD", "alias": "Mango", "host": true})
	fake.server_send(round_view(2, false, 100))
	eq(Session.act("lock"), "", "after the fresh view it works again")


# ---- N18: the app goes to the background and comes back ----

func test_n18_coming_back_from_the_background_resumes_and_distrusts_the_timer() -> void:
	in_round(2)
	Session.notification(Node.NOTIFICATION_APPLICATION_RESUMED)
	eq(Net.state, "reconnecting", "the socket is replaced")
	check(not Session.timer_known(), "the timer is unknown")
	check(not Session.picker_open(), "the picker is shut")
	Net.tick()
	eq(fake.open_urls.size(), 2, "reopened at once")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.last("resume").get("token"), "tok-secret-1", "resumed with the seat")


func test_n18_the_back_gesture_is_a_signal_not_a_quit() -> void:
	var seen := [0]
	var cb := func(): seen[0] += 1
	Session.back_requested.connect(cb)
	Session.notification(Node.NOTIFICATION_WM_GO_BACK_REQUEST)
	Session.back_requested.disconnect(cb)
	eq(seen[0], 1, "screens are told")
	check(not get_tree().quit_on_go_back, "the engine will not quit by itself")


# ---- N04: refusing a resume is not losing the seat ----

func test_n04_a_rate_limited_resume_keeps_the_seat_and_retries() -> void:
	Session.token = "tok"
	Session.room_code = "ABCD"
	Session.resume_if_stored()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "error", "code": "refused", "message": "Too many reconnects; wait a minute."})
	eq(Session.token, "tok", "seat kept")
	eq(Net.state, "reconnecting", "will try again")


func test_n04_a_server_error_on_resume_keeps_the_seat() -> void:
	Session.token = "tok"
	Session.room_code = "ABCD"
	Session.resume_if_stored()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "error", "code": "server_error", "message": "Something went wrong on the server."})
	eq(Session.token, "tok", "seat kept")


func test_n04_seat_gone_codes_still_forget_the_seat() -> void:
	for code in ["seat_gone", "room_gone", "bad_token"]:
		setup()
		Session.token = "tok"
		Session.resume_if_stored()
		fake.server_open()
		fake.server_send({"t": "hello_ok", "proto": 1})
		fake.server_send({"t": "error", "code": code, "message": "x"})
		eq(Session.token, "", code + " forgets the seat")


# ---- N03: frame shapes ----

func _bad_shapes() -> Array:
	var rv := {"t": "reveal", "round": 1, "news": [], "private": [], "radio": [], "board": null, "seconds_left": 20}
	var out: Array = []
	for f in [
		func(v): v.news = [null], func(v): v.news = ["x"], func(v): v.news = [{}],
		func(v): v.news = [{"code": 5}], func(v): v.news = [{"code": "a", "args": [1]}],
		func(v): v.private = [{"args": {}}], func(v): v.radio = [null], func(v): v.board = [null],
		func(v): v.board = "nope", func(v): v.board = [{"band": "x"}], func(v): v.news = "x"]:
		var v := rv.duplicate(true)
		f.call(v)
		out.append(v)
	for f in [
		func(v): v.legal.steal = null, func(v): v.legal = {"steal": [1]}, func(v): v.radio_phrases = [null],
		func(v): v.radio_phrases = [{"key": "a"}], func(v): v.aliases = [1, null], func(v): v.my_pick = {},
		func(v): v.me.goal = "text", func(v): v.me.goal_progress = [], func(v): v.gift_amounts = ["a"],
		func(v): v.me = "x", func(v): v.legal = [], func(v): v.me.erase("alias")]:
		var v := round_view(1)
		f.call(v)
		out.append(v)
	for f in [
		func(v): v.results = [null], func(v): v.results = [{"alias": "a"}], func(v): v.winners = "x",
		func(v): v.extracted = [1]]:
		var v := {"t": "end", "extracted": [], "winners": [], "results": []}
		f.call(v)
		out.append(v)
	return out


func test_n03_every_malformed_shape_is_rejected_by_the_validator() -> void:
	var n := 0
	for v in _bad_shapes():
		n += 1
		check(Session.ruleset.validate(v) != "", "accepted a bad %s: %s" % [v.t, JSON.stringify(v).left(120)])
	check(n >= 27, "enough shapes: %d" % n)


func test_n03_a_malformed_frame_never_reaches_the_adapter_or_changes_the_screen() -> void:
	in_round(2)
	var mark2 := Log.mark()
	for v in _bad_shapes():
		fake.server_send(v)
	eq(Session.view.round, 2, "still round 2")
	eq(Session.screen, "round", "still the round screen")
	eq(Log.since(mark2, "ERROR").size(), 0, "no engine error: nothing indexed into a bad shape")


func test_n03_odd_but_valid_shapes_do_not_crash_the_model_builders() -> void:
	var v := round_view(1)
	v.me.goal = null
	v.me.goal_progress = null
	v.me.erase("guarded")
	v.my_pick = {"kind": "steal"}
	v.erase("board")
	var m := A.round_model(v)
	eq(m.goal.key, "goal.unknown", "no goal is neutral")
	eq(m.my_pick.target, null, "pick without a target")
	var e := {"t": "end", "extracted": [], "winners": [], "results": [{"alias": "A", "score": 1, "rations": 1,
		"seat": false, "goal_done": false, "stole": 0, "times_robbed": 0, "gave_away": 0}]}
	eq(A.end_model(e, "A").rows[0].goal.key, "goal.unknown", "a result without a goal")
	no_errors()


# ---- N19: plurals and nulls ----

func test_n19_a_single_ration_is_not_plural() -> void:
	Words.use(load("res://themes/placeholder/words.po"))
	var one := A.line("now_have", {"rations": 1})
	var many := A.line("now_have", {"rations": 3})
	eq(Words.render(one.key, one.slots), "You now have 1 ration.", "singular")
	eq(Words.render(many.key, many.slots), "You now have 3 rations.", "plural")


func test_n19_a_missing_value_renders_as_nothing_not_null() -> void:
	Words.use(load("res://themes/placeholder/words.po"))
	var ln := A.line("gave", {"receiver": null, "amount": null})
	var text := Words.render(ln.key, ln.slots)
	check(not ("null" in text.to_lower()) and not ("<" in text), "no 'null' in: " + text)


# ---- N15: the log file ----

func test_n15_a_release_build_ignores_the_log_flag() -> void:
	var args := PackedStringArray(["--log=C:/somewhere/else.log"])
	eq(Log.path_from(args, false, "user://client.log"), "user://client.log", "release: default path")
	eq(Log.path_from(args, true, "user://client.log"), "C:/somewhere/else.log", "debug: honoured")
	eq(Log.path_from(PackedStringArray(), true, "user://client.log"), "user://client.log", "no flag: default")


func test_n15_import_and_export_runs_do_not_touch_the_log() -> void:
	check(Log.is_tooling(PackedStringArray(["--headless", "--path", "x", "--import"])), "import")
	check(Log.is_tooling(PackedStringArray(["--export-pack", "Windows", "a.pck"])), "export")
	check(Log.is_tooling(PackedStringArray(["--editor"])), "editor")
	check(not Log.is_tooling(PackedStringArray(["--headless", "--path", "x", "res://tests/runner.tscn"])), "a normal run")


func test_n15_the_previous_run_is_kept_as_dot_one() -> void:
	var p := "user://rotate_probe.log"
	var f := FileAccess.open(p, FileAccess.WRITE)
	f.store_string("last run")
	f.close()
	Log.rotate_file(p)
	eq(FileAccess.get_file_as_string(p + ".1"), "last run", "kept")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(p))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(p + ".1"))
	Log.rotate_file(p)                                 # nothing to rotate: harmless
	check(not FileAccess.file_exists(p + ".1"), "no phantom copy")


# ---- N20 N21: the log ----

func test_n21_a_value_cannot_forge_a_second_log_line() -> void:
	Log.event("t", "forge", {"v": "a\nINFO [fake] injected=1", "q": 'say "hi"'})
	var last: String = Log.lines.back()
	check(not ("\n" in last), "single line")
	check("\\n" in last, "newline escaped")
	check('\\"hi\\"' in last, "quotes escaped")


func test_n20_log_timestamps_never_go_backwards() -> void:
	var stamps: Array[String] = []
	for i in 6:
		Log.event("t", "tick", {"i": i})
		stamps.append(Log.lines.back().substr(0, 23))
	var sorted := stamps.duplicate()
	sorted.sort()
	eq(stamps, sorted, "timestamps are in order")
	check(stamps[0].substr(19, 1) == "." and stamps[0].substr(20, 3).is_valid_int(), "has a millisecond field")


func test_n21_the_unknown_value_log_is_capped() -> void:
	A.forget_unknowns()
	var m2 := Log.mark()
	for i in 300:
		A.band_id("band%d" % i)
	var warns := Log.since(m2, "WARN").size()
	check(warns <= A.UNKNOWN_LOG_CAP + 1, "a hostile server cannot flood the log: %d lines" % warns)
