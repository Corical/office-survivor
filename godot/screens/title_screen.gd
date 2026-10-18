class_name TitleScreen
extends Control
## Create a room, join one by code, resume a stored seat, and set the server address. Builds only from Feed.status()
## and talks only through Intents. The logo bobs and glows, the buttons are chunky and bounce when pressed, and the whole
## menu pops in the first time it appears (all of it from the theme's art and effect settings, none of it required).

## Reasons a connection can end that the title explains (an upgrade has its own screen; `kicked` also drops the seat).
const TERMINAL_ON_TITLE := ["taken_over", "too_big", "flapping", "kicked"]
const MAX_CODE_SHOWN := 12          # real codes are 4 letters; a button must never grow with a hostile one

var _notice := ""
var _code_text := ""
var _show_settings := false
var _show_advanced := false
var _intro_played := false
var _hero_node: Control                       # the logo and its glow, built once
var _hero_tweens: Array = []
var _sheet_fresh := false                     # the sheet was just opened: fade it in once, not on every rebuild
var _sheet_open := false                     # the "new camp" form
var _vis := "public"
var _camp_name := ""
var _vis_buttons := {}
var _vis_help: Label
var _game := ""                               # the game picked on the picker (only drawn with more than one game)


func _ready() -> void:
	Feed.status_changed.connect(_on_status)
	Feed.notice_raised.connect(_on_notice)
	Feed.model_changed.connect(func(kind, _m): if kind == "games": _build())          # a new hello_ok may offer other games
	_build()
	Intents.rooms_watch(true)                 # the open-camps list runs for as long as this screen does (menu rebuilds do not touch it)


func _exit_tree() -> void:
	Intents.rooms_watch(false)


## A tap on Create or Join is on its way into a camp (the seat may already have arrived): the screen is about to change, so
## nothing here is laid out again until it does or the attempt fails. A relayout at this point showed a "Rejoin camp" button
## for a few frames and jumped every button.
func _on_status(st: Dictionary) -> void:
	if st.get("entering", false):
		return
	_build()


func _on_notice(n: Dictionary) -> void:
	_notice = Words.render(n.key, {"text": n.text})
	_build()


func _build() -> void:
	# the logo outlives a rebuild (a status or notice rebuilds the menu): taking it out first keeps it, and its bob, running
	if _hero_node != null and _hero_node.get_parent() != null:
		_hero_node.get_parent().remove_child(_hero_node)
	for c in get_children():
		remove_child(c)
		c.queue_free()
	var st := Feed.status()
	var menu := Ui.menu_column(Ui.page(self))
	var entries: Array = []                   # what pops in, in order
	var hero := _hero()
	if hero != null:
		menu.add_child(hero)
		entries.append(hero)
	var title := Ui.label(Words.render("ui.app_name"), "app_name", "BigLabel")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.visible = hero == null or not bool(Themes.fx("logo").get("has_title", false))      # a logo that spells it out
	menu.add_child(title)
	if title.visible:
		entries.append(title)
	var said := _notice
	if said == "" and st.terminal in TERMINAL_ON_TITLE:
		# The notice for this was emitted when the connection ended, before this screen existed. The reason is state, so
		# read it from there: the player must be able to see why they were disconnected, not just that they were.
		said = Words.render("notice." + st.terminal)
	if said != "":
		var note := Ui.label(said, "notice")
		note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		menu.add_child(note)
	if st.has_seat and not st.get("entering", false):
		var code_tag := str(st.room_code).left(MAX_CODE_SHOWN)
		var resume_label := Words.render("ui.resume_code", {"code": code_tag}) if code_tag != "" else Words.render("ui.resume")
		var resume := Ui.button(resume_label, "resume", func(): _show(Intents.resume()), false, "PrimaryButton")
		menu.add_child(resume)
		entries.append(resume)
	var games := Feed.games_model()
	if games.pick:
		var picker := _picker(games.games)
		menu.add_child(picker)
		entries.append(picker)
	var create := Ui.button(Words.render("ui.create_room"), "create", func(): _on_create(), false, "PrimaryButton")
	menu.add_child(create)
	entries.append(create)
	var row := Ui.hbox(10)
	var code := LineEdit.new()
	code.set_meta("id", "code")
	code.placeholder_text = Words.render("ui.enter_code")
	code.text = _code_text
	code.max_length = 8
	code.custom_minimum_size = Vector2(160, Ui.MIN_ART_BUTTON_HEIGHT)          # as tall as the Join button beside it
	code.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	code.text_changed.connect(func(t: String):
		var caps := t.to_upper()                       # codes are capitals: show what will be sent, caret where it was
		if caps != t:
			var at := code.caret_column
			code.text = caps
			code.caret_column = at
		_code_text = caps)
	row.add_child(code)
	var join := Ui.button(Words.render("ui.join_room"), "join", func(): _reason(Intents.join_room(_code_text)))
	join.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(join)
	menu.add_child(row)
	entries.append(row)
	menu.add_child(OpenCamps.new())            # shows itself only when the server can list camps
	var settings := Ui.button(Words.render("ui.hide_settings") if _show_settings else Words.render("ui.settings"),
		"settings_toggle", func():
			_show_settings = not _show_settings
			_build())
	menu.add_child(settings)
	entries.append(settings)
	if _show_settings:
		_settings(menu, st)
	if _sheet_open:
		var sheet := _make_sheet()
		add_child(sheet)
		if _sheet_fresh:
			_sheet_fresh = false
			_fade_in_sheet(sheet)
	if not _intro_played:
		_intro_played = true
		Ui.intro_all(entries)


