class_name Stage
extends Control
## The reveal as a picture: one home per player around a campfire (me at the bottom), and the night's beats played on
## it by the pure Timeline. Knows beat kinds and endpoints only: no game words, no colours and no asset paths (art by id
## from Themes.texture, colours by name from Themes.color / the "Stage" type, effect settings from Themes.fx), and no
## ordering that could say who joined when (homes are placed from the alias-sorted roster).
##
## Two ways to draw, chosen by what the theme has: with art (a hut texture) each home is a hut with its owner's avatar and
## a name plate, the fire burns in the middle and each beat plays real effects (crumbs in arcs, a shield bubble, shake,
## washes); with no art the homes are plain discs and beats are simple shapes. Effects are layered ON TOP of the
## Timeline's beat progress: nothing here changes when a beat starts or ends.
##
## Privacy by construction: another player's food is never drawn as a number (a band word and icon, from the model), and an
## unnamed actor (@offstage) comes in from outside the ring, belonging to no home.

const ME := "@me"                       # the adapter's markers for "I" and "someone unnamed" (a test keeps these equal)
const OFFSTAGE := "@offstage"
const PLATE_GAP := 2.0                  # between a hut and its plate
const PLATE_LINE_GAP := 2.0
const PLATE_MIN_MARGIN_X := 12.0        # a plate's padding never drops below this, whatever the style says
const PLATE_MIN_MARGIN_Y := 7.0
const PLATE_DEFAULT_EDGE := 3.0         # the rim of a plate when the theme does not say (constant plate_edge)
const ICON_PX := 20.0
const ICON_GAP := 6.0
const SHAKE_DECAY := 46.0               # chosen: pixels of shake lost per second
const FLASH_DECAY := 2.6                # chosen: flash alpha lost per second
const CAPTION_H := 60.0                # chosen: the strip at the top that holds the line being played
const SKIP_ROOM := 130.0               # chosen: space kept free at the top right for the Skip pill

var _roster: Array = []
var _beats: Array = []
var _timeline: Timeline
var _model: Dictionary = {}
var _pos := {}                          # alias -> Vector2, and ME -> my position
var _food_mine := 0
var _applied := 0                       # how many beats' effects are already in _food_mine / _shields
var _shields := {}
var _out := {}                          # aliases currently marked as outcasts by a finished status beat

var _round := -1
var _me_alias := ""
var _hut_px := 120.0
var _rich := false                      # the theme has art: draw huts, avatars, the fire
var _tex := {}                          # the art this Stage uses, fetched once
var _avatars := {}
var _order: Array = []                  # roster, back to front (by y), for drawing
var _plates := {}                       # alias -> {rect, items, style}: each plate's frame and what sits on it
var _pool := FxPool.new()
var _fx: Backdrop.Layer                 # the additive layer: glows, sparks, rings
var _t := 0.0
var _seen_idx := -1
var _shake := 0.0
var _shake_off := Vector2.ZERO
var _flash := 0.0
var _hit_pause := 0.0
var _bubble := {}                       # alias -> 0..1, how far its shield bubble has grown
var _dark := {}                         # alias -> 0..1, how far its hut has gone dark
var _food_shown := 0.0
var _food_pop := 0.0
var _shown_int := 0
var _caption_idx := -2
var _caption := ""
var _caption_size := Vector2.ZERO


func _ready() -> void:
	clip_contents = true
	custom_minimum_size = Vector2(0, 360)
	resized.connect(_layout)
	Feed.model_changed.connect(_on_model)
	_fx = Backdrop.Layer.new()
	_fx.painter = _paint_additive
	_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fx.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_fx.material = add
	add_child(_fx)
	_load_art()
	_load()


func _on_model(kind: String, _m: Dictionary) -> void:
	if kind == "reveal":
		_load()


func _load_art() -> void:
	_tex = {}
	for pair in [["hut", "hut"], ["hut_me", "hut_me"], ["fire", "campfire"], ["glow", "campfire_glow"],
			["shield", "fx_shield"], ["ring", "fx_ring"], ["spark", "fx_spark"], ["crumb", "fx_crumb"]]:
		_tex[pair[0]] = Themes.texture(pair[1])
	_rich = _tex.hut != null


func _load() -> void:
	_model = Feed.models.get("reveal", {})
	if _model.is_empty():
		return
	_roster = _model.roster
	_beats = _model.beats
	_timeline = Feed.player.timeline
	_shields = {}
	_out = {}
	_applied = 0
	var t: Dictionary = _model.totals
	var animated := _timeline != null and not _timeline.finished and t.before != null
	_food_mine = int(t.before) if animated else int(t.after if t.after != null else (t.before if t.before != null else 0))
	if _timeline != null and (_timeline.finished or t.before == null):
		_applied = _beats.size()                  # snapped: effects are already in the final numbers
	_me_alias = ""
	for e in _roster:
		if e.is_me:
			_me_alias = e.alias
	_avatars = Ui.avatar_ids(_roster.map(func(e): return e.alias))
	var rnd := int(_model.round)
	if rnd != _round:                             # a new night: forget the last one's visuals (the same night pushed again keeps its)
		_round = rnd
		_seen_idx = -1
		_pool.clear()
		_bubble = {}
		_dark = {}
		_hit_pause = 0.0
		_shake = 0.0
		_flash = 0.0
		_food_shown = float(_food_mine)
		_shown_int = _food_mine
	_layout()
	queue_redraw()


