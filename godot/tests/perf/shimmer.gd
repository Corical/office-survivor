extends Control
## Does a slowly moving, shrunk picture shimmer? The logo is drawn at about half its size. It is moved down in quarter-pixel
## steps and, after each step, the picture is rendered and compared with the step before: for a picture that moves
## smoothly that difference is small and even; aliasing makes it large and jumpy. Compared for the plain linear filter
## and for the mipmapped one (needs the art imported with mipmaps).
##   godot --path godot res://tests/perf/shimmer.tscn
## Prints "SHIMMER <filter>: mean step difference .. , worst step .." (0..255 grey levels per pixel; lower is smoother).

const STEPS := 24
const STEP_PX := 0.25
const BOX := Rect2i(20, 100, 500, 260)


func _ready() -> void:
	await get_tree().process_frame
	get_window().size = Vector2i(540, 540)
	Themes.use("flash")
	var logo := Themes.texture("logo")
	var bg := ColorRect.new()
	bg.color = Themes.color("ink")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var pic := TextureRect.new()
	pic.texture = logo
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	pic.size = Vector2(500.0, 229.0)
	add_child(pic)
	await _frames(10)
	for mode in [["linear", CanvasItem.TEXTURE_FILTER_LINEAR], ["linear + mipmaps", CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS]]:
		pic.texture_filter = mode[1]
		var prev: Image = null
		var total := 0.0
		var worst := 0.0
		var n := 0
		for k in STEPS:
			pic.position = Vector2(20.0, 120.0 + float(k) * STEP_PX)
			await _frames(2)
			await RenderingServer.frame_post_draw
			var img := get_viewport().get_texture().get_image().get_region(BOX)
			if prev != null:
				var d := _diff(prev, img)
				total += d
				worst = maxf(worst, d)
				n += 1
			prev = img
		print("SHIMMER %s: mean step difference %.3f, worst step %.3f" % [mode[0], total / float(n), worst])
	print("SHIMMER DONE")
	get_tree().quit(0)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


## Mean absolute grey-level difference per pixel between two same-size images.
func _diff(a: Image, b: Image) -> float:
	var sum := 0.0
	var w := a.get_width()
	var h := a.get_height()
	for y in range(0, h, 2):
		for x in range(0, w, 2):
			sum += absf(a.get_pixel(x, y).get_luminance() - b.get_pixel(x, y).get_luminance())
	return sum / float(w * h / 4) * 255.0
