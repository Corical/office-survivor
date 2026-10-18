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


## A name label fits when it shows ALL of its text: on one line, or on two; "trimmed" is only for a name longer than that.
func _shows_all(l: Label) -> bool:
	return l is FitLabel and not (l as FitLabel).describe().trimmed


func _fit_label_in(width: float, text: String) -> FitLabel:
	var l := Ui.name_label(text, "", "NameLabel") as FitLabel
	l.custom_minimum_size = Vector2(width, 30)
	add_child(l)
	_mounted.append(l)
	l.size = Vector2(width, 30)
	l._fit()
	return l


func test_a_name_label_shrinks_then_wraps_and_only_then_trims() -> void:
	var font := ThemeDB.fallback_font
	var base: int = 18
	var w_base: float = font.get_string_size("SoggyBiscuit", HORIZONTAL_ALIGNMENT_LEFT, -1, base).x
	var roomy := _fit_label_in(w_base + 20.0, "SoggyBiscuit")
	eq(roomy.describe().size, roomy.describe().base, "enough room: the theme's own size")
	var tight := _fit_label_in(w_base * 0.8, "SoggyBiscuit")
	check(tight.describe().size < tight.describe().base, "a little too wide: a smaller font")
	eq(tight.describe().lines, 1, "still one line")
	check(not tight.describe().trimmed, "and all of it shown")
	var very := _fit_label_in(w_base * 0.45, "SoggyBiscuit")
	eq(very.describe().lines, 2, "far too wide even small: two lines")
	check(not very.describe().trimmed, "still all of it")
	var absurd := _fit_label_in(w_base * 0.12, "SoggyBiscuit")
	check(absurd.describe().trimmed, "only a hopeless width ends in an ellipsis")


func test_the_games_own_12_letter_names_fit_at_phone_width() -> void:
	for n in ["SoggyBiscuit", "LuckyLantern", "IronSpatula", "QuietBadger", "WobblyTable"]:
		var l := _fit_label_in(150.0, n)
		check(_shows_all(l), "%s shows all of itself in 150 px: %s" % [n, l.describe()])


func test_the_round_screen_never_cuts_my_own_name() -> void:
	Themes.use("placeholder")
	in_round(1)
	var v := round_view(1)
	v.me.alias = LONG
	fake.server_send(v)
	var s := _mount(RoundScreen.new())
	var you := Ui.find(s, "you_are") as Label
	check(you is FitLabel, "my name is a fitted label")
	eq(you.text, LONG, "the whole name, not a clipped copy")
	var cells := Ui.find_all(s, "home_")
	check(cells.size() >= 3, "the roster has its cells")
	for e in cells:
		for n in e.find_children("*", "Label", true, false):
			check(n is FitLabel, "roster cell labels are fitted: " + n.text)


func test_the_end_screen_fits_every_name() -> void:
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
		check(l != null and l is FitLabel and l.text == r, "result row name is a fitted label with the whole name: " + r)
	for l in Ui.find_all(s, "cell_"):
		check(l is FitLabel, "stat values are fitted labels")


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
	st._roster = [{"alias": LONG, "is_me": false, "band": "well_fed", "band_before": ""},
		{"alias": "Fig", "is_me": true, "band": "", "band_before": ""}]
	st._layout()
	_every_plate_item_is_inside(st)
	var long_name: String = (st._plates[LONG].items[0] as Dictionary).text
	check(long_name.ends_with("..."), "a name too long is cut with an ellipsis: " + long_name)
	eq((st._plates["Fig"].items[0] as Dictionary).text, "Fig", "a short name is left alone")
	# my food growing to three digits: the plate grows to hold it, nothing touches the rim
	var narrow: float = st._plates["Fig"].rect.size.x
	st._shown_int = 128
	st._build_plate(st._roster[1])
	_every_plate_item_is_inside(st)
	check(st._plates["Fig"].rect.size.x >= narrow, "the plate did not shrink for a longer number")


func test_floating_numbers_never_touch_a_plate_or_each_other() -> void:
	Themes.use("flash")
	in_round(2)
	var v := round_view(2)
	fake.server_send(v)
	fake.server_send({"t": "reveal", "round": 2, "news": [], "private": [{"code": "now_have", "args": {"rations": 8}}],
		"radio": [], "board": null, "seconds_left": 20})
	var st := Stage.new()
	_mount(st)
	st.size = Vector2(540, 400)
	st._load()
	check(st._rich, "the flash theme has the art this test needs")
	var white := Themes.color("white")
	var homes: Array = st._pos.keys().filter(func(k): return k != Stage.ME)
	# the same number twice at my hut, one at each other hut, all at once: the case that used to stack on itself
	st._float_text("+2", st._pos[Stage.ME], 0.0, white)
	st._float_text("+2", st._pos[Stage.ME], 0.0, white)
	st._float_text("-12", st._pos[Stage.ME], 0.0, white)
	for k in homes:
		st._float_text("+3", st._pos[k], 0.0, white)
		st._float_text("-1", st._pos[k], 0.0, white)
	var boxes: Array = st._pool.text_boxes(st.get_theme_default_font(), st.get_theme_default_font_size() + 6, true)
	check(boxes.size() >= 5, "the numbers are alive: %d" % boxes.size())
	for i in boxes.size():
		var r: Rect2 = boxes[i].rect
		for a in st._plates:
			check(not (st._plates[a].rect as Rect2).grow(Stage.FLOAT_CLEAR).intersects(r),
				"'%s' stays %.0f px clear of the plate of %s" % [boxes[i].text, Stage.FLOAT_CLEAR, a])
		for j in range(i + 1, boxes.size()):
			check(not r.intersects(boxes[j].rect), "'%s' and '%s' never share pixels" % [boxes[i].text, boxes[j].text])
	Themes.use("placeholder")


## Every item on every plate lies inside the plate with at least 4 px to spare on each side.
func _every_plate_item_is_inside(st: Stage) -> void:
	for alias in st._plates:
		var pl: Dictionary = st._plates[alias]
		var inner: Rect2 = (pl.rect as Rect2).grow(-4.0)
		for it in pl.items:
			check(inner.encloses(it.rect), "%s / %s %s is inside its plate %s" % [alias, it.what, it.rect, pl.rect])