func _layout() -> void:
	_pos = {}
	# The ring fills the Stage. Plates go above the huts in the top half and below them in the bottom half, so the
	# vertical room needed is: caption strip + plate + hut at the top, hut + plate at the bottom. The centre is chosen so
	# both ends have the same room; the radius is whatever is left, so a tall desktop Stage gets a big ring.
	var tall := clampf((size.y - 400.0) / 300.0, 0.0, 1.0)                 # a tall Stage (desktop) can afford bigger huts
	var hs := clampf(minf(size.x * 0.27, size.y * lerpf(0.2, 0.27, tall)), 64.0, 200.0)
	_hut_px = hs
	var plate := _plate_height() + PLATE_GAP
	var c := Vector2(size.x * 0.5, (size.y + CAPTION_H + 0.06 * hs) * 0.5)
	var ry := maxf(36.0, minf(size.y - 4.0 - plate - hs * 0.5 - c.y, c.y - CAPTION_H - plate - hs * 0.56))
	var rx := maxf(40.0, minf(size.x * 0.5 - hs * 0.5 - 10.0, ry * 1.8))
	var others: Array = _roster.filter(func(e): return not e.is_me)
	for e in _roster:
		if e.is_me:
			_pos[e.alias] = c + Vector2(0, ry)
			_pos[ME] = c + Vector2(0, ry)
	for i in others.size():
		var angle := PI / 2.0 + TAU * float(i + 1) / float(others.size() + 1)
		_pos[others[i].alias] = c + Vector2(cos(angle) * rx, sin(angle) * ry)
	set_meta("centre", c)
	set_meta("radius", (rx + ry) * 0.5)
	_order = _roster.duplicate()
	_order.sort_custom(func(a, b): return _pos[a.alias].y < _pos[b.alias].y)
	_build_plates()


## The plates. One layout per home, built once per layout (and again when my food number changes digits), and used by BOTH
## the drawing and the clearance check, so what is checked is what is drawn. A plate is sized from its content plus the
## frame style's own content margins, and grows (up to a share of the Stage) rather than let anything touch its rim; a
## name or word too long for that is cut with an ellipsis.
func _build_plates() -> void:
	_plates = {}
	for e in _roster:
		_build_plate(e)


func _build_plate(e: Dictionary) -> void:
	var at: Vector2 = _pos[e.alias]
	var font := get_theme_default_font()
	var ps := _plate_size()
	var sb := get_theme_stylebox("plate_me" if e.is_me else "plate", "Stage")
	var mx := maxf(sb.get_margin(SIDE_LEFT), PLATE_MIN_MARGIN_X)
	var my := maxf(sb.get_margin(SIDE_TOP), PLATE_MIN_MARGIN_Y)
	var room := maxf(size.x * 0.42, 130.0) - mx * 2.0
	var name_s := _fit(font, e.alias, ps + 1, room)
	var name_w := font.get_string_size(name_s, HORIZONTAL_ALIGNMENT_LEFT, -1, ps + 1).x
	var icon: Texture2D = null
	var text2 := ""
	if e.is_me:
		icon = Themes.icon("food")
		text2 = str(_shown_int)
	elif e.band != "":
		icon = Themes.icon(e.band)
		text2 = Words.render(e.band)
	var size2 := ps + 8 if e.is_me else ps - 1          # my number is reserved room at the biggest it pops to
	var icon_room := ICON_PX + ICON_GAP if icon != null else 0.0
	text2 = _fit(font, text2, size2, room - icon_room)
	var tw2 := font.get_string_size(text2, HORIZONTAL_ALIGNMENT_LEFT, -1, size2).x if text2 != "" else 0.0
	var w2 := icon_room + tw2
	var w := maxf(_hut_px * 0.95, maxf(name_w, w2) + mx * 2.0)
	var h := _plate_height()
	var l1h := font.get_height(ps + 1)
	var l2h := h - my * 2.0 - l1h - PLATE_LINE_GAP
	var centre: Vector2 = get_meta("centre", size * 0.5)
	var above: bool = at.y < centre.y - _hut_px * 0.4      # homes in the top half carry their plate above, clear of the fire
	var py := at.y - _hut_px * 0.56 - h - PLATE_GAP if above else at.y + _hut_px * 0.5 + PLATE_GAP
	var px := clampf(at.x - w * 0.5, 4.0, maxf(4.0, size.x - w - 4.0))
	var items: Array = []
	var nx := px + (w - name_w) * 0.5
	items.append({"kind": "text", "what": "name", "text": name_s, "size": ps + 1, "tint": "text",
		"rect": Rect2(nx, py + my, name_w, l1h), "base": Vector2(nx, py + my + font.get_ascent(ps + 1))})
	var top2 := py + my + l1h + PLATE_LINE_GAP
	var x := px + (w - w2) * 0.5
	if icon != null:
		items.append({"kind": "icon", "what": "icon", "tex": icon,
			"rect": Rect2(x, top2 + (l2h - ICON_PX) * 0.5, ICON_PX, ICON_PX)})
		x += icon_room
	if text2 != "":
		var th := font.get_height(size2)
		var ty := top2 + (l2h - th) * 0.5
		items.append({"kind": "text", "what": "number" if e.is_me else "band", "text": text2, "size": size2,
			"tint": "gain" if e.is_me else "text", "number": e.is_me,
			"rect": Rect2(x, ty, tw2, th), "base": Vector2(x, ty + font.get_ascent(size2))})
	_plates[e.alias] = {"rect": Rect2(px, py, w, h), "items": items, "style": sb}


