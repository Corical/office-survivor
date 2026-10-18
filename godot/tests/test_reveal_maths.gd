extends BaseTest
## What the reveal animates must add up, point the right way, and not leak seat order. Each test names the mutant of
## the second review that it exists to kill.

const A = preload("res://rulesets/survivors/adapter.gd")


func _reveal(news: Array, priv: Array, rnd := 1) -> Dictionary:
	return {"t": "reveal", "round": rnd, "news": news, "private": priv, "radio": [], "board": null, "seconds_left": 20}


func _l(code: String, args := {}) -> Dictionary:
	return {"code": code, "args": args}


func _before(rations: int, others := ["Bo", "Cy"]) -> Dictionary:
	return {"t": "round", "round": 1, "aliases": others, "me": {"alias": "Me", "rations": rations}, "board": null}


func _only(beats: Array, kind: String) -> Array:
	return beats.filter(func(b): return b.kind == kind)


# ---- conservation: the animation always ends on the true total ----

func test_every_real_night_ends_on_the_true_total() -> void:
	var n := 0
	var with_residual := 0
	for r in Fixtures.of_type("reveal"):
		if r.before.is_empty():
			continue
		var m := A.reveal_model(r.msg, r.me, r.before)
		if m.totals.before == null or m.totals.after == null:
			continue
		n += 1
		eq(m.totals.before, int(r.before.me.rations), "before total is the round view's")
		eq(A.net_for_me(m.beats), int(m.totals.after) - int(m.totals.before),
			"beats must add up to the night's change (round %s, game %s)" % [r.msg.round, r.game])
		if m.totals.residual != 0:
			with_residual += 1
	check(n > 25, "enough real nights checked: %d" % n)
	check(with_residual > 0, "the residual path was exercised by real data (events / guard income)")


func test_a_missing_amount_is_made_up_by_a_residual_beat() -> void:
	# +1 scavenged, but I ended 2 higher: an event or guard income carried no amount
	var m := A.reveal_model(_reveal([], [_l("scavenged", {"found": 1}), _l("now_have", {"rations": 9})]), "Me", _before(6))
	eq(m.totals.residual, 2, "residual")
	var res = m.beats.filter(func(b): return b.style == "other")
	eq(res.size(), 1, "one residual beat")
	eq(res[0].to, A.ME, "arrives at me")
	eq(res[0].amount_in, 2, "amount")
	eq(m.beats.back().kind, "total", "the total beat is still last")
	eq(A.net_for_me(m.beats), 3, "6 -> 9")


func test_a_negative_residual_leaves_me() -> void:
	var m := A.reveal_model(_reveal([], [_l("now_have", {"rations": 4})]), "Me", _before(6))
	eq(m.totals.residual, -2, "residual")
	var res = m.beats.filter(func(b): return b.style == "other")
	eq(res[0].from, A.ME, "leaves me")
	eq(res[0].amount_out, 2, "amount")


func test_no_residual_when_the_lines_already_add_up() -> void:
	var m := A.reveal_model(_reveal([], [_l("scavenged", {"found": 2}), _l("ate", {"amount": 1}),
		_l("now_have", {"rations": 7})]), "Me", _before(6))
	eq(m.totals.residual, 0, "exact")
	eq(m.beats.filter(func(b): return b.style == "other").size(), 0, "no invented beat")


func test_no_total_line_means_no_residual_not_a_guess() -> void:
	var m := A.reveal_model(_reveal([], [_l("scavenged", {"found": 1})]), "Me", _before(6))
	eq(m.totals.after, null, "after unknown")
	eq(m.totals.residual, 0, "nothing invented")


func test_an_unknown_before_state_means_no_residual() -> void:
	var m := A.reveal_model(_reveal([], [_l("scavenged", {"found": 1}), _l("now_have", {"rations": 9})]), "Me", {})
	eq(m.totals.residual, 0, "no before state: nothing to compare with")
	eq(m.totals.before, null, "before unknown")


