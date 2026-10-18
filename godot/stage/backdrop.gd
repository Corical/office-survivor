class_name Backdrop
extends Control
## The persistent scene behind every screen: a far sky that drifts a little, twinkling stars, two layers of fog, the
## near trees framing the edges, embers rising off the camp and a flickering warm glow at the foot. It is built only
## from art ids (Themes.texture) and effect settings (Themes.fx "ambient" / "embers" / "flicker"); a theme with no art
## gets nothing drawn (the window's clear colour shows), and reduced motion freezes it into a still picture.
##
## Cost, for a mid phone: 3 canvas items redrawn per frame (about 70 draw calls) and one CPUParticles2D with at most
## `embers.amount` live particles.

## One painted layer. The Backdrop owns the drawing; the layer only calls it back.
class Layer extends Control:
	var painter: Callable

	func _draw() -> void:
		if painter.is_valid():
			painter.call(self)


const STAR_SEED := 20261018
const PAN_PER_SCREEN := 1.0                 # parallax steps per screen index (scaled by ambient.parallax_px)
const MAX_UPSCALE := 1.25                   # chosen: the most an art pixel is stretched on screen before the picture looks soft
const HORIZON_AT := 0.38                    # chosen: in a wide window the horizon sits this far down
const HORIZON_IN_ART := 0.635               # where the horizon is in the far art (row 1220 of 1920)
const NEAR_EDGE_L := 270.0                  # the near art's dark arch ends here on the left (art pixels from the left edge)
const NEAR_EDGE_R := 810.0                  # and here on the right
const NEAR_SOFT_PX := 150.0                 # chosen: width of the soft strip beside each edge (logical px)

var _ambient: Dictionary = {}
var _flicker: Dictionary = {}
var _back: Layer
var _front: Layer
var _glow: Layer
var _embers: CPUParticles2D
var _stars := PackedVector2Array()
var _star_phase := PackedFloat32Array()
var _star_rate := PackedFloat32Array()
var _star_size := PackedFloat32Array()
var _t := 0.0
var _pan := 0.0
var _pan_goal := 0.0
var _moving := false
var _tex_far: Texture2D
var _tex_near: Texture2D
var _tex_cloud: Texture2D
var _tex_star: Texture2D
var _tex_glow: Texture2D
var _add: CanvasItemMaterial
var _soft: Texture2D


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_add = CanvasItemMaterial.new()
	_add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_back = _layer(_paint_back)
	_embers = CPUParticles2D.new()
	_embers.emitting = false
	add_child(_embers)
	_front = _layer(_paint_front)
	_glow = _layer(_paint_glow)
	_glow.material = _add
	var rng := RandomNumberGenerator.new()
	rng.seed = STAR_SEED
	for i in 64:
		_stars.append(Vector2(rng.randf(), rng.randf() * 0.62))
		_star_phase.append(rng.randf() * TAU)
		_star_rate.append(rng.randf_range(0.8, 2.6))
		_star_size.append(rng.randf_range(7.0, 17.0))
	resized.connect(_on_resized)
	Themes.theme_changed.connect(func(_id): _setup())
	Themes.motion_changed.connect(func(_r): _setup())
	_setup()


func _layer(painter: Callable) -> Layer:
	var l := Layer.new()
	l.painter = painter
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(l)
	return l


## Read the theme again: the art, the effect settings and whether motion is allowed.
func _setup() -> void:
	_ambient = Themes.fx("ambient")
	_flicker = Themes.fx("flicker")
	_tex_far = Themes.texture("backdrop_far")
	_tex_near = Themes.texture("backdrop_near")
	_tex_cloud = Themes.texture("cloud")
	_tex_star = Themes.texture("fx_spark")
	_tex_glow = Themes.texture("campfire_glow")
	_soft = null
	_setup_embers()
	set_process(not _ambient.is_empty() or not _flicker.is_empty() or _embers.emitting)
	for l in [_back, _front, _glow]:
		l.queue_redraw()


func _setup_embers() -> void:
	var e := Themes.fx("embers")
	if e.is_empty() or _tex_star == null:
		_embers.emitting = false
		_embers.visible = false
		return
	_embers.visible = true
	_embers.texture = _tex_star
	_embers.material = _add
	_embers.amount = int(e.get("amount", 30))
	_embers.lifetime = float(e.get("lifetime", 6.0))
	_embers.preprocess = _embers.lifetime
	_embers.local_coords = false
	_embers.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	_embers.direction = Vector2(0, -1)
	_embers.spread = 22.0
	_embers.gravity = Vector2(0, -6)
	_embers.initial_velocity_min = 36.0
	_embers.initial_velocity_max = 110.0
	_embers.scale_amount_min = 0.12
	_embers.scale_amount_max = 0.42
	_embers.angle_max = 360.0
	_embers.angular_velocity_min = -90.0
	_embers.angular_velocity_max = 90.0
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.12, 0.7, 1.0])
	g.colors = PackedColorArray([Themes.color_a("ember", 0.0), Themes.color_a("gold", 0.95), Themes.color_a("ember", 0.55),
		Themes.color_a("loss", 0.0)])
	_embers.color_ramp = g
	_embers.emitting = true
	_place_embers()