## `s` cut with an ellipsis until it fits `room` pixels at `px` size (unchanged when it already fits).
static func _fit(font: Font, s: String, px: int, room: float) -> String:
	if font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x <= room:
		return s
	var cut := s
	while cut.length() > 1 and font.get_string_size(cut + "...", HORIZONTAL_ALIGNMENT_LEFT, -1, px).x > room:
		cut = cut.substr(0, cut.length() - 1)
	return cut.strip_edges() + "..."


func _plate_size() -> int:
	var ps := get_theme_font_size("plate_size", "Stage")
	return ps if ps > 0 else maxi(12, get_theme_default_font_size() - 3)


## Every plate is as tall as its two lines plus the style's top and bottom margins.
func _plate_height() -> float:
	var font := get_theme_default_font()
	var ps := _plate_size()
	var sb := get_theme_stylebox("plate", "Stage")
	var my := maxf(sb.get_margin(SIDE_TOP), PLATE_MIN_MARGIN_Y)
	return my * 2.0 + font.get_height(ps + 1) + PLATE_LINE_GAP + maxf(font.get_height(ps + 8), ICON_PX)


func _process(delta: float) -> void:
	if _timeline == null or _model.is_empty():
		return
	var dt := delta
	if _hit_pause > 0.0:                          # the impact holds the world for a moment; the shake still plays
		_hit_pause -= delta
		dt = 0.0
	if dt > 0.0:
		_timeline.advance(dt * 1000.0)
	_apply_done()
	_detect_beat()
	_animate(dt, delta)
	queue_redraw()
	_fx.queue_redraw()


## Fold the effects of every beat that has finished into what is drawn (my food, shields, outcasts).
func _apply_done() -> void:
	var upto: int = _beats.size() if _timeline.finished else _timeline.index
	while _applied < upto:
		var b: Dictionary = _beats[_applied]
		match b.kind:
			"move_resource":
				if b.to == ME:
					_food_mine += int(b.amount_in)
				if b.from == ME:
					_food_mine -= int(b.amount_out)
			"total":
				_food_mine = int(b.amount_in)
			"shield_on":
				_shields[b.to] = true
			"shield_off":
				_shields.erase(b.to)
			"status":
				if b.style == "enter":
					_out[b.to] = true
				else:
					_out.erase(b.to)
		_applied += 1


## What the Stage is showing, for tests: the current beat and my displayed food.
func describe() -> Dictionary:
	var cur: Dictionary = _timeline.current() if _timeline != null else {}
	return {"beat": cur.get("kind", ""), "from": cur.get("from", ""), "to": cur.get("to", ""), "my_food": _food_mine,
		"finished": _timeline == null or _timeline.finished, "applied": _applied}


func where(endpoint: String, toward: String = "") -> Vector2:
	if endpoint == OFFSTAGE:
		var c: Vector2 = get_meta("centre", size / 2.0)
		var dir := ((_pos.get(toward, c) as Vector2) - c).normalized()
		if dir == Vector2.ZERO:
			dir = Vector2.UP
		return c + dir * float(get_meta("radius", 100.0)) * 2.4          # outside the ring, belonging to nobody
	return _pos.get(endpoint, size / 2.0)


# ---------------- animation state (never changes beat timing) ----------------

## A beat just became the current one: start its effects (once).
func _detect_beat() -> void:
	var idx: int = _beats.size() if _timeline.finished else _timeline.index
	if idx == _seen_idx:
		return
	_seen_idx = idx
	if idx < _beats.size() and not _timeline.finished:
		_on_beat(_beats[idx])


func _animate(dt: float, real: float) -> void:
	_t += real
	_pool.update(dt)
	for e in _roster:
		var a: String = e.alias
		_bubble[a] = move_toward(float(_bubble.get(a, 0.0)), 1.0 if _shield_goal(e) else 0.0, dt * 2.6)
		_dark[a] = move_toward(float(_dark.get(a, 0.0)), 1.0 if _outcast_goal(e) else 0.0, dt * 2.0)
	var goal := float(_food_mine)
	if not _timeline.finished:
		var cur := _timeline.current()
		match cur.get("kind"):
			"move_resource":
				if cur.to == ME:
					goal += float(cur.amount_in)
				if cur.from == ME:
					goal -= float(cur.amount_out)
			"total":
				goal = float(cur.amount_in)
	_food_shown = move_toward(_food_shown, goal, dt * maxf(6.0, absf(goal - _food_shown) * 3.5))
	var n := int(roundf(_food_shown))
	if n != _shown_int:
		_shown_int = n
		_food_pop = 1.0
		for e in _roster:
			if e.is_me:
				_build_plate(e)                       # the number may have changed digits: the plate grows or shrinks to hold it
	_food_pop = maxf(0.0, _food_pop - real * 4.5)
	if _shake > 0.0:
		_shake = maxf(0.0, _shake - real * SHAKE_DECAY)
		_shake_off = Vector2(sin(_t * 63.0), cos(_t * 71.0)) * _shake
	else:
		_shake_off = Vector2.ZERO
	_flash = maxf(0.0, _flash - real * FLASH_DECAY)
	_fx.position = _shake_off