# ---- direction and size of each kind of beat (mutants M11 M12 M15 M16) ----

func test_ate_leaves_me() -> void:
	var b = A.beats_for("ate", {"amount": 1})[0]
	eq([b.from, b.to, b.amount_out], [A.ME, A.OFFSTAGE, 1], "M11: eating takes food away")


func test_a_gift_I_receive_is_worth_the_total_not_the_amount() -> void:
	var b = A.beats_for("got_gift_bonus", {"giver": "Bo", "amount": 1, "total": 2})[0]
	eq([b.from, b.to, b.amount_out, b.amount_in], ["Bo", A.ME, 1, 2], "M12: gifts grow")


func test_a_gift_I_give_leaves_me_for_the_receiver() -> void:
	var b = A.beats_for("gave", {"receiver": "Bo", "amount": 2})[0]
	eq([b.from, b.to, b.amount_out], [A.ME, "Bo", 2], "gift out")


func test_being_exposed_pays_the_investigator_and_returns_the_loot_to_the_victim() -> void:
	var bs := A.beats_for("exposed_me_back", {"victim": "Bo", "paid": 1, "back": 2})
	var pay = bs.filter(func(b): return b.style == "bounty")[0]
	var back = bs.filter(func(b): return b.style == "return")[0]
	eq([pay.from, pay.to, pay.amount_out], [A.ME, A.OFFSTAGE, 1], "bounty goes to the unnamed investigator")
	eq([back.from, back.to, back.amount_out], [A.ME, "Bo", 2], "M16: the loot goes back to the victim")


func test_a_steal_I_got_caught_at_pays_the_guard() -> void:
	var bs := A.beats_for("steal_caught", {"target": "Bo", "paid": 2})
	var fine = bs.filter(func(b): return b.kind == "move_resource")[0]
	eq([fine.from, fine.to, fine.amount_out], [A.ME, "Bo", 2], "M15: I pay, the guard receives")


func test_a_thief_my_guard_caught_pays_me() -> void:
	var bs := A.beats_for("caught_thief_paid", {"thief": "Bo", "got": 2})
	var fine = bs.filter(func(b): return b.kind == "move_resource")[0]
	eq([fine.from, fine.to, fine.amount_out], ["Bo", A.ME, 2], "guard income from the thief")


func test_every_emitted_beat_kind_is_a_known_kind() -> void:
	for code in A.line_codes():
		for b in A.beats_for(code, {}):
			check(b.kind in A.BEAT_KINDS, "%s emits an unlisted kind '%s'" % [code, b.kind])
	for b in A.beats_for("not_a_code", {}):
		check(b.kind in A.BEAT_KINDS, "unknown code beat kind")


# ---- coverage arms (mutants M02 M04) ----

func test_my_own_idol_news_is_covered_by_my_private_line() -> void:
	var m := A.reveal_model(_reveal([_l("news_idol", {"player": "Me"})], [_l("idol_saved")]), "Me", {})
	eq(_only(m.beats, "blocked").size(), 1, "M02: one block, not two")


func test_someone_elses_idol_news_is_drawn() -> void:
	var m := A.reveal_model(_reveal([_l("news_idol", {"player": "Bo"})], []), "Me", {})
	eq(_only(m.beats, "blocked").size(), 1, "Bo's idol is shown")


func test_my_own_rejoin_news_is_covered() -> void:
	var m := A.reveal_model(_reveal([_l("news_rejoined", {"player": "Me"})], [_l("rejoined_me")]), "Me", {})
	eq(_only(m.beats, "status").size(), 1, "M02: one status change")


func test_a_catch_where_I_am_the_guard_is_covered_by_my_private_line() -> void:
	var m := A.reveal_model(_reveal([_l("news_caught", {"target": "Me", "thief": "Bo", "paid": 2})],
		[_l("caught_thief_paid", {"thief": "Bo", "got": 2})]), "Me", {})
	var to_me = m.beats.filter(func(b): return b.kind == "move_resource" and b.to == A.ME)
	eq(to_me.size(), 1, "M04: I am paid once, not twice")