func _place_embers() -> void:
	if _embers == null:
		return
	_embers.position = Vector2(size.x * 0.5, size.y + 10.0)
	_embers.emission_rect_extents = Vector2(size.x * 0.46, 6.0)


func _on_resized() -> void:
	_place_embers()
	for l in [_back, _front, _glow]:
		if l != null:
			l.queue_redraw()


## Called by the router when the screen changes: the far and near layers slide a little, as if the camera turned.
func pan_to(screen_index: int) -> void:
	_pan_goal = float(screen_index) * PAN_PER_SCREEN
	_moving = true


func has_art() -> bool:
	return _tex_far != null or _tex_near != null


func _process(delta: float) -> void:
	_t += delta
	if _moving:
		_pan = lerpf(_pan, _pan_goal, minf(1.0, delta * 2.2))
		if absf(_pan - _pan_goal) < 0.002:
			_pan = _pan_goal
			_moving = false
	_back.queue_redraw()
	_front.queue_redraw()
	if _tex_glow != null and not _flicker.is_empty():
		_glow.queue_redraw()


# ---------------- painting ----------------

## The horizontal shift of a layer: a slow sway plus the screen-to-screen pan, scaled by its depth (0 far .. 1 near).
func _shift(depth: float) -> float:
	var px := float(_ambient.get("parallax_px", 0.0))
	var drift := float(_ambient.get("drift_px", 0.0))
	return (sin(_t * 0.21) * drift + (_pan - 2.0) * px) * depth


## Draw `tex` to cover this control, anchored to the bottom, with `extra` pixels of margin each side for panning.
func _cover(c: CanvasItem, tex: Texture2D, shift_x: float, extra: float) -> void:
	var tw := float(tex.get_width())
	var th := float(tex.get_height())
	var s := maxf((size.x + extra * 2.0) / tw, size.y / th)
	var w := tw * s
	var h := th * s
	c.draw_texture_rect(tex, Rect2((size.x - w) * 0.5 + shift_x, size.y - h, w, h), false)


## How many screen pixels one logical unit is (the window stretch), so an art pixel's real on-screen size can be known.
func _screen_scale() -> float:
	return maxf(0.01, get_viewport().get_final_transform().get_scale().x) if is_inside_tree() else 1.0


## The most one art pixel may be stretched to on screen. Past this the picture goes soft, so a wide window gets more scene
## (mirrored at the sides, ground at the foot) instead of a bigger picture.
func _max_scale() -> float:
	return MAX_UPSCALE / _screen_scale()


## The cover scale this window would need for `tex` (width or height, whichever is larger).
func _cover_scale(tex: Texture2D, extra: float) -> float:
	return maxf((size.x + extra * 2.0) / float(tex.get_width()), size.y / float(tex.get_height()))


## `tex` into `r`, mirrored left-to-right when `flip` (a negative scale about the rectangle's own middle).
func _draw_flipped(c: CanvasItem, tex: Texture2D, r: Rect2, flip: bool) -> void:
	if not flip:
		c.draw_texture_rect(tex, r, false)
		return
	c.draw_set_transform(Vector2(r.position.x + r.size.x, r.position.y), 0.0, Vector2(-1.0, 1.0))
	c.draw_texture_rect(tex, Rect2(Vector2.ZERO, r.size), false)
	c.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## The far scene in a window too wide for the portrait art at a sharp scale: drawn at the capped scale with the horizon at a
## fixed height, and the art mirrored left and right as far as the window goes (a mirror is continuous at every seam).
func _far_wide(c: CanvasItem, tex: Texture2D, shift_x: float) -> void:
	var s := _max_scale()
	var w := float(tex.get_width()) * s
	var h := float(tex.get_height()) * s
	var top := minf(0.0, maxf(size.y * HORIZON_AT - h * HORIZON_IN_ART, size.y - h))
	var x0 := (size.x - w) * 0.5 + shift_x
	var first := -ceili(x0 / w) - 1
	var last := ceili((size.x - x0) / w) + 1
	for k in range(first, last + 1):
		var x := x0 + float(k) * w
		_draw_flipped(c, tex, Rect2(x, top, w, h), k % 2 != 0)


