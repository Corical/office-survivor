extends BaseTest
## The adapter against real harvested server views, plus hand-built nasty cases: merge/dedupe, privacy ordering,
## unknown inputs. The point is what could go wrong, not that the happy path renders.

const A = preload("res://rulesets/survivors/adapter.gd")


func setup() -> void:
	super.setup()
	A.forget_unknowns()


func _reveal(news: Array, priv: Array, rnd := 1) -> Dictionary:
	return {"t": "reveal", "round": rnd, "news": news, "private": priv, "radio": [], "board": null, "seconds_left": 20}


func _l(code: String, args := {}) -> Dictionary:
	return {"code": code, "args": args}


func _moves_out_of(beats: Array, who: String) -> int:
	var n := 0
	for b in beats:
		if b.kind == "move_resource" and b.from == who:
			n += b.amount_out
	return n


# ---- coverage of the vocabulary ----

func test_every_server_code_has_a_known_line_and_beats() -> void:
	for code in A.line_codes():
		var ln := A.line(code, {}, "private")
		eq(ln.key, "line." + code, code + " key")
		if A.is_text_only(code):
			eq(ln.beats, [], code + " is card text: no beats")       # goal_* and progress_*
			continue
		check(not ln.beats.is_empty(), code + " has beats")
		check(ln.beats[0].kind != "unknown", code + " is not mapped to the unknown beat")


func test_codes_seen_in_real_play_all_map() -> void:
	for code in Fixtures.seen_codes():
		check(code in A.line_codes(), "real play produced a code the table lacks: " + code)


func test_lines_table_is_the_servers() -> void:
	# The server's folder is ../arena next to godot/, or ARENA_DIR. Missing is a FAILURE, not a skip (review N24):
	# a silent skip lets the copy drift. Set ARENA_SIBLING=0 to opt out on a machine that has only godot/.
	var dir := OS.get_environment("ARENA_DIR")
	var base: String = dir if dir != "" else ProjectSettings.globalize_path("res://").path_join("../arena")
	var server := base.path_join("lines_en.json")
	if not FileAccess.file_exists(server):
		if OS.get_environment("ARENA_SIBLING") != "0":
			failures.append("cannot compare lines_en.json: %s not found (set ARENA_DIR, or ARENA_SIBLING=0 to skip)" % server)
		return
	eq(FileAccess.get_file_as_string(A.LINES_PATH).replace("\r\n", "\n"),
		FileAccess.get_file_as_string(server).replace("\r\n", "\n"), "godot copy of lines_en.json drifted from arena/")


func test_unknown_code_is_neutral_and_logged_once() -> void:
	var a := A.line("brand_new_code", {"x": 1})
	var b := A.line("brand_new_code", {"x": 1})
	eq(a.key, "line.unknown", "neutral key")
	eq(a.beats[0].kind, "unknown", "unknown beat")
	eq(Log.since(mark, "WARN").filter(func(l): return "brand_new_code" in l).size(), 1, "logged once, not per line")


# ---- real views ----

func test_every_real_round_view_becomes_a_consistent_model() -> void:
	var n := 0
	for r in Fixtures.of_type("round"):
		var v: Dictionary = r.msg
		var m := A.round_model(v)
		n += 1
		eq(m.pickers.map(func(p): return p.server_id).size(), v.legal.size(), "one picker per legal kind")
		for p in m.pickers:
			eq(p.targets, v.legal[p.server_id], "targets are exactly the server's, sorted")
			if p.move_id != "gift":
				eq(p.amounts, [], "amounts only on gift")
			else:
				eq(p.amounts, v.gift_amounts, "gift amounts")
			if p.move_id in ["scavenge", "guard"]:
				eq(p.takes_target, false, p.move_id + " takes no target")
			else:
				eq(p.takes_target, true, p.move_id + " takes a target")
		eq(m.roster.size(), v.aliases.size() + 1, "everyone including me")
		eq(m.roster.filter(func(e): return e.is_me).size(), 1, "exactly one me")
		eq(m.me.alias, r.me, "me")
	check(n > 50, "enough views exercised: %d" % n)


func test_roster_is_sorted_by_alias_whatever_order_the_server_sends() -> void:
	var board := [{"alias": "Zed", "band": "bandit"}, {"alias": "Amy", "band": "well_fed"},
		{"alias": "Kit", "band": "starving"}, {"alias": "Mia", "band": "getting_by"}]
	var a := A.roster("Mia", ["Zed", "Amy", "Kit"], board)
	var b := A.roster("Mia", ["Kit", "Zed", "Amy"], board.duplicate().slice(0, 4))
	b.reverse()
	eq(a.map(func(e): return e.alias), ["Amy", "Kit", "Mia", "Zed"], "sorted")
	var shuffled := A.roster("Mia", ["Amy", "Kit", "Zed"], [board[2], board[3], board[0], board[1]])
	eq(shuffled, a, "board order does not change the roster")


