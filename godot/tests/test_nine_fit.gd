extends BaseTest
## No control may be smaller than the fixed edges of the nine-patch it wears (see NineFit), in any state, at the window sizes
## that matter. Mounts the screens this branch owns with the real flash theme and walks the live tree.

const SIZES := [Vector2(450, 800), Vector2(540, 960), Vector2(700, 800), Vector2(1904, 1001)]

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("flash")


func teardown() -> void:
	super.teardown()
	Themes.use("placeholder")
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


## The screen inside a holder of the given size, with the theme applied the way the router does it.
func _mount(screen: Control, size: Vector2) -> Control:
	var holder := Control.new()
	holder.theme = Themes.current.godot_theme
	holder.size = size
	add_child(holder)
	holder.add_child(screen)
	_mounted.append(holder)
	return holder


func _settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame


func _expect_clean(holder: Control, tag: String) -> void:
	for v in NineFit.check(holder):
		check(false, "%s: %s" % [tag, v])


func test_title_buttons_are_never_smaller_than_their_art_at_any_size() -> void:
	for s in SIZES:
		var screen := TitleScreen.new()
		var holder := _mount(screen, s)
		await _settle()
		_expect_clean(holder, "title %s" % s)
		(Ui.find(screen, "settings_toggle") as Button).pressed.emit()
		await _settle()
		(Ui.find(screen, "advanced_toggle") as Button).pressed.emit()
		await _settle()
		_expect_clean(holder, "title settings+advanced %s" % s)
		(Ui.find(screen, "settings_toggle") as Button).pressed.emit()
		await _settle()
		screen._sheet_open = true                                # the new-camp sheet, as Create opens it
		screen._build()
		await _settle()
		_expect_clean(holder, "title sheet %s" % s)


func test_lobby_buttons_and_cards_fit_their_art_for_host_and_guest() -> void:
	for host in [true, false]:
		go_online()
		give_seat("t", "ABCD", host)
		fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 1, "seats_total": 4, "host": host})
		for s in SIZES:
			var holder := _mount(LobbyScreen.new(), s)
			await _settle()
			_expect_clean(holder, "lobby host=%s %s" % [host, s])


func test_end_screen_fits_its_art_for_every_tie_shape() -> void:
	in_round(10)
	for scores in [[4, 3, 2, 1], [3, 3, 3, 3], [5, 3, 3, 3]]:
		var rows := []
		for i in scores.size():
			rows.append({"alias": "Player%d" % i, "score": scores[i], "rations": 1, "seat": i == 0, "goal_done": false,
				"stole": 0, "times_robbed": 0, "gave_away": 0})
		fake.server_send({"t": "end", "extracted": [], "winners": ["Player0"], "results": rows})
		for s in SIZES:
			var holder := _mount(EndScreen.new(), s)
			await _settle()
			_expect_clean(holder, "end %s %s" % [scores, s])


func test_the_walker_really_catches_a_nine_patch_squashed_below_its_edges() -> void:
	# adversarial: prove the check can fail (otherwise a green run means nothing)
	var b := Button.new()
	var sb := StyleBoxTexture.new()
	sb.texture = ImageTexture.create_from_image(Image.create(8, 8, false, Image.FORMAT_RGBA8))
	sb.texture_margin_top = 30
	sb.texture_margin_bottom = 30
	sb.texture_margin_left = 10
	sb.texture_margin_right = 10
	b.add_theme_stylebox_override("hover", sb)
	b.size = Vector2(200, 56)
	add_child(b)
	_mounted.append(b)
	var found := NineFit.check(b)
	check(found.size() >= 1 and "[hover]" in found[0], "a 56 px button wearing 30+30 edges is reported, in its hover state: %s" % [found])
	b.size = Vector2(200, 60)
	eq(NineFit.check(b).size(), 0, "exactly tall enough is fine")
	b.size = Vector2(19, 60)
	check(NineFit.check(b).size() >= 1, "too narrow is reported too")
