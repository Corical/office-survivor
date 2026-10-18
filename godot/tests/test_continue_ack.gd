extends BaseTest
## Stranger pass 2, finding N3: tap Continue early in a 20 s reveal and the server says nothing until the reveal ends. The
## client used to wait 8 s for an answer, decide the line was dead, drop it and show a red "Signal lost" banner on a healthy
## connection (nights 6, 8, 10). The wait for `continue` must last as long as the reveal can, and still end.

const MARGIN := Session.CONTINUE_ACK_MARGIN_MS


func _reveal(seconds_left: Variant = 20) -> Dictionary:
	return {"t": "reveal", "round": 1, "news": [], "private": [], "radio": [], "board": null, "seconds_left": seconds_left}


func _in_reveal(seconds_left: Variant = 20) -> void:
	in_round(1)
	fake.server_send(_reveal(seconds_left))


func test_a_healthy_line_is_not_dropped_while_the_reveal_runs_out() -> void:
	_in_reveal(20)
	clock.advance(6000)                                   # the player taps Continue 6 s in
	eq(Session.act("continue"), "", "sent")
	var opened := fake.open_urls.size()
	clock.advance(8000 + 3000)                            # past the old 8 s deadline
	Net.tick()
	eq(Net.state, "online", "still online 11 s after the tap: the server is waiting for the others, not dead")
	eq(fake.open_urls.size(), opened, "no reconnect was started")
	clock.advance(8000)                                   # 19 s after the tap, 25 s into the reveal
	Net.tick()
	eq(Net.state, "online", "still online when the reveal itself has run out")


func test_a_server_that_never_answers_is_still_given_up_on() -> void:
	_in_reveal(20)
	Session.act("continue")
	clock.advance(20000 + MARGIN + 2000)                  # the whole reveal plus the margin, and nothing came
	Net.tick()
	check(Net.state != "online" or fake.open_urls.size() > 1, "the safety net still catches a dead line: state %s" % Net.state)


func test_other_intents_keep_the_short_deadline() -> void:
	in_round(1)
	Session.pick("scavenge", null)
	Session.act("lock")
	clock.advance(Net.ACK_TIMEOUT_MS + 1000)
	Net.tick()
	check(Net.state != "online" or fake.open_urls.size() > 1, "an unanswered lock is still a dead line after 8 s")


func test_a_hostile_countdown_cannot_buy_an_unbounded_wait() -> void:
	for secs in [1.0e12, -5, 0, 9999999]:
		setup()
		in_round(1)
		fake.server_send(_reveal(secs))
		var why := Session.act("continue")
		if why != "":
			continue                                      # (a reveal the schema refused is not a reveal)
		clock.advance(Session.CONTINUE_ACK_MAX_MS + 1000)
		Net.tick()
		check(Net.state != "online" or fake.open_urls.size() > 1, "the wait is capped for seconds_left=%s" % [secs])


func test_tapping_continue_again_does_not_stretch_the_wait() -> void:
	_in_reveal(20)
	Session.act("continue")
	clock.advance(5000)
	eq(Session.act("continue"), "in_flight", "a second tap is ignored")
	clock.advance(20000 + MARGIN)                         # measured from the FIRST tap
	Net.tick()
	check(Net.state != "online" or fake.open_urls.size() > 1, "the deadline belongs to the first tap")


func test_the_next_round_ends_the_wait_cleanly() -> void:
	_in_reveal(20)
	Session.act("continue")
	fake.server_send(round_view(2))
	clock.advance(60000)
	Net.tick()
	eq(Net.state, "online", "answered by the next round: nothing is still waiting")