func _shield_goal(e: Dictionary) -> bool:
	var on: bool = _shields.has(e.alias) or (e.is_me and _shields.has(ME))
	if _timeline != null and not _timeline.finished:
		var cur := _timeline.current()
		var k: String = cur.get("kind", "")
		if k == "shield_on" or k == "shield_off":
			if cur.to == e.alias or (e.is_me and cur.to == ME):
				on = k == "shield_on"
	return on


func _outcast_goal(e: Dictionary) -> bool:
	var on: bool = _out.has(e.alias) or (e.is_me and _out.has(ME))
	if _timeline != null and not _timeline.finished:
		var cur := _timeline.current()
		if cur.get("kind") == "status" and (cur.to == e.alias or (e.is_me and cur.to == ME)):
			on = cur.style == "enter"
	return on


# ---------------- starting a beat's effects ----------------

func _on_beat(b: Dictionary) -> void:
	if not _rich:
		return
	var c: Vector2 = get_meta("centre", size * 0.5)
	var from_pos := where(b.from, b.to)
	var to_pos := where(b.to, b.from)
	var at := to_pos if b.to != OFFSTAGE else c
	match b.kind:
		"move_resource":
			_crumbs(b, from_pos, to_pos)
		"blocked":
			_pop_bubble(at)
			_ring(at, "shield", _hut_px * 0.5, _hut_px * 1.7, 0.5)
			_burst(at, "gold")
			_impact(b)
		"empty":
			_puffs(at)
		"learn":
			_spark_flight(from_pos, to_pos)
		"marked":
			_ring(at, "mark", _hut_px * 0.4, _hut_px * 1.5, 0.6)
			_ring(at, "mark", _hut_px * 0.3, _hut_px * 1.1, 0.6, 0.18)
			_burst(at, "mark")
		"status":
			_ring(at, "loss", _hut_px * 0.4, _hut_px * 1.4, 0.6)
			_burst(at, "loss")
		"shield_on":
			_ring(at, "shield", _hut_px * 0.6, _hut_px * 1.6, 0.5)
		"shield_off":
			_ring(at, "shield", _hut_px * 1.4, _hut_px * 0.8, 0.5)
		"camp":
			_ring(c, "warm", _hut_px * 0.6, _hut_px * 3.0, 0.9)
			_burst(c, "warm")
		"charm":
			_burst(at, "gold")
			_ring(at, "gold", _hut_px * 0.3, _hut_px * 1.2, 0.6)
		"quiet":
			_ring(c, "glow", _hut_px * 0.8, _hut_px * 2.4, 0.9)
		"total":
			pass                           # the count-up of my food is animated from the beat's progress, not spawned
		_:                               # a happening in the world, or a beat this Stage has no special effect for
			_burst(c, "gold")
			_ring(c, "glow", _hut_px * 0.6, _hut_px * 1.8, 0.7)


## Food leaving one place for another: crumbs in arcs with trails, "+N" where it lands and "-N" where it came from.
func _crumbs(b: Dictionary, from_pos: Vector2, to_pos: Vector2) -> void:
	var f := Themes.fx("stage.crumbs")
	var crumb: Texture2D = _tex.crumb
	var amount_in := int(b.amount_in)
	var amount_out := int(b.amount_out)
	var fl := Themes.fx("stage.float")
	var rise := float(fl.get("rise", 50.0))
	var life := float(fl.get("time", 1.0))
	var tint := _tint_for(String(b.style))
	if f.is_empty() or crumb == null:
		# reduced motion or no crumb art: the numbers still show, the crumbs do not fly
		if b.to != OFFSTAGE and amount_in > 0 and not fl.is_empty():
			_pool.spawn_text("+%d" % amount_in, to_pos + Vector2(0, -_hut_px * 0.55), rise, 0.35, life, Themes.color("gain"))
		if b.from != OFFSTAGE and amount_out > 0 and not fl.is_empty():
			_pool.spawn_text("-%d" % amount_out, from_pos + Vector2(0, -_hut_px * 0.55), rise, 0.0, life, Themes.color("loss"))
		return
	var n := mini(maxi(amount_in, amount_out), int(f.get("max", 8)))
	var flight := float(f.get("flight", 0.6))
	var stagger := float(f.get("stagger", 0.07))
	var dist := from_pos.distance_to(to_pos)
	var lift := dist * float(f.get("arc", 0.3))
	var sz := float(f.get("size", 24.0))
	for i in n:
		var side := -1.0 if i % 2 == 0 else 1.0
		var ctrl := (from_pos + to_pos) * 0.5 + Vector2(side * lift * (0.4 + 0.1 * float(i % 3)), -lift)
		_pool.spawn(FxPool.Kind.FLIGHT, crumb, from_pos, to_pos, ctrl, float(i) * stagger, flight, sz, sz * 0.8, tint,
			2.0 * side, true)
	var landed := flight + float(maxi(n - 1, 0)) * stagger
	if b.to != OFFSTAGE and amount_in > 0:
		_pool.spawn_text("+%d" % amount_in, to_pos + Vector2(0, -_hut_px * 0.55), rise, landed * 0.9, life, Themes.color("gain"))
	if b.from != OFFSTAGE and amount_out > 0:
		_pool.spawn_text("-%d" % amount_out, from_pos + Vector2(0, -_hut_px * 0.55), rise, 0.0, life, Themes.color("loss"))


