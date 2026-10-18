class_name FxPool
extends RefCounted
## A fixed pool of short-lived sprites and floating numbers for the reveal: crumbs that fly in arcs and leave trails,
## bursts of sparks, expanding rings and puffs, the shield bubble's pop. Every array is sized once, so playing an effect
## never allocates and the number alive can never pass CAP (a spawn into a full pool is dropped and counted, not queued).
##
## It is pure data and drawing: it knows no game words, no colours and no paths. The caller hands in textures and
## colours. `update(dt)` advances time; `draw_sprites` / `draw_texts` paint onto any CanvasItem.

enum Kind { FLIGHT, BURST, RING, PUFF, TRAIL, BUBBLE, TEXT }

const CAP := 160                       # chosen: sprites; well under the 200 live-particle budget
const TEXT_CAP := 12                   # chosen: floating numbers alive at once
const FLOAT_OUTLINE := 4.0              # the dark edge drawn around a floating number spills this far
const TRAIL_LIFE := 0.3
const TRAIL_EVERY := 0.03

var dropped := 0                       # spawns refused because the pool was full (diagnostics and tests)

var _alive := PackedByteArray()
var _kind := PackedInt32Array()
var _age := PackedFloat32Array()
var _delay := PackedFloat32Array()
var _life := PackedFloat32Array()
var _from := PackedVector2Array()
var _to := PackedVector2Array()
var _ctrl := PackedVector2Array()
var _size0 := PackedFloat32Array()
var _size1 := PackedFloat32Array()
var _spin := PackedFloat32Array()
var _trail := PackedFloat32Array()      # >0 = this flight leaves a trail; the value is the time since the last dot
var _col := PackedColorArray()
var _tex: Array = []
var _text: Array = []                   # the string of a TEXT slot (assigned on spawn, never allocated per frame)
var _live := 0
var _live_texts := 0


func _init() -> void:
	_alive.resize(CAP)
	_kind.resize(CAP)
	_age.resize(CAP)
	_delay.resize(CAP)
	_life.resize(CAP)
	_from.resize(CAP)
	_to.resize(CAP)
	_ctrl.resize(CAP)
	_size0.resize(CAP)
	_size1.resize(CAP)
	_spin.resize(CAP)
	_trail.resize(CAP)
	_col.resize(CAP)
	_tex.resize(CAP)
	_text.resize(CAP)


func live() -> int:
	return _live


func live_texts() -> int:
	return _live_texts


func clear() -> void:
	for i in CAP:
		_alive[i] = 0
		_tex[i] = null
	_live = 0
	_live_texts = 0


## One sprite. FLIGHT follows a curve from `from` to `to` bent toward `ctrl`; BURST flies out from `from` along
## `to - from` and slows; RING / PUFF / BUBBLE sit at `from` and grow from size0 to size1. `delay` holds it back.
func spawn(kind: int, tex: Texture2D, from: Vector2, to: Vector2, ctrl: Vector2, delay: float, life: float, size0: float,
		size1: float, col: Color, spin := 0.0, trail := false) -> int:
	if kind == Kind.TEXT:
		return -1
	var i := _free_slot()
	if i < 0:
		dropped += 1
		return -1
	_fill(i, kind, tex, from, to, ctrl, delay, life, size0, size1, col, spin, trail)
	return i


## A floating number or word: it rises from `at` by `rise` pixels while it fades.
func spawn_text(text: String, at: Vector2, rise: float, delay: float, life: float, col: Color) -> int:
	if _live_texts >= TEXT_CAP:
		dropped += 1
		return -1
	var i := _free_slot()
	if i < 0:
		dropped += 1
		return -1
	_fill(i, Kind.TEXT, null, at, at + Vector2(0, -rise), at, delay, life, 1.0, 1.0, col, 0.0, false)
	_text[i] = text
	_live_texts += 1
	return i


func _fill(i: int, kind: int, tex: Texture2D, from: Vector2, to: Vector2, ctrl: Vector2, delay: float, life: float,
		size0: float, size1: float, col: Color, spin: float, trail: bool) -> void:
	_alive[i] = 1
	_kind[i] = kind
	_age[i] = 0.0
	_delay[i] = delay
	_life[i] = maxf(life, 0.01)
	_from[i] = from
	_to[i] = to
	_ctrl[i] = ctrl
	_size0[i] = size0
	_size1[i] = size1
	_spin[i] = spin
	_trail[i] = 0.001 if trail else 0.0
	_col[i] = col
	_tex[i] = tex
	_live += 1


func _free_slot() -> int:
	for i in CAP:
		if _alive[i] == 0:
			return i
	return -1


func _kill(i: int) -> void:
	_alive[i] = 0
	_tex[i] = null
	_live -= 1
	if _kind[i] == Kind.TEXT:
		_live_texts -= 1
		_text[i] = ""


func update(dt: float) -> void:
	if _live == 0 or dt <= 0.0:
		return
	for i in CAP:
		if _alive[i] == 0:
			continue
		_age[i] += dt
		if _age[i] < _delay[i]:
			continue
		if _age[i] - _delay[i] >= _life[i]:
			_kill(i)
			continue
		if _kind[i] == Kind.FLIGHT and _trail[i] > 0.0:
			_trail[i] += dt
			if _trail[i] >= TRAIL_EVERY:
				_trail[i] = 0.001
				var t := (_age[i] - _delay[i]) / _life[i]
				_drop_trail(i, t)


