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
## Heights: Ui.button gives 72 to a PrimaryButton and Ui.MIN_ART_BUTTON_HEIGHT (64) to every other wood button; the chosen
## pick is flat (56); the pill is its own padding (15 px text + 6 + 6).
const CASES := [
	["Create / Continue / Start / Back / sheet Create", "PrimaryButton", 72, "wood_dark_text"],
	["Settings / Join / Cancel / Leave / Copy / Advanced / sheet Public-Private", "Button", 64, "wood_light_text"],
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
	await _studs(bg)
	get_tree().quit(1 if _failed > 0 else 0)


## The brass studs at the two ends of a wood button must be ROUND. Renders each wood variation at 2x (the control scaled 2x,
## so the art is drawn at twice the pixels), cuts out each end's stud (the pixels that differ strongly from the wood around
## them, in a window beside the end cap) and prints its width / height; FAILS outside STUD_RATIO_MIN..STUD_RATIO_MAX.
const STUD_DARK := 55.0                              # brightness below which a pixel belongs to the stud's dark ring
const STUD_W := 160
const STUD_RATIO_MIN := 0.8
const STUD_RATIO_MAX := 1.25
const STUD_CASES := [["PrimaryButton", 72], ["Button", 64], ["Button", 72]]       # the heights the screens give wood buttons


func _studs(bg: Control) -> void:
	for c in get_children():
		if c != bg:
			remove_child(c)
			c.queue_free()
	var y := 6
	var cases: Array = []
	for c in STUD_CASES:
		for pressed in [false, true]:
			var b := Button.new()
			b.text = ""
			b.theme_type_variation = c[0]
			b.toggle_mode = true
			b.button_pressed = pressed
			b.size = Vector2(STUD_W, c[1])
			b.scale = Vector2(2, 2)
			b.position = Vector2(20, y)
			b.focus_mode = Control.FOCUS_NONE
			add_child(b)
			cases.append([c[0], int(c[1]), pressed, Rect2i(20, y, STUD_W * 2, int(c[1]) * 2)])
			y += int(c[1]) * 2 + 6
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png("user://button_studs_2x.png")
	for k in cases:
		for end in ["left", "right"]:
			_stud(img, k, end)
	print("STUDS DONE: %d off" % [_failed])


func _stud(img: Image, k: Array, end: String) -> void:
	var r: Rect2i = k[3]
	# Where the stud sits (measured on the art): about 12.5 px in from the end and 25 px down, in the top edge of the art, at
	# every height. The window (logical px 4..22 across, 14..36 down, doubled) holds the stud and some plain wood, never the
	# cap's outline.
	var win_w := 47
	var x0 := r.position.x + 11 if end == "left" else r.end.x - 11 - win_w
	var y0 := r.position.y + 24
	var y1 := r.position.y + 100                          # the pressed stud sits about 12 px (2x) lower
	var lums: Array = []
	for yy in range(y0, y1):
		for xx in range(x0, x0 + win_w):
			lums.append(_lum(img.get_pixel(xx, yy)))
	var sorted := lums.duplicate()
	sorted.sort()
	var median: float = sorted[sorted.size() / 2]
	# the stud is the biggest connected blob of pixels that differ strongly from the wood around it (scattered grain and
	# gradient pixels are other, smaller blobs)
	var win_h := y1 - y0
	var mask := PackedByteArray()
	mask.resize(win_w * win_h)
	for i in lums.size():
		mask[i] = 1 if lums[i] < STUD_DARK else 0           # the stud's dark ring (the same in every tint and state)
	var minx := 0
	var maxx := -1
	var miny := 0
	var maxy := -1
	var count := 0
	var seen := PackedByteArray()
	seen.resize(win_w * win_h)
	for start in mask.size():
		if mask[start] == 0 or seen[start] == 1:
			continue
		var stack: Array = [start]
		seen[start] = 1
		var n := 0
		var bx0 := win_w
		var bx1 := -1
		var by0 := win_h
		var by1 := -1
		while not stack.is_empty():
			var p: int = stack.pop_back()
			var px := p % win_w
			var py := p / win_w
			n += 1
			bx0 = mini(bx0, px)
			bx1 = maxi(bx1, px)
			by0 = mini(by0, py)
			by1 = maxi(by1, py)
			for dy in [-1, 0, 1]:
				for dx in [-1, 0, 1]:
					var qx: int = px + dx
					var qy: int = py + dy
					if qx < 0 or qy < 0 or qx >= win_w or qy >= win_h:
						continue
					var q := qy * win_w + qx
					if mask[q] == 1 and seen[q] == 0:
						seen[q] = 1
						stack.append(q)
		# a blob touching the window's edge is the cap's outline, a seam or the rim highlight, not a stud sitting in plain wood
		var touches := bx0 == 0 or bx1 == win_w - 1 or by0 == 0 or by1 == win_h - 1
		if n > count and not touches and n >= 40:
			count = n
			minx = bx0
			maxx = bx1
			miny = by0
			maxy = by1
	var name := "%s %d px %s %s stud" % [k[0], k[1], "pressed" if k[2] else "normal", end]
	if count < 12:
		_failed += 1
		print("STUD FAIL %s: not found (%d pixels differ from the wood)" % [name, count])
		return
	var w := float(maxx - minx + 1)
	var h := float(maxy - miny + 1)
	var ratio := w / h
	var bad := ratio < STUD_RATIO_MIN or ratio > STUD_RATIO_MAX
	if bad:
		_failed += 1
	print("STUD %s%s: %dx%d px at 2x, width/height %.2f (%d px)" % ["FAIL " if bad else "", name, int(w), int(h), ratio, count])


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
