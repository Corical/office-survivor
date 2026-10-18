extends Control
## A contact sheet of the flash theme: every icon, every button state, the inputs, the bar, the Stage colours.
##   godot_console --path godot res://themes/flash/tools_snapshot/sheet.tscn -- --out=<png path>

var out_path := ""


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_path = a.substr(6)
	await get_tree().process_frame
	Themes.use("flash")
	var th: Theme = Themes.current.godot_theme
	theme = th
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	get_window().size = Vector2i(1100, 900)
	var back := Panel.new()
	back.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var sb := th.get_stylebox("panel", "ScrollContainer")
	back.add_theme_stylebox_override("panel", sb)
	add_child(back)
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.offset_left = 20
	root.offset_top = 16
	root.add_theme_constant_override("separation", 16)
	add_child(root)

	var icons := HFlowContainer.new()
	icons.custom_minimum_size = Vector2(1060, 0)
	for id in Themes.current.icons:
		var cell := VBoxContainer.new()
		var tr := TextureRect.new()
		tr.texture = Themes.current.icons[id]
		tr.custom_minimum_size = Vector2(72, 72)
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		cell.add_child(tr)
		var l := Label.new()
		l.text = id
		l.theme_type_variation = "MutedLabel"
		l.custom_minimum_size = Vector2(110, 0)
		l.add_theme_font_size_override("font_size", 11)
		cell.add_child(l)
		icons.add_child(cell)
	root.add_child(icons)

	var states := HBoxContainer.new()
	states.add_theme_constant_override("separation", 14)
	for variation in ["Button", "PrimaryButton"]:
		for st in ["normal", "hover", "pressed", "disabled", "focus"]:
			var p := PanelContainer.new()
			p.add_theme_stylebox_override("panel", th.get_stylebox(st, variation))
			var l := Label.new()
			l.text = "%s" % st
			l.add_theme_font_override("font", th.get_font("font", variation))
			l.add_theme_font_size_override("font_size", th.get_font_size("font_size", variation))
			var key := "font_disabled_color" if st == "disabled" else ("font_pressed_color" if st == "pressed" else "font_color")
			l.add_theme_color_override("font_color", th.get_color(key, variation))
			p.add_child(l)
			states.add_child(p)
	root.add_child(states)

	var real := HBoxContainer.new()
	real.add_theme_constant_override("separation", 14)
	var b1 := Button.new()
	b1.text = "A real button"
	var b2 := Button.new()
	b2.text = "Lock in for the night"
	b2.theme_type_variation = "PrimaryButton"
	var b3 := Button.new()
	b3.text = "Disabled"
	b3.disabled = true
	var le := LineEdit.new()
	le.placeholder_text = "Camp code"
	le.custom_minimum_size = Vector2(200, 0)
	var le2 := LineEdit.new()
	le2.text = "KXQM"
	le2.custom_minimum_size = Vector2(120, 0)
	for c in [b1, b2, b3, le, le2]:
		real.add_child(c)
	root.add_child(real)

	var bars := HBoxContainer.new()
	for v in [0.9, 0.5, 0.12]:
		var pb := ProgressBar.new()
		pb.show_percentage = false
		pb.max_value = 1.0
		pb.value = v
		pb.custom_minimum_size = Vector2(300, 14)
		bars.add_child(pb)
	root.add_child(bars)

	var type_row := VBoxContainer.new()
	for pair in [["BigLabel", "You are Alias18"], ["HeaderLabel", "Rations: 7   180 s"], ["", "Body: Your watch caught Alias16 red-handed. They paid you 2."], ["MutedLabel", "PICK YOUR MOVE FOR TONIGHT   Night 4 of 10"]]:
		var l := Label.new()
		l.text = pair[1]
		if pair[0] != "":
			l.theme_type_variation = pair[0]
		type_row.add_child(l)
	root.add_child(type_row)

	var sw := HBoxContainer.new()
	sw.add_theme_constant_override("separation", 10)
	for n in ["text", "home", "home_me", "food", "loss", "shield", "marked"]:
		var cr := ColorRect.new()
		cr.color = th.get_color(n, "Stage")
		cr.custom_minimum_size = Vector2(70, 40)
		var l := Label.new()
		l.text = n
		l.add_theme_font_size_override("font_size", 12)
		l.add_theme_color_override("font_color", Color.BLACK)
		cr.add_child(l)
		sw.add_child(cr)
	root.add_child(sw)

	for i in 5:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	print("save ", out_path, " ", img.save_png(out_path))
	get_tree().quit(0)