## A fading dot where the flight is now.
func _drop_trail(i: int, t: float) -> void:
	var slot := _free_slot()
	if slot < 0:
		dropped += 1
		return
	_fill(slot, Kind.TRAIL, _tex[i], _position(i, t), Vector2.ZERO, Vector2.ZERO, 0.0, TRAIL_LIFE, _size0[i] * 0.7, 0.0,
		_col[i], 0.0, false)


## Where slot `i` is at progress `t` (0..1 through its own life).
func _position(i: int, t: float) -> Vector2:
	match _kind[i]:
		Kind.FLIGHT:
			var e := t * t * (3.0 - 2.0 * t)
			var u := 1.0 - e
			return _from[i] * (u * u) + _ctrl[i] * (2.0 * u * e) + _to[i] * (e * e)
		Kind.BURST:
			var slow := 1.0 - (1.0 - t) * (1.0 - t)
			return _from[i] + (_to[i] - _from[i]) * slow
		Kind.TEXT:
			var rise := 1.0 - (1.0 - t) * (1.0 - t)
			return _from[i].lerp(_to[i], rise)
	return _from[i]


func _alpha(i: int, t: float) -> float:
	match _kind[i]:
		Kind.FLIGHT:
			return minf(1.0, t * 8.0) * (1.0 - maxf(0.0, t - 0.85) * 6.0)
		Kind.BUBBLE:
			return 1.0 if t < 0.45 else 1.0 - (t - 0.45) / 0.55
		Kind.TEXT:
			return 1.0 if t < 0.55 else 1.0 - (t - 0.55) / 0.45
	var k := 1.0 - t
	return k * k


## Paint every sprite (not the texts) onto `canvas`, offset by `at`.
func draw_sprites(canvas: CanvasItem, at: Vector2 = Vector2.ZERO) -> void:
	if _live == _live_texts:
		return
	for i in CAP:
		if _alive[i] == 0 or _kind[i] == Kind.TEXT or _age[i] < _delay[i]:
			continue
		var t := (_age[i] - _delay[i]) / _life[i]
		var tex: Texture2D = _tex[i]
		if tex == null:
			continue
		var grow := 1.0 - (1.0 - t) * (1.0 - t)
		var s := lerpf(_size0[i], _size1[i], grow if _kind[i] != Kind.FLIGHT else t)
		var p := _position(i, t) + at
		var col := _col[i]
		col.a *= _alpha(i, t)
		if col.a <= 0.01 or s <= 0.5:
			continue
		if _spin[i] != 0.0:
			canvas.draw_set_transform(p, _spin[i] * (_age[i] - _delay[i]), Vector2.ONE)
			canvas.draw_texture_rect(tex, Rect2(Vector2(-s, -s) * 0.5, Vector2(s, s)), false, col)
		else:
			canvas.draw_set_transform(p, 0.0, Vector2.ONE)
			canvas.draw_texture_rect(tex, Rect2(Vector2(-s, -s) * 0.5, Vector2(s, s)), false, col)
	canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## The box each floating text occupies, in the coordinates it is drawn in, with its outline. `swept` = the whole region it
## passes through on its rise (and including ones still waiting for their delay), for planning where a new one may go;
## otherwise only what is visible right now, for checking. Each entry is {"text": String, "rect": Rect2}.
func text_boxes(font: Font, size: int, swept := false) -> Array:
	var out: Array = []
	if _live_texts == 0:
		return out
	for i in CAP:
		if _alive[i] == 0 or _kind[i] != Kind.TEXT:
			continue
		if not swept and _age[i] < _delay[i]:
			continue
		var t := clampf((_age[i] - _delay[i]) / _life[i], 0.0, 1.0)
		var pop := 1.0 + 0.45 * (1.0 if swept else maxf(0.0, 1.0 - t * 5.0))
		var fs := int(float(size) * pop)
		var w := font.get_string_size(_text[i], HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		var asc := font.get_ascent(fs)
		var h := font.get_height(fs)
		var r: Rect2
		if swept:
			var a: Vector2 = _from[i]
			var b: Vector2 = _to[i]
			var top := minf(a.y, b.y) - asc
			var bottom := maxf(a.y, b.y) - asc + h
			r = Rect2(minf(a.x, b.x) - w * 0.5, top, absf(a.x - b.x) + w, bottom - top)
		else:
			var p := _position(i, t)
			r = Rect2(p.x - w * 0.5, p.y - asc, w, h)
		out.append({"text": _text[i], "rect": r.grow(FLOAT_OUTLINE)})
	return out


## Paint the floating texts: a dark outline then the colour.
func draw_texts(canvas: CanvasItem, font: Font, size: int, outline: Color, at: Vector2 = Vector2.ZERO) -> void:
	if _live_texts == 0:
		return
	for i in CAP:
		if _alive[i] == 0 or _kind[i] != Kind.TEXT or _age[i] < _delay[i]:
			continue
		var t := (_age[i] - _delay[i]) / _life[i]
		var col := _col[i]
		col.a *= _alpha(i, t)
		var oc := outline
		oc.a = col.a
		var p := _position(i, t) + at
		p.x -= 80.0                                   # the text is centred inside a 160 px box that starts at p
		var pop := 1.0 + 0.45 * maxf(0.0, 1.0 - t * 5.0)
		var fs := int(float(size) * pop)
		canvas.draw_string_outline(font, p, _text[i], HORIZONTAL_ALIGNMENT_CENTER, 160.0, fs, 8, oc)
		canvas.draw_string(font, p, _text[i], HORIZONTAL_ALIGNMENT_CENTER, 160.0, fs, col)
