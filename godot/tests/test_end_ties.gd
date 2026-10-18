extends BaseTest
## The end screen must show EVERY player exactly once on the podium and once in the results, for any pattern of ties.
## These tests try to break it: every score pattern, the server's order shuffled, names that are prefixes of each other,
## winners that are not the whole top group, and a list longer than the view.

const NAMES := ["Fig", "Figaro", "SoggyBiscuit", "LuckyLantern", "IronSpatula", "QuietOtter"]

var _mounted: Array = []
var _in_room := false


func setup() -> void:
	super.setup()
	Themes.use("placeholder")
	_in_room = false


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _send(scores: Array, winners: Array, names := NAMES) -> void:
	if not _in_room:                       # building the room costs ~0.3 s: once per test, not once per pattern
		in_round(10)
		_in_room = true
	var rows := []
	for i in scores.size():
		rows.append({"alias": names[i], "score": scores[i], "rations": 1, "seat": i == 0, "goal_done": false, "stole": 0,
			"times_robbed": 0, "gave_away": 0})
	var win := []
	for w in winners:
		win.append(names[w])
	fake.server_send({"t": "end", "extracted": [], "winners": win, "results": rows})


func _mount() -> Control:
	var s: Control = EndScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


## How many nodes under `root` carry exactly this id.
func _count(root: Node, id: String) -> int:
	var n := 0
	if root.has_meta("id") and root.get_meta("id") == id:
		n += 1
	for c in root.get_children():
		n += _count(c, id)
	return n


func _expect_everyone_once(s: Control, scores: Array, tag: String) -> void:
	var podium := Ui.find(s, "podium")
	check(podium != null, tag + ": there is a podium")
	if podium == null:
		return
	for i in scores.size():
		eq(_count(podium, "podium_" + NAMES[i]), 1, "%s: %s on the podium exactly once" % [tag, NAMES[i]])
		eq(_count(s, "row_" + NAMES[i]), 1, "%s: %s in the results exactly once" % [tag, NAMES[i]])
	var steps := Ui.find_all(podium, "step_").size()
	check(steps <= 3, "%s: at most three steps (%d)" % [tag, steps])


func test_every_tie_shape_of_four_players_shows_all_four_once() -> void:
	var shapes := {
		"all distinct": [4, 3, 2, 1], "2-way at the top": [3, 3, 2, 1], "2-way second": [3, 2, 2, 1],
		"2-way at the bottom": [3, 2, 1, 1], "3-way at the top": [3, 3, 3, 1], "3-way second": [3, 1, 1, 1],
		"first and second tied pairs": [2, 2, 1, 1], "all tied": [2, 2, 2, 2], "all zero": [0, 0, 0, 0],
		"a lone zero": [2, 2, 2, 0], "winner last in the server order": [1, 1, 1, 5]}
	for tag in shapes:
		_send(shapes[tag], [0])
		_expect_everyone_once(_mount(), shapes[tag], tag)


func test_every_score_pattern_and_every_server_order_keeps_everyone() -> void:
	# all 81 vectors over {0,1,2} for four players: this covers every tie shape in every order
	for code in 81:
		var scores := [code % 3, (code / 3) % 3, (code / 9) % 3, (code / 27) % 3]
		_send(scores, [0])
		_expect_everyone_once(_mount(), scores, str(scores))
		for c in _mounted:
			if is_instance_valid(c):
				c.free()
		_mounted.clear()


func test_other_room_sizes_keep_everyone_too() -> void:
	for scores in [[1], [1, 1], [2, 1], [1, 1, 1], [3, 2, 1], [2, 2, 1], [1, 2, 2, 3, 3], [5, 5, 5, 5, 5, 5], [6, 5, 4, 3, 2, 1],
			[1, 2, 3, 4, 5, 6]]:
		_send(scores, [0])
		_expect_everyone_once(_mount(), scores, str(scores))


