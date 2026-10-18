extends BaseTest
## The Stage's state logic (headless draws nothing, so what is drawn is checked by the windowed snapshot and driver):
## where the homes sit, where an unnamed actor comes from, and that the food shown for me always ends on the real total.

const A = preload("res://rulesets/survivors/adapter.gd")
var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _stage() -> Stage:
	var s := Stage.new()
	add_child(s)
	s.size = Vector2(540, 340)
	s._load()
	_mounted.append(s)
	return s


func _play_through(r: Dictionary) -> Stage:
	setup()
	go_online()
	give_seat("t", "ABCD", true, r.me)
	fake.server_send(r.before)
	fake.server_send(r.msg)
	return _stage()


func test_the_marker_names_match_the_adapters() -> void:
	eq(Stage.ME, A.ME, "me")
	eq(Stage.OFFSTAGE, A.OFFSTAGE, "unnamed actor")


func test_every_real_night_ends_with_exactly_the_real_total_on_screen() -> void:
	var n := 0
	for r in Fixtures.of_type("reveal"):
		if r.before.is_empty():
			continue
		var s := _play_through(r)
		var m: Dictionary = Feed.models.reveal
		if m.totals.before == null or m.totals.after == null:
			continue
		n += 1
		eq(s.describe().my_food, int(m.totals.before), "starts from the food I had (round %s game %s)" % [r.msg.round, r.game])
		var tl: Timeline = Feed.player.timeline
		var guard := 0
		while not tl.finished and guard < 500:
			tl.advance(250)
			s._apply_done()
			guard += 1
		s._apply_done()
		eq(s.describe().my_food, int(m.totals.after), "ends on the server's total (round %s game %s)" % [r.msg.round, r.game])
	check(n > 25, "enough real nights played through: %d" % n)


func test_a_snapped_reveal_shows_the_final_food_at_once_and_invents_nothing() -> void:
	in_round(1)
	fake.server_send({"t": "reveal", "round": 7, "news": [], "private": [{"code": "now_have", "args": {"rations": 9}}],
		"radio": [], "board": null, "seconds_left": 20})                     # no round-7 view held: nothing to animate from
	var s := _stage()
	check(s.describe().finished, "snapped")
	eq(s.describe().my_food, 9, "the final food")


func test_homes_are_placed_from_the_sorted_roster_with_me_at_the_bottom() -> void:
	var r: Dictionary = Fixtures.of_type("reveal")[0]
	var s := _play_through(r)
	var centre: Vector2 = s.get_meta("centre")
	check((s._pos[Stage.ME] as Vector2).y > centre.y, "I sit below the centre")
	for e in Feed.models.reveal.roster:
		var p: Vector2 = s._pos[e.alias]
		check(Rect2(Vector2.ZERO, s.size).has_point(p), "%s is inside the stage: %s" % [e.alias, p])
	var again := _stage()
	eq(again._pos, s._pos, "same roster, same layout: nothing depends on arrival order")


func test_an_unnamed_actor_comes_from_outside_the_ring_not_from_a_home() -> void:
	var r: Dictionary = Fixtures.of_type("reveal")[0]
	var s := _play_through(r)
	var centre: Vector2 = s.get_meta("centre")
	var radius: float = s.get_meta("radius")
	for e in Feed.models.reveal.roster:
		var from_edge: Vector2 = s.where(Stage.OFFSTAGE, e.alias)
		check(from_edge.distance_to(centre) > radius * 1.5, "outside the ring toward %s" % e.alias)
		for h in Feed.models.reveal.roster:
			check(from_edge.distance_to(s._pos[h.alias]) > 30.0, "not on top of a home")


func test_the_stage_never_shows_another_players_exact_food() -> void:
	var r: Dictionary = Fixtures.of_type("reveal")[0]
	_play_through(r)
	for e in Feed.models.reveal.roster:
		if not e.is_me:
			check(not e.has("food") and not e.has("rations") and not e.has("amount"), "the roster entry carries no number: %s" % [e.keys()])


func test_skip_finishes_the_animation_and_the_log_stays_complete() -> void:
	in_round(2)
	fake.server_send({"t": "reveal", "round": 2, "news": [{"code": "news_bandit", "args": {"player": "Fig"}}],
		"private": [{"code": "scavenged", "args": {"found": 1}}, {"code": "now_have", "args": {"rations": 8}}],
		"radio": [], "board": null, "seconds_left": 20})
	var screen := RevealScreen.new()
	add_child(screen)
	_mounted.append(screen)
	check(not Feed.player.timeline.finished, "playing")
	(Ui.find(screen, "skip") as Button).pressed.emit()
	check(Feed.player.timeline.finished, "skipped")
	check(Ui.find_all(screen, "line_").size() >= 3, "every line is still written below")