## The colour a style of movement is tinted by (the theme maps style -> colour name; unknown styles are untinted).
func _tint_for(style: String) -> Color:
	var map := Themes.fx("stage.style")
	return Themes.color(str(map.get(style, map.get("default", "white"))))


func _spark_flight(from_pos: Vector2, to_pos: Vector2) -> void:
	var f := Themes.fx("stage.crumbs")
	var spark: Texture2D = _tex.spark
	if f.is_empty() or spark == null:
		return
	var mid := (from_pos + to_pos) * 0.5 + Vector2(0, -from_pos.distance_to(to_pos) * 0.25)
	_pool.spawn(FxPool.Kind.FLIGHT, spark, from_pos, to_pos, mid, 0.0, 0.7, 34.0, 26.0, Themes.color("mark"), 3.0, true)


func _burst(at: Vector2, tint_name: String) -> void:
	var f := Themes.fx("stage.burst")
	var spark: Texture2D = _tex.spark
	if f.is_empty() or spark == null:
		return
	var n := int(f.get("sparks", 10))
	var speed := float(f.get("speed", 180.0))
	var col := Themes.color(tint_name)
	for i in n:
		var ang := TAU * float(i) / float(n) + float(i % 3) * 0.2
		var dist := speed * (0.45 + 0.12 * float(i % 4))
		_pool.spawn(FxPool.Kind.BURST, spark, at, at + Vector2(cos(ang), sin(ang)) * dist, at, 0.0, 0.55, 26.0, 6.0, col, 4.0)


func _ring(at: Vector2, tint_name: String, s0: float, s1: float, life: float, delay := 0.0) -> void:
	var ring: Texture2D = _tex.ring
	if ring == null:
		return
	_pool.spawn(FxPool.Kind.RING, ring, at, at, at, delay, life, s0, s1, Themes.color(tint_name))


func _pop_bubble(at: Vector2) -> void:
	var shield: Texture2D = _tex.shield
	if shield == null:
		return
	var life := float(Themes.fx("stage.pop").get("time", 0.55))
	_pool.spawn(FxPool.Kind.BUBBLE, shield, at, at, at, 0.0, life, _hut_px * 0.55, _hut_px * 1.6, Themes.color("white"))


func _puffs(at: Vector2) -> void:
	var glow: Texture2D = _tex.glow
	if glow == null:
		return
	for i in 3:
		var jitter := Vector2(float(i - 1) * _hut_px * 0.22, -float(i) * 6.0)
		_pool.spawn(FxPool.Kind.PUFF, glow, at + jitter, at + jitter, at, float(i) * 0.09, 0.75, _hut_px * 0.3, _hut_px * 1.0,
			Themes.color_a("fog", 0.55))


## A caught thief: the world holds for a beat, the picture shakes and the edges flash. Settings by style, else the default.
func _impact(b: Dictionary) -> void:
	var imp := Themes.fx("beat.blocked.impact." + str(b.style))
	if imp.is_empty():
		imp = Themes.fx("beat.blocked.impact")
	if imp.is_empty():
		return
	_shake = maxf(_shake, float(imp.get("shake", 0.0)))
	_flash = maxf(_flash, float(imp.get("flash", 0.0)))
	_hit_pause = maxf(_hit_pause, float(imp.get("pause_ms", 0)) / 1000.0)


# ---------------- drawing ----------------

func _draw() -> void:
	if _model.is_empty():
		return
	if _rich:
		_draw_rich()
	else:
		_draw_plain()


func _paint_additive(layer: Control) -> void:
	if _model.is_empty() or not _rich:
		return
	var glow: Texture2D = _tex.glow
	if glow != null:
		var c: Vector2 = get_meta("centre", size * 0.5)
		var s := _hut_px * 4.4
		var fl := 0.0 if Themes.fx("flicker").is_empty() else sin(_t * 8.1) * 0.5 + sin(_t * 13.7 + 0.8) * 0.3
		var col := Themes.color_a("glow", 0.5 + 0.16 * fl)
		layer.draw_texture_rect(glow, Rect2(c - Vector2(s, s) * 0.5 + Vector2(0, _hut_px * 0.1), Vector2(s, s)), false, col)
	_pool.draw_sprites(layer)