## The game the player picked: their choice if the server still offers it, else the first game offered ("" with no list).
func _game_choice() -> String:
	var games: Array = Feed.games_model().games
	for g in games:
		if g.id == _game:
			return _game
	return str(games[0].id) if not games.is_empty() else ""


## "Choose a game": one row per game the server offers (its name and its seat range), the chosen one in the pick style.
## Drawn only when there is more than one game; the ids, names and seat counts are the server's, never words of this screen.
func _picker(games: Array) -> Control:
	var col := Ui.vbox(8)
	col.set_meta("id", "game_picker")
	col.add_child(Ui.label(Words.render("ui.choose_game"), "game_picker_title", "MutedLabel"))
	var chosen := _game_choice()
	for g in games:
		var id: String = g.id
		var pick := func():
			_game = id
			_build()
		var b := Ui.button("%s\n%s" % [g.name, players_text(g)], "game_" + id, pick, false, "ChosenButton" if id == chosen else "")
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col.add_child(b)
	return col


## "3 to 8 players", or "4 players" when the game has one size.
static func players_text(g: Dictionary) -> String:
	if int(g.seats_min) == int(g.seats_max):
		return Words.render("ui.game_players_exact", {"n": g.seats_min})
	return Words.render("ui.game_players", {"min": g.seats_min, "max": g.seats_max})


## Create: with a server that can list camps there is something to choose (public or private, a name), so a small sheet
## opens first; with any other server there is nothing to ask and the camp is created straight away, as it always was.
func _on_create() -> void:
	if Feed.rooms_model().get("can_list", Feed.rooms_model().supported):
		_sheet_open = true
		_sheet_fresh = true
		_build()
		return
	_reason(Intents.create_room("", "", _game_choice()))


## The new-camp form: a veil over the screen and a card with an optional name and a Public / Private choice.
func _make_sheet() -> Control:
	var veil := Ui.card("Veil")
	veil.set_meta("id", "sheet")
	veil.mouse_filter = Control.MOUSE_FILTER_STOP
	veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var centre := CenterContainer.new()
	veil.add_child(centre)
	var card := Ui.card()
	card.custom_minimum_size = Vector2(minf(500.0, maxf(280.0, size.x - 32.0)), 0)
	centre.add_child(card)
	var col := Ui.vbox(12)
	card.add_child(col)
	col.add_child(Ui.label(Words.render("ui.create_sheet_title"), "sheet_title", "HeaderLabel"))
	var field := LineEdit.new()
	field.set_meta("id", "camp_name")
	field.placeholder_text = Words.render("ui.camp_name_hint")
	field.text = _camp_name
	field.max_length = 24
	field.custom_minimum_size = Vector2(0, 56)
	field.text_changed.connect(func(t): _camp_name = t)
	col.add_child(field)
	var choice := Ui.hbox(10)
	_vis_buttons = {}
	for v in ["public", "private"]:
		var b := Ui.button(Words.render("ui." + v), "vis_" + v, func(): _pick_visibility(v))
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_vis_buttons[v] = b
		choice.add_child(b)
	col.add_child(choice)
	_vis_help = Ui.label("", "vis_help", "MutedLabel")
	col.add_child(_vis_help)
	_show_visibility()
	col.add_child(Ui.button(Words.render("ui.create_go"), "sheet_create", func(): _confirm_create(), false, "PrimaryButton"))
	col.add_child(Ui.button(Words.render("ui.cancel"), "sheet_cancel", func():
		_sheet_open = false
		_build()))
	return veil


## The sheet comes in over the screen instead of cutting in: the veil fades up in the theme's transition time and the card
## settles with the usual entrance. Reduced motion keeps the fade and drops the settling. A rebuild never replays it.
func _fade_in_sheet(veil: Control) -> void:
	var fx := Themes.fx("transition")
	if fx.is_empty():
		return
	veil.modulate.a = 0.0
	veil.create_tween().tween_property(veil, "modulate:a", 1.0, float(fx.get("fade", 0.2)))
	if not Themes.reduced_motion:
		var holder := veil.get_child(0)
		if holder != null and holder.get_child_count() > 0:
			Ui.intro(holder.get_child(0) as Control)


func _pick_visibility(v: String) -> void:
	_vis = v
	_show_visibility()


## The chosen side wears the pick style and its one-line explanation is shown (no rebuild: the name field keeps its focus).
func _show_visibility() -> void:
	for v in _vis_buttons:
		(_vis_buttons[v] as Button).theme_type_variation = "ChosenButton" if v == _vis else ""
	if _vis_help != null:
		_vis_help.text = Words.render("ui." + _vis + "_help")


