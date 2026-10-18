extends BaseTest
## Text must fit where it is put: a name is one line (trimmed with an ellipsis, never broken mid-word), and a plate
## on the Stage holds its name. Checked with the longest aliases a player can pick.

const LONG := "Bartholomew_Jr_III_Extremely_Long"

var _mounted: Array = []


func teardown() -> void:
	super.teardown()
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _mount(node: Node) -> Node:
	add_child(node)
	_mounted.append(node)
	return node


func _is_one_line(l: Label) -> bool:
	return l.autowrap_mode == TextServer.AUTOWRAP_OFF and l.text_overrun_behavior == TextServer.OVERRUN_TRIM_ELLIPSIS


func test_a_name_label_is_one_line_with_an_ellipsis() -> void:
	var l := Ui.name_label(LONG)
	check(_is_one_line(l), "no wrapping, trimmed with an ellipsis")
	check(l.clip_text, "clipped to its box")
	l.free()


func test_the_round_screen_never_breaks_my_own_name_across_lines() -> void:
	Themes.use("placeholder")
	in_round(1)
	var v := round_view(1)
	v.me.alias = LONG
	fake.server_send(v)
	var s := _mount(RoundScreen.new())
	var you := Ui.find(s, "you_are") as Label
	check(you != null and _is_one_line(you), "the 'You are <name>' line is one line")
	for e in Ui.find_all(s, "home_"):
		for n in e.get_children():
			if n is Label:
				check(_is_one_line(n), "roster cell labels are one line: " + n.text)


func test_the_end_screen_keeps_every_name_on_one_line() -> void:
	Themes.use("placeholder")
	in_round(10)
	var rows := []
	for a in [[LONG, 5], ["Wolfgang Amadeus Mozart The Third", 3], ["Fig", 1]]:
		rows.append({"alias": a[0], "score": a[1], "rations": 1, "seat": false, "goal_done": false, "stole": 0,
			"times_robbed": 0, "gave_away": 0})
	fake.server_send({"t": "end", "extracted": [], "winners": [LONG], "results": rows})
	var s := _mount(EndScreen.new())
	for r in [LONG, "Wolfgang Amadeus Mozart The Third", "Fig"]:
		var l := Ui.find(s, "row_" + r) as Label
		check(l != null and _is_one_line(l), "result row name is one line: " + r)
	for l in Ui.find_all(s, "cell_"):
		check(_is_one_line(l), "stat values never wrap")


func test_a_stage_plate_holds_the_longest_name() -> void:
	Themes.use("placeholder")
	in_round(2)
	var v := round_view(2)
	v.me.alias = LONG
	fake.server_send(v)
	fake.server_send({"t": "reveal", "round": 2, "news": [], "private": [{"code": "now_have", "args": {"rations": 8}}],
		"radio": [], "board": null, "seconds_left": 20})
	var st := Stage.new()
	_mount(st)
	st.size = Vector2(540, 400)
	st._load()
	var font := st.get_theme_default_font()
	var room: float = st._plate_w() - 28.0
	st._roster = [{"alias": LONG, "is_me": false, "band": "", "band_before": ""},
		{"alias": "Fig", "is_me": true, "band": "", "band_before": ""}]
	st._trim_plates()
	for alias in st._plate_name:
		var shown: String = st._plate_name[alias]
		check(font.get_string_size(shown.trim_suffix("..."), HORIZONTAL_ALIGNMENT_LEFT, -1, st._plate_size() + 1).x <= room,
			"the plate text for '%s' fits: %s" % [alias, shown])
	check(st._plate_name[LONG].ends_with("..."), "a name too long is cut with an ellipsis")
	eq(st._plate_name["Fig"], "Fig", "a short name is left alone")