func test_an_exposure_where_I_am_the_victim_is_covered() -> void:
	var m := A.reveal_model(_reveal([_l("news_exposed", {"thief": "Bo", "victim": "Me", "paid": 1})],
		[_l("thief_exposed_for_me", {"thief": "Bo", "back": 2})]), "Me", {})
	eq(_only(m.beats, "marked").size(), 1, "Bo is marked once")


# ---- who am I (N26) ----

func test_an_unknown_me_never_matches_a_missing_argument() -> void:
	var m := A.reveal_model(_reveal([_l("news_hit_1", {}), _l("news_caught", {}), _l("news_bandit", {})], []), "", {})
	check(m.lines.all(func(l): return not l.covered), "nothing is covered when I do not know who I am")


func test_me_falls_back_to_the_round_views_alias() -> void:
	var m := A.reveal_model(_reveal([_l("news_bandit", {"player": "Me"})], [_l("became_bandit_me")]), "", _before(3))
	eq(_only(m.beats, "status").size(), 1, "covered through the before-state's alias")


# ---- privacy: public lines carry no seat order (N14) ----

func test_public_lines_come_out_in_the_same_order_whatever_order_they_arrive() -> void:
	var lines := [_l("news_bandit", {"player": "Zed"}), _l("news_bandit", {"player": "Amy"}),
		_l("news_caught", {"target": "Kit", "thief": "Bo", "paid": 2}), _l("news_hit_1", {"victim": "Mia", "total": 2}),
		_l("news_caught", {"target": "Ann", "thief": "Cy", "paid": 1})]
	var forward := A.reveal_model(_reveal(lines, []), "Me", {})
	var reversed_in := lines.duplicate()
	reversed_in.reverse()
	var backward := A.reveal_model(_reveal(reversed_in, []), "Me", {})
	var shuffled_in := [lines[3], lines[0], lines[4], lines[2], lines[1]]
	var shuffled := A.reveal_model(_reveal(shuffled_in, []), "Me", {})
	eq(JSON.stringify(forward.lines), JSON.stringify(backward.lines), "reversed input, same output")
	eq(JSON.stringify(forward.lines), JSON.stringify(shuffled.lines), "shuffled input, same output")
	eq(JSON.stringify(forward.beats), JSON.stringify(shuffled.beats), "the beats too")


func test_my_private_lines_keep_their_night_order() -> void:
	var priv := [_l("scavenged", {"found": 1}), _l("ate", {"amount": 1}), _l("now_have", {"rations": 3})]
	var m := A.reveal_model(_reveal([], priv), "Me", {})
	var codes = m.lines.filter(func(l): return l.source == "private").map(func(l): return l.code)
	eq(codes, ["scavenged", "ate", "now_have"], "private lines are in the order they happened to me")


func test_anonymous_news_never_names_the_actor_in_its_beats() -> void:
	# the thief behind a hit, the investigator behind an exposure, the intruder in a break-in: all anonymous
	for r in Fixtures.of_type("reveal"):
		var m := A.reveal_model(r.msg, r.me, r.before)
		for ln_i in m.lines.size():
			var ln: Dictionary = m.lines[ln_i]
			if ln.code in ["news_hit_1", "news_hit_n"]:
				for b in m.beats.filter(func(x): return x.line_index == ln_i):
					eq(b.to, A.OFFSTAGE, "a hit goes to nobody in particular")
			if ln.code == "news_break_in_empty":
				for b in m.beats.filter(func(x): return x.line_index == ln_i):
					eq(b.from, A.OFFSTAGE, "the intruder is unnamed")


func test_the_round_model_exposes_only_a_count_of_who_locked() -> void:
	var m := A.round_model(round_view(1, false, 100, 2))
	eq(m.locked_count, 2, "a count")
	for k in m.keys():
		check(not ("locked_by" in str(k) or "who" in str(k)), "no list of lockers: " + str(k))