func test_a_tied_second_place_stands_on_one_step_with_its_own_number() -> void:
	_send([5, 3, 3, 3], [0])
	var s := _mount()
	eq(_count(s, "step_1"), 1, "one first step")
	eq(_count(s, "step_2"), 1, "one second step for the three level players")
	eq(_count(s, "step_3"), 0, "no third or fourth place exists, so no such step")
	var second := Ui.find(s, "step_2")
	for n in ["Figaro", "SoggyBiscuit", "LuckyLantern"]:
		check(Ui.find(second, "podium_" + n) != null, n + " stands on the second step")
	check(Ui.find(second, "podium_Fig") == null, "the leader is not on the second step")
	# the results show the same place for the three
	var places := Ui.texts(Ui.find(s, "results"))
	eq(places.count("#2"), 3, "three results rows say #2")
	eq(places.count("#1"), 1, "one says #1")


func test_competition_ranking_skips_the_places_a_tie_swallowed() -> void:
	_send([5, 3, 3, 1], [0])                       # #1, #2, #2, #4: nobody is #3
	var s := _mount()
	eq(_count(s, "step_3"), 0, "no step labelled #3")
	eq(_count(s, "step_4"), 1, "the last player stands on the third step, labelled #4")
	var texts := Ui.texts(Ui.find(s, "podium"))
	check("#4" in texts and not ("#3" in texts), "podium numbers: " + str(texts))


func test_a_fourth_distinct_place_is_a_line_under_the_steps_not_missing() -> void:
	_send([4, 3, 2, 1], [0])
	var s := _mount()
	eq(_count(s, "place_4"), 1, "place 4 is a line under the steps")
	check(Ui.find(Ui.find(s, "place_4"), "podium_LuckyLantern") != null, "the fourth player is on that line")


func test_a_winner_who_shares_a_score_still_wears_the_win_and_nobody_is_dropped() -> void:
	_send([3, 3, 3, 3], [2])                       # the server broke the tie: only the third seat won
	var s := _mount()
	_expect_everyone_once(s, [3, 3, 3, 3], "tie broken by the server")
	eq(_count(s, "step_1"), 1, "all four share the first step")
	check("winner" in text_of_node(Ui.find(s, "marks_SoggyBiscuit")), "the winner is marked")
	check(not ("winner" in text_of_node(Ui.find(s, "marks_Fig"))), "the others are not")


func text_of_node(n: Node) -> String:
	return n.text if n != null else "<missing>"


func test_prefix_names_are_not_confused() -> void:
	_send([2, 2, 1, 1], [0, 1])
	var s := _mount()
	eq(_count(s, "podium_Fig"), 1, "Fig once")
	eq(_count(s, "podium_Figaro"), 1, "Figaro once")


func test_the_bracket_legend_is_shown_and_robbed_is_never_bracketed() -> void:
	_send([3, 3, 1, 0], [0, 1])
	var s := _mount()
	check(Ui.find(s, "legend") != null and "[ ]" in text_of_node(Ui.find(s, "legend")), "a legend explains the brackets")
	eq(text_of_node(Ui.find(s, "cell_Fig_score")), "[3]", "tied top bracketed")
	eq(text_of_node(Ui.find(s, "cell_Figaro_score")), "[3]", "tied top bracketed, both")
	eq(text_of_node(Ui.find(s, "cell_LuckyLantern_score")), "0", "a zero is never the top")
	eq(text_of_node(Ui.find(s, "cell_Fig_stole")), "0", "a column whose top is 0 has no bracket")


func test_the_scroll_hint_shows_while_the_list_runs_past_the_view_and_hides_at_the_end() -> void:
	_send([4, 3, 2, 1], [0])
	var holder := Control.new()
	holder.size = Vector2(450, 700)
	add_child(holder)
	_mounted.append(holder)
	var s: Control = EndScreen.new()
	holder.add_child(s)
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	var hint := Ui.find(s, "scroll_hint") as Label
	check(hint != null and hint.visible, "the hint shows when four players do not fit")
	var sc := s.find_children("*", "ScrollContainer", true, false)[0] as ScrollContainer
	sc.scroll_vertical = 100000
	await get_tree().process_frame
	await get_tree().process_frame
	check(not hint.visible, "the hint goes away at the bottom")
	holder.size = Vector2(450, 6000)
	await get_tree().process_frame
	await get_tree().process_frame
	check(not hint.visible, "and is never shown when everything fits")
