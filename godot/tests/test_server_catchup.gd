extends BaseTest
## What the server shipped at 11:02: goals and progress as codes, wilderness events with an id and who they hit.

const A = preload("res://rulesets/survivors/adapter.gd")


func setup() -> void:
	super.setup()
	A.forget_unknowns()
	Words.use(load("res://themes/placeholder/words.po"))


func _round_with(goal: Variant, progress: Variant) -> Dictionary:
	var v := round_view(1)
	v.me.goal = goal
	v.me.goal_progress = progress
	return v


func _ev(event: String, scope: String, who := "", line := "A sentence.") -> Dictionary:
	var a := {"line": line, "event": event, "scope": scope}
	if who != "":
		a["who"] = who
	return {"code": "event", "args": a}


func _reveal(news: Array, priv: Array) -> Dictionary:
	return {"t": "reveal", "round": 1, "news": news, "private": priv, "radio": [], "board": null, "seconds_left": 20}


# ---- goals and progress as codes ----

func test_the_goal_card_is_worded_from_the_servers_code_and_values() -> void:
	var v := _round_with(
		{"code": "beat", "target": "Fig", "text": "finish with more rations than Fig",
			"line": {"code": "goal_beat", "args": {"target": "Fig"}}},
		{"state": "end", "text": "x", "line": {"code": "progress_give", "args": {"have": 1, "need": 3}}})
	var g: Dictionary = A.round_model(v).goal
	eq(g.key, "line.goal_beat", "key from the code")
	eq(g.from_code, true, "marked as worded from a code")
	eq(Words.render(g.key, g.slots), "finish with more food than Fig".replace("food", "rations"), "worded by the theme")
	eq(g.progress.key, "line.progress_give", "progress key")
	eq(Words.render(g.progress.key, g.progress.slots), "1/3 given", "progress worded with its values")
	eq(g.state_key, "goal.state.end", "state key")


func test_a_goal_without_a_line_falls_back_to_the_old_key_and_the_english() -> void:
	var g: Dictionary = A.round_model(_round_with(
		{"code": "give", "target": null, "text": "give away 3 rations over the game"},
		{"state": "open", "text": "0/3 given"})).goal
	eq(g.key, "goal.give", "old key")
	eq(g.from_code, false, "not from a code")
	eq(Words.render(g.key, g.slots), "give away 3 rations over the game", "the server's English")
	eq(g.progress.slots.text, "0/3 given", "progress English in the slot")


func test_a_goal_line_the_client_has_no_words_for_degrades_and_is_logged_once() -> void:
	var v := _round_with({"code": "give", "text": "give away 3", "line": {"code": "goal_from_the_future", "args": {}}},
		{"state": "open", "text": "t"})
	var g: Dictionary = A.round_model(v).goal
	eq(g.key, "goal.give", "falls back to the goal id")
	A.round_model(v)
	eq(Log.since(mark, "WARN").filter(func(l): return "goal_from_the_future" in l).size(), 1, "logged once")


func test_a_malformed_goal_line_is_rejected_by_the_validator() -> void:
	var v := _round_with({"code": "give", "line": {"code": 5}}, {"state": "open", "text": "t"})
	check(Session.ruleset.validate(v) != "", "a numeric code is not a line")
	var w := _round_with({"code": "give", "line": "goal_give"}, {"state": "open", "text": "t"})
	check(Session.ruleset.validate(w) != "", "a string is not a line")


func test_a_null_goal_line_is_valid_and_falls_back() -> void:
	var v := _round_with({"code": "give", "text": "give", "line": null}, {"state": "open", "text": "t", "line": null})
	eq(Session.ruleset.validate(v), "", "null line allowed")
	eq(A.round_model(v).goal.key, "goal.give", "fallback")


func test_every_real_round_view_has_a_worded_goal_and_progress() -> void:
	var n := 0
	for r in Fixtures.of_type("round"):
		var m: Dictionary = A.round_model(r.msg)
		n += 1
		check(m.goal.from_code and m.goal.progress.from_code, "the server now sends codes for both")
		check(Words.has(m.goal.key) and Words.has(m.goal.progress.key), "the theme has words for %s / %s" % [m.goal.key, m.goal.progress.key])
		var text := Words.render(m.goal.key, m.goal.slots)
		check(not ("{" in text) and not text.begins_with("["), "goal text complete: " + text)
		var prog := Words.render(m.goal.progress.key, m.goal.progress.slots)
		check(not ("{" in prog) and not prog.begins_with("["), "progress text complete: " + prog)
	check(n > 20, "enough real views: %d" % n)


