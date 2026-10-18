extends BaseTest
## Feed and Intents: the only door between the server's state and a screen. Screens will see these models and nothing
## else, so everything they need must be in them (review N01, N02).

var _models: Array = []
var _notices: Array = []
var _statuses: Array = []
var _wired := false


func setup() -> void:
	super.setup()
	_models.clear()
	_notices.clear()
	_statuses.clear()
	if not _wired:
		_wired = true
		Feed.model_changed.connect(func(kind, _m): _models.append(kind))
		Feed.notice_raised.connect(func(n): _notices.append(n))
		Feed.status_changed.connect(func(s): _statuses.append(s))


func _reveal_view(rnd: int) -> Dictionary:
	return {"t": "reveal", "round": rnd, "news": [], "private": [{"code": "scavenged", "args": {"found": 1}},
		{"code": "now_have", "args": {"rations": 8}}], "radio": [], "board": null, "seconds_left": 20}


func test_a_round_view_becomes_a_complete_round_model() -> void:
	in_round(3)
	check(Feed.models.has("round"), "model exists")
	var m: Dictionary = Feed.models.round
	eq(m.round, 3, "round")
	check(m.has("pickers") and m.has("roster") and m.has("goal") and m.has("radio"), "the pieces a round screen needs")
	check(m.timer.has("total_s") and m.timer.has("deadline_msec") and m.timer.has("known"), "a ring has what it needs")
	eq(m.lock.state, "open", "lock state")
	eq(m.lock.picker_open, true, "picker open")
	check("round" in _models, "model_changed was emitted")


func test_the_timer_base_is_the_first_value_of_the_round_not_the_latest() -> void:
	in_round(1)
	eq(Feed.models.round.timer.total_s, 180.0, "first sight of round 1")
	fake.server_send(round_view(1, false, 150, 1))
	eq(Feed.models.round.timer.total_s, 180.0, "still 180 after a later view")
	eq(Feed.models.round.timer.seconds_left, 150.0, "the current value moves")
	fake.server_send(round_view(2, false, 175))
	eq(Feed.models.round.timer.total_s, 175.0, "a new round has its own base")


func test_the_lock_state_follows_an_intent_without_waiting_for_a_view() -> void:
	in_round()
	_models.clear()
	eq(Intents.lock(), "", "lock goes out")
	eq(Feed.models.round.lock.state, "sent", "the model already says sent")
	eq(Feed.models.round.lock.picker_open, false, "and the picker is shut")
	check("round" in _models, "the screen was told")
	eq(Intents.lock(), "in_flight", "a second tap is refused with a reason")


func test_a_picker_move_goes_out_by_the_ids_the_model_carries() -> void:
	in_round()
	var steal: Dictionary = Feed.models.round.pickers.filter(func(p): return p.move_id == "steal")[0]
	eq(Intents.pick(steal.server_id, steal.targets[0]), "", "pick sent")
	eq(fake.last("pick").kind, "steal", "kind")
	eq(fake.last("pick").target, "Fig", "target")


func test_a_gift_carries_its_amount() -> void:
	in_round()
	var gift: Dictionary = Feed.models.round.pickers.filter(func(p): return p.move_id == "gift")[0]
	Intents.pick(gift.server_id, gift.targets[0], gift.amounts[1])
	eq(fake.last("pick").amount, 2, "amount")


func test_pick_after_lock_is_refused_with_a_reason_a_screen_can_show() -> void:
	in_round()
	Intents.lock()
	eq(Intents.pick("scavenge"), "locked_round", "refused")


func test_joining_uppercases_and_trims_the_room_code() -> void:
	Intents.join_room("  abcd ")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	eq(fake.last("join_room").get("code"), "ABCD", "normalised")


func test_a_bad_server_address_comes_back_as_a_reason() -> void:
	Session.server_url = ""
	eq(Intents.create_room(), "no_server_url", "the title screen can say so")