func test_no_board_means_no_bands_not_invented_ones() -> void:
	var r := A.roster("Me", ["A", "B"], null)
	for e in r:
		eq(e.band, "", "no band without a board")


func test_unknown_band_is_neutral() -> void:
	eq(A.band_id("starving"), "band.starving", "known")
	eq(A.band_id("exalted"), "band.unknown", "unknown")
	eq(A.band_id(null), "band.unknown", "null")
	eq(Log.since(mark, "WARN").size(), 2, "each unknown logged once")


func test_every_real_reveal_becomes_a_clean_model() -> void:
	var n := 0
	for r in Fixtures.of_type("reveal"):
		var before := {"aliases": r.others, "round": r.msg.round}
		var m := A.reveal_model(r.msg, r.me, before)
		n += 1
		var known := {A.ME: true, A.OFFSTAGE: true}
		for e in m.roster:
			known[e.alias] = true
		for ln in m.lines:
			check(ln.key != "line.unknown", "unknown line in real play: " + ln.code)
		for b in m.beats:
			check(b.from in known and b.to in known, "beat names someone outside the game: %s -> %s" % [b.from, b.to])
			check(b.amount_out >= 0 and b.amount_in >= 0, "negative amount")
			check(b.line_index >= 0 and b.line_index < m.lines.size(), "beat points at a real line")
		eq(m.roster.size(), r.others.size() + 1, "roster is everyone")
	check(n > 30, "enough reveals exercised: %d" % n)


func test_quiet_night_is_synthesised_from_an_empty_news_list() -> void:
	var m := A.reveal_model(_reveal([], [_l("now_have", {"rations": 5})]), "Me", {"aliases": ["A"]})
	eq(m.lines[0].code, "news_quiet", "quiet first")
	eq(m.beats[0].kind, "quiet", "quiet beat")


func test_now_have_is_the_last_beat_when_it_is_the_last_line() -> void:
	var m := A.reveal_model(_reveal([], [_l("scavenged", {"found": 1}), _l("now_have", {"rations": 8})]), "Me", {"aliases": ["A"]})
	eq(m.beats.back().kind, "total", "total last")
	eq(m.beats.back().amount_in, 8, "carries my total")


# ---- merge and dedupe (the nasty ones) ----

func test_my_theft_is_one_animation_not_two() -> void:
	# I stole 2 from Bo; the news also says someone hit Bo for 2. Bo must lose 2 once, not 4.
	var m := A.reveal_model(_reveal([_l("news_hit_1", {"victim": "Bo", "total": 2})],
		[_l("stole", {"target": "Bo", "amount": 2})]), "Me", {"aliases": ["Bo", "Cy"]})
	eq(_moves_out_of(m.beats, "Bo"), 2, "Bo loses 2 once")
	eq(m.lines.size(), 2, "both lines still appear in the log")
	check(m.lines.filter(func(l): return l.covered).size() == 1, "the news line is marked covered")


func test_being_robbed_is_one_animation_not_two() -> void:
	var m := A.reveal_model(_reveal([_l("news_hit_1", {"victim": "Me", "total": 2})],
		[_l("robbed", {"amount": 2})]), "Me", {"aliases": ["Bo"]})
	eq(_moves_out_of(m.beats, A.ME), 2, "I lose 2 once")


func test_a_theft_of_someone_else_is_still_shown() -> void:
	var m := A.reveal_model(_reveal([_l("news_hit_1", {"victim": "Bo", "total": 2})],
		[_l("scavenged", {"found": 0})]), "Me", {"aliases": ["Bo", "Cy"]})
	eq(_moves_out_of(m.beats, "Bo"), 2, "Bo's loss is animated")
	check(m.beats.filter(func(b): return b.to == A.OFFSTAGE and b.from == "Bo").size() == 1, "to the offstage thief")


func test_the_same_event_sentence_in_news_and_private_shows_once() -> void:
	var ev := _l("event", {"line": "A storm rolled in."})
	var m := A.reveal_model(_reveal([ev], [ev, _l("now_have", {"rations": 3})]), "Me", {"aliases": ["Bo"]})
	eq(m.lines.filter(func(l): return l.code == "event").size(), 1, "one event line")
	eq(m.beats.filter(func(b): return b.kind == "event").size(), 1, "one event beat")


func test_two_different_events_both_show() -> void:
	var m := A.reveal_model(_reveal([_l("event", {"line": "A storm."}), _l("event", {"line": "Rats."})], []), "Me", {})
	eq(m.lines.filter(func(l): return l.code == "event").size(), 2, "both")