func _draw_rich() -> void:
	var font := get_theme_default_font()
	var fs := get_theme_default_font_size()
	var ink := Themes.color("ink")
	var cur: Dictionary = _timeline.current() if _timeline != null else {}
	var p: float = _timeline.beat_progress() if _timeline != null else 1.0
	var c: Vector2 = get_meta("centre", size * 0.5)
	draw_set_transform(_shake_off, 0.0, Vector2.ONE)
	_draw_wash(cur, p)
	_draw_fire(c)                                  # the fire is the back of the scene: plates and huts sit in front of it
	for e in _order:
		_draw_home(e, font, ink)
	if not cur.is_empty():
		_draw_beat(cur, p, c)
	_pool.draw_texts(self, font, fs + 6, ink)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	_draw_caption(cur, font, fs)
	if _flash > 0.01:
		draw_rect(Rect2(Vector2.ZERO, size), Themes.color_a("hit", _flash * minf(1.0, _flash * 2.0 + 0.2)))


func _draw_wash(cur: Dictionary, p: float) -> void:
	if cur.get("kind") != "camp":
		return
	var w := Themes.fx("wash")
	if w.is_empty():
		return
	var tint_name := str(w.get(str(cur.get("style", "")), w.get("default", "cold")))
	draw_rect(Rect2(-_shake_off, size), Themes.color_a(tint_name, float(w.get("alpha", 0.25)) * sin(p * PI)))


func _draw_fire(c: Vector2) -> void:
	var fire: Texture2D = _tex.fire
	if fire == null:
		return
	var s := _hut_px * 0.62
	var fl := 1.0
	if not Themes.fx("flicker").is_empty():
		fl = 1.0 + 0.04 * sin(_t * 11.0) + 0.022 * sin(_t * 17.3 + 1.0)
	var w := s * (1.0 - (fl - 1.0) * 0.7)
	var h := s * fl
	var base := c.y + s * 0.36
	draw_set_transform(_shake_off + Vector2(c.x, base + 2.0), 0.0, Vector2(1.0, 0.26))
	draw_circle(Vector2.ZERO, s * 0.62, Themes.color("shade"))
	draw_set_transform(_shake_off, 0.0, Vector2.ONE)
	draw_texture_rect(fire, Rect2(c.x - w * 0.5, base - h, w, h), false)


func _draw_home(e: Dictionary, font: Font, ink: Color) -> void:
	var at: Vector2 = _pos[e.alias]
	var hs := _hut_px
	var tex: Texture2D = _tex.hut_me if (e.is_me and _tex.hut_me != null) else _tex.hut
	var dark := float(_dark.get(e.alias, 0.0))
	var tint := Themes.color("white").lerp(Themes.color("cold").darkened(0.6), dark * 0.75)
	draw_set_transform(_shake_off + at + Vector2(0, hs * 0.43), 0.0, Vector2(1.0, 0.26))
	draw_circle(Vector2.ZERO, hs * 0.55, Themes.color("shade"))
	draw_set_transform(_shake_off, 0.0, Vector2.ONE)
	draw_texture_rect(tex, Rect2(at + Vector2(-hs * 0.5, -hs * 0.56), Vector2(hs, hs)), false, tint)
	if dark > 0.6:                                 # eyes in the doorway: they blink now and then
		if fmod(_t * 1.0 + float(e.alias.hash() % 7), 3.4) < 3.1:
			var eye := Themes.color("loss")
			for dx in [-1.0, 1.0]:
				var ep := at + Vector2(dx * hs * 0.065, hs * 0.13)
				draw_circle(ep, hs * 0.05, Themes.color_a("loss", 0.35 * dark))
				draw_circle(ep, hs * 0.028, eye)
				draw_circle(ep + Vector2(-1, -1), hs * 0.008, Themes.color("white"))
	var b := float(_bubble.get(e.alias, 0.0))
	var shield: Texture2D = _tex.shield
	if b > 0.01 and shield != null:
		var back := 1.0 + 0.7 * (1.0 - b) * (1.0 - b)            # overshoot, then settle
		var sz := hs * 1.38 * (b * back) * (1.0 + 0.025 * sin(_t * 3.0))
		draw_texture_rect(shield, Rect2(at + Vector2(-sz * 0.5, -sz * 0.5 - hs * 0.05), Vector2(sz, sz)), false,
			Themes.color_a("white", 0.9 * b))
	var face := Ui.avatar(e.alias, _avatars)
	if face != null:
		var asz := hs * 0.44
		var bob := sin(_t * 2.2 + float(e.alias.hash() % 11)) * 2.0
		draw_texture_rect(face, Rect2(at + Vector2(hs * 0.42 - asz * 0.5, hs * 0.12 - asz * 0.5 + bob), Vector2(asz, asz)), false)
	_draw_plate(e, font, ink)


## What is drawn on each plate, in global coordinates, for the clearance check: {path, what, rect, frame, edge}.
func plate_items() -> Array:
	var out: Array = []
	if not _rich or _model.is_empty():
		return out
	var origin := get_global_rect().position
	var edge := float(get_theme_constant("plate_edge", "Stage"))
	if edge <= 0.0:
		edge = PLATE_DEFAULT_EDGE
	for e in _roster:
		var pl: Dictionary = _plates.get(e.alias, {})
		if pl.is_empty():
			continue
		var frame := Rect2(pl.rect.position + origin, pl.rect.size)
		var tag := "%s/plate:%s" % [get_path(), e.alias]
		for it in pl.items:
			out.append({"path": tag + "/" + it.what, "what": it.what, "frame": frame, "edge": edge,
				"rect": Rect2(it.rect.position + origin, it.rect.size)})
	return out