func test_the_end_screen_goal_uses_the_code_when_present() -> void:
	var e := {"t": "end", "extracted": [], "winners": ["A"], "results": [{"alias": "A", "score": 1, "rations": 1,
		"seat": false, "goal_done": true, "stole": 0, "times_robbed": 0, "gave_away": 0,
		"goal": {"code": "give", "target": null, "text": "give", "line": {"code": "goal_give", "args": {"n": 3}}}}]}
	var row: Dictionary = A.end_model(e, "A").rows[0]
	eq(row.goal.key, "line.goal_give", "from the code")
	eq(Words.render(row.goal.key, row.goal.slots), "give away 3 rations over the game", "worded")


# ---- wilderness events ----

func test_finding_events_bring_food_to_the_player_they_name() -> void:
	for c in [["bananas", 1], ["coconut", 1], ["cache", 2]]:
		var b: Dictionary = A.beats_for("event", _ev(c[0], "player", "Bo").args)[0]
		eq([b.kind, b.from, b.to, b.amount_in, b.style], ["move_resource", A.OFFSTAGE, "Bo", c[1], c[0]], c[0])


func test_losing_events_take_food_from_the_player_they_name() -> void:
	for c in [["snake", 1], ["rain", 1], ["raid", 2]]:
		var b: Dictionary = A.beats_for("event", _ev(c[0], "player", "Bo").args)[0]
		eq([b.kind, b.from, b.to, b.amount_out, b.style], ["move_resource", "Bo", A.OFFSTAGE, c[1], c[0]], c[0])


func test_a_shelter_collapse_drops_that_players_shield() -> void:
	var b: Dictionary = A.beats_for("event", _ev("shelter", "player", "Bo").args)[0]
	eq([b.kind, b.from, b.to], ["shield_off", "Bo", "Bo"], "shield off")


func test_camp_wide_events_are_camp_beats_with_the_event_as_style() -> void:
	for ev in ["storm", "feast", "rats", "rats_top"]:
		var b: Dictionary = A.beats_for("event", _ev(ev, "camp").args)[0]
		eq([b.kind, b.style], ["camp", ev], ev)


func test_a_camp_event_that_took_from_me_appears_in_my_private_lines_and_costs_me_food() -> void:
	var priv := A.line("event", _ev("rats_top", "camp").args, "private")
	var news := A.line("event", _ev("rats_top", "camp").args, "news")
	eq(priv.beats.size(), 2, "camp beat plus my loss")
	eq(priv.beats[1].from, A.ME, "I lose")
	eq(priv.beats[1].amount_out, 1, "1")
	eq(news.beats.size(), 1, "the public copy only shows the camp effect: who lost is not in it")


func test_an_unknown_or_unnamed_event_stays_a_generic_event_beat_with_its_sentence() -> void:
	var unknown: Dictionary = A.beats_for("event", _ev("meteor", "player", "Bo", "A meteor.").args)[0]
	eq([unknown.kind, unknown.detail], ["event", "A meteor."], "unknown id")
	var unnamed: Dictionary = A.beats_for("event", _ev("snake", "player").args)[0]
	eq(unnamed.kind, "event", "no 'who': cannot move food")
	var old: Dictionary = A.beats_for("event", {"line": "Old style."})[0]
	eq([old.kind, old.detail], ["event", "Old style."], "an old-contract event line still works")


func test_my_own_find_event_is_normalised_to_me() -> void:
	var m := A.reveal_model(_reveal([_ev("bananas", "player", "Me")], [_ev("bananas", "player", "Me"),
		{"code": "now_have", "args": {"rations": 8}}]), "Me", {"me": {"alias": "Me", "rations": 7}, "aliases": ["Bo"]})
	eq(m.lines.filter(func(l): return l.code == "event").size(), 1, "shown once")
	var mv = m.beats.filter(func(b): return b.style == "bananas")[0]
	eq([mv.to, mv.amount_in], [A.ME, 1], "arrives at me, as ME")
	eq(m.totals.residual, 0, "the event explains the +1: no invented beat")


func test_every_real_night_now_adds_up_with_no_invented_beat() -> void:
	var n := 0
	var bad: Array = []
	for r in Fixtures.of_type("reveal"):
		if r.before.is_empty():
			continue
		var m: Dictionary = A.reveal_model(r.msg, r.me, r.before)
		if m.totals.before == null or m.totals.after == null:
			continue
		n += 1
		eq(A.net_for_me(m.beats), int(m.totals.after) - int(m.totals.before), "beats add up")
		if m.totals.residual != 0:
			bad.append("round %s game %s residual %s" % [r.msg.round, r.game, m.totals.residual])
	check(n > 25, "enough real nights: %d" % n)
	eq(bad, [], "with event ids the lines explain every night (guard income is 0 in the live rules)")


func test_every_event_kind_the_theme_must_show_is_a_listed_beat_kind() -> void:
	for ev in ["bananas", "snake", "shelter", "storm", "meteor"]:
		var b: Dictionary = A.beats_for("event", _ev(ev, "player", "Bo").args)[0]
		check(b.kind in A.BEAT_KINDS, "%s -> %s" % [ev, b.kind])