func test_a_catch_that_involves_me_is_covered_by_my_private_line() -> void:
	var news := _l("news_caught", {"target": "Bo", "thief": "Me", "paid": 2})
	var priv := _l("steal_caught", {"target": "Bo", "paid": 2})
	var m := A.reveal_model(_reveal([news], [priv]), "Me", {"aliases": ["Bo"]})
	eq(_moves_out_of(m.beats, A.ME), 2, "I pay 2 once, not 4")


func test_exposure_I_caused_is_not_drawn_twice() -> void:
	var m := A.reveal_model(_reveal([_l("news_exposed", {"thief": "Bo", "victim": "Cy", "paid": 1})],
		[_l("exposed_by_me", {"thief": "Bo", "paid": 1})]), "Me", {"aliases": ["Bo", "Cy"]})
	eq(m.beats.filter(func(b): return b.kind == "marked").size(), 1, "Bo is marked once")
	eq(_moves_out_of(m.beats, "Bo"), 1, "Bo pays once")


func test_my_own_bandit_news_is_covered() -> void:
	var m := A.reveal_model(_reveal([_l("news_bandit", {"player": "Me"})], [_l("became_bandit_me")]), "Me", {"aliases": ["Bo"]})
	eq(m.beats.filter(func(b): return b.kind == "status").size(), 1, "one status change")


func test_other_peoples_bandit_news_is_drawn() -> void:
	var m := A.reveal_model(_reveal([_l("news_bandit", {"player": "Bo"})], []), "Me", {"aliases": ["Bo"]})
	eq(m.beats.filter(func(b): return b.kind == "status" and b.to == "Bo").size(), 1, "Bo changes")


func test_order_is_news_events_then_private_then_other_news() -> void:
	var m := A.reveal_model(_reveal([_l("event", {"line": "Storm"}), _l("news_bandit", {"player": "Bo"})],
		[_l("scavenged", {"found": 1}), _l("now_have", {"rations": 4})]), "Me", {"aliases": ["Bo"]})
	eq(m.lines.map(func(l): return l.code), ["event", "scavenged", "now_have", "news_bandit"], "order")


func test_malformed_lines_do_not_crash_the_adapter() -> void:
	var m := A.reveal_model(_reveal([_l("news_hit_1", {}), _l("stole", {"amount": "two"}), _l("watched", {"saw": 5})],
		[_l("gave", {"receiver": null, "amount": null})]), "Me", {})
	check(m.lines.size() >= 4, "all lines survived")
	no_errors()


func test_a_watched_move_the_theme_cannot_word_degrades_to_something() -> void:
	var ln := A.line("watched", {"target": "Bo", "saw": "teleport"})
	eq(ln.slots.saw, {"key": "move.unknown.choice"}, "neutral move word")


# ---- radio, goals, end ----

func test_unknown_radio_phrase_is_neutral() -> void:
	var v := _reveal([], [])
	v.radio = [{"phrase": "trust", "about": "Bo"}, {"phrase": "nonsense", "about": null}, {"phrase": null, "about": null}]
	var m := A.reveal_model(v, "Me", {})
	eq(m.radio[0], {"key": "radio.trust", "slots": {"a": "Bo"}}, "known phrase")
	eq(m.radio[1].key, "radio.unknown", "unknown phrase")
	eq(m.radio[2].key, "radio.unknown", "null phrase")


func test_end_model_never_ranks_or_highlights_by_being_robbed() -> void:
	var e: Dictionary = Fixtures.of_type("end")[0].msg
	var m := A.end_model(e, Fixtures.of_type("end")[0].me)
	var robbed: Dictionary = m.columns.filter(func(c): return c.id == "times_robbed")[0]
	eq(robbed.highlight, false, "robbed is shown but never highlighted")
	eq(m.rows.map(func(r): return r.alias), e.results.map(func(r): return r.alias), "rows in the server's score order")
	check(m.rows.any(func(r): return r.is_winner), "a winner is marked")
	eq(m.rows.filter(func(r): return r.is_me).size(), 1, "I am marked once")


func test_goal_with_an_unknown_code_is_neutral_and_keeps_the_servers_text() -> void:
	var v: Dictionary = Fixtures.of_type("round")[0].msg.duplicate(true)
	v.me.goal = {"code": "conquer", "target": null, "text": "conquer the island"}
	var m := A.round_model(v)
	eq(m.goal.key, "goal.unknown", "neutral key")
	eq(m.goal.slots.text, "conquer the island", "the server's wording is kept as the fallback")


func test_a_view_with_nobody_to_target_does_not_break_the_picker() -> void:
	var v: Dictionary = Fixtures.of_type("round")[0].msg.duplicate(true)
	v.legal = {"scavenge": [], "steal": []}
	v.aliases = []
	var m := A.round_model(v)
	eq(m.pickers.size(), 2, "both kinds listed")
	eq(m.pickers.filter(func(p): return p.move_id == "steal")[0].targets, [], "steal has no targets: the screen shows it disabled")