func _confirm_create() -> void:
	_sheet_open = false
	var why := Intents.create_room(_vis, _camp_name, _game_choice())
	if why != "":
		_reason(why)
	else:
		_build()


func _settings(menu: VBoxContainer, st: Dictionary) -> void:
	var calm := "%s: %s" % [Words.render("ui.reduced_motion"), Words.render("ui.on" if Themes.reduced_motion else "ui.off")]
	menu.add_child(Ui.button(calm, "reduced_motion_toggle", func():
		Themes.reduced_motion = not Themes.reduced_motion
		_drop_hero()
		_build()))
	if Intents.can_fullscreen():
		menu.add_child(Ui.button(Words.render("ui.fullscreen"), "fullscreen_toggle", func(): Intents.toggle_fullscreen()))
	# the server address is for the few who were given one: folded away until asked for
	menu.add_child(Ui.button(Words.render("ui.hide_advanced") if _show_advanced else Words.render("ui.advanced"),
		"advanced_toggle", func():
			_show_advanced = not _show_advanced
			_build()))
	if _show_advanced:
		menu.add_child(Ui.label(Words.render("ui.server_address"), "", "MutedLabel"))
		var url := LineEdit.new()
		url.set_meta("id", "server_url")
		url.text = st.server_url
		url.text_changed.connect(func(t): Intents.set_server_url(t))
		menu.add_child(url)
		menu.add_child(Ui.label(Words.render("ui.advanced_hint"), "advanced_hint", "MutedLabel"))


## The logo, bobbing, over a glow that pulses. Null when the theme has no logo (the title is then plain text).
func _hero() -> Control:
	if _hero_node != null:
		return _hero_node
	var logo := Themes.texture("logo")
	if logo == null:
		return null
	var p := Themes.fx("logo")
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(0, 250)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.set_meta("id", "logo")
	var glow_tex := Themes.texture("campfire_glow")
	var glow: TextureRect = null
	if glow_tex != null:
		glow = Ui.picture(glow_tex, Vector2.ZERO)
		glow.modulate = Themes.color_a("glow", 0.5)
		var add := CanvasItemMaterial.new()
		add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		glow.material = add
		holder.add_child(glow)
	# The logo is a Sprite2D under a Node2D, NOT a Control: the engine rounds every Control's position to whole pixels, so a
	# bobbing Control moves in 1 px steps (it holds a few frames, then jumps). A Node2D's position is not rounded, so the bob
	# is a true sub-pixel glide. Nothing is laid out or resized while it animates, so the image keeps its exact size.
	var pic := Node2D.new()
	holder.add_child(pic)
	var sprite := Sprite2D.new()
	sprite.texture = logo
	pic.add_child(sprite)
	var fit := func():
		var ts := logo.get_size()
		var k := minf(holder.size.x / ts.x, holder.size.y / ts.y) if ts.x > 0.0 and ts.y > 0.0 else 1.0
		sprite.scale = Vector2(k, k)                                  # as a picture kept to its box without distortion
		sprite.position = holder.size * 0.5
		if glow != null:
			glow.size = holder.size + Vector2(180.0, 100.0)
			glow.position = Vector2(-90.0, -50.0)
	holder.resized.connect(fit)
	if not p.is_empty() and not Themes.reduced_motion:
		var bob := float(p.get("bob_px", 6.0))
		var secs := float(p.get("bob_s", 2.8))
		# bound to this screen, not to the logo: it survives the logo being lifted out and put back on a rebuild
		var tw := create_tween().set_loops()
		_hero_tweens.append(tw)
		tw.tween_method(_bob.bind(pic), -bob, bob, secs).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		tw.tween_method(_bob.bind(pic), bob, -bob, secs).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		if glow != null:
			var pulse := float(p.get("glow_s", 1.9))
			var gt := create_tween().set_loops()
			_hero_tweens.append(gt)
			gt.tween_property(glow, "modulate:a", 0.85, pulse).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
			gt.tween_property(glow, "modulate:a", 0.35, pulse).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_hero_node = holder
	return holder


## Stop the logo's motion and forget it (the next build makes a new one): used when the motion setting changes.
func _drop_hero() -> void:
	for t in _hero_tweens:
		if t != null and t.is_valid():
			t.kill()
	_hero_tweens = []
	if _hero_node != null:
		if _hero_node.get_parent() != null:
			_hero_node.get_parent().remove_child(_hero_node)
		_hero_node.queue_free()
		_hero_node = null


func _bob(v: float, pic: Node2D) -> void:
	pic.position.y = v


func _show(started: bool) -> void:
	if not started:
		_notice = Words.render("notice.no_server_url")
		_build()


## An intent came back refused: show the reason in the theme's words.
func _reason(why: String) -> void:
	if why == "":
		return
	_notice = Words.render(UiKeys.notice_key("", why), {"text": why})
	_build()
