class_name TitleScreen
extends Control
## Create a room, join one by code, resume a stored seat, and set the server address. Builds only from Feed.status()
## and talks only through Intents. The logo bobs and glows, the buttons are chunky and bounce when pressed, and the whole
## menu pops in the first time it appears (all of it from the theme's art and effect settings, none of it required).

var _notice := ""
var _code_text := ""
var _show_settings := false
var _intro_played := false


func _ready() -> void:
	Feed.status_changed.connect(func(_s): _build())
	Feed.notice_raised.connect(_on_notice)
	_build()


func _on_notice(n: Dictionary) -> void:
	_notice = Words.render(n.key, {"text": n.text})
	_build()


func _build() -> void:
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
	if _notice != "":
		var note := Ui.label(_notice, "notice")
		note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		menu.add_child(note)
	if st.has_seat:
		var resume := Ui.button(Words.render("ui.resume"), "resume", func(): _show(Intents.resume()), false, "PrimaryButton")
		menu.add_child(resume)
		entries.append(resume)
	var create := Ui.button(Words.render("ui.create_room"), "create", func(): _reason(Intents.create_room()), false,
		"PrimaryButton")
	menu.add_child(create)
	entries.append(create)
	var row := Ui.hbox(10)
	var code := LineEdit.new()
	code.set_meta("id", "code")
	code.placeholder_text = Words.render("ui.enter_code")
	code.text = _code_text
	code.max_length = 8
	code.custom_minimum_size = Vector2(160, 56)
	code.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	code.text_changed.connect(func(t): _code_text = t)
	row.add_child(code)
	var join := Ui.button(Words.render("ui.join_room"), "join", func(): _reason(Intents.join_room(_code_text)))
	join.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(join)
	menu.add_child(row)
	entries.append(row)
	var settings := Ui.button(Words.render("ui.hide_settings") if _show_settings else Words.render("ui.settings"),
		"settings_toggle", func():
			_show_settings = not _show_settings
			_build())
	menu.add_child(settings)
	entries.append(settings)
	if _show_settings:
		_settings(menu, st)
	if not _intro_played:
		_intro_played = true
		Ui.intro_all(entries)


func _settings(menu: VBoxContainer, st: Dictionary) -> void:
	menu.add_child(Ui.label(Words.render("ui.server_address"), "", "MutedLabel"))
	var url := LineEdit.new()
	url.set_meta("id", "server_url")
	url.text = st.server_url
	url.text_changed.connect(func(t): Intents.set_server_url(t))
	menu.add_child(url)
	var ids: Array = Themes.ids()
	var label := "%s: %s" % [Words.render("ui.theme"), Themes.current.title]
	menu.add_child(Ui.button(label, "theme_toggle", func():
		Themes.use(ids[(ids.find(Themes.current.id) + 1) % ids.size()])))
	var calm := "%s: %s" % [Words.render("ui.reduced_motion"), Words.render("ui.on" if Themes.reduced_motion else "ui.off")]
	menu.add_child(Ui.button(calm, "reduced_motion_toggle", func():
		Themes.reduced_motion = not Themes.reduced_motion
		_build()))


## The logo, bobbing, over a glow that pulses. Null when the theme has no logo (the title is then plain text).
func _hero() -> Control:
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
		glow.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		glow.offset_left = -90
		glow.offset_right = 90
		glow.offset_top = -50
		glow.offset_bottom = 50
		glow.modulate = Themes.color_a("glow", 0.5)
		var add := CanvasItemMaterial.new()
		add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		glow.material = add
		holder.add_child(glow)
	var pic := Ui.picture(logo, Vector2.ZERO)
	pic.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.add_child(pic)
	if not p.is_empty() and not Themes.reduced_motion:
		var bob := float(p.get("bob_px", 6.0))
		var secs := float(p.get("bob_s", 2.8))
		var tw := holder.create_tween().set_loops()
		tw.tween_method(_bob.bind(pic), -bob, bob, secs).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		tw.tween_method(_bob.bind(pic), bob, -bob, secs).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		if glow != null:
			var pulse := float(p.get("glow_s", 1.9))
			var gt := glow.create_tween().set_loops()
			gt.tween_property(glow, "modulate:a", 0.85, pulse).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
			gt.tween_property(glow, "modulate:a", 0.35, pulse).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	return holder


func _bob(v: float, pic: Control) -> void:
	pic.offset_top = v
	pic.offset_bottom = v


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