## The plate under (or over) a home, from its layout: the frame, then each item in place.
func _draw_plate(e: Dictionary, font: Font, ink: Color) -> void:
	var pl: Dictionary = _plates.get(e.alias, {})
	if pl.is_empty():
		return
	draw_style_box(pl.style, pl.rect)
	var col_text := get_theme_color("text", "Stage")
	for it in pl.items:
		if it.kind == "icon":
			draw_texture_rect(it.tex, it.rect, false)
			continue
		var col := Themes.color("gain") if it.tint == "gain" else col_text
		if it.get("number", false):
			# my food pops bigger for a moment; it is centred in the room reserved for its biggest size
			var dsz := _plate_size() + 3 + int(5.0 * _food_pop)
			var r: Rect2 = it.rect
			var tw := font.get_string_size(it.text, HORIZONTAL_ALIGNMENT_LEFT, -1, dsz).x
			var by := r.position.y + (r.size.y - font.get_height(dsz)) * 0.5 + font.get_ascent(dsz)
			_text(font, it.text, Vector2(r.position.x + (r.size.x - tw) * 0.5, by), dsz, col, ink, -1.0, HORIZONTAL_ALIGNMENT_LEFT)
		else:
			_text(font, it.text, it.base, it.size, col, ink, -1.0, HORIZONTAL_ALIGNMENT_LEFT)


func _text(font: Font, s: String, at: Vector2, size_px: int, col: Color, outline: Color, width := -1.0,
		align := HORIZONTAL_ALIGNMENT_CENTER) -> void:
	draw_string_outline(font, at, s, align, width, size_px, 6, outline)
	draw_string(font, at, s, align, width, size_px, col)


## The icon of the beat that is playing, popping in above where it happens and fading out.
func _draw_beat(cur: Dictionary, p: float, c: Vector2) -> void:
	var to_pos := where(cur.to, cur.from)
	var from_pos := where(cur.from, cur.to)
	var at := to_pos if cur.to != OFFSTAGE else c
	var kind: String = cur.kind
	if kind == "learn":
		draw_line(from_pos, to_pos, Themes.color_a("white", 0.5 * sin(p * PI)), 2.0, true)
	if kind == "move_resource":
		if Themes.fx("stage.crumbs").is_empty():
			_draw_travelling_food(cur, from_pos, to_pos, p)
		return
	var tex := _beat_icon(cur)
	if tex == null or kind == "total":
		return
	var pop := _ease_back(clampf(p * 3.5, 0.0, 1.0))
	var fade := 1.0 - maxf(0.0, p - 0.72) / 0.28
	var s := 60.0 * pop
	var top := at + Vector2(0, -_hut_px * 0.66)
	if cur.to == OFFSTAGE:
		top = c + Vector2(0, -_hut_px * 0.9)
	draw_texture_rect(tex, Rect2(top - Vector2(s, s) * 0.5, Vector2(s, s)), false, Themes.color_a("white", fade))


## The picture for a beat: "<kind>.<style>" when the theme has one for that exact happening (a particular wilderness event,
## say), else the kind's own.
func _beat_icon(cur: Dictionary) -> Texture2D:
	var style := str(cur.get("style", ""))
	if style != "":
		var specific := Themes.icon("%s.%s" % [cur.kind, style])
		if specific != null:
			return specific
	return Themes.icon(cur.kind)


static func _ease_back(t: float) -> float:
	var s := 1.70158
	t -= 1.0
	return t * t * ((s + 1.0) * t + s) + 1.0


## The caption: the log line being played, in the theme's words, on a dark strip (leaving room for the Skip pill).
func _draw_caption(cur: Dictionary, font: Font, fs: int) -> void:
	var li: int = int(cur.get("line_index", -1))
	if li < 0 or li >= _model.lines.size():
		return
	var w := size.x - 16.0 - SKIP_ROOM
	if li != _caption_idx:
		_caption_idx = li
		var ln: Dictionary = _model.lines[li]
		_caption = Words.render(ln.key, ln.slots)
		_caption_size = font.get_multiline_string_size(_caption, HORIZONTAL_ALIGNMENT_LEFT, w, fs - 3, 2)
	var bg := Rect2(6, 4, minf(w + 16.0, _caption_size.x + 20.0), _caption_size.y + 12.0)
	draw_rect(bg, Themes.color("shade"))
	draw_multiline_string(font, Vector2(14, 6.0 + float(fs)), _caption, HORIZONTAL_ALIGNMENT_LEFT, w, fs - 3, 2,
		get_theme_color("text", "Stage"))


# ---------------- the plain look (a theme with no art) ----------------

