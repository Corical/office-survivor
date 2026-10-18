extends BaseTest
## Adds to test_end_ties: EVERY score pattern for four players (all 81 vectors over {0,1,2}, so every tie shape in every
## server order), rooms of 1 to 6, names that are prefixes of one another, and the bracket legend. A player in the first
## three places is on the podium exactly once; every player is in the results exactly once.

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


func _mount_end(scores: Array, winners: Array) -> Control:
	if not _in_room:                       # building the room costs ~0.3 s: once per test, not once per pattern
		in_round(10)
		_in_room = true
	var rows := []
	for i in scores.size():
		rows.append({"alias": NAMES[i], "score": scores[i], "rations": 1, "seat": i == 0, "goal_done": false, "stole": 0,
			"times_robbed": 0, "gave_away": 0})
	var win := []
	for w in winners:
		win.append(NAMES[w])
	fake.server_send({"t": "end", "extracted": [], "winners": win, "results": rows})
	var s: Control = EndScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


func _count(root: Node, id: String) -> int:
	var n := 1 if (root.has_meta("id") and root.get_meta("id") == id) else 0
	for c in root.get_children():
		n += _count(c, id)
	return n


## Which of the first three places a score holds (0 = first), or -1 when it is a fourth place or worse.
func _tier(scores: Array, i: int) -> int:
	var distinct: Array = []
	for s in scores:
		if not distinct.has(s):
			distinct.append(s)
	distinct.sort()
	distinct.reverse()
	var t := distinct.find(scores[i])
	return t if t < 3 else -1


func _expect(s: Control, scores: Array, tag: String) -> void:
	var podium := Ui.find(s, "podium")
	check(podium != null, tag + ": a podium")
	if podium == null:
		return
	for i in scores.size():
		eq(_count(s, "row_" + NAMES[i]), 1, "%s: %s in the results once" % [tag, NAMES[i]])
		eq(_count(podium, "podium_" + NAMES[i]), 1 if _tier(scores, i) >= 0 else 0,
			"%s: %s on the podium once if in the first three places, else not" % [tag, NAMES[i]])


func test_every_score_pattern_in_every_order_keeps_everyone() -> void:
	for code in 81:
		var scores := [code % 3, (code / 3) % 3, (code / 9) % 3, (code / 27) % 3]
		var s := _mount_end(scores, [0])
		_expect(s, scores, str(scores))
		s.free()


func test_other_room_sizes_keep_everyone_too() -> void:
	for scores in [[1], [1, 1], [2, 1], [1, 1, 1], [3, 2, 1], [2, 2, 1], [1, 2, 2, 3, 3], [5, 5, 5, 5, 5, 5],
			[6, 5, 4, 3, 2, 1], [1, 2, 3, 4, 5, 6]]:
		_expect(_mount_end(scores, [0]), scores, str(scores))


func test_a_winner_chosen_by_the_server_among_equal_scores_keeps_all_four_on_one_step() -> void:
	var scores := [3, 3, 3, 3]
	var s := _mount_end(scores, [2])
	_expect(s, scores, "tie broken by the server")
	check("winner" in (Ui.find(s, "marks_SoggyBiscuit") as Label).text, "the winner is marked")
	check(not ("winner" in (Ui.find(s, "marks_Fig") as Label).text), "the others are not")


func test_prefix_names_are_not_confused() -> void:
	var s := _mount_end([2, 2, 1, 1], [0, 1])
	eq(_count(s, "podium_Fig"), 1, "Fig once")
	eq(_count(s, "podium_Figaro"), 1, "Figaro once")


func test_the_bracket_means_highest_of_its_column_and_the_legend_says_so() -> void:
	var s := _mount_end([3, 3, 1, 0], [0, 1])
	var legend := Ui.find(s, "legend") as Label
	check(legend != null and "[ ]" in legend.text, "a legend explains the brackets")
	eq((Ui.find(s, "cell_Fig_score") as Label).text, "[3]", "tied top bracketed")
	eq((Ui.find(s, "cell_Figaro_score") as Label).text, "[3]", "tied top bracketed, both")
	eq((Ui.find(s, "cell_SoggyBiscuit_score") as Label).text, "1", "below the top: plain")
	eq((Ui.find(s, "cell_LuckyLantern_score") as Label).text, "0", "a zero is never bracketed")
	eq((Ui.find(s, "cell_Fig_stole") as Label).text, "0", "a column whose top is 0 has no bracket")
	for n in NAMES.slice(0, 4):
		check(not ("[" in (Ui.find(s, "cell_%s_times_robbed" % n) as Label).text), "robbed is never bracketed")


func test_stat_headers_and_values_are_one_line_in_every_column() -> void:
	var s := _mount_end([3, 3, 1, 0], [0, 1])
	for h in Ui.find_all(s, "head_"):
		eq((h as Label).autowrap_mode, TextServer.AUTOWRAP_OFF, "header never wraps: " + (h as Label).text)
	for c in Ui.find_all(s, "cell_"):
		eq((c as Label).autowrap_mode, TextServer.AUTOWRAP_OFF, "value never wraps")
