extends BaseTest
## The reveal timeline: pure, driven by advance(ms). Written for the failure modes the server actually has: the same
## reveal pushed again and again, a later round arriving mid-animation, a resume with nothing to animate from.


func _beats(n: int) -> Array:
	var out: Array = []
	for i in n:
		out.append({"kind": "move_resource", "style": "", "from": "A", "to": "B", "amount_out": 1, "amount_in": 1,
			"detail": "", "line_index": i})
	return out


func _model(rnd: int, n: int, has_before := true) -> Dictionary:
	return {"round": rnd, "beats": _beats(n), "has_before_state": has_before}


func test_plays_beats_in_order_and_finishes() -> void:
	var t := Timeline.new(1, _beats(3))
	eq(t.current().line_index, 0, "first")
	t.advance(Timeline.DEFAULT_MS)
	eq(t.current().line_index, 1, "second")
	t.advance(Timeline.DEFAULT_MS * 2)
	check(t.finished, "finished after the last")
	eq(t.current(), {}, "nothing current once finished")


func test_a_huge_time_step_does_not_skip_or_loop_forever() -> void:
	var t := Timeline.new(1, _beats(5))
	t.advance(1.0e9)
	check(t.finished, "finished")
	eq(t.index, 5, "index parked at the end")
	t.advance(100)
	check(t.finished, "advancing a finished timeline is harmless")


func test_zero_and_negative_steps_do_nothing_harmful() -> void:
	var t := Timeline.new(1, _beats(2))
	t.advance(0)
	eq(t.index, 0, "zero step")
	t.advance(-500)
	check(t.index == 0 and not t.finished, "a negative step never rewinds or finishes")


func test_skip_goes_to_the_next_beat_and_past_the_last() -> void:
	var t := Timeline.new(1, _beats(2))
	t.skip()
	eq(t.current().line_index, 1, "skipped to the second")
	t.skip()
	check(t.finished, "skipping the last finishes")
	t.skip()
	check(t.finished, "skipping a finished timeline is harmless")


func test_empty_beats_are_born_finished() -> void:
	check(Timeline.new(1, []).finished, "nothing to play")


func test_snap_starts_finished_with_the_end_state() -> void:
	var t := Timeline.new(1, _beats(4), true)
	check(t.finished, "snapped")
	eq(t.beat_progress(), 1.0, "progress at the end")


func test_total_beats_are_short_and_quiet_beats_are_not() -> void:
	check(Timeline.duration_ms({"kind": "total"}) < Timeline.duration_ms({"kind": "move_resource"}), "total is brief")
	check(Timeline.duration_ms({"kind": "quiet"}) > 0, "quiet has a length")


func test_the_same_reveal_pushed_again_never_restarts() -> void:
	var p := TimelinePlayer.new()
	var t1 := p.offer(_model(3, 4))
	t1.advance(Timeline.DEFAULT_MS * 2)
	var t2 := p.offer(_model(3, 4))
	check(t1 == t2, "the same timeline object")
	eq(t2.index, 2, "progress kept")
	for i in 30:                                      # 30 pushes in one game, as the real server did
		p.offer(_model(3, 4))
	eq(p.timeline.index, 2, "still at beat 2 after 30 pushes")


func test_a_new_round_starts_a_new_timeline() -> void:
	var p := TimelinePlayer.new()
	var t1 := p.offer(_model(3, 4))
	t1.advance(Timeline.DEFAULT_MS)
	var t2 := p.offer(_model(4, 2))
	check(t1 != t2, "new object")
	eq(t2.round, 4, "round 4")
	eq(t2.index, 0, "from the start")


func test_no_before_state_means_snap_not_invention() -> void:
	var p := TimelinePlayer.new()
	check(p.offer(_model(5, 6, false)).finished, "resumed mid-reveal: show the end, animate nothing")


func test_a_later_round_arriving_mid_animation_finishes_it_at_once() -> void:
	var p := TimelinePlayer.new()
	var t := p.offer(_model(3, 5))
	t.advance(Timeline.DEFAULT_MS)
	p.later_round_arrived(3)
	check(not t.finished, "the same round does not snap")
	p.later_round_arrived(2)
	check(not t.finished, "an older round does not snap")
	p.later_round_arrived(4)
	check(t.finished, "round 4 arrives: snap")


func test_a_late_reveal_for_an_old_round_does_not_replace_a_newer_timeline() -> void:
	var p := TimelinePlayer.new()
	var t4 := p.offer(_model(4, 2))
	t4.advance(Timeline.DEFAULT_MS)
	var t := p.offer(_model(3, 2))
	check(t == t4, "round 3 arriving after round 4 changes nothing")
	eq(t.round, 4, "still round 4")
	eq(t.index, 1, "progress kept")