func _draw_plain() -> void:
	var font := get_theme_default_font()
	var fs := get_theme_default_font_size()
	var col_text := get_theme_color("text", "Stage")
	var col_home := get_theme_color("home", "Stage")
	var col_me := get_theme_color("home_me", "Stage")
	var col_food := get_theme_color("food", "Stage")
	var col_loss := get_theme_color("loss", "Stage")
	var col_shield := get_theme_color("shield", "Stage")
	var col_mark := get_theme_color("marked", "Stage")
	var cur: Dictionary = _timeline.current() if _timeline != null else {}
	var p: float = _timeline.beat_progress() if _timeline != null else 1.0
	var radius_home := 26.0

	if cur.get("kind") == "camp":
		var tint := col_mark
		tint.a = 0.18 * sin(p * PI)
		draw_rect(Rect2(Vector2.ZERO, size), tint)
	var centre_icon := Themes.icon("camp")
	if centre_icon != null:
		var cc: Vector2 = get_meta("centre", size * 0.5)
		draw_texture_rect(centre_icon, Rect2(cc - Vector2(32, 32), Vector2(64, 64)), false)
	for e in _roster:
		var at: Vector2 = _pos[e.alias]
		draw_circle(at, radius_home, col_me if e.is_me else col_home)
		if _shields.has(e.alias) or _shields.has(ME) and e.is_me:
			draw_arc(at, radius_home + 6, 0, TAU, 40, col_shield, 3.0)
		if _out.has(e.alias) or (_out.has(ME) and e.is_me):
			draw_arc(at, radius_home + 12, 0, TAU, 40, col_loss, 2.0)
		# the alias on one line, the band (or my food) on the next, each trimmed to fit under the home
		var line1: String = e.alias
		var line2 := ""
		if e.is_me:
			line2 = str(_food_mine)
		elif e.band != "":
			line2 = Words.render(e.band)
		var band_icon := Themes.icon(e.band) if (e.band != "" and not e.is_me) else null
		if band_icon != null:
			draw_texture_rect(band_icon, Rect2(at + Vector2(-10, -10), Vector2(20, 20)), false)
		draw_string(font, at + Vector2(-70, radius_home + 20), line1, HORIZONTAL_ALIGNMENT_CENTER, 140, fs - 4, col_text)
		if line2 != "":
			draw_string(font, at + Vector2(-70, radius_home + 38), line2, HORIZONTAL_ALIGNMENT_CENTER, 140, fs - 4, col_text)

	if cur.is_empty():
		return
	var to_pos := where(cur.to, cur.from)
	var from_pos := where(cur.from, cur.to)
	match cur.kind:
		"move_resource":
			_draw_travelling_food(cur, from_pos, to_pos, p)
		"blocked":
			draw_arc(to_pos, radius_home + 8, 0, TAU, 40, col_shield, 4.0)
			draw_line(to_pos + Vector2(-14, -14), to_pos + Vector2(14, 14), col_loss, 4.0)
			draw_line(to_pos + Vector2(-14, 14), to_pos + Vector2(14, -14), col_loss, 4.0)
		"empty":
			draw_arc(to_pos, radius_home - 6, 0, TAU, 32, col_text, 2.0)
		"learn":
			draw_line(from_pos, to_pos, col_text, 2.0)
		"marked":
			draw_arc(to_pos, radius_home + 10, 0, TAU, 40, col_mark, 4.0 + 2.0 * sin(p * PI))
		"status":
			draw_arc(to_pos, radius_home + 12, 0, TAU, 40, col_loss, 3.0)
		"shield_on", "shield_off":
			draw_arc(to_pos, radius_home + 6 + 6.0 * p, 0, TAU, 40, col_shield, 3.0)
		"charm":
			var d := 10.0
			draw_colored_polygon(PackedVector2Array([to_pos + Vector2(0, -d), to_pos + Vector2(d, 0), to_pos + Vector2(0, d),
				to_pos + Vector2(-d, 0)]), col_mark)
		"total":
			draw_arc(_pos.get(ME, size / 2.0), radius_home + 4, 0, TAU, 40, col_food, 3.0)
	var beat_icon := _beat_icon(cur)
	if beat_icon != null and cur.kind != "move_resource" and cur.kind != "total":
		var icon_at := to_pos + Vector2(0, -radius_home - 24)
		draw_texture_rect(beat_icon, Rect2(icon_at - Vector2(16, 16), Vector2(32, 32)), false)
	_draw_caption_plain(cur, font, fs, col_text)


## The food on its way: the theme's food icon (a plain gold disc without one) and the amount beside it.
func _draw_travelling_food(cur: Dictionary, from_pos: Vector2, to_pos: Vector2, p: float) -> void:
	var font := get_theme_default_font()
	var fs := get_theme_default_font_size()
	var eased := p * p * (3.0 - 2.0 * p)
	var at := from_pos.lerp(to_pos, eased)
	var icon := Themes.icon("food")
	if icon != null:
		draw_texture_rect(icon, Rect2(at - Vector2(16, 16), Vector2(32, 32)), false)
	else:
		draw_circle(at, 10.0, get_theme_color("food", "Stage"))
	var amt: int = int(cur.amount_in) if cur.to == ME or cur.from == OFFSTAGE else int(cur.amount_out)
	draw_string(font, at + Vector2(14, -8), "%d" % amt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, get_theme_color("text", "Stage"))


func _draw_caption_plain(cur: Dictionary, font: Font, fs: int, col_text: Color) -> void:
	var li: int = int(cur.get("line_index", -1))
	if li >= 0 and li < _model.lines.size():
		var ln: Dictionary = _model.lines[li]
		draw_multiline_string(font, Vector2(8, 20), Words.render(ln.key, ln.slots), HORIZONTAL_ALIGNMENT_LEFT,
			size.x - 16 - SKIP_ROOM, fs - 3, 2, col_text)
