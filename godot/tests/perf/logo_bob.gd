extends Control
## Does the title logo move smoothly? Mounts the real title screen, captures every frame of one full bob (6 s), finds the
## logo's vertical position in each frame (the brightness-weighted middle of its bright pixels, so a half-pixel move shows),
## and writes a slit-scan picture (one pixel column of the logo per frame, side by side: a smooth bob is a smooth wave, a
## snapped one is a staircase). Prints the longest hold (frames in a row at the same position while the bob is moving) and the
## biggest single-frame jump; FAILS (exit 1) if the logo ever holds for more than MAX_HOLD frames or jumps more than MAX_JUMP px.
##   godot --path godot res://tests/perf/logo_bob.tscn -- --out=<dir> [--name=before]

const FRAMES := 400
const MAX_HOLD := 3                 # chosen: at 60 fps the bob moves at most 0.13 px a frame, so a smooth one never repeats long
const MAX_JUMP := 0.5               # chosen: whole-pixel snapping jumps by 1.0; half a pixel is already invisible
const STRIP := 12                   # half-width of the column strip read from the logo's centre
const BRIGHT := 200.0              # luminance above which a pixel belongs to the logo's lettering and rim

const MOVING_PX := 0.06            # px a frame (smoothed over 10 frames) above which the logo must be seen to move every frame
const WINDOW := 12                # rows either side of the first frame's edge searched in later frames
var _anchor := -1
var _out := "user://"
var _name := "logo"


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			_out = a.substr(6)
		elif a.begins_with("--name="):
			_name = a.substr(7)
	await get_tree().process_frame
	get_window().size = Vector2i(540, 960)
	await get_tree().process_frame
	Themes.use("flash")
	Themes.reduced_motion = false
	theme = Themes.current.godot_theme
	var bg := ColorRect.new()
	bg.color = Themes.color("ink")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var title := TitleScreen.new()
	add_child(title)
	await get_tree().create_timer(1.2).timeout            # the menu pops in first
	var logo := Ui.find(title, "logo") as Control
	if logo == null:
		print("LOGO FAIL: no logo on the title")
		get_tree().quit(1)
		return
	var rect := logo.get_global_rect()
	var cx := int(rect.position.x + rect.size.x * 0.5)
	var y0 := int(rect.position.y) - 20
	var y1 := int(rect.position.y + rect.size.y) + 20
	var scan := Image.create(FRAMES, y1 - y0, false, Image.FORMAT_RGB8)
	var ys: Array = []
	for f in FRAMES:
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		var lum: Array = []
		for yy in range(y0, y1):
			var l := 0.0
			for xx in range(cx - STRIP, cx + STRIP + 1):
				var p := img.get_pixel(xx, yy)
				l += (p.r * 0.3 + p.g * 0.59 + p.b * 0.11) * 255.0
			lum.append(l / float(2 * STRIP + 1))
			scan.set_pixel(f, yy - y0, img.get_pixel(cx, yy))
		ys.append(_edge(lum) + float(y0))
	scan.save_png(_out.path_join("%s_slitscan.png" % _name))
	_report(ys)


## Sub-pixel position of the steepest brightness change in a column (the logo's top edge): the row with the largest
## difference, refined by a parabola through it and its two neighbours. A glow behind the logo is smooth, so it cannot move this.
func _edge(lum: Array) -> float:
	var best := 1
	var best_g := 0.0
	var g: Array = [0.0]
	for i in range(1, lum.size() - 1):
		g.append(absf(lum[i + 1] - lum[i - 1]))
	# the first frame finds the edge anywhere; later frames look only near it (the bob is far smaller than the window)
	var from := 1 if _anchor < 0 else maxi(1, _anchor - WINDOW)
	var to := lum.size() - 2 if _anchor < 0 else mini(lum.size() - 2, _anchor + WINDOW)
	for i in range(from, to + 1):
		if g[i] > best_g:
			best_g = g[i]
			best = i
	if _anchor < 0:
		_anchor = best
	if best <= 1 or best >= g.size() - 1:
		return float(best)
	var a: float = g[best - 1]
	var b: float = g[best]
	var c: float = g[best + 1]
	var denom := a - 2.0 * b + c
	return float(best) + (0.5 * (a - c) / denom if absf(denom) > 0.0001 else 0.0)


func _report(ys: Array) -> void:
	var longest := 0
	var run := 0
	var biggest := 0.0
	var moving := 0
	for i in range(1, ys.size()):
		var d := absf(ys[i] - ys[i - 1])
		biggest = maxf(biggest, d)
		# a hold only counts where the bob should be moving: near the top and bottom of the swing it slows to a stop on its own
		var lo_i := maxi(0, i - 5)
		var hi_i := mini(ys.size() - 1, i + 5)
		var expected := absf(ys[hi_i] - ys[lo_i]) / float(hi_i - lo_i)
		if d < 0.02 and expected > MOVING_PX:
			run += 1
			longest = maxi(longest, run)
		else:
			run = 0
		if d >= 0.02:
			moving += 1
	var lo := 1e9
	var hi := -1e9
	for y in ys:
		lo = minf(lo, y)
		hi = maxf(hi, y)
	var bad := longest > MAX_HOLD or biggest > MAX_JUMP
	print("LOGO %s: %d frames, travel %.2f px, longest hold %d frames, biggest jump %.2f px, moved on %d of %d frames -> %s" % [
		_name, FRAMES, hi - lo, longest, biggest, moving, FRAMES - 1, "FAIL" if bad else "ok"])
	get_tree().quit(1 if bad else 0)
