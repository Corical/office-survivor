extends Control
## Is the label on the lit face of every button variation? Renders each variation at the height the screens give it (normal
## and pressed), finds the FACE rows and the TEXT rows (capital letters), and prints where the text's middle sits against the
## face's middle. 0 px = optically centred; the sign says which way it is off. The run FAILS (exit 1) if any is off by more
## than TOLERANCE_PX. Wood buttons: the face is the bright wood read from a column beside the text. Flat buttons (the pick
## and the pill): the face is the whole box.
##   godot --path godot res://tests/perf/button_centre.tscn
## Prints "CENTRE <name> <state>: face rows a..b, text rows c..d, text middle is N px (above|below) the face middle".

const W := 300
const SAMPLE := "HHHH"              # capitals: the body of any word sits between their top and the baseline
const TOLERANCE_PX := 1.0

## name, theme variation, height the screens give it, kind: "wood_dark_text" | "wood_light_text" | "flat"
## Heights: Ui.button gives 72 to a PrimaryButton and 56 to everything else; the pill is its own padding (15 px text + 6 + 6).
const CASES := [
	["Create / Continue / Start / Back / sheet Create", "PrimaryButton", 72, "wood_dark_text"],
	["Settings / Join / Cancel / Leave / Copy / Advanced / sheet Public-Private", "Button", 56, "wood_light_text"],
	["Chosen (picked amount / sheet choice)", "ChosenButton", 56, "flat"],
	["Skip pill", "SkipPill", 44, "flat"],
]

var _failed := 0


func _ready() -> void:
	await get_tree().process_frame
	get_window().size = Vector2i(540, 960)               # the project's own size: one logical pixel is one screen pixel
	await get_tree().process_frame
	Themes.use("flash")
	theme = Themes.current.godot_theme
	var bg := ColorRect.new()
	bg.color = Themes.color("ink")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var y := 12
	var cases: Array = []
	for c in CASES:
		for pressed in [false, true]:
			var b := Button.new()
			b.text = SAMPLE
			b.theme_type_variation = c[1]
			b.toggle_mode = true
			b.button_pressed = pressed
			b.size = Vector2(W, c[2])
			b.position = Vector2(60, y)
			b.focus_mode = Control.FOCUS_NONE
			add_child(b)
			cases.append([c[0], c[3], "pressed" if pressed else "normal", Rect2i(60, y, W, c[2])])
			y += int(c[2]) + 14
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png("user://button_centre.png")
	for c in cases:
		_measure(img, c[0], c[1], c[2], c[3])
	print("CENTRE DONE: %d off by more than %.1f px" % [_failed, TOLERANCE_PX])
	get_tree().quit(1 if _failed > 0 else 0)


func _lum(p: Color) -> float:
	return (p.r * 0.3 + p.g * 0.59 + p.b * 0.11) * 255.0


func _measure(img: Image, label: String, kind: String, state: String, r: Rect2i) -> void:
	var face_x := r.position.x + 22                       # a column left of the text and right of the rim
	var top := -1
	var bottom := -1
	if kind == "flat":
		top = 0
		bottom = r.size.y - 1
	else:
		var bright := kind == "wood_dark_text"
		for yy in r.size.y:
			var l := _lum(img.get_pixel(face_x, r.position.y + yy))
			if l > (95.0 if bright else 55.0) and l < 235.0:
				if top < 0:
					top = yy
				bottom = yy
	if "--profile" in OS.get_cmdline_user_args() and state == "normal" and kind != "flat":
		var prof := ""
		for yy in r.size.y:
			prof += "%d " % int(_lum(img.get_pixel(face_x, r.position.y + yy)))
		print("PROFILE %s: %s" % [label.left(12), prof])
	var base := _lum(img.get_pixel(r.position.x + 40, r.position.y + (top + bottom) / 2))      # the face colour beside the text
	var t0 := -1
	var t1 := -1
	var inset := 6 if kind == "flat" else 0              # a flat box has a border line along its edge: not text
	var search_top := maxi(top, 0) + inset
	var search_bottom := (bottom - inset) if kind == "flat" else bottom + (6 if kind == "wood_light_text" else 0)    # light text may run a little past the lit face
	for yy in range(search_top, search_bottom + 1):
		for xx in range(r.position.x + 110, r.position.x + 190):
			var l := _lum(img.get_pixel(xx, r.position.y + yy))
			var is_text := false
			match kind:
				"wood_dark_text": is_text = l < 70.0
				"wood_light_text": is_text = l > 200.0
				_: is_text = absf(l - base) > 70.0
			if is_text:
				if t0 < 0:
					t0 = yy
				t1 = yy
				break
	if top < 0 or t0 < 0:
		_failed += 1
		print("CENTRE FAIL %s %s: could not find the face or the text (face %d..%d, text %d..%d)" % [label, state, top, bottom, t0, t1])
		return
	var face_mid := (top + bottom) / 2.0
	var text_mid := (t0 + t1) / 2.0
	var d := text_mid - face_mid
	var bad := absf(d) > TOLERANCE_PX
	if bad:
		_failed += 1
	print("CENTRE %s%s %s: face rows %d..%d, text rows %d..%d, text middle is %.1f px %s the face middle" % [
		"FAIL " if bad else "", label, state, top, bottom, t0, t1, absf(d), "below" if d > 0.0 else "above"])
