extends Control
## Is the label on the lit face of a wooden button? Renders buttons, finds the FACE rows (bright wood, read from a column
## beside the text) and the TEXT rows (dark capital letters), and prints where the text's middle sits against the face's
## middle. 0 px = optically centred; the sign says which way it is off.
##   godot --path godot res://tests/perf/button_centre.tscn
## Prints "CENTRE <variation> <state>: face rows a..b, text rows c..d, text middle is N px (above|below) the face middle".

const W := 300
const H := 72


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
	var y := 20
	var cases: Array = []
	for variation in ["PrimaryButton", "Button"]:
		for pressed in [false, true]:
			var b := Button.new()
			b.text = "HHHH"
			b.theme_type_variation = variation
			b.toggle_mode = true
			b.button_pressed = pressed
			b.size = Vector2(W, H)
			b.position = Vector2(60, y)
			b.focus_mode = Control.FOCUS_NONE
			add_child(b)
			cases.append([variation, "pressed" if pressed else "normal", Rect2i(60, y, W, H)])
			y += H + 24
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png("user://button_centre.png")
	for c in cases:
		_measure(img, c[0], c[1], c[2])
	print("CENTRE DONE")
	get_tree().quit(0)


func _lum(p: Color) -> float:
	return (p.r * 0.3 + p.g * 0.59 + p.b * 0.11) * 255.0


func _measure(img: Image, variation: String, state: String, r: Rect2i) -> void:
	var bright := variation == "PrimaryButton"           # dark text on light wood; light text on dark wood otherwise
	var face_x := r.position.x + 22                       # a column left of the text and right of the rim
	var top := -1
	var bottom := -1
	for yy in r.size.y:
		var l := _lum(img.get_pixel(face_x, r.position.y + yy))
		if l > (95.0 if bright else 55.0) and l < 235.0:
			if top < 0:
				top = yy
			bottom = yy
	var t0 := -1
	var t1 := -1
	for yy in range(maxi(top, 0), bottom + 1):
		for xx in range(r.position.x + 110, r.position.x + 190):
			var l := _lum(img.get_pixel(xx, r.position.y + yy))
			var is_text := l < 70.0 if bright else l > 200.0
			if is_text:
				if t0 < 0:
					t0 = yy
				t1 = yy
				break
	var face_mid := (top + bottom) / 2.0
	var text_mid := (t0 + t1) / 2.0
	var d := text_mid - face_mid
	print("CENTRE %s %s: face rows %d..%d, text rows %d..%d, text middle is %.1f px %s the face middle" % [variation, state,
		top, bottom, t0, t1, absf(d), "below" if d > 0.0 else "above"])