func test_a_reveal_builds_one_timeline_and_pushing_it_again_does_not_restart_it() -> void:
	in_round(2)
	fake.server_send(_reveal_view(2))
	var t1: Timeline = Feed.player.timeline
	check(t1 != null and t1.round == 2, "timeline for round 2")
	t1.advance(Timeline.DEFAULT_MS)
	for i in 10:
		fake.server_send(_reveal_view(2))
	check(Feed.player.timeline == t1, "same timeline object after 10 re-sends")
	check(Feed.models.reveal.has("totals") and Feed.models.reveal.has("timer"), "reveal model complete")


func test_the_reveal_has_a_before_state_when_the_round_view_came_first() -> void:
	in_round(2)
	fake.server_send(_reveal_view(2))
	check(Feed.models.reveal.has_before_state, "before-state found")
	eq(Feed.models.reveal.totals.before, 7, "start total from the round view")
	eq(Feed.models.reveal.totals.after, 8, "end total from the now_have line")


func test_a_resumed_reveal_with_no_before_state_snaps() -> void:
	go_online()
	give_seat()
	fake.server_send(_reveal_view(4))                 # we joined mid-reveal: no round view was ever held
	check(not Feed.models.reveal.has_before_state, "no before-state")
	check(Feed.player.timeline.finished, "snapped to the end, nothing invented")


func test_the_second_game_plays_again_from_round_one() -> void:
	in_round(1)
	fake.server_send(_reveal_view(1))
	Feed.player.timeline.skip()
	Intents.leave()
	Intents.create_room()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	give_seat("tok-2", "WXYZ")
	fake.server_send(round_view(1))
	fake.server_send(_reveal_view(1))
	eq(Feed.player.timeline.round, 1, "a new timeline for the new room's round 1")
	eq(Feed.player.timeline.index, 0, "from the start, not left at the end of the last game's round 1")
	check(not Feed.player.timeline.finished, "playing")


func test_the_end_screen_finishes_any_running_timeline() -> void:
	in_round(10)
	fake.server_send(_reveal_view(10))
	var t: Timeline = Feed.player.timeline
	fake.server_send({"t": "end", "extracted": ["A"], "winners": ["A"], "results": [{"alias": "A", "score": 3,
		"rations": 5, "seat": true, "goal_done": true, "stole": 0, "times_robbed": 0, "gave_away": 0}]})
	check(t.finished, "the reveal does not keep playing under the end screen")
	check(Feed.models.has("end"), "end model")


func test_the_status_follows_the_connection() -> void:
	in_round()
	fake.server_close(1006)
	var s: Dictionary = Feed.status()
	eq(s.net, "reconnecting", "net")
	eq(s.net_key, "ui.net.reconnecting", "a theme key, not a sentence")
	check(not _statuses.is_empty(), "status_changed was emitted")
	var stale: Dictionary = Feed.models.round
	eq(stale.lock.picker_open, false, "the round model shut its picker when the net dropped")
	eq(stale.timer.known, false, "and its timer is unknown")


func test_notices_arrive_with_a_theme_key_and_the_servers_text_as_fallback() -> void:
	in_round()
	fake.server_send({"t": "error", "code": "refused", "message": "Pick a move before you lock in."})
	eq(_notices.back().key, "notice.generic", "an unrecognised refusal uses the generic key")
	eq(_notices.back().text, "Pick a move before you lock in.", "with the server's wording to fill it")
	fake.server_close(4001, "seat_gone")
	eq(_notices.back().key, "notice.seat_gone", "a known terminal reason has its own key")


func test_the_lobby_model() -> void:
	go_online()
	give_seat("t", "ABCD", true)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 2, "seats_total": 4, "host": true})
	eq(Feed.models.lobby, {"room_code": "ABCD", "seats_taken": 2, "seats_total": 4, "is_host": true, "seats": []},
		"lobby model (a lobby frame without a seat list gives an empty one)")
