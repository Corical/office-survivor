extends BaseTest
## However the scores tie, every player is on the podium exactly once or (past the third place) in the ordered list, no place
## is shown twice as separate steps, and the list shows every player once, best place first. The stranger pass found a
## three-way tie for second showing two "#2" steps and dropping a player.

const NAMES := ["QuietBadger", "IronSpatula", "LuckyLantern", "SoggyBiscuit", "WobblyTable", "SaltyPretzel"]

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _end(scores: Array) -> Control:
	Themes.use("placeholder")
	in_round(10)
	var rows := []
	var best := 0
	for s in scores:
		best = maxi(best, int(s))
	var winners := []
	for i in scores.size():
		rows.append({"alias": NAMES[i], "score": scores[i], "rations": 3, "seat": false, "goal_done": false, "stole": 0,
			"times_robbed": 0, "gave_away": 0})
		if int(scores[i]) == best:
			winners.append(NAMES[i])
	fake.server_send({"t": "end", "extracted": [], "winners": winners, "results": rows})
	var s := EndScreen.new()
	add_child(s)
	_mounted.append(s)
	return s


func _count_in(node: Node, who: String) -> int:
	var n := 0
	for t in Ui.texts(node):
		if t == who:
			n += 1
	return n


func _check_shape(label: String, scores: Array, want_steps: int, want_places: Array) -> void:
	var s := _end(scores)
	var podium := Ui.find(s, "podium")
	check(podium != null, label + ": there is a podium")
	var board := Ui.find(s, "results")
	var distinct := {}
	var ranks_seen: Array = []
	for t in Ui.texts(podium):
		if t.begins_with("#"):
			ranks_seen.append(t)
	eq(podium.get_child_count(), want_steps, label + ": steps on the podium")
	eq(ranks_seen, want_places, label + ": the places on the steps, each once, in the podium's own order")
	var top_places := {}
	for p in ranks_seen:
		distinct[p] = true
	eq(distinct.size(), ranks_seen.size(), label + ": no place appears on two steps")
	for i in scores.size():
		var on_podium := _count_in(podium, NAMES[i])
		var in_list := _count_in(board, NAMES[i])
		eq(in_list, 1, "%s: %s is in the list exactly once" % [label, NAMES[i]])
		check(on_podium <= 1, "%s: %s is on the podium at most once (%d)" % [label, NAMES[i], on_podium])
	# the list is in the server's order, which is best place first
	var order: Array = Ui.find_all(s, "row_").map(func(l): return l.text)
	eq(order, NAMES.slice(0, scores.size()), label + ": the list is ordered")
	check(_find_hint(s) != null, label + ": the page can say there is more below")


func _find_hint(n: Node) -> Node:
	if n is ScrollHint:
		return n
	for c in n.get_children():
		var h := _find_hint(c)
		if h != null:
			return h
	return null


func test_no_tie() -> void:
	_check_shape("no tie", [6, 5, 3, 1], 3, ["#2", "#1", "#3"])


func test_three_way_tie_for_second() -> void:
	_check_shape("3-way at #2", [5, 3, 3, 3], 2, ["#2", "#1"])
	var s := _end([5, 3, 3, 3])
	var podium := Ui.find(s, "podium")
	for who in ["IronSpatula", "LuckyLantern", "SoggyBiscuit", "QuietBadger"]:
		eq(_count_in(podium, who), 1, who + " is on the podium once")


func test_two_way_tie_for_second() -> void:
	_check_shape("2-way at #2", [5, 3, 3, 1], 3, ["#2", "#1", "#4"])


func test_first_and_second_tie() -> void:
	_check_shape("1st and 2nd tie", [5, 5, 3, 1], 3, ["#3", "#1", "#4"])


func test_two_way_tie_for_first() -> void:
	_check_shape("2-way at #1", [4, 4, 2, 1], 3, ["#3", "#1", "#4"])


func test_four_way_tie() -> void:
	_check_shape("4-way tie", [4, 4, 4, 4], 1, ["#1"])
	var podium := Ui.find(_end([4, 4, 4, 4]), "podium")
	for who in NAMES.slice(0, 4):
		eq(_count_in(podium, who), 1, who + " is on the podium once")


func test_two_players_level() -> void:
	_check_shape("2 level", [3, 3], 1, ["#1"])


func test_one_player() -> void:
	_check_shape("1 player", [3], 1, ["#1"])


func test_more_players_than_steps_the_rest_are_in_the_list_only() -> void:
	var s := _end([9, 7, 5, 3, 2, 1])
	var podium := Ui.find(s, "podium")
	for who in NAMES.slice(3, 6):
		eq(_count_in(podium, who), 0, who + " is past the third place: not on the podium")
		eq(_count_in(Ui.find(s, "results"), who), 1, who + " is in the list once")