## A strip that is the night's shade at its left edge and clear at its right (flipped for the right-hand side).
func _soft_edge() -> Texture2D:
	if _soft == null:
		var g := Gradient.new()
		g.colors = PackedColorArray([Themes.color_a("ink", 0.62), Themes.color_a("ink", 0.0)])
		var t := GradientTexture2D.new()
		t.gradient = g
		t.fill_from = Vector2(0, 0)
		t.fill_to = Vector2(1, 0)
		t.width = 64
		t.height = 4
		_soft = t
	return _soft


func _paint_back(c: Layer) -> void:
	var margin := float(_ambient.get("parallax_px", 0.0)) * 3.0 + float(_ambient.get("drift_px", 0.0)) * 2.0 + 4.0
	if _tex_far != null:
		if _cover_scale(_tex_far, margin) > _max_scale():
			_far_wide(c, _tex_far, _shift(0.35))
		else:
			_cover(c, _tex_far, _shift(0.35), margin)
	if _tex_star != null and not _ambient.is_empty():
		var n := mini(int(_ambient.get("stars", 0)), _stars.size())
		var calm := Themes.reduced_motion
		var sx := _shift(0.2)
		var col := Themes.color("star")
		for i in n:
			var tw := 0.62 if calm else 0.3 + 0.7 * (0.5 + 0.5 * sin(_t * _star_rate[i] + _star_phase[i]))
			col.a = tw
			var sz := _star_size[i] * (0.8 + 0.3 * tw)
			var p := Vector2(_stars[i].x * size.x + sx, _stars[i].y * size.y)
			c.draw_texture_rect(_tex_star, Rect2(p - Vector2(sz, sz) * 0.5, Vector2(sz, sz)), false, col)
	if _tex_cloud != null and int(_ambient.get("fog_layers", 0)) > 0:
		var cw := size.x * 1.7
		var ch := cw * float(_tex_cloud.get_height()) / float(_tex_cloud.get_width())
		var layers := int(_ambient.get("fog_layers", 0))
		var calm := Themes.reduced_motion
		for k in layers:
			var speed := 7.0 + 5.0 * k
			var x := 0.0 if calm else fmod(_t * speed + k * cw * 0.5, cw)
			var y := size.y * (0.34 + 0.2 * k) - ch * 0.5
			var col := Themes.color_a("fog", 0.5 - 0.12 * k)
			c.draw_texture_rect(_tex_cloud, Rect2(x - cw + _shift(0.5), y, cw, ch), false, col)
			c.draw_texture_rect(_tex_cloud, Rect2(x + _shift(0.5), y, cw, ch), false, col)


func _paint_front(c: Layer) -> void:
	if _tex_near == null:
		return
	var margin := float(_ambient.get("parallax_px", 0.0)) * 3.0 + float(_ambient.get("drift_px", 0.0)) * 2.0 + 4.0
	if _cover_scale(_tex_near, margin) <= _max_scale():
		_cover(c, _tex_near, _shift(1.0), margin)
		return
	# a wide window: the framing leaves and palms hug the two edges at a sharp scale (the left half of the art on the left,
	# the right half on the right) and the middle stays open for the screen's own content
	var s := minf(_max_scale(), size.y / float(_tex_near.get_height()) * 2.0)
	var half := float(_tex_near.get_width()) * 0.5
	var h := float(_tex_near.get_height()) * s
	var sh := _shift(1.0)
	c.draw_texture_rect_region(_tex_near, Rect2(-margin + sh, size.y - h, half * s, h), Rect2(0, 0, half, _tex_near.get_height()))
	var right_x := size.x + margin + sh - half * s
	c.draw_texture_rect_region(_tex_near, Rect2(right_x, size.y - h, half * s, h), Rect2(half, 0, half, _tex_near.get_height()))
	# the art's dark arch ends in a straight edge: a soft strip beside it so the edge reads as shade, not as a wall
	var soft := _soft_edge()
	var strip := NEAR_SOFT_PX
	_draw_flipped(c, soft, Rect2(-margin + sh + NEAR_EDGE_L * s, size.y - h, strip, h), false)
	_draw_flipped(c, soft, Rect2(right_x + (NEAR_EDGE_R - half) * s - strip, size.y - h, strip, h), true)


func _paint_glow(c: Layer) -> void:
	if _tex_glow == null or _flicker.is_empty():
		return
	var k := float(_flicker.get("strength", 0.2))
	# three unrelated sines read as a flame's flicker; reduced motion holds the average
	var f := 0.0 if Themes.reduced_motion else (sin(_t * 7.3) * 0.5 + sin(_t * 12.9 + 1.3) * 0.3 + sin(_t * 3.1 + 0.4) * 0.2)
	var w := size.x * 1.7
	var h := w * float(_tex_glow.get_height()) / float(_tex_glow.get_width())
	var col := Themes.color_a("glow", 0.26 + k * 0.5 * f)
	c.draw_texture_rect(_tex_glow, Rect2((size.x - w) * 0.5, size.y - h * 0.62, w, h), false, col)
